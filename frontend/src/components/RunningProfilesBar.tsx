import { Loader2, Square } from "lucide-react";
import { useState } from "react";
import type { Profile } from "../lib/api";
import { StatusIndicator } from "./StatusIndicator";

interface RunningProfilesBarProps {
  profiles: Profile[];
  selectedId: string | null;
  onOpenProfile: (id: string) => void;
  onStopProfile: (id: string) => Promise<void>;
}

export function RunningProfilesBar({
  profiles,
  selectedId,
  onOpenProfile,
  onStopProfile,
}: RunningProfilesBarProps) {
  const [stoppingId, setStoppingId] = useState<string | null>(null);
  const runningProfiles = profiles.filter((profile) => profile.status === "running");

  if (runningProfiles.length === 0) return null;

  const stopProfile = async (profileId: string) => {
    setStoppingId(profileId);
    try {
      await onStopProfile(profileId);
    } finally {
      setStoppingId((current) => (current === profileId ? null : current));
    }
  };

  return (
    <div className="border-b border-border bg-surface-0 px-4 py-2">
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex flex-shrink-0 items-center gap-2 text-xs text-gray-400">
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.85)]" />
          <span className="font-medium text-gray-200">Running</span>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[11px] text-emerald-300">
            {runningProfiles.length}
          </span>
        </div>

        <div className="flex-1 overflow-x-auto">
          <div className="flex min-w-max items-center gap-2">
            {runningProfiles.map((profile) => {
              const isSelected = profile.id === selectedId;
              const isStopping = stoppingId === profile.id;

              return (
                <div
                  key={profile.id}
                  className={`flex h-9 max-w-[300px] items-center rounded-md border bg-surface-1 ${
                    isSelected ? "border-accent/70 ring-1 ring-accent/30" : "border-border"
                  }`}
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-1.5 text-left hover:text-accent"
                    onClick={() => onOpenProfile(profile.id)}
                    aria-current={isSelected ? "true" : undefined}
                    aria-label={`Open ${profile.name}`}
                    title="Open running profile"
                  >
                    <StatusIndicator status="running" />
                    <span className="truncate text-xs font-medium text-gray-100">{profile.name}</span>
                    <span className="flex-shrink-0 text-[11px] capitalize text-gray-500">{profile.platform}</span>
                  </button>
                  <button
                    type="button"
                    className="mr-1 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded text-gray-500 hover:bg-red-500/10 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={() => stopProfile(profile.id)}
                    disabled={isStopping}
                    aria-label={`Stop ${profile.name}`}
                    title="Stop profile"
                  >
                    {isStopping ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Square className="h-3.5 w-3.5" />}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
