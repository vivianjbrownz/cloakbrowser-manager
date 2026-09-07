import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  class MockRFB {
    static instances: MockRFB[] = [];

    qualityLevel = 0;
    compressionLevel = 0;
    scaleViewport = false;
    resizeSession = true;
    showDotCursor = false;
    keyboard = { enableIME: false };
    updateConnectionSettings = vi.fn();
    args: unknown[];
    keys: Array<[number, string, boolean | undefined]> = [];
    listeners = new Map<string, Array<(event: any) => void>>();

    constructor(...args: unknown[]) {
      this.args = args;
      MockRFB.instances.push(this);
    }

    addEventListener(type: string, listener: (event: any) => void) {
      const listeners = this.listeners.get(type) ?? [];
      listeners.push(listener);
      this.listeners.set(type, listeners);
    }

    removeEventListener(type: string, listener: (event: any) => void) {
      const listeners = this.listeners.get(type) ?? [];
      this.listeners.set(type, listeners.filter((item) => item !== listener));
    }

    emit(type: string, detail: any = {}) {
      for (const listener of this.listeners.get(type) ?? []) {
        listener({ detail });
      }
    }

    disconnect = vi.fn();

    sendKey(keysym: number, code: string, down?: boolean) {
      this.keys.push([keysym, code, down]);
    }
  }

  return {
    MockRFB,
    api: {
      getClipboard: vi.fn(),
      setClipboard: vi.fn(),
      getProfileStatus: vi.fn(),
    },
  };
});

vi.mock("@novnc/novnc/core/rfb.js", () => ({
  default: mocks.MockRFB,
}));

vi.mock("../vendor/kasmvnc/core/rfb.js", () => ({ default: mocks.MockRFB }));

vi.mock("../lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../lib/api")>(),
  api: mocks.api,
}));

import { ProfileViewer } from "./ProfileViewer";
import { ApiError } from "../lib/api";

const storageKey = "cloakbrowser.viewer.qualityMode";

async function renderConnected(clipboardSync = false) {
  render(
    <ProfileViewer
      profileId="profile-1"
      cdpUrl={null}
      clipboardSync={clipboardSync}
      onDisconnect={vi.fn()}
    />,
  );

  await waitFor(() => expect(mocks.MockRFB.instances).toHaveLength(1));
  const rfb = mocks.MockRFB.instances[0];
  act(() => rfb.emit("connect"));
  await screen.findByText("Connected");
  return rfb;
}

