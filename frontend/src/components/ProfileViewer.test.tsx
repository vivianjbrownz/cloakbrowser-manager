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
    keys: Array<[number, string, boolean | undefined]> = [];
    listeners = new Map<string, Array<(event: any) => void>>();

    constructor() {
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

    disconnect() {}

    sendKey(keysym: number, code: string, down?: boolean) {
      this.keys.push([keysym, code, down]);
    }
  }

  return {
    MockRFB,
    api: {
      getClipboard: vi.fn(),
      setClipboard: vi.fn(),
    },
  };
});

vi.mock("@novnc/novnc/core/rfb.js", () => ({
  default: mocks.MockRFB,
}));

vi.mock("../lib/api", () => ({
  api: mocks.api,
}));

import { ProfileViewer } from "./ProfileViewer";

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
});
