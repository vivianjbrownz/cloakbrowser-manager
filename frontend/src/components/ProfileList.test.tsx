import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "../lib/api";
import { ProfileList } from "./ProfileList";

function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "profile-1",
    name: "Alpha",
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
    status: "stopped",
    vnc_ws_port: null,
    cdp_url: null,
    ...overrides,
  };
}

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

afterEach(() => {
  cleanup();
});

describe("ProfileList", () => {
  it("hides archived profiles from the sidebar", () => {
    render(
      <ProfileList
        profiles={[
          makeProfile({ id: "active", name: "Active" }),
          makeProfile({ id: "archived", name: "Archived", is_archived: true }),
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        onNew={vi.fn()}
      />,
    );

    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.queryByText("Archived")).toBeNull();
  });

  it("copies the full ID without selecting the profile", async () => {
    const onSelect = vi.fn();
    const id = "12345678-abcd-4def-8123-1234567890ab";
    render(
      <ProfileList
        profiles={[makeProfile({ id })]}
        selectedId={null}
        onSelect={onSelect}
        onNew={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTitle("Copy full Profile ID"));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(id));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
