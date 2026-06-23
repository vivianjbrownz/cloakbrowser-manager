import {
  DatabaseZap,
  FileUp,
  Lightbulb,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Tags,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type ArticleType,
  type ContentOpportunity,
  type ContentState,
  type DomainClassification,
  type DomainReviewLabel,
  type MonetizationType,
  type OpportunityPriority,
  type ResearchDomain,
  type ResearchImportResult,
  type ResearchKeyword,
} from "../lib/api";

type ResearchTab = "domains" | "keywords" | "content";

const DOMAIN_STATUSES: DomainClassification[] = ["pass", "review", "reject"];
const REVIEW_LABELS: DomainReviewLabel[] = ["good", "risky", "bad"];
const INTENTS = ["informational", "commercial", "transactional", "navigational", "comparison"] as const;
const ARTICLE_TYPES: ArticleType[] = ["best", "vs", "review", "alternatives", "how_to_choose"];
const PRIORITIES: OpportunityPriority[] = ["high", "medium", "low"];
const MONETIZATION_TYPES: MonetizationType[] = ["affiliate", "lead_gen", "ads", "product", "none"];
const CONTENT_STATES: ContentState[] = ["idea", "approved", "drafting", "published"];

function labelText(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "-";
}

function statusClass(status: string) {
  if (status === "pass" || status === "good" || status === "approved" || status === "published") {
    return "bg-emerald-500/15 text-emerald-300 border-emerald-500/25";
  }
  if (status === "reject" || status === "bad") {
    return "bg-red-500/15 text-red-300 border-red-500/25";
  }
  if (status === "risky" || status === "drafting") {
    return "bg-amber-500/15 text-amber-300 border-amber-500/25";
  }
  return "bg-sky-500/15 text-sky-300 border-sky-500/25";
}

function scoreClass(score: number) {
  if (score >= 70) return "text-emerald-300";
  if (score >= 45) return "text-amber-300";
  return "text-red-300";
}

function splitSeedKeywords(text: string) {
  return text.replaceAll(",", "\n").split("\n");
}

function normalizeSeedKeywords(text: string) {
  return splitSeedKeywords(text).map((item) => item.trim()).filter(Boolean);
}

interface DomainNoteDraft {
  status: DomainClassification;
  reviewer_label: DomainReviewLabel | "";
  notes: string;
}

