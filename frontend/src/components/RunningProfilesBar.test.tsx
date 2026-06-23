import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "../lib/api";
import { RunningProfilesBar } from "./RunningProfilesBar";

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

afterEach(() => {
  cleanup();
});

describe("RunningProfilesBar", () => {
  it("does not render when no profiles are running", () => {
    const { container } = render(
      <RunningProfilesBar
        profiles={[makeProfile({ status: "stopped" })]}
        selectedId={null}
        onOpenProfile={vi.fn()}
        onStopProfile={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("shows running profile count and hides stopped profiles", () => {
    render(
      <RunningProfilesBar
        profiles={[
          makeProfile({ id: "alpha", name: "Alpha", status: "running" }),
          makeProfile({ id: "beta", name: "Beta", status: "stopped" }),
          makeProfile({ id: "gamma", name: "Gamma", status: "running" }),
        ]}
        selectedId={null}
        onOpenProfile={vi.fn()}
        onStopProfile={vi.fn()}
      />,
    );

    expect(screen.getByText("Running")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(screen.getByText("Gamma")).toBeTruthy();
    expect(screen.queryByText("Beta")).toBeNull();
  });

  it("opens a running profile from its chip", () => {
    const onOpenProfile = vi.fn();

    render(
      <RunningProfilesBar
        profiles={[makeProfile({ id: "alpha", name: "Alpha", status: "running" })]}
        selectedId={null}
        onOpenProfile={onOpenProfile}
        onStopProfile={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Open Alpha/i }));

    expect(onOpenProfile).toHaveBeenCalledWith("alpha");
  });

  it("stops a profile without opening it", async () => {
    const onOpenProfile = vi.fn();
    const onStopProfile = vi.fn().mockResolvedValue(undefined);

    render(
      <RunningProfilesBar
        profiles={[makeProfile({ id: "alpha", name: "Alpha", status: "running" })]}
        selectedId={null}
        onOpenProfile={onOpenProfile}
        onStopProfile={onStopProfile}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Stop Alpha/i }));

    await waitFor(() => {
      expect(onStopProfile).toHaveBeenCalledWith("alpha");
    });
    expect(onOpenProfile).not.toHaveBeenCalled();
  });

  it("marks the selected running profile", () => {
    render(
      <RunningProfilesBar
        profiles={[makeProfile({ id: "alpha", name: "Alpha", status: "running" })]}
        selectedId="alpha"
        onOpenProfile={vi.fn()}
        onStopProfile={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /Open Alpha/i }).getAttribute("aria-current")).toBe("true");
  });
});
