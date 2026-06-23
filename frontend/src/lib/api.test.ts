import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "./api";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(data),
  };
}

beforeEach(() => {
  mockFetch.mockReset();
});

// ── listProfiles ────────────────────────────────────────────────────────────

describe("api.listProfiles", () => {
  it("returns profile array on success", async () => {
    const profiles = [{ id: "1", name: "Test" }];
    mockFetch.mockResolvedValueOnce(jsonResponse(profiles));
    const result = await api.listProfiles();
    expect(result).toEqual(profiles);
    expect(mockFetch).toHaveBeenCalledWith("/api/profiles", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

// ── createProfile ───────────────────────────────────────────────────────────

describe("api.createProfile", () => {
  it("sends POST with JSON body", async () => {
    const profile = { id: "2", name: "New" };
    mockFetch.mockResolvedValueOnce(jsonResponse(profile));
    await api.createProfile({ name: "New" });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ name: "New" });
  });
});

// ── updateProfile ───────────────────────────────────────────────────────────

describe("api.updateProfile", () => {
  it("sends PUT with JSON body", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "1", name: "Updated" }));
    await api.updateProfile("1", { name: "Updated" });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/1");
    expect(options.method).toBe("PUT");
  });
});

// ── deleteProfile ───────────────────────────────────────────────────────────

describe("api.deleteProfile", () => {
  it("sends DELETE request", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    const result = await api.deleteProfile("1");
    expect(result).toEqual({ ok: true });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/1");
    expect(options.method).toBe("DELETE");
  });
});

describe("api.archiveProfile", () => {
  it("sends POST to archive endpoint", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "1", is_archived: true }));
    const result = await api.archiveProfile("1");
    expect(result).toEqual({ id: "1", is_archived: true });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/1/archive");
    expect(options.method).toBe("POST");
  });
});

describe("api.restoreProfile", () => {
  it("sends POST to restore endpoint", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "1", is_archived: false }));
    await api.restoreProfile("1");
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/1/restore");
    expect(options.method).toBe("POST");
  });
});

// ── launchProfile ───────────────────────────────────────────────────────────

describe("api.launchProfile", () => {
  it("sends POST to launch endpoint", async () => {
    const result = { profile_id: "1", status: "running", vnc_ws_port: 6100, display: ":100" };
    mockFetch.mockResolvedValueOnce(jsonResponse(result));
    const data = await api.launchProfile("1");
    expect(data.vnc_ws_port).toBe(6100);
    expect(mockFetch.mock.calls[0][0]).toBe("/api/profiles/1/launch");
  });
});

// ── stopProfile ─────────────────────────────────────────────────────────────

describe("api.stopProfile", () => {
  it("sends POST to stop endpoint", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api.stopProfile("1");
    expect(mockFetch.mock.calls[0][0]).toBe("/api/profiles/1/stop");
  });
});

// ── setClipboard ────────────────────────────────────────────────────────────

describe("api.setClipboard", () => {
  it("sends POST with text body", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api.setClipboard("1", "hello");
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/1/clipboard");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ text: "hello" });
  });
});

// ── getClipboard ────────────────────────────────────────────────────────────

describe("api.getClipboard", () => {
  it("returns clipboard text", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ text: "copied" }));
    const result = await api.getClipboard("1");
    expect(result.text).toBe("copied");
  });
});

describe("api.openProfileUrl", () => {
  it("opens a URL inside a running profile", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true, profile_id: "1", url: "https://www.reddit.com/register/" }));
    await api.openProfileUrl("1", "https://www.reddit.com/register/");
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/1/open-url");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ url: "https://www.reddit.com/register/" });
  });
});

// ── Inventory ──────────────────────────────────────────────────────────────

describe("api.listInventoryRows", () => {
  it("passes include_retired and include_archived flags", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse([]));
    await api.listInventoryRows(true, true);
    expect(mockFetch.mock.calls[0][0]).toBe("/api/inventory/rows?include_retired=true&include_archived=true");
  });
});

describe("api.createAccount", () => {
  it("creates account assets under a profile", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "a1", profile_id: "p1" }));
    await api.createAccount("p1", {
      platform: "facebook",
      account_identifier: "fb-user",
      account_status: "active",
    });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/profiles/p1/accounts");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      platform: "facebook",
      account_identifier: "fb-user",
      account_status: "active",
    });
  });
});

describe("api.importInventoryCsv", () => {
  it("sends CSV text with dry run flag", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ dry_run: true, created: 1, updated: 0, skipped: 0, rejected: 0, errors: [] }));
    await api.importInventoryCsv("profile_id,platform\n", true);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/inventory/import.csv?dry_run=true");
    expect(options.method).toBe("POST");
    expect(options.headers).toEqual({ "Content-Type": "text/csv" });
    expect(options.body).toBe("profile_id,platform\n");
  });
});

describe("api.exportInventoryCsv", () => {
  it("returns CSV text", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve("profile_id\np1\n"),
    });
    const text = await api.exportInventoryCsv();
    expect(text).toBe("profile_id\np1\n");
    expect(mockFetch.mock.calls[0][0]).toBe("/api/inventory/export.csv?include_archived=false");
  });

  it("can include archived profiles", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve("profile_id\np1\n"),
    });
    await api.exportInventoryCsv(true);
    expect(mockFetch.mock.calls[0][0]).toBe("/api/inventory/export.csv?include_archived=true");
  });
});

// ── Research Center ────────────────────────────────────────────────────────

describe("api.listResearchDomains", () => {
  it("passes domain filters as query params", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse([]));
    await api.listResearchDomains({ status: "review", min_score: 50, q: "hosting" });
    expect(mockFetch.mock.calls[0][0]).toBe("/api/research/domains?status=review&min_score=50&q=hosting");
  });
});

describe("api.bulkCreateResearchDomains", () => {
  it("sends bulk domain text", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ created: 1, updated: 0, skipped: 0, rejected: 0, errors: [] }));
    await api.bulkCreateResearchDomains("example.com", "hosting", "manual");
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/research/domains/bulk");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      text: "example.com",
      niche: "hosting",
      source: "manual",
    });
  });
});

describe("api.refreshResearchDomainWayback", () => {
  it("posts to the Wayback refresh endpoint", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ domain: { id: "d1" }, signals: {} }));
    await api.refreshResearchDomainWayback("d1");
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/research/domains/d1/wayback");
    expect(options.method).toBe("POST");
  });
});

describe("api.createResearchKeywords", () => {
  it("creates keyword research tasks", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse([]));
    await api.createResearchKeywords({
      niche: "hosting",
      seed_keywords: ["best hosting"],
      target_country: "US",
      target_language: "en",
    });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/research/keywords");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      niche: "hosting",
      seed_keywords: ["best hosting"],
      target_country: "US",
      target_language: "en",
    });
  });
});

describe("api.createContentOpportunity", () => {
  it("creates content opportunities", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "c1" }));
    await api.createContentOpportunity({
      keyword_id: "k1",
      niche: "hosting",
      keyword: "best hosting",
      article_type: "best",
      priority: "high",
      monetization_type: "affiliate",
    });
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/research/content-opportunities");
    expect(options.method).toBe("POST");
  });
});

// ── Error handling ──────────────────────────────────────────────────────────

describe("error handling", () => {
  it("throws ApiError with detail on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: () => Promise.resolve({ detail: "Profile not found" }),
    });
    await expect(api.getProfile("bad")).rejects.toThrow("Profile not found");
  });

  it("falls back to statusText when response is not JSON", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.reject(new Error("not json")),
    });
    await expect(api.getStatus()).rejects.toThrow("Internal Server Error");
  });
});
