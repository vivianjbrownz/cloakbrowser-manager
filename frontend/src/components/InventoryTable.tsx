import {
  Archive,
  ChevronDown,
  ChevronRight,
  Download,
  Eye,
  FileUp,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type AccountAssetData, type AccountStatus, type CsvImportResult, type InventoryRow, type Profile } from "../lib/api";
import { StatusIndicator } from "./StatusIndicator";

const ACCOUNT_STATUSES: AccountStatus[] = ["new", "warming", "active", "limited", "blocked", "retired"];

type StatusFilter = "all" | "profile-only" | AccountStatus;
type SortKey = "profile" | "platform" | "status" | "last_used";

interface InventoryTableProps {
  profiles: Profile[];
  onNewProfile: () => void;
  onOpenProfile: (id: string) => void;
  onLaunchProfile: (id: string) => Promise<void>;
  onStopProfile: (id: string) => Promise<void>;
  onRefreshProfiles: () => Promise<void>;
  onArchiveProfile: (id: string) => Promise<void>;
  onRestoreProfile: (id: string) => Promise<void>;
}

interface AccountDraft extends AccountAssetData {
  profile_id: string;
  account_id: string | null;
}

interface InventoryGroup {
  profile: InventoryRow;
  accountRows: InventoryRow[];
}

interface VisibleInventoryGroup extends InventoryGroup {
  visibleRows: InventoryRow[];
}

function draftFromRow(row: InventoryRow): AccountDraft {
  return {
    profile_id: row.profile_id,
    account_id: row.account_id,
    platform: row.platform ?? "",
    account_identifier: row.account_identifier ?? "",
    email_or_phone: row.email_or_phone ?? "",
    account_status: row.account_status ?? "new",
    platform_status_detail: row.platform_status_detail ?? "",
    purpose: row.purpose ?? "",
    last_used_at: row.last_used_at ?? "",
    notes: row.account_notes ?? "",
  };
}

function newDraftFromRow(row: InventoryRow): AccountDraft {
  return {
    profile_id: row.profile_id,
    account_id: null,
    platform: "",
    account_identifier: "",
    email_or_phone: "",
    account_status: "new",
    platform_status_detail: "",
    purpose: "",
    last_used_at: "",
    notes: "",
  };
}

function normalizeDraft(draft: AccountDraft): AccountAssetData {
  return {
    platform: draft.platform.trim().toLowerCase(),
    account_identifier: draft.account_identifier.trim(),
    email_or_phone: draft.email_or_phone?.trim() || null,
    account_status: draft.account_status,
    platform_status_detail: draft.platform_status_detail?.trim() || null,
    purpose: draft.purpose?.trim() || null,
    last_used_at: draft.last_used_at?.trim() || null,
    notes: draft.notes?.trim() || null,
  };
}

function statusClass(status: AccountStatus | null) {
  switch (status) {
    case "active":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/25";
    case "warming":
      return "bg-sky-500/15 text-sky-300 border-sky-500/25";
    case "limited":
      return "bg-amber-500/15 text-amber-300 border-amber-500/25";
    case "blocked":
      return "bg-red-500/15 text-red-300 border-red-500/25";
    case "retired":
      return "bg-gray-500/15 text-gray-400 border-gray-500/25";
    case "new":
      return "bg-violet-500/15 text-violet-300 border-violet-500/25";
    default:
      return "bg-surface-3 text-gray-500 border-border";
  }
}

function rowSearchText(row: InventoryRow) {
  return [
    row.profile_name,
    row.profile_proxy,
    row.platform,
    row.account_identifier,
    row.email_or_phone,
    row.account_status,
    row.platform_status_detail,
    row.purpose,
    row.account_notes,
    ...row.profile_tags.map((tag) => tag.tag),
  ].filter(Boolean).join(" ").toLowerCase();
}

function profileSearchText(row: InventoryRow) {
  return [
    row.profile_name,
    row.profile_proxy,
    row.profile_platform,
    ...row.profile_tags.map((tag) => tag.tag),
  ].filter(Boolean).join(" ").toLowerCase();
}