beforeEach(() => {
  mocks.MockRFB.instances = [];
  mocks.api.getClipboard.mockReset().mockResolvedValue({ text: "" });
  mocks.api.setClipboard.mockReset().mockResolvedValue({ ok: true });
  mocks.api.getProfileStatus.mockReset().mockResolvedValue({ status: "running" });
  window.localStorage.clear();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: {
      readText: vi.fn().mockResolvedValue(""),
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ProfileViewer quality mode", () => {
  it("uses fast mode by default", async () => {
    const rfb = await renderConnected();

    expect(rfb.qualityLevel).toBe(4);
    expect(rfb.compressionLevel).toBe(7);
    expect(rfb.scaleViewport).toBe(true);
    expect(rfb.resizeSession).toBe(false);
  });

  it("loads saved quality mode from localStorage", async () => {
    window.localStorage.setItem(storageKey, "sharp");

    const rfb = await renderConnected();

    expect(rfb.qualityLevel).toBe(9);
    expect(rfb.compressionLevel).toBe(2);
  });

  it("updates quality mode without reconnecting", async () => {
    const rfb = await renderConnected();

    fireEvent.click(screen.getByRole("button", { name: "Sharp" }));

    expect(rfb.qualityLevel).toBe(9);
    expect(rfb.compressionLevel).toBe(2);
    expect(window.localStorage.getItem(storageKey)).toBe("sharp");
    expect(mocks.MockRFB.instances).toHaveLength(1);
  });
});

describe("ProfileViewer one-time paste", () => {
  it("does not paste stale text when updating the remote clipboard fails", async () => {
    vi.mocked(navigator.clipboard.readText).mockResolvedValue("new text");
    mocks.api.setClipboard.mockRejectedValue(new TypeError("Network request failed"));
    const rfb = await renderConnected();
    fireEvent.keyDown(screen.getByTestId("vnc-canvas-container"), { key: "v", ctrlKey: true });
    await screen.findByRole("alert");
    expect(rfb.keys).toEqual([]);
  });

  it("pastes from host clipboard even when continuous sync is disabled", async () => {
    vi.mocked(navigator.clipboard.readText).mockResolvedValue("secret");
    const rfb = await renderConnected(false);

    fireEvent.keyDown(screen.getByTestId("vnc-canvas-container"), {
      key: "v",
      ctrlKey: true,
    });

    await waitFor(() => {
      expect(mocks.api.setClipboard).toHaveBeenCalledWith("profile-1", "secret");
    });
    expect(rfb.keys).toEqual([
      [0xffe3, "ControlLeft", true],
      [0x0076, "KeyV", true],
      [0x0076, "KeyV", false],
      [0xffe3, "ControlLeft", false],
    ]);
    expect(mocks.api.getClipboard).not.toHaveBeenCalled();
  });

  it("does not send paste to a replaced connection after the clipboard read resolves", async () => {
    let resolve!: (text: string) => void;
    vi.mocked(navigator.clipboard.readText).mockReturnValue(new Promise((done) => { resolve = done; }));
    const old = await renderConnected();
    fireEvent.keyDown(screen.getByTestId("vnc-canvas-container"), { key: "v", ctrlKey: true });
    fireEvent.change(screen.getByRole("combobox", { name: "Viewer client" }), { target: { value: "kasm" } });
    await waitFor(() => expect(mocks.MockRFB.instances).toHaveLength(2));
    await act(async () => resolve("private text"));
    expect(mocks.api.setClipboard).not.toHaveBeenCalled();
    expect(old.keys).toEqual([]);
    expect(mocks.MockRFB.instances[1].keys).toEqual([]);
  });
});

describe("native viewer", () => {
  it("uses the server default, native endpoint and fixed geometry without WebRTC or competing clipboard handlers", async () => {
    render(<ProfileViewer profileId="profile-1" cdpUrl={null} clipboardSync={false} onDisconnect={vi.fn()} defaultImplementation="kasm" />);
    await waitFor(() => expect(mocks.MockRFB.instances).toHaveLength(1));
    const rfb = mocks.MockRFB.instances[0] as any;
    expect(rfb.args[1]).toBe(screen.getByRole("textbox", { name: "Remote browser keyboard" }));
    expect(rfb.args[2]).toMatch(/\/api\/profiles\/profile-1\/vnc-native$/);
    expect(rfb.args[3]).toMatchObject({ allowRemoteResize: false, enableWebRTC: false, shared: true });
    expect(rfb.resizeSession).toBe(false);
    expect(rfb.videoQuality).toBe(10);
    expect(rfb.frameRate).toBe(30);
    expect(rfb.enableWebRTC).toBe(false);
    expect(rfb.keyboard.enableIME).toBe(true);
    expect([rfb.clipboardUp, rfb.clipboardDown, rfb.clipboardSeamless]).toEqual([false, false, false]);
    for (const name of ["Balanced", "Sharp", "Fast"]) {
      fireEvent.click(screen.getByRole("button", { name }));
      expect(rfb.videoQuality).toBe(10);
      expect(rfb.resizeSession).toBe(false);
    }
    expect(mocks.MockRFB.instances).toHaveLength(1);
  });

  it("gives simultaneous profiles separate input channels and keeps explicit compatibility preference", async () => {
    const props = { cdpUrl: null, clipboardSync: false, onDisconnect: vi.fn(), defaultImplementation: "kasm" as const };
    const rendered = render(<><ProfileViewer {...props} profileId="a" /><ProfileViewer {...props} profileId="b" /></>);
    await act(async () => { await vi.dynamicImportSettled(); });
    expect(mocks.MockRFB.instances).toHaveLength(2);
    const ids = mocks.MockRFB.instances.map((rfb) => (rfb.args[3] as any).connectionID);
    expect(new Set(ids).size).toBe(2);
    fireEvent.change(screen.getAllByRole("combobox", { name: "Viewer client" })[0], { target: { value: "novnc" } });
    await waitFor(() => expect(mocks.MockRFB.instances).toHaveLength(3));
    expect(mocks.MockRFB.instances[0].disconnect).toHaveBeenCalledTimes(1);
    expect(mocks.MockRFB.instances[1].disconnect).not.toHaveBeenCalled();
    rendered.unmount();
    render(<ProfileViewer {...props} profileId="a" />);
    await waitFor(() => expect(mocks.MockRFB.instances).toHaveLength(4));
    expect(mocks.MockRFB.instances[3].args[1]).toMatch(/\/vnc$/);
  });

  it("does not reconnect when only the parent callback changes", async () => {
    const props = { profileId: "a", cdpUrl: null, clipboardSync: false };
    const rendered = render(<ProfileViewer {...props} onDisconnect={vi.fn()} />);
    await waitFor(() => expect(mocks.MockRFB.instances).toHaveLength(1));
    rendered.rerender(<ProfileViewer {...props} onDisconnect={vi.fn()} />);
    await act(async () => { await vi.dynamicImportSettled(); });
    expect(mocks.MockRFB.instances).toHaveLength(1);
    expect(mocks.MockRFB.instances[0].disconnect).not.toHaveBeenCalled();
  });
});

describe("viewer recovery", () => {
  async function start() {
    vi.useFakeTimers();
    render(<ProfileViewer profileId="profile-1" cdpUrl={null} clipboardSync={false} onDisconnect={vi.fn()} />);
    await act(async () => { await vi.dynamicImportSettled(); });
    const rfb = mocks.MockRFB.instances[0];
    act(() => rfb.emit("connect"));
    return rfb;
  }

  it("checks authorization and status before reconnecting to the same profile", async () => {
    const first = await start();
    act(() => first.emit("disconnect"));
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); await vi.dynamicImportSettled(); });
    expect(mocks.api.getProfileStatus).toHaveBeenCalledWith("profile-1", expect.any(AbortSignal));
    expect(mocks.MockRFB.instances).toHaveLength(2);
    expect(mocks.MockRFB.instances[1].args[1]).toMatch(/profiles\/profile-1\/vnc$/);
    act(() => mocks.MockRFB.instances[1].emit("connect"));
    expect(screen.getByText("Connected")).toBeDefined();
  });

  it.each(["stopped", "revoked"])("stops retries when the profile is %s", async (condition) => {
    const first = await start();
    if (condition === "stopped") mocks.api.getProfileStatus.mockResolvedValue({ status: "stopped" });
    else mocks.api.getProfileStatus.mockRejectedValue(new ApiError(403, "Forbidden"));
    act(() => first.emit("disconnect"));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(mocks.MockRFB.instances).toHaveLength(1);
    expect(mocks.api.getProfileStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toBeDefined();
    expect(screen.getByRole("button", { name: "Reconnect" })).toBeDefined();
    expect(screen.getByRole("combobox", { name: "Viewer client" })).toBeDefined();
  });

  it("exhausts five retries even if each new connection briefly succeeds", async () => {
    let rfb = await start();
    for (const delay of [1000, 2000, 4000, 8000, 8000]) {
      act(() => rfb.emit("disconnect"));
      await act(async () => { await vi.advanceTimersByTimeAsync(delay); await vi.dynamicImportSettled(); });
      rfb = mocks.MockRFB.instances.at(-1)!;
      act(() => rfb.emit("connect"));
    }
    act(() => rfb.emit("disconnect"));
    expect(screen.getByRole("alert").textContent).toMatch(/Unable to reconnect/);
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(mocks.MockRFB.instances).toHaveLength(6);
  });
});
