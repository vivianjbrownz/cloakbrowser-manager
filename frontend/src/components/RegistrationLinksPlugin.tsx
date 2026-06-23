import { Check, Clipboard, ExternalLink, Search, UserPlus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type Profile } from "../lib/api";

export interface RegistrationPlatform {
  id: string;
  name: string;
  category: string;
  url: string;
}

export const REGISTRATION_PLATFORMS: RegistrationPlatform[] = [
  { id: "reddit", name: "Reddit", category: "Community", url: "https://www.reddit.com/register/" },
  { id: "facebook", name: "Facebook", category: "Social", url: "https://www.facebook.com/r.php" },
  { id: "instagram", name: "Instagram", category: "Social", url: "https://www.instagram.com/accounts/emailsignup/" },
  { id: "x", name: "X", category: "Social", url: "https://x.com/i/flow/signup" },
  { id: "tiktok", name: "TikTok", category: "Video", url: "https://www.tiktok.com/signup" },
  { id: "linkedin", name: "LinkedIn", category: "Professional", url: "https://www.linkedin.com/signup" },
  { id: "pinterest", name: "Pinterest", category: "Discovery", url: "https://www.pinterest.com/" },
  { id: "discord", name: "Discord", category: "Community", url: "https://discord.com/register" },
  { id: "twitch", name: "Twitch", category: "Video", url: "https://www.twitch.tv/signup" },
  { id: "snapchat", name: "Snapchat", category: "Social", url: "https://accounts.snapchat.com/accounts/v2/signup" },
  { id: "youtube", name: "YouTube / Google", category: "Video", url: "https://accounts.google.com/signup" },
];

interface RegistrationLinksPluginProps {
  profiles: Profile[];
  onOpenProfile: (id: string) => void;
}