function groupInventoryRows(rows: InventoryRow[]): InventoryGroup[] {
  const groups = new Map<string, InventoryGroup>();
  for (const row of rows) {
    const group = groups.get(row.profile_id);
    if (!group) {
      groups.set(row.profile_id, {
        profile: row,
        accountRows: row.account_id ? [row] : [],
      });
      continue;
    }
    if (row.account_id) {
      group.accountRows.push(row);
    } else if (!group.profile.account_id) {
      group.profile = row;
    }
  }
  return Array.from(groups.values()).sort((a, b) => a.profile.profile_name.localeCompare(b.profile.profile_name));
}

function sortAccountRows(rows: InventoryRow[], sortKey: SortKey) {
  return [...rows].sort((a, b) => {
    const value = (row: InventoryRow) => {
      if (sortKey === "platform") return row.platform ?? "";
      if (sortKey === "status") return row.account_status ?? "";
      if (sortKey === "last_used") return row.last_used_at ?? "";
      return row.platform ?? row.account_identifier ?? "";
    };
    return value(a).localeCompare(value(b));
  });
}

function platformSummary(rows: InventoryRow[]) {
  const platforms = Array.from(new Set(rows.map((row) => row.platform).filter((platform): platform is string => Boolean(platform))));
  if (platforms.length === 0) return "No platforms";
  const visible = platforms.slice(0, 4).join(" · ");
  return platforms.length > 4 ? `${visible} · +${platforms.length - 4}` : visible;
}

