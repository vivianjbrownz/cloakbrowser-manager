import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InventoryRow, Profile } from "../lib/api";
import { InventoryTable } from "./InventoryTable";

vi.mock("../lib/api", () => ({
  api: {
    listInventoryRows: vi.fn(),
    createAccount: vi.fn(),
    updateAccount: vi.fn(),
    deleteAccount: vi.fn(),
    importInventoryCsv: vi.fn(),
    exportInventoryCsv: vi.fn(),
  },
}));

import { api } from "../lib/api";

const mockApi = api as {
  listInventoryRows: ReturnType<typeof vi.fn>;
  createAccount: ReturnType<typeof vi.fn>;
  updateAccount: ReturnType<typeof vi.fn>;
  deleteAccount: ReturnType<typeof vi.fn>;
  importInventoryCsv: ReturnType<typeof vi.fn>;
  exportInventoryCsv: ReturnType<typeof vi.fn>;
};

function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: "profile-9",
    name: "IP-09 192.126.190.33",
    fingerprint_seed: 9,
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
    user_data_dir: "/tmp/profile-9",
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:00:00Z",
    tags: [],
    status: "stopped",
    vnc_ws_port: null,
    cdp_url: null,
    ...overrides,
  };
}

function makeRow(overrides: Partial<InventoryRow> = {}): InventoryRow {
  return {
    profile_id: "profile-9",
    profile_name: "IP-09 192.126.190.33",
    profile_proxy: null,
    profile_platform: "windows",
    profile_tags: [],
    profile_is_archived: false,
    profile_archived_at: null,
    profile_status: "stopped",
    profile_vnc_ws_port: null,
    profile_cdp_url: null,
    is_profile_only: false,
    account_id: "account-1",
    platform: "reddit",
    account_identifier: "beatriceemurdockz@gmail.com",
    email_or_phone: "beatriceemurdockz@gmail.com",
    account_status: "active",
    platform_status_detail: null,
    purpose: null,
    last_used_at: null,
    account_notes: null,
    account_created_at: "2026-06-05T00:00:00Z",
    account_updated_at: "2026-06-05T00:00:00Z",
    ...overrides,
  };
}

function renderInventory(rows: InventoryRow[]) {
  mockApi.listInventoryRows.mockResolvedValue(rows);
  mockApi.createAccount.mockResolvedValue({ id: "account-2", profile_id: "profile-9" });
  mockApi.updateAccount.mockResolvedValue({ id: "account-1", profile_id: "profile-9" });

  return render(
    <InventoryTable
      profiles={[makeProfile()]}
      onNewProfile={vi.fn()}
      onOpenProfile={vi.fn()}
      onLaunchProfile={vi.fn()}
      onStopProfile={vi.fn()}
      onRefreshProfiles={vi.fn()}
      onArchiveProfile={vi.fn()}
      onRestoreProfile={vi.fn()}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("InventoryTable account actions", () => {
  it("collapses stopped profile groups by default and expands on click", async () => {
    renderInventory([
      makeRow(),
      makeRow({
        account_id: "account-2",
        platform: "facebook",
        account_identifier: "fb-user",
        email_or_phone: "beatriceemurdockz@gmail.com",
      }),
    ]);

    expect(await screen.findByText("2 platforms")).toBeTruthy();
    expect(screen.getAllByText("IP-09 192.126.190.33")).toHaveLength(1);
    expect(screen.getByText("reddit · facebook")).toBeTruthy();
    expect(screen.queryByTitle("Edit account")).toBeNull();

    fireEvent.click(screen.getAllByTitle("Expand profile")[0]);

    expect(screen.getAllByTitle("Edit account")).toHaveLength(2);

    fireEvent.click(screen.getAllByTitle("Collapse profile")[0]);

    expect(screen.queryByTitle("Edit account")).toBeNull();
  });

  it("lets a collapsed profile add another platform", async () => {
    renderInventory([makeRow()]);

    expect(await screen.findByTitle("Add platform")).toBeTruthy();
    expect(screen.queryByTitle("Edit account")).toBeNull();
    fireEvent.click(screen.getByTitle("Add platform"));

    expect(screen.getByText("Add account asset")).toBeTruthy();
    expect((screen.getByPlaceholderText("platform") as HTMLInputElement).value).toBe("");
    expect((screen.getByPlaceholderText("account") as HTMLInputElement).value).toBe("");

    fireEvent.change(screen.getByPlaceholderText("platform"), { target: { value: "Facebook" } });
    fireEvent.change(screen.getByPlaceholderText("account"), { target: { value: "beatriceemurdockz@gmail.com" } });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(mockApi.createAccount).toHaveBeenCalledWith("profile-9", {
        platform: "facebook",
        account_identifier: "beatriceemurdockz@gmail.com",
        email_or_phone: null,
        account_status: "new",
        platform_status_detail: null,
        purpose: null,
        last_used_at: null,
        notes: null,
      });
    });
    expect(mockApi.updateAccount).not.toHaveBeenCalled();
  });

  it("auto-expands running profiles and marks the header", async () => {
    renderInventory([makeRow({ profile_status: "running" })]);

    expect(await screen.findByText("Running")).toBeTruthy();
    expect(screen.getByTestId("inventory-profile-profile-9").className).toContain("border-l-accent");
    expect(screen.getByTitle("Edit account")).toBeTruthy();
  });

  it("auto-expands matching profiles while searching", async () => {
    renderInventory([
      makeRow(),
      makeRow({
        account_id: "account-2",
        platform: "facebook",
        account_identifier: "fb-user",
      }),
    ]);

    expect(await screen.findByText("2 platforms")).toBeTruthy();
    expect(screen.queryByTitle("Edit account")).toBeNull();

    fireEvent.change(screen.getByPlaceholderText("Search profile, account, proxy, notes..."), {
      target: { value: "facebook" },
    });

    await waitFor(() => {
      expect(screen.getAllByTitle("Edit account")).toHaveLength(1);
    });
    expect(screen.getAllByText("facebook").length).toBeGreaterThan(0);
  });

  it("does not show add platform on archived rows", async () => {
    renderInventory([makeRow({ profile_is_archived: true, profile_archived_at: "2026-06-05T00:00:00Z" })]);

    expect(await screen.findByTitle("Restore profile")).toBeTruthy();
    expect(screen.queryByTitle("Add platform")).toBeNull();
    expect(screen.queryByTitle("Edit account")).toBeNull();
  });
});
