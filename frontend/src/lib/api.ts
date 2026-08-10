/**
 * API client for CloakBrowser Manager backend.
 */

export interface Profile {
  id: string;
  name: string;
  fingerprint_seed: number;
  proxy: string | null;
  timezone: string | null;
  locale: string | null;
  platform: string;
  user_agent: string | null;
  screen_width: number;
  screen_height: number;
  gpu_vendor: string | null;
  gpu_renderer: string | null;
  hardware_concurrency: number | null;
  humanize: boolean;
  human_preset: string;
  headless: boolean;
  geoip: boolean;
  clipboard_sync: boolean;
  auto_launch: boolean;
  restore_last_session: boolean;
  is_archived: boolean;
  archived_at: string | null;
  color_scheme: string | null;
  launch_args: string[];
  notes: string | null;
  user_data_dir: string;
  created_at: string;
  updated_at: string;
  tags: { tag: string; color: string | null }[];
  status: "running" | "stopped";
  vnc_ws_port: number | null;
  cdp_url: string | null;
}

export interface ProfileCreateData {
  name: string;
  fingerprint_seed?: number | null;
  proxy?: string | null;
  timezone?: string | null;
  locale?: string | null;
  platform?: string;
  user_agent?: string | null;
  screen_width?: number;
  screen_height?: number;
  gpu_vendor?: string | null;
  gpu_renderer?: string | null;
  hardware_concurrency?: number | null;
  humanize?: boolean;
  human_preset?: string;
  headless?: boolean;
  geoip?: boolean;
  clipboard_sync?: boolean;
  auto_launch?: boolean;
  restore_last_session?: boolean;
  color_scheme?: string | null;
  launch_args?: string[];
  notes?: string | null;
  tags?: { tag: string; color: string | null }[];
}

export interface LaunchResult {
  profile_id: string;
  status: string;
  vnc_ws_port: number;
  display: string;
  cdp_url: string | null;
}

export interface SystemStatus {
  running_count: number;
  binary_version: string;
  profiles_total: number;
}

export type AccountStatus = "new" | "warming" | "active" | "limited" | "blocked" | "retired";

