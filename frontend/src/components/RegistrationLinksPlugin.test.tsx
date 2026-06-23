import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "../lib/api";
import { REGISTRATION_PLATFORMS, RegistrationLinksPlugin } from "./RegistrationLinksPlugin";

vi.mock("../lib/api", () => ({
  api: {
    openProfileUrl: vi.fn(),
  },
}));

import { api } from "../lib/api";

const mockApi = api as {
  openProfileUrl: ReturnType<typeof vi.fn>;
};

const redditUrl = "https://www.reddit.com/register/";

function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "profile-1",
    name: "IP-01",
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
    headless: false,
    geoip: true,
    clipboard_sync: false,
    auto_launch: false,
    restore_last_session: true,
    is_archived: false,
    archived_at: null,
    color_scheme: null,
    launch_args: [],
    notes: null,
    user_data_dir: "/tmp/profile-1",
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:00:00Z",
    tags: [],
    status: "running",
    vnc_ws_port: 6100,
    cdp_url: "/api/profiles/profile-1/cdp",
    ...overrides,
  };
}

function renderPlugin(profiles: Profile[] = [makeProfile()]) {
  return render(
    <RegistrationLinksPlugin
      profiles={profiles}
      onOpenProfile={vi.fn()}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.openProfileUrl.mockResolvedValue({ ok: true, profile_id: "profile-1", url: redditUrl });
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RegistrationLinksPlugin", () => {
  it("renders major platform registration links and the running profile selector", async () => {
    renderPlugin();

    expect(screen.getByText("Registration Links")).toBeTruthy();
    expect(screen.getByText(`${REGISTRATION_PLATFORMS.length} selected / ${REGISTRATION_PLATFORMS.length} platforms · IP-01`)).toBeTruthy();
    expect(screen.getByTitle("Target running profile")).toBeTruthy();
    expect(screen.getByText("Reddit")).toBeTruthy();
    expect(screen.getByText("Facebook")).toBeTruthy();
    expect(screen.getByText("YouTube / Google")).toBeTruthy();
  });

  it("opens only the selected registration pages inside the selected profile", async () => {
    const onOpenProfile = vi.fn();
    render(
      <RegistrationLinksPlugin
        profiles={[makeProfile()]}
        onOpenProfile={onOpenProfile}
      />,
    );

    fireEvent.click(screen.getByTitle("Clear selection"));
    fireEvent.change(screen.getByPlaceholderText("Search platform..."), { target: { value: "reddit" } });
    fireEvent.click(screen.getByTitle("Select visible platforms"));
    fireEvent.click(screen.getByTitle("Open selected registration pages in the selected running profile"));

    await waitFor(() => {
      expect(mockApi.openProfileUrl).toHaveBeenCalledWith("profile-1", redditUrl);
    });
    expect(mockApi.openProfileUrl).toHaveBeenCalledTimes(1);
    expect(onOpenProfile).toHaveBeenCalledWith("profile-1");
  });

  it("opens one platform from its row action inside the selected profile", async () => {
    const onOpenProfile = vi.fn();
    render(
      <RegistrationLinksPlugin
        profiles={[makeProfile()]}
        onOpenProfile={onOpenProfile}
      />,
    );

    fireEvent.click(screen.getByTitle("Open Reddit registration in selected profile"));

    await waitFor(() => {
      expect(mockApi.openProfileUrl).toHaveBeenCalledWith("profile-1", redditUrl);
    });
    expect(onOpenProfile).toHaveBeenCalledWith("profile-1");
  });

  it("disables profile-opening actions when no profile is running", () => {
    renderPlugin([makeProfile({ status: "stopped", vnc_ws_port: null, cdp_url: null })]);

    expect(screen.getByText("No running profile")).toBeTruthy();
    expect((screen.getByTitle("Open selected registration pages in the selected running profile") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTitle("Open Reddit registration in selected profile") as HTMLButtonElement).disabled).toBe(true);
  });

  it("copies a platform registration URL", async () => {
    renderPlugin();

    fireEvent.click(screen.getByTitle("Copy Reddit registration URL"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(redditUrl);
    });
    expect(screen.getByText("Copied")).toBeTruthy();
  });
});