export function RegistrationLinksPlugin({ profiles, onOpenProfile }: RegistrationLinksPluginProps) {
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(REGISTRATION_PLATFORMS.map((platform) => platform.id)),
  );
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState("");

  const runningProfiles = useMemo(
    () => profiles.filter((profile) => profile.status === "running" && !profile.is_archived),
    [profiles],
  );

  useEffect(() => {
    if (runningProfiles.length === 0) {
      setSelectedProfileId("");
      return;
    }
    if (!runningProfiles.some((profile) => profile.id === selectedProfileId)) {
      setSelectedProfileId(runningProfiles[0]?.id ?? "");
    }
  }, [runningProfiles, selectedProfileId]);

  const filteredPlatforms = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return REGISTRATION_PLATFORMS;
    return REGISTRATION_PLATFORMS.filter((platform) =>
      [platform.name, platform.category, platform.url].join(" ").toLowerCase().includes(term),
    );
  }, [query]);

  const selectedCount = selectedIds.size;
  const selectedProfile = runningProfiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const selectedProfileHint = selectedProfile ? selectedProfile.name : "Launch a profile first";
  const openSelectedDisabled = selectedCount === 0 || !selectedProfile || openingId !== null;

  const togglePlatform = (platformId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(platformId)) {
        next.delete(platformId);
      } else {
        next.add(platformId);
      }
      return next;
    });
  };

  const selectVisible = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const platform of filteredPlatforms) next.add(platform.id);
      return next;
    });
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  const openProfileViewer = () => {
    if (selectedProfile) onOpenProfile(selectedProfile.id);
  };

  const openInProfile = async (platform: RegistrationPlatform) => {
    if (!selectedProfile) {
      setError("Launch a profile first, then open the registration page in that profile.");
      setStatusMessage("");
      return;
    }

    setOpeningId(platform.id);
    setError("");
    try {
      await api.openProfileUrl(selectedProfile.id, platform.url);
      setStatusMessage(`${platform.name} opened in ${selectedProfile.name}`);
      onOpenProfile(selectedProfile.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open URL in profile");
    } finally {
      setOpeningId(null);
    }
  };

  const openSelected = async () => {
    if (!selectedProfile) {
      setError("Launch a profile first, then open the selected pages in that profile.");
      setStatusMessage("");
      return;
    }

    const platforms = REGISTRATION_PLATFORMS.filter((platform) => selectedIds.has(platform.id));
    setOpeningId("selected");
    setError("");
    try {
      for (const platform of platforms) {
        await api.openProfileUrl(selectedProfile.id, platform.url);
      }
      setStatusMessage(`${platforms.length} pages opened in ${selectedProfile.name}`);
      onOpenProfile(selectedProfile.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open selected URLs in profile");
    } finally {
      setOpeningId(null);
    }
  };

  const copyUrl = async (platform: RegistrationPlatform) => {
    await navigator.clipboard.writeText(platform.url);
    setCopiedId(platform.id);
  };

  return (
    <div className="h-full flex flex-col bg-surface-0">
      <div className="border-b border-border bg-surface-1 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Registration Links</h2>
            <p className="text-xs text-gray-500">{selectedCount} selected / {REGISTRATION_PLATFORMS.length} platforms · {selectedProfileHint}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="input w-[260px]"
                value={selectedProfileId}
                onChange={(event) => setSelectedProfileId(event.target.value)}
                disabled={runningProfiles.length === 0}
                title="Target running profile"
              >
                {runningProfiles.length === 0 ? (
                  <option value="">No running profile</option>
                ) : (
                  runningProfiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>{profile.name}</option>
                  ))
                )}
              </select>
              <button
                className="btn-secondary"
                onClick={openProfileViewer}
                disabled={!selectedProfile}
                title="Open selected profile viewer"
              >
                Viewer
              </button>
            </div>
            <button className="btn-secondary flex items-center gap-1.5" onClick={selectVisible} title="Select visible platforms">
              <Check className="h-3.5 w-3.5" />
              <span>Select</span>
            </button>
            <button className="btn-secondary" onClick={clearSelection} title="Clear selection">
              Clear
            </button>
            <button className="btn-primary flex items-center gap-1.5" onClick={() => void openSelected()} disabled={openSelectedDisabled} title="Open selected registration pages in the selected running profile">
              <ExternalLink className="h-3.5 w-3.5" />
              <span>{openingId === "selected" ? "Opening..." : "Open Selected in Profile"}</span>
            </button>
          </div>
        </div>
        <div className="relative mt-3 max-w-xl">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
          <input
            className="input pl-8"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search platform..."
          />
        </div>
      </div>

      {(error || statusMessage) && (
        <div className={`px-4 py-2 border-b text-sm ${error ? "bg-red-600/15 border-red-600/30 text-red-400" : "bg-emerald-600/10 border-emerald-600/25 text-emerald-300"}`}>
          {error || statusMessage}
        </div>
      )}

      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filteredPlatforms.map((platform) => {
            const checked = selectedIds.has(platform.id);
            const copied = copiedId === platform.id;
            const opening = openingId === platform.id;
            return (
              <div key={platform.id} className="rounded-md border border-border bg-surface-1 p-3">
                <div className="flex items-start justify-between gap-3">
                  <label className="min-w-0 flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => togglePlatform(platform.id)}
                      aria-label={`Select ${platform.name}`}
                    />
                    <span className="font-medium text-gray-100 truncate">{platform.name}</span>
                  </label>
                  <span className="flex-shrink-0 text-[10px] uppercase tracking-wide text-gray-500 border border-border rounded-full px-2 py-0.5">
                    {platform.category}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-500 truncate" title={platform.url}>
                  {platform.url}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    className="btn-secondary flex items-center gap-1.5"
                    onClick={() => void openInProfile(platform)}
                    disabled={!selectedProfile || openingId !== null}
                    title={`Open ${platform.name} registration in selected profile`}
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    <span>{opening ? "Opening..." : "Open in Profile"}</span>
                  </button>
                  <button
                    className="btn-secondary flex items-center gap-1.5"
                    onClick={() => void copyUrl(platform)}
                    title={`Copy ${platform.name} registration URL`}
                  >
                    <Clipboard className="h-3.5 w-3.5" />
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </button>
                </div>
              </div>
            );
          })}

          {filteredPlatforms.length === 0 && (
            <div className="col-span-full flex h-40 items-center justify-center rounded-md border border-border bg-surface-1 text-sm text-gray-500">
              No platforms match the current search
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function RegistrationLinksIcon() {
  return <UserPlus className="h-4 w-4" />;
}