export interface AccountAsset {
  id: string;
  profile_id: string;
  platform: string;
  account_identifier: string;
  email_or_phone: string | null;
  account_status: AccountStatus;
  platform_status_detail: string | null;
  purpose: string | null;
  last_used_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountAssetData {
  platform: string;
  account_identifier: string;
  email_or_phone?: string | null;
  account_status?: AccountStatus;
  platform_status_detail?: string | null;
  purpose?: string | null;
  last_used_at?: string | null;
  notes?: string | null;
}

export interface InventoryRow {
  profile_id: string;
  profile_name: string;
  profile_proxy: string | null;
  profile_platform: string | null;
  profile_tags: { tag: string; color: string | null }[];
  profile_is_archived: boolean;
  profile_archived_at: string | null;
  profile_status: "running" | "stopped";
  profile_vnc_ws_port: number | null;
  profile_cdp_url: string | null;
  is_profile_only: boolean;
  account_id: string | null;
  platform: string | null;
  account_identifier: string | null;
  email_or_phone: string | null;
  account_status: AccountStatus | null;
  platform_status_detail: string | null;
  purpose: string | null;
  last_used_at: string | null;
  account_notes: string | null;
  account_created_at: string | null;
  account_updated_at: string | null;
}

export interface CsvImportResult {
  dry_run: boolean;
  created: number;
  updated: number;
  skipped: number;
  rejected: number;
  errors: { row: number; detail: string }[];
}

export type DomainClassification = "pass" | "review" | "reject";
export type DomainReviewLabel = "good" | "risky" | "bad";
export type KeywordIntent = "informational" | "commercial" | "transactional" | "navigational" | "comparison";
export type ArticleType = "best" | "vs" | "review" | "alternatives" | "how_to_choose";
export type OpportunityPriority = "high" | "medium" | "low";
export type MonetizationType = "affiliate" | "lead_gen" | "ads" | "product" | "none";
export type ContentState = "idea" | "approved" | "drafting" | "published";

export interface ResearchImportResult {
  created: number;
  updated: number;
  skipped: number;
  rejected: number;
  errors: { row: number; detail: string }[];
}

export interface ResearchDomain {
  id: string;
  domain: string;
  niche: string | null;
  source: string | null;
  status: DomainClassification;
  score: number;
  classification: DomainClassification;
  notes: string | null;
  reviewer_label: DomainReviewLabel | null;
  reviewed_at: string | null;
  wayback_history_exists: boolean;
  wayback_snapshot_count: number;
  wayback_first_snapshot_at: string | null;
  wayback_last_snapshot_at: string | null;
  wayback_snapshot_span_days: number;
  wayback_title_change_count: number;
  wayback_high_risk_terms: string[];
  wayback_checked_at: string | null;
  scoring_signals: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ResearchDomainCreateData {
  domain: string;
  niche?: string | null;
  source?: string | null;
  notes?: string | null;
}

export interface ResearchDomainUpdateData {
  niche?: string | null;
  source?: string | null;
  status?: DomainClassification;
  notes?: string | null;
  reviewer_label?: DomainReviewLabel | null;
}

export interface ResearchKeyword {
  id: string;
  niche: string;
  seed_keywords: string[];
  target_country: string;
  target_language: string;
  keyword: string;
  intent: KeywordIntent;
  article_type: ArticleType;
  priority: OpportunityPriority;
  monetization_type: MonetizationType;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResearchKeywordTaskData {
  niche: string;
  seed_keywords: string[];
  target_country?: string;
  target_language?: string;
}

export interface ResearchKeywordUpdateData {
  intent?: KeywordIntent;
  article_type?: ArticleType;
  priority?: OpportunityPriority;
  monetization_type?: MonetizationType;
  notes?: string | null;
}

export interface ContentOpportunity {
  id: string;
  keyword_id: string | null;
  niche: string | null;
  keyword: string;
  article_type: ArticleType;
  priority: OpportunityPriority;
  monetization_type: MonetizationType;
  state: ContentState;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentOpportunityData {
  keyword_id?: string | null;
  niche?: string | null;
  keyword: string;
  article_type?: ArticleType;
  priority?: OpportunityPriority;
  monetization_type?: MonetizationType;
  state?: ContentState;
  notes?: string | null;
}

export interface ResearchProviderConfig {
  providers: Record<string, {
    enabled: boolean;
    provider: string | null;
    ready_for: string[];
    requires_api_key: boolean;
  }>;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Global 401 callback — set by App to trigger login page on auth failure
let _onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(cb: (() => void) | null) {
  _onUnauthorized = cb;
}

function queryString(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    if (res.status === 401 && _onUnauthorized) {
      _onUnauthorized();
      throw new ApiError(401, "Unauthorized");
    }
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  authStatus: () =>
    request<{
      auth_required: boolean;
      authenticated: boolean;
      role?: "admin" | "scoped";
      email?: string;
      assigned_profile_id?: string;
    }>("/api/auth/status"),

  login: (token: string) =>
    request<{ ok: boolean }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  logout: () =>
    request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  listProfiles: () => request<Profile[]>("/api/profiles"),

  getProfile: (id: string) => request<Profile>(`/api/profiles/${id}`),

  createProfile: (data: ProfileCreateData) =>
    request<Profile>("/api/profiles", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProfile: (id: string, data: Partial<ProfileCreateData>) =>
    request<Profile>(`/api/profiles/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProfile: (id: string) =>
    request<{ ok: boolean }>(`/api/profiles/${id}`, { method: "DELETE" }),

  archiveProfile: (id: string) =>
    request<Profile>(`/api/profiles/${id}/archive`, { method: "POST" }),

  restoreProfile: (id: string) =>
    request<Profile>(`/api/profiles/${id}/restore`, { method: "POST" }),

  launchProfile: (id: string) =>
    request<LaunchResult>(`/api/profiles/${id}/launch`, { method: "POST" }),

  stopProfile: (id: string) =>
    request<{ ok: boolean }>(`/api/profiles/${id}/stop`, { method: "POST" }),

  startProfileUi: (id: string) =>
    request<LaunchResult>(`/api/profiles/${id}/ui/start`, { method: "POST" }),

  stopProfileUi: (id: string) =>
    request<LaunchResult>(`/api/profiles/${id}/ui/stop`, { method: "POST" }),

  getStatus: () => request<SystemStatus>("/api/status"),

  setClipboard: (id: string, text: string) =>
    request<{ ok: boolean }>(`/api/profiles/${id}/clipboard`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  getClipboard: (id: string) =>
    request<{ text: string }>(`/api/profiles/${id}/clipboard`),

  openProfileUrl: (id: string, url: string) =>
    request<{ ok: boolean; profile_id: string; url: string }>(`/api/profiles/${id}/open-url`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  listInventoryRows: (includeRetired = false, includeArchived = false) =>
    request<InventoryRow[]>(
      `/api/inventory/rows?include_retired=${includeRetired ? "true" : "false"}&include_archived=${includeArchived ? "true" : "false"}`,
    ),

  createAccount: (profileId: string, data: AccountAssetData) =>
    request<AccountAsset>(`/api/profiles/${profileId}/accounts`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateAccount: (accountId: string, data: Partial<AccountAssetData>) =>
    request<AccountAsset>(`/api/accounts/${accountId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteAccount: (accountId: string) =>
    request<{ ok: boolean }>(`/api/accounts/${accountId}`, { method: "DELETE" }),

  importInventoryCsv: (csvText: string, dryRun: boolean) =>
    request<CsvImportResult>(`/api/inventory/import.csv?dry_run=${dryRun ? "true" : "false"}`, {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: csvText,
    }),

  exportInventoryCsv: async (includeArchived = false) => {
    const res = await fetch(`/api/inventory/export.csv?include_archived=${includeArchived ? "true" : "false"}`);
    if (!res.ok) {
      if (res.status === 401 && _onUnauthorized) {
        _onUnauthorized();
        throw new ApiError(401, "Unauthorized");
      }
      throw new ApiError(res.status, res.statusText);
    }
    return res.text();
  },

  getResearchProviderConfig: () =>
    request<ResearchProviderConfig>("/api/research/provider-config"),

  listResearchDomains: (filters: { status?: string; niche?: string; min_score?: number; q?: string } = {}) =>
    request<ResearchDomain[]>(`/api/research/domains${queryString(filters)}`),

  createResearchDomain: (data: ResearchDomainCreateData) =>
    request<ResearchDomain>("/api/research/domains", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkCreateResearchDomains: (text: string, niche?: string | null, source?: string | null) =>
    request<ResearchImportResult>("/api/research/domains/bulk", {
      method: "POST",
      body: JSON.stringify({ text, niche, source }),
    }),

  updateResearchDomain: (id: string, data: ResearchDomainUpdateData) =>
    request<ResearchDomain>(`/api/research/domains/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  refreshResearchDomainWayback: (id: string) =>
    request<{ domain: ResearchDomain; signals: Record<string, unknown> }>(`/api/research/domains/${id}/wayback`, {
      method: "POST",
    }),

  listResearchKeywords: (filters: { niche?: string; q?: string } = {}) =>
    request<ResearchKeyword[]>(`/api/research/keywords${queryString(filters)}`),

  createResearchKeywords: (data: ResearchKeywordTaskData) =>
    request<ResearchKeyword[]>("/api/research/keywords", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateResearchKeyword: (id: string, data: ResearchKeywordUpdateData) =>
    request<ResearchKeyword>(`/api/research/keywords/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  listContentOpportunities: (filters: { state?: string; niche?: string; q?: string } = {}) =>
    request<ContentOpportunity[]>(`/api/research/content-opportunities${queryString(filters)}`),

  createContentOpportunity: (data: ContentOpportunityData) =>
    request<ContentOpportunity>("/api/research/content-opportunities", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateContentOpportunity: (id: string, data: Partial<ContentOpportunityData>) =>
    request<ContentOpportunity>(`/api/research/content-opportunities/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};
