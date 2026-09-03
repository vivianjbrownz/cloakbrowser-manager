import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "./lib/api";

const fullId = "87654321-abcd-4def-8123-1234567890ab";
const assignedProfile: Profile = {
  id: fullId,
  name: "Employee Browser",
  fingerprint_seed: 1,
  proxy: null,
  timezone: null,
  locale: null,
  platform: "windows",
  user_agent: null,
  screen_width: 1920,
  screen_height: 1080,
  gpu_vendor: null,
  gpu_renderer: null,
  hardware_concurrency: null,
  humanize: true,
  human_preset: "careful",
  headless: true,
  geoip: true,
  clipboard_sync: false,
  auto_launch: false,
  restore_last_session: true,
  is_archived: false,
  archived_at: null,
  color_scheme: null,
  launch_args: [],
  notes: null,
  user_data_dir: `/data/profiles/${fullId}`,
  created_at: "2026-08-18T00:00:00Z",
  updated_at: "2026-08-18T00:00:00Z",
  tags: [],
  status: "stopped",
  vnc_ws_port: null,
  cdp_url: null,
};

const mocks = vi.hoisted(() => ({
  setOnUnauthorized: vi.fn(),
  refresh: vi.fn(),
  api: {
    authStatus: vi.fn(),
    logout: vi.fn(),
    startProfileUi: vi.fn(),
    stopProfileUi: vi.fn(),
  },
  useProfiles: vi.fn(),
}));

vi.mock("./lib/api", () => ({
  api: mocks.api,
  setOnUnauthorized: mocks.setOnUnauthorized,
}));

vi.mock("./hooks/useProfiles", () => ({
  useProfiles: mocks.useProfiles,
}));

import App from "./App";

beforeEach(() => {
  mocks.api.authStatus.mockReset().mockResolvedValue({
    auth_required: true,
    authenticated: true,
    role: "scoped",
  });
  mocks.api.startProfileUi.mockReset().mockResolvedValue({
    profile_id: fullId,
    status: "running",
    vnc_ws_port: 6100,
    display: ":100",
    cdp_url: `/api/profiles/${fullId}/cdp`,
  });
  mocks.api.stopProfileUi.mockReset();
  mocks.refresh.mockReset().mockResolvedValue(undefined);
  mocks.useProfiles.mockReset().mockReturnValue({
    profiles: [assignedProfile],
    loading: false,
    error: null,
    refresh: mocks.refresh,
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    archive: vi.fn(),
    restore: vi.fn(),
    launch: vi.fn(),
    stop: vi.fn(),
  });
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

afterEach(() => {
  cleanup();
});

describe("scoped employee profile ID", () => {
  it("shows the assigned short ID and copies the full UUID", async () => {
    render(<App />);

    expect(await screen.findByText("Employee Browser")).toBeTruthy();
    expect(screen.getByText("ID: 567890ab")).toBeTruthy();
    fireEvent.click(screen.getByTitle("复制完整 Profile ID"));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(fullId));
  });

  it("explains a running headless profile instead of mounting a black VNC viewer", async () => {
    mocks.useProfiles.mockReturnValue({
      ...mocks.useProfiles(),
      profiles: [{ ...assignedProfile, status: "running", headless: true }],
    });

    render(<App />);

    expect(await screen.findByText("浏览器正在无头模式运行")).toBeTruthy();
    expect(screen.queryByTestId("vnc-canvas-container")).toBeNull();
  });

  it("opens the browser UI once and refreshes the profile state", async () => {
    mocks.useProfiles.mockReturnValue({
      ...mocks.useProfiles(),
      profiles: [{ ...assignedProfile, status: "running", headless: true }],
    });

    render(<App />);
    const button = await screen.findByRole("button", { name: "打开浏览器 UI" });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(mocks.api.startProfileUi).toHaveBeenCalledTimes(1));
    expect(mocks.api.startProfileUi).toHaveBeenCalledWith(fullId);
    await waitFor(() => expect(mocks.refresh).toHaveBeenCalledTimes(1));
  });

  it("keeps a retry action visible when opening the browser UI fails", async () => {
    mocks.api.startProfileUi.mockRejectedValueOnce(new Error("Browser restart failed"));
    mocks.useProfiles.mockReturnValue({
      ...mocks.useProfiles(),
      profiles: [{ ...assignedProfile, status: "running", headless: true }],
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "打开浏览器 UI" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Browser restart failed");
    expect((screen.getByRole("button", { name: "打开浏览器 UI" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("administrator headless profile handoff", () => {
  it("shows the explicit UI switch instead of the VNC viewer", async () => {
    mocks.api.authStatus.mockResolvedValue({
      auth_required: true,
      authenticated: true,
      role: "admin",
    });
    mocks.useProfiles.mockReturnValue({
      ...mocks.useProfiles(),
      profiles: [{ ...assignedProfile, status: "running", headless: true }],
    });

    render(<App />);
    const openButtons = await screen.findAllByRole("button", { name: "Open Employee Browser" });
    fireEvent.click(openButtons[0]);

    expect(await screen.findByText("This profile is running headless")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open browser UI" })).toBeTruthy();
    expect(screen.queryByTestId("vnc-canvas-container")).toBeNull();
  });
});