export function InventoryTable({
  profiles,
  onNewProfile,
  onOpenProfile,
  onLaunchProfile,
  onStopProfile,
  onRefreshProfiles,
  onArchiveProfile,
  onRestoreProfile,
}: InventoryTableProps) {
  const [rows, setRows] = useState<InventoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyProfileId, setBusyProfileId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [includeRetired, setIncludeRetired] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("profile");
  const [expandedProfileIds, setExpandedProfileIds] = useState<Set<string>>(() => new Set());
  const [draft, setDraft] = useState<AccountDraft | null>(null);
  const [importPreview, setImportPreview] = useState<{ name: string; text: string; result: CsvImportResult } | null>(null);
  const [importResult, setImportResult] = useState<CsvImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const refreshRows = useCallback(async () => {
    try {
      const data = await api.listInventoryRows(includeRetired, includeArchived);
      setRows(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch inventory");
    } finally {
      setLoading(false);
    }
  }, [includeArchived, includeRetired]);

  useEffect(() => {
    refreshRows();
    const interval = setInterval(refreshRows, 5000);
    return () => clearInterval(interval);
  }, [refreshRows]);

  const selectableProfiles = useMemo(() => profiles.filter((profile) => !profile.is_archived), [profiles]);
  const visibleProfileCount = includeArchived ? profiles.length : selectableProfiles.length;

  const platformOptions = useMemo(() => {
    return Array.from(new Set(rows.map((row) => row.platform).filter((platform): platform is string => Boolean(platform)))).sort();
  }, [rows]);

  const groupedRows = useMemo(() => groupInventoryRows(rows), [rows]);

  const visibleGroups = useMemo(() => {
    const term = search.trim().toLowerCase();
    const groups: VisibleInventoryGroup[] = [];

    for (const group of groupedRows) {
      const profileMatches = !term || profileSearchText(group.profile).includes(term);

      if (group.accountRows.length === 0) {
        if (statusFilter !== "all" && statusFilter !== "profile-only") continue;
        if (platformFilter !== "all") continue;
        if (term && !profileMatches && !rowSearchText(group.profile).includes(term)) continue;
        groups.push({ ...group, visibleRows: [group.profile] });
        continue;
      }

      const accountRows = group.accountRows.filter((row) => {
        if (statusFilter === "profile-only") return false;
        if (statusFilter !== "all" && row.account_status !== statusFilter) return false;
        if (platformFilter !== "all" && row.platform !== platformFilter) return false;
        if (term && !profileMatches && !rowSearchText(row).includes(term)) return false;
        return true;
      });

      const visibleRows = sortAccountRows(accountRows, sortKey);
      if (visibleRows.length > 0) {
        groups.push({ ...group, visibleRows });
      }
    }

    return groups;
  }, [groupedRows, platformFilter, search, sortKey, statusFilter]);

  const visibleRowCount = visibleGroups.reduce((sum, group) => sum + group.visibleRows.length, 0);
  const hasAutoExpandFilter = search.trim().length > 0 || statusFilter !== "all" || platformFilter !== "all";

  const toggleProfileExpanded = (profileId: string) => {
    setExpandedProfileIds((prev) => {
      const next = new Set(prev);
      if (next.has(profileId)) {
        next.delete(profileId);
      } else {
        next.add(profileId);
      }
      return next;
    });
  };

  const saveDraft = async () => {
    if (!draft) return;
    const data = normalizeDraft(draft);
    if (!data.platform || !data.account_identifier) {
      setError("Platform and account identifier are required");
      return;
    }
    try {
      if (draft.account_id) {
        await api.updateAccount(draft.account_id, data);
      } else {
        await api.createAccount(draft.profile_id, data);
      }
      setDraft(null);
      await refreshRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save account");
    }
  };

  const deleteAccount = async (row: InventoryRow) => {
    if (!row.account_id) return;
    if (!window.confirm(`Delete ${row.account_identifier ?? "this account"} from inventory?`)) return;
    try {
      await api.deleteAccount(row.account_id);
      await refreshRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete account");
    }
  };

  const runProfileAction = async (row: InventoryRow) => {
    if (row.profile_is_archived) return;
    setBusyProfileId(row.profile_id);
    try {
      if (row.profile_status === "running") {
        await onStopProfile(row.profile_id);
      } else {
        await onLaunchProfile(row.profile_id);
      }
      await onRefreshProfiles();
      await refreshRows();
    } finally {
      setBusyProfileId(null);
    }
  };

  const archiveProfile = async (row: InventoryRow) => {
    if (row.profile_is_archived || row.profile_status === "running") return;
    const label = row.profile_name || "this profile";
    if (!window.confirm(`Archive ${label}? This deletes browser cookies, cache, history, local storage, and session tabs. Profile settings and inventory records remain.`)) return;
    setBusyProfileId(row.profile_id);
    try {
      await onArchiveProfile(row.profile_id);
      await onRefreshProfiles();
      await refreshRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive profile");
    } finally {
      setBusyProfileId(null);
    }
  };

  const restoreProfile = async (row: InventoryRow) => {
    if (!row.profile_is_archived) return;
    setBusyProfileId(row.profile_id);
    try {
      await onRestoreProfile(row.profile_id);
      await onRefreshProfiles();
      await refreshRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore profile");
    } finally {
      setBusyProfileId(null);
    }
  };

  const exportCsv = async () => {
    const text = await api.exportInventoryCsv(includeArchived);
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "cloakbrowser-inventory.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleImportFile = async (file: File | null) => {
    if (!file) return;
    try {
      const text = await file.text();
      const result = await api.importInventoryCsv(text, true);
      setImportPreview({ name: file.name, text, result });
      setImportResult(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview CSV import");
    }
  };

  const confirmImport = async () => {
    if (!importPreview) return;
    try {
      const result = await api.importInventoryCsv(importPreview.text, false);
      setImportResult(result);
      setImportPreview(null);
      await refreshRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import CSV");
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading inventory...</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-surface-0">
      <div className="border-b border-border bg-surface-1 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Inventory</h2>
            <p className="text-xs text-gray-500">{visibleGroups.length} profiles / {visibleRowCount} platform rows shown from {visibleProfileCount} profiles</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-secondary flex items-center gap-1.5" onClick={refreshRows} title="Refresh inventory">
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Refresh</span>
            </button>
            <button className="btn-secondary flex items-center gap-1.5" onClick={exportCsv} title="Export CSV">
              <Download className="h-3.5 w-3.5" />
              <span>Export</span>
            </button>
            <button className="btn-secondary flex items-center gap-1.5" onClick={() => fileInputRef.current?.click()} title="Import CSV">
              <FileUp className="h-3.5 w-3.5" />
              <span>Import</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => handleImportFile(event.target.files?.[0] ?? null)}
            />
            <button className="btn-primary flex items-center gap-1.5" onClick={onNewProfile}>
              <Plus className="h-3.5 w-3.5" />
              <span>Profile</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[minmax(220px,1fr)_160px_160px_160px_auto] gap-2 mt-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
            <input
              className="input pl-8"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search profile, account, proxy, notes..."
            />
          </div>
          <select className="input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
            <option value="all">All statuses</option>
            <option value="profile-only">Profile only</option>
            {ACCOUNT_STATUSES.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
          <select className="input" value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)}>
            <option value="all">All platforms</option>
            {platformOptions.map((platform) => (
              <option key={platform} value={platform}>{platform}</option>
            ))}
          </select>
          <select className="input" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            <option value="profile">Sort by profile</option>
            <option value="platform">Sort by platform</option>
            <option value="status">Sort by status</option>
            <option value="last_used">Sort by last used</option>
          </select>
          <div className="h-9 flex items-center gap-3 px-3 rounded-md border border-border bg-surface-2 text-xs text-gray-400 whitespace-nowrap">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={includeRetired} onChange={(event) => setIncludeRetired(event.target.checked)} />
              <span>Retired</span>
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
              <span>Archived</span>
            </label>
          </div>
        </div>
      </div>

      {error && (
        <div className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {(importPreview || importResult) && (
        <div className="px-4 py-2 border-b border-border bg-surface-1 text-sm">
          {importPreview && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-gray-300">
                Preview {importPreview.name}: {importPreview.result.created} new, {importPreview.result.updated} updates,
                {" "}{importPreview.result.skipped} skipped, {importPreview.result.rejected} rejected
              </span>
              <div className="flex items-center gap-2">
                <button className="btn-primary" onClick={confirmImport} disabled={importPreview.result.rejected > 0}>Apply Import</button>
                <button className="btn-secondary" onClick={() => setImportPreview(null)}>Cancel</button>
              </div>
            </div>
          )}
          {importResult && (
            <span className="text-gray-300">
              Import complete: {importResult.created} new, {importResult.updated} updates, {importResult.skipped} skipped,
              {" "}{importResult.rejected} rejected
            </span>
          )}
          {(importPreview?.result.errors.length ?? importResult?.errors.length ?? 0) > 0 && (
            <div className="mt-2 text-xs text-amber-300 space-y-1">
              {(importPreview?.result.errors ?? importResult?.errors ?? []).slice(0, 5).map((item) => (
                <div key={`${item.row}-${item.detail}`}>Row {item.row}: {item.detail}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {draft && (
        <div className="border-b border-border bg-surface-1 px-4 py-3">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-gray-200">
              {draft.account_id ? "Edit account asset" : "Add account asset"}
            </div>
            <button className="text-gray-500 hover:text-gray-300 p-1" onClick={() => setDraft(null)} title="Close editor">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 xl:grid-cols-8 gap-2">
            <select className="input" value={draft.profile_id} onChange={(event) => setDraft({ ...draft, profile_id: event.target.value })} disabled={Boolean(draft.account_id)}>
              {profiles
                .filter((profile) => !profile.is_archived || profile.id === draft.profile_id)
                .map((profile) => (
                <option key={profile.id} value={profile.id}>{profile.name}</option>
              ))}
            </select>
            <input className="input" value={draft.platform} onChange={(event) => setDraft({ ...draft, platform: event.target.value })} placeholder="platform" />
            <input className="input" value={draft.account_identifier} onChange={(event) => setDraft({ ...draft, account_identifier: event.target.value })} placeholder="account" />
            <input className="input" value={draft.email_or_phone ?? ""} onChange={(event) => setDraft({ ...draft, email_or_phone: event.target.value })} placeholder="email or phone" />
            <select className="input" value={draft.account_status} onChange={(event) => setDraft({ ...draft, account_status: event.target.value as AccountStatus })}>
              {ACCOUNT_STATUSES.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
            <input className="input" value={draft.platform_status_detail ?? ""} onChange={(event) => setDraft({ ...draft, platform_status_detail: event.target.value })} placeholder="status detail" />
            <input className="input" value={draft.purpose ?? ""} onChange={(event) => setDraft({ ...draft, purpose: event.target.value })} placeholder="purpose" />
            <input className="input" type="date" value={draft.last_used_at ?? ""} onChange={(event) => setDraft({ ...draft, last_used_at: event.target.value })} />
            <textarea className="input md:col-span-3 xl:col-span-6" rows={2} value={draft.notes ?? ""} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} placeholder="notes" />
            <button className="btn-primary flex items-center justify-center gap-1.5 md:col-span-1" onClick={saveDraft}>
              <Save className="h-3.5 w-3.5" />
              <span>Save</span>
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        <table className="w-full min-w-[1180px] text-sm">
          <thead className="sticky top-0 z-10 bg-surface-1 border-b border-border">
            <tr className="text-left text-xs text-gray-500">
              <th className="px-3 py-2 font-medium w-[220px]">Profile</th>
              <th className="px-3 py-2 font-medium w-[190px]">Proxy</th>
              <th className="px-3 py-2 font-medium w-[120px]">Platform</th>
              <th className="px-3 py-2 font-medium w-[180px]">Account</th>
              <th className="px-3 py-2 font-medium w-[180px]">Contact</th>
              <th className="px-3 py-2 font-medium w-[120px]">Status</th>
              <th className="px-3 py-2 font-medium w-[180px]">Detail</th>
              <th className="px-3 py-2 font-medium w-[160px]">Purpose</th>
              <th className="px-3 py-2 font-medium w-[120px]">Last Used</th>
              <th className="px-3 py-2 font-medium w-[220px]">Notes</th>
              <th className="px-3 py-2 font-medium w-[220px]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleGroups.length === 0 && (
              <tr>
                <td className="px-3 py-10 text-center text-gray-500" colSpan={11}>No inventory rows match the current filters</td>
              </tr>
            )}
            {visibleGroups.map((group) => {
              const isRunning = group.profile.profile_status === "running";
              const isExpanded = isRunning || hasAutoExpandFilter || expandedProfileIds.has(group.profile.profile_id);
              return (
              <Fragment key={group.profile.profile_id}>
                <tr
                  data-testid={`inventory-profile-${group.profile.profile_id}`}
                  data-status={group.profile.profile_status}
                  className={`border-t border-border ${
                    isRunning
                      ? "border-l-2 border-l-accent bg-accent/10"
                      : "bg-surface-1/90"
                  }`}
                >
                  <td className="px-3 py-2" colSpan={11}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 min-w-0">
                          <button
                            className="btn-secondary px-2"
                            onClick={() => toggleProfileExpanded(group.profile.profile_id)}
                            title={isExpanded ? "Collapse profile" : "Expand profile"}
                            aria-expanded={isExpanded}
                          >
                            {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                          </button>
                          <StatusIndicator status={group.profile.profile_status} />
                          <button className="font-semibold text-gray-100 truncate hover:text-accent" onClick={() => toggleProfileExpanded(group.profile.profile_id)} title={isExpanded ? "Collapse profile" : "Expand profile"}>
                            {group.profile.profile_name}
                          </button>
                          <span className="text-xs text-gray-500 capitalize">{group.profile.profile_platform ?? "profile"}</span>
                          {group.profile.profile_proxy && (
                            <span className="text-xs text-gray-500 truncate max-w-[240px]" title={group.profile.profile_proxy}>
                              Proxy
                            </span>
                          )}
                          <span className="text-xs text-gray-500">
                            {group.accountRows.length} platform{group.accountRows.length === 1 ? "" : "s"}
                          </span>
                          <span className="text-xs text-gray-500 truncate max-w-[260px]" title={platformSummary(group.accountRows)}>
                            {platformSummary(group.accountRows)}
                          </span>
                          {isRunning && (
                            <span className="inline-flex items-center text-[10px] uppercase tracking-wide border border-accent/30 rounded-full px-1.5 py-0.5 text-accent bg-accent/10">
                              Running
                            </span>
                          )}
                          {group.profile.profile_is_archived && (
                            <span className="inline-flex items-center text-[10px] uppercase tracking-wide border border-border rounded-full px-1.5 py-0.5 text-gray-500 bg-surface-2">
                              Archived
                            </span>
                          )}
                        </div>
                        {group.profile.profile_tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1 ml-4">
                            {group.profile.profile_tags.map((tag) => (
                              <span key={tag.tag} className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-3 text-gray-400">
                                {tag.tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button className="btn-secondary px-2" onClick={() => onOpenProfile(group.profile.profile_id)} title="Open profile">
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        {group.profile.profile_is_archived ? (
                          <button className="btn-primary px-2" onClick={() => restoreProfile(group.profile)} title="Restore profile" disabled={busyProfileId === group.profile.profile_id}>
                            <RotateCcw className="h-3.5 w-3.5" />
                          </button>
                        ) : (
                          <>
                            <button className="btn-secondary px-2" onClick={() => runProfileAction(group.profile)} title={group.profile.profile_status === "running" ? "Stop profile" : "Launch profile"} disabled={busyProfileId === group.profile.profile_id}>
                              {group.profile.profile_status === "running" ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                            </button>
                            <button className="btn-secondary px-2" onClick={() => setDraft(newDraftFromRow(group.profile))} title={group.accountRows.length > 0 ? "Add platform" : "Add account"}>
                              <Plus className="h-3.5 w-3.5" />
                            </button>
                            {group.profile.profile_status !== "running" && (
                              <button className="btn-secondary px-2" onClick={() => archiveProfile(group.profile)} title="Archive profile" disabled={busyProfileId === group.profile.profile_id}>
                                <Archive className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>

                {isExpanded && group.visibleRows.map((row) => (
                  row.account_id ? (
                    <tr key={`${row.profile_id}-${row.account_id}`} className="border-b border-border/60 hover:bg-surface-1/60">
                      <td className="px-3 py-2 align-top">
                        <div className="ml-6 h-full border-l border-border pl-3 text-xs text-gray-500">
                          Account
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 align-top text-gray-300">{row.platform ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-gray-200">{row.account_identifier ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-gray-400">{row.email_or_phone ?? "-"}</td>
                      <td className="px-3 py-2 align-top">
                        <span className={`inline-flex border text-xs px-2 py-0.5 rounded-full ${statusClass(row.account_status)}`}>
                          {row.account_status ?? "profile-only"}
                        </span>
                      </td>
                      <td className="px-3 py-2 align-top text-gray-400 truncate" title={row.platform_status_detail ?? ""}>{row.platform_status_detail ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-gray-400 truncate" title={row.purpose ?? ""}>{row.purpose ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-gray-400">{row.last_used_at ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-gray-400 truncate" title={row.account_notes ?? ""}>{row.account_notes ?? "-"}</td>
                      <td className="px-3 py-2 align-top">
                        {!group.profile.profile_is_archived && (
                          <div className="flex items-center gap-1.5">
                            <button className="btn-secondary px-2" onClick={() => setDraft(draftFromRow(row))} title="Edit account">
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <button className="btn-danger px-2" onClick={() => deleteAccount(row)} title="Delete account">
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ) : (
                    <tr key={`${row.profile_id}-empty`} className="border-b border-border/60 hover:bg-surface-1/60">
                      <td className="px-3 py-2 align-top">
                        <div className="ml-6 h-full border-l border-border pl-3 text-xs text-gray-500">
                          No platform rows
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 align-top text-gray-500">-</td>
                      <td className="px-3 py-2 align-top text-gray-500">No account</td>
                      <td className="px-3 py-2 align-top text-gray-500">-</td>
                      <td className="px-3 py-2 align-top">
                        <span className={`inline-flex border text-xs px-2 py-0.5 rounded-full ${statusClass(null)}`}>
                          profile-only
                        </span>
                      </td>
                      <td className="px-3 py-2 align-top text-gray-500">-</td>
                      <td className="px-3 py-2 align-top text-gray-500">-</td>
                      <td className="px-3 py-2 align-top text-gray-500">-</td>
                      <td className="px-3 py-2 align-top text-gray-500">-</td>
                      <td className="px-3 py-2 align-top" />
                    </tr>
                  )
                ))}
              </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