export function ResearchCenter() {
  const [tab, setTab] = useState<ResearchTab>("domains");
  const [domains, setDomains] = useState<ResearchDomain[]>([]);
  const [keywords, setKeywords] = useState<ResearchKeyword[]>([]);
  const [contentIdeas, setContentIdeas] = useState<ContentOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [domainInput, setDomainInput] = useState("");
  const [domainBulkText, setDomainBulkText] = useState("");
  const [domainNiche, setDomainNiche] = useState("");
  const [domainSource, setDomainSource] = useState("");
  const [domainQuery, setDomainQuery] = useState("");
  const [domainStatusFilter, setDomainStatusFilter] = useState<"all" | DomainClassification>("all");
  const [minScore, setMinScore] = useState("");
  const [importResult, setImportResult] = useState<ResearchImportResult | null>(null);
  const [domainDrafts, setDomainDrafts] = useState<Record<string, DomainNoteDraft>>({});
  const [keywordNiche, setKeywordNiche] = useState("");
  const [targetCountry, setTargetCountry] = useState("US");
  const [targetLanguage, setTargetLanguage] = useState("en");
  const [seedKeywords, setSeedKeywords] = useState("");
  const [keywordQuery, setKeywordQuery] = useState("");
  const [contentQuery, setContentQuery] = useState("");
  const [contentStateFilter, setContentStateFilter] = useState<"all" | ContentState>("all");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const domainNiches = useMemo(() => {
    return Array.from(new Set(domains.map((domain) => domain.niche).filter((niche): niche is string => Boolean(niche)))).sort();
  }, [domains]);

  const loadDomains = useCallback(async () => {
    const data = await api.listResearchDomains({
      status: domainStatusFilter === "all" ? undefined : domainStatusFilter,
      min_score: minScore ? Number(minScore) : undefined,
      q: domainQuery || undefined,
    });
    setDomains(data);
    setDomainDrafts((prev) => {
      const next = { ...prev };
      for (const domain of data) {
        next[domain.id] = {
          status: domain.status,
          reviewer_label: domain.reviewer_label ?? "",
          notes: domain.notes ?? "",
        };
      }
      return next;
    });
  }, [domainQuery, domainStatusFilter, minScore]);

  const loadKeywords = useCallback(async () => {
    setKeywords(await api.listResearchKeywords({ q: keywordQuery || undefined }));
  }, [keywordQuery]);

  const loadContentIdeas = useCallback(async () => {
    setContentIdeas(await api.listContentOpportunities({
      state: contentStateFilter === "all" ? undefined : contentStateFilter,
      q: contentQuery || undefined,
    }));
  }, [contentQuery, contentStateFilter]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([loadDomains(), loadKeywords(), loadContentIdeas()]);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Research Center");
    } finally {
      setLoading(false);
    }
  }, [loadContentIdeas, loadDomains, loadKeywords]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addSingleDomain = async () => {
    if (!domainInput.trim()) return;
    setBusyId("domain-add");
    try {
      const created = await api.createResearchDomain({
        domain: domainInput,
        niche: domainNiche || null,
        source: domainSource || null,
      });
      setDomains((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      setDomainInput("");
      setMessage(`${created.domain} added`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add domain");
    } finally {
      setBusyId(null);
    }
  };

  const bulkAddDomains = async (text = domainBulkText) => {
    if (!text.trim()) return;
    setBusyId("domain-bulk");
    try {
      const result = await api.bulkCreateResearchDomains(text, domainNiche || null, domainSource || null);
      setImportResult(result);
      setDomainBulkText("");
      await loadDomains();
      setMessage(`${result.created} domains added, ${result.skipped} skipped`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import domains");
    } finally {
      setBusyId(null);
    }
  };

  const handleDomainFile = async (file: File | null) => {
    if (!file) return;
    const text = await file.text();
    await bulkAddDomains(text);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const saveDomainDraft = async (domain: ResearchDomain) => {
    const draft = domainDrafts[domain.id];
    if (!draft) return;
    setBusyId(domain.id);
    try {
      const updated = await api.updateResearchDomain(domain.id, {
        status: draft.status,
        reviewer_label: draft.reviewer_label || null,
        notes: draft.notes || null,
      });
      setDomains((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setMessage(`${updated.domain} updated`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update domain");
    } finally {
      setBusyId(null);
    }
  };

  const refreshWayback = async (domain: ResearchDomain) => {
    setBusyId(`wayback-${domain.id}`);
    try {
      const result = await api.refreshResearchDomainWayback(domain.id);
      setDomains((prev) => prev.map((item) => (item.id === result.domain.id ? result.domain : item)));
      setMessage(`${domain.domain} Wayback signals refreshed`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh Wayback signals");
    } finally {
      setBusyId(null);
    }
  };

  const createKeywordTask = async () => {
    const seeds = normalizeSeedKeywords(seedKeywords);
    if (!keywordNiche.trim() || seeds.length === 0) {
      setError("Niche and seed keywords are required");
      return;
    }
    setBusyId("keyword-add");
    try {
      const created = await api.createResearchKeywords({
        niche: keywordNiche,
        seed_keywords: seeds,
        target_country: targetCountry || "US",
        target_language: targetLanguage || "en",
      });
      setKeywords((prev) => [...created, ...prev.filter((item) => !created.some((createdItem) => createdItem.id === item.id))]);
      setSeedKeywords("");
      setMessage(`${created.length} keyword opportunities organized`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create keyword task");
    } finally {
      setBusyId(null);
    }
  };

  const updateKeyword = async (keyword: ResearchKeyword, patch: Partial<ResearchKeyword>) => {
    setBusyId(keyword.id);
    try {
      const updated = await api.updateResearchKeyword(keyword.id, patch);
      setKeywords((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update keyword");
    } finally {
      setBusyId(null);
    }
  };

  const createContentFromKeyword = async (keyword: ResearchKeyword) => {
    setBusyId(`content-${keyword.id}`);
    try {
      const created = await api.createContentOpportunity({
        keyword_id: keyword.id,
        niche: keyword.niche,
        keyword: keyword.keyword,
        article_type: keyword.article_type,
        priority: keyword.priority,
        monetization_type: keyword.monetization_type,
        state: "idea",
      });
      setContentIdeas((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      setMessage(`${keyword.keyword} added to content ideas`);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create content idea");
    } finally {
      setBusyId(null);
    }
  };

  const updateContentIdea = async (idea: ContentOpportunity, patch: Partial<ContentOpportunity>) => {
    setBusyId(idea.id);
    try {
      const updated = await api.updateContentOpportunity(idea.id, patch);
      setContentIdeas((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update content idea");
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading Research Center...</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-surface-0">
      <div className="border-b border-border bg-surface-1 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Research Center</h2>
            <p className="text-xs text-gray-500">
              {domains.length} domains · {keywords.length} keywords · {contentIdeas.length} content ideas
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-xs text-gray-400 border border-border rounded-md px-2 py-1 bg-surface-2">
              <DatabaseZap className="h-3.5 w-3.5" />
              Providers staged
            </span>
            <button className="btn-secondary flex items-center gap-1.5" onClick={refresh} title="Refresh Research Center">
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {([
            ["domains", "Domains", ShieldCheck],
            ["keywords", "Keywords", Tags],
            ["content", "Content Ideas", Lightbulb],
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              className={`btn-secondary flex items-center gap-1.5 ${tab === id ? "text-accent border border-accent/30" : ""}`}
              onClick={() => setTab(id)}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-sm flex items-center justify-between gap-3">
          <span>{error}</span>
          <button className="text-red-300 hover:text-red-200" onClick={() => setError("")} title="Dismiss error">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {message && !error && (
        <div className="px-4 py-2 bg-emerald-600/10 border-b border-emerald-600/25 text-emerald-300 text-sm flex items-center justify-between gap-3">
          <span>{message}</span>
          <button className="text-emerald-300 hover:text-emerald-200" onClick={() => setMessage("")} title="Dismiss message">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {tab === "domains" && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="border-b border-border bg-surface-1 px-4 py-3">
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(220px,1fr)_160px_160px_auto] gap-2">
              <input className="input" value={domainInput} onChange={(event) => setDomainInput(event.target.value)} placeholder="example.com" />
              <input className="input" value={domainNiche} onChange={(event) => setDomainNiche(event.target.value)} placeholder="niche" list="research-domain-niches" />
              <input className="input" value={domainSource} onChange={(event) => setDomainSource(event.target.value)} placeholder="source" />
              <button className="btn-primary flex items-center justify-center gap-1.5" onClick={addSingleDomain} disabled={busyId === "domain-add"}>
                <Plus className="h-3.5 w-3.5" />
                <span>Domain</span>
              </button>
            </div>
            <datalist id="research-domain-niches">
              {domainNiches.map((niche) => <option key={niche} value={niche} />)}
            </datalist>
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(260px,1fr)_auto_auto] gap-2 mt-2">
              <textarea
                className="input"
                rows={2}
                value={domainBulkText}
                onChange={(event) => setDomainBulkText(event.target.value)}
                placeholder="Bulk paste domains, one per line or first CSV column"
              />
              <button className="btn-secondary flex items-center justify-center gap-1.5" onClick={() => fileInputRef.current?.click()} title="Import TXT or CSV">
                <FileUp className="h-3.5 w-3.5" />
                <span>Import</span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.csv,text/plain,text/csv"
                className="hidden"
                onChange={(event) => handleDomainFile(event.target.files?.[0] ?? null)}
              />
              <button className="btn-primary flex items-center justify-center gap-1.5" onClick={() => bulkAddDomains()} disabled={busyId === "domain-bulk"}>
                <Save className="h-3.5 w-3.5" />
                <span>Bulk Add</span>
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[minmax(220px,1fr)_150px_130px_auto] gap-2 mt-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
                <input className="input pl-8" value={domainQuery} onChange={(event) => setDomainQuery(event.target.value)} placeholder="Search domain, niche, source, notes..." />
              </div>
              <select className="input" value={domainStatusFilter} onChange={(event) => setDomainStatusFilter(event.target.value as typeof domainStatusFilter)}>
                <option value="all">All statuses</option>
                {DOMAIN_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
              <input className="input" type="number" min="0" max="100" value={minScore} onChange={(event) => setMinScore(event.target.value)} placeholder="min score" />
              <button className="btn-secondary" onClick={loadDomains}>Apply</button>
            </div>
          </div>

          {importResult && (
            <div className="px-4 py-2 border-b border-border bg-surface-1 text-sm text-gray-300">
              Import: {importResult.created} created, {importResult.skipped} skipped, {importResult.rejected} rejected
              {importResult.errors.slice(0, 3).map((item) => (
                <span key={`${item.row}-${item.detail}`} className="ml-3 text-amber-300">Row {item.row}: {item.detail}</span>
              ))}
            </div>
          )}

          <div className="flex-1 overflow-auto">
            <table className="w-full min-w-[1280px] text-sm">
              <thead className="sticky top-0 z-10 bg-surface-1 border-b border-border">
                <tr className="text-left text-xs text-gray-500">
                  <th className="px-3 py-2 font-medium w-[210px]">Domain</th>
                  <th className="px-3 py-2 font-medium w-[90px]">Score</th>
                  <th className="px-3 py-2 font-medium w-[120px]">Status</th>
                  <th className="px-3 py-2 font-medium w-[110px]">Label</th>
                  <th className="px-3 py-2 font-medium w-[130px]">Niche</th>
                  <th className="px-3 py-2 font-medium w-[130px]">Source</th>
                  <th className="px-3 py-2 font-medium w-[220px]">Wayback</th>
                  <th className="px-3 py-2 font-medium w-[260px]">Notes</th>
                  <th className="px-3 py-2 font-medium w-[170px]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {domains.length === 0 && (
                  <tr><td className="px-3 py-10 text-center text-gray-500" colSpan={9}>No domains match the current filters</td></tr>
                )}
                {domains.map((domain) => {
                  const draft = domainDrafts[domain.id] ?? {
                    status: domain.status,
                    reviewer_label: domain.reviewer_label ?? "",
                    notes: domain.notes ?? "",
                  };
                  return (
                    <tr key={domain.id} className="border-b border-border/60 hover:bg-surface-1/60">
                      <td className="px-3 py-2 align-top">
                        <div className="font-medium text-gray-100">{domain.domain}</div>
                        <div className="text-xs text-gray-500">{labelText(domain.classification)}</div>
                      </td>
                      <td className={`px-3 py-2 align-top font-semibold ${scoreClass(domain.score)}`}>{domain.score}</td>
                      <td className="px-3 py-2 align-top">
                        <select
                          className="input h-8"
                          value={draft.status}
                          onChange={(event) => setDomainDrafts((prev) => ({
                            ...prev,
                            [domain.id]: { ...draft, status: event.target.value as DomainClassification },
                          }))}
                        >
                          {DOMAIN_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2 align-top">
                        <select
                          className="input h-8"
                          value={draft.reviewer_label}
                          onChange={(event) => setDomainDrafts((prev) => ({
                            ...prev,
                            [domain.id]: { ...draft, reviewer_label: event.target.value as DomainReviewLabel | "" },
                          }))}
                        >
                          <option value="">-</option>
                          {REVIEW_LABELS.map((label) => <option key={label} value={label}>{label}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2 align-top text-gray-400">{domain.niche ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-gray-400">{domain.source ?? "-"}</td>
                      <td className="px-3 py-2 align-top text-xs text-gray-400">
                        <div>{domain.wayback_history_exists ? `${domain.wayback_snapshot_count} snapshots` : "No signal"}</div>
                        <div>{domain.wayback_snapshot_span_days ? `${domain.wayback_snapshot_span_days} days span` : "span -"}</div>
                        {domain.wayback_high_risk_terms.length > 0 && (
                          <div className="text-red-300 truncate" title={domain.wayback_high_risk_terms.join(", ")}>
                            {domain.wayback_high_risk_terms.join(", ")}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <input
                          className="input h-8"
                          value={draft.notes}
                          onChange={(event) => setDomainDrafts((prev) => ({
                            ...prev,
                            [domain.id]: { ...draft, notes: event.target.value },
                          }))}
                          placeholder="review notes"
                        />
                      </td>
                      <td className="px-3 py-2 align-top">
                        <div className="flex items-center gap-1.5">
                          <button className="btn-secondary px-2" onClick={() => refreshWayback(domain)} disabled={busyId === `wayback-${domain.id}`} title="Refresh Wayback">
                            <RefreshCw className="h-3.5 w-3.5" />
                          </button>
                          <button className="btn-primary px-2" onClick={() => saveDomainDraft(domain)} disabled={busyId === domain.id} title="Save review">
                            <Save className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "keywords" && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="border-b border-border bg-surface-1 px-4 py-3">
            <div className="grid grid-cols-1 lg:grid-cols-[190px_100px_100px_minmax(260px,1fr)_auto] gap-2">
              <input className="input" value={keywordNiche} onChange={(event) => setKeywordNiche(event.target.value)} placeholder="niche" />
              <input className="input" value={targetCountry} onChange={(event) => setTargetCountry(event.target.value)} placeholder="US" />
              <input className="input" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)} placeholder="en" />
              <textarea className="input" rows={2} value={seedKeywords} onChange={(event) => setSeedKeywords(event.target.value)} placeholder="Seed keywords, one per line" />
              <button className="btn-primary flex items-center justify-center gap-1.5" onClick={createKeywordTask} disabled={busyId === "keyword-add"}>
                <Plus className="h-3.5 w-3.5" />
                <span>Task</span>
              </button>
            </div>
            <div className="relative mt-3">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
              <input className="input pl-8" value={keywordQuery} onChange={(event) => setKeywordQuery(event.target.value)} placeholder="Search keywords, niche, notes..." />
            </div>
          </div>
          <div className="flex-1 overflow-auto">
            <table className="w-full min-w-[1180px] text-sm">
              <thead className="sticky top-0 z-10 bg-surface-1 border-b border-border">
                <tr className="text-left text-xs text-gray-500">
                  <th className="px-3 py-2 font-medium w-[250px]">Keyword</th>
                  <th className="px-3 py-2 font-medium w-[130px]">Niche</th>
                  <th className="px-3 py-2 font-medium w-[150px]">Intent</th>
                  <th className="px-3 py-2 font-medium w-[150px]">Article Type</th>
                  <th className="px-3 py-2 font-medium w-[120px]">Priority</th>
                  <th className="px-3 py-2 font-medium w-[150px]">Monetization</th>
                  <th className="px-3 py-2 font-medium w-[140px]">Market</th>
                  <th className="px-3 py-2 font-medium w-[120px]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {keywords.length === 0 && (
                  <tr><td className="px-3 py-10 text-center text-gray-500" colSpan={8}>No keyword opportunities yet</td></tr>
                )}
                {keywords.map((keyword) => (
                  <tr key={keyword.id} className="border-b border-border/60 hover:bg-surface-1/60">
                    <td className="px-3 py-2 align-top text-gray-100 font-medium">{keyword.keyword}</td>
                    <td className="px-3 py-2 align-top text-gray-400">{keyword.niche}</td>
                    <td className="px-3 py-2 align-top">
                      <select className="input h-8" value={keyword.intent} onChange={(event) => updateKeyword(keyword, { intent: event.target.value as ResearchKeyword["intent"] })}>
                        {INTENTS.map((intent) => <option key={intent} value={intent}>{intent}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <select className="input h-8" value={keyword.article_type} onChange={(event) => updateKeyword(keyword, { article_type: event.target.value as ArticleType })}>
                        {ARTICLE_TYPES.map((type) => <option key={type} value={type}>{labelText(type)}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <select className="input h-8" value={keyword.priority} onChange={(event) => updateKeyword(keyword, { priority: event.target.value as OpportunityPriority })}>
                        {PRIORITIES.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <select className="input h-8" value={keyword.monetization_type} onChange={(event) => updateKeyword(keyword, { monetization_type: event.target.value as MonetizationType })}>
                        {MONETIZATION_TYPES.map((type) => <option key={type} value={type}>{labelText(type)}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2 align-top text-gray-400">{keyword.target_country} · {keyword.target_language}</td>
                    <td className="px-3 py-2 align-top">
                      <button className="btn-primary px-2" onClick={() => createContentFromKeyword(keyword)} disabled={busyId === `content-${keyword.id}`} title="Create content idea">
                        <Lightbulb className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "content" && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="border-b border-border bg-surface-1 px-4 py-3">
            <div className="grid grid-cols-1 md:grid-cols-[minmax(220px,1fr)_160px_auto] gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
                <input className="input pl-8" value={contentQuery} onChange={(event) => setContentQuery(event.target.value)} placeholder="Search content ideas..." />
              </div>
              <select className="input" value={contentStateFilter} onChange={(event) => setContentStateFilter(event.target.value as typeof contentStateFilter)}>
                <option value="all">All states</option>
                {CONTENT_STATES.map((state) => <option key={state} value={state}>{state}</option>)}
              </select>
              <button className="btn-secondary" onClick={loadContentIdeas}>Apply</button>
            </div>
          </div>
          <div className="flex-1 overflow-auto">
            <table className="w-full min-w-[1040px] text-sm">
              <thead className="sticky top-0 z-10 bg-surface-1 border-b border-border">
                <tr className="text-left text-xs text-gray-500">
                  <th className="px-3 py-2 font-medium w-[280px]">Keyword</th>
                  <th className="px-3 py-2 font-medium w-[140px]">Niche</th>
                  <th className="px-3 py-2 font-medium w-[150px]">Article Type</th>
                  <th className="px-3 py-2 font-medium w-[120px]">Priority</th>
                  <th className="px-3 py-2 font-medium w-[150px]">Monetization</th>
                  <th className="px-3 py-2 font-medium w-[140px]">State</th>
                  <th className="px-3 py-2 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody>
                {contentIdeas.length === 0 && (
                  <tr><td className="px-3 py-10 text-center text-gray-500" colSpan={7}>No content ideas yet</td></tr>
                )}
                {contentIdeas.map((idea) => (
                  <tr key={idea.id} className="border-b border-border/60 hover:bg-surface-1/60">
                    <td className="px-3 py-2 align-top text-gray-100 font-medium">{idea.keyword}</td>
                    <td className="px-3 py-2 align-top text-gray-400">{idea.niche ?? "-"}</td>
                    <td className="px-3 py-2 align-top text-gray-400">{labelText(idea.article_type)}</td>
                    <td className="px-3 py-2 align-top">
                      <span className={`inline-flex border text-xs px-2 py-0.5 rounded-full ${statusClass(idea.priority)}`}>
                        {idea.priority}
                      </span>
                    </td>
                    <td className="px-3 py-2 align-top text-gray-400">{labelText(idea.monetization_type)}</td>
                    <td className="px-3 py-2 align-top">
                      <select className="input h-8" value={idea.state} onChange={(event) => updateContentIdea(idea, { state: event.target.value as ContentState })}>
                        {CONTENT_STATES.map((state) => <option key={state} value={state}>{state}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2 align-top text-gray-400 truncate" title={idea.notes ?? ""}>{idea.notes ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
