import { Check, Copy, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface ProfileIdCopyProps {
  profileId: string;
  locale?: "en" | "zh";
  className?: string;
}

type CopyState = "idle" | "copied" | "error";

const labels = {
  en: {
    copy: "Copy full Profile ID",
    copied: "Copied",
    error: "Copy failed",
  },
  zh: {
    copy: "复制完整 Profile ID",
    copied: "已复制",
    error: "复制失败",
  },
};

export function ProfileIdCopy({ profileId, locale = "en", className = "" }: ProfileIdCopyProps) {
  const [state, setState] = useState<CopyState>("idle");
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const text = labels[locale];
  const shortId = profileId.slice(0, 8);

  useEffect(() => () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
  }, []);

  const copyProfileId = async () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable");
      await navigator.clipboard.writeText(profileId);
      setState("copied");
    } catch (error) {
      console.warn("[profile-id] copy failed:", error);
      setState("error");
    }
    resetTimer.current = setTimeout(() => setState("idle"), 2000);
  };

  const statusLabel = state === "copied" ? text.copied : state === "error" ? text.error : "";

  return (
    <div className={`inline-flex max-w-full items-center gap-1.5 ${className}`}>
      <code
        className="truncate rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[10px] text-gray-400"
        title={`Profile ID: ${profileId}`}
      >
        ID: {shortId}
      </code>
      <button
        type="button"
        onClick={() => void copyProfileId()}
        className={`inline-flex min-h-6 min-w-6 items-center justify-center gap-1 rounded px-1 text-[10px] transition-colors ${
          state === "copied"
            ? "text-emerald-400"
            : state === "error"
              ? "text-red-400"
              : "text-gray-500 hover:bg-surface-3 hover:text-gray-200"
        }`}
        aria-label={state === "idle" ? text.copy : statusLabel}
        title={state === "idle" ? text.copy : statusLabel}
      >
        {state === "copied" ? (
          <Check className="h-3.5 w-3.5" />
        ) : state === "error" ? (
          <TriangleAlert className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
        {statusLabel && <span aria-live="polite">{statusLabel}</span>}
      </button>
    </div>
  );
}
