import { useEffect, useRef, useState } from "react";
import { ClipboardCopy, Code2, Gauge, Maximize2, Minimize2 } from "lucide-react";
import { api } from "../lib/api";

interface ProfileViewerProps {
  profileId: string;
  cdpUrl: string | null;
  clipboardSync: boolean;
  onDisconnect: () => void;
}

// X11 keysym for V key (Ctrl is already held in VNC by the time we intercept)
const XK_v = 0x0076;
const VIEWER_MODE_STORAGE_KEY = "cloakbrowser.viewer.qualityMode";

type ViewerQualityMode = "fast" | "balanced" | "sharp";

const VIEWER_QUALITY_MODES: Record<
  ViewerQualityMode,
  { label: string; qualityLevel: number; compressionLevel: number }
> = {
  fast: { label: "Fast", qualityLevel: 4, compressionLevel: 7 },
  balanced: { label: "Balanced", qualityLevel: 6, compressionLevel: 5 },
  sharp: { label: "Sharp", qualityLevel: 9, compressionLevel: 2 },
};

function loadViewerQualityMode(): ViewerQualityMode {
  try {
    const saved = window.localStorage.getItem(VIEWER_MODE_STORAGE_KEY);
    if (saved === "fast" || saved === "balanced" || saved === "sharp") {
      return saved;
    }
  } catch (err) {
    console.debug("[vnc] failed to load viewer quality mode:", err);
  }
  return "fast";
}

function saveViewerQualityMode(mode: ViewerQualityMode) {
  try {
    window.localStorage.setItem(VIEWER_MODE_STORAGE_KEY, mode);
  } catch (err) {
    console.debug("[vnc] failed to save viewer quality mode:", err);
  }
}

function applyViewerQualityMode(rfb: any, mode: ViewerQualityMode) {
  const preset = VIEWER_QUALITY_MODES[mode];
  rfb.qualityLevel = preset.qualityLevel;
  rfb.compressionLevel = preset.compressionLevel;
}

export function ProfileViewer({ profileId, cdpUrl, clipboardSync: initialClipboardSync, onDisconnect }: ProfileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<any>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [clipboardSync, setClipboardSync] = useState(initialClipboardSync);
  const [cdpCopied, setCdpCopied] = useState(false);
  const [viewerMode, setViewerMode] = useState<ViewerQualityMode>(loadViewerQualityMode);

  useEffect(() => {
    let rfb: any = null;
    let cancelled = false;

    async function connect() {
      try {
        // Import noVNC dynamically
        const { default: RFB } = await import("@novnc/novnc/core/rfb.js");

        if (cancelled) return;

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/api/profiles/${profileId}/vnc`;

        rfb = new RFB(containerRef.current!, wsUrl, {
          wsProtocols: ["binary"],
        });
        rfbRef.current = rfb;

        rfb.scaleViewport = true;
        rfb.resizeSession = false;
        rfb.showDotCursor = true;
        applyViewerQualityMode(rfb, viewerMode);

        rfb.addEventListener("connect", () => {
          if (!cancelled) setConnected(true);
        });

        rfb.addEventListener("disconnect", () => {
          if (!cancelled) {
            setConnected(false);
            onDisconnect();
          }
        });

        rfb.addEventListener("securityfailure", (e: any) => {
          setError(`Security failure: ${e.detail.reason}`);
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to connect");
        }
      }
    }

    connect();

    return () => {
      cancelled = true;
      if (rfb) {
        try {
          rfb.disconnect();
        } catch (err) {
          console.debug("[vnc] disconnect cleanup failed:", err);
        }
      }
      rfbRef.current = null;
    };
  }, [profileId, onDisconnect]);

  const selectViewerMode = (mode: ViewerQualityMode) => {
    setViewerMode(mode);
    saveViewerQualityMode(mode);
    if (rfbRef.current) {
      applyViewerQualityMode(rfbRef.current, mode);
    }
  };

  const sendPasteKeys = () => {
    const rfb = rfbRef.current;
    if (!rfb) return;
    // Send the full Ctrl+V sequence because the host key state can change
    // while the async clipboard API call is in flight.
    rfb.sendKey(0xffe3, "ControlLeft", true);
    rfb.sendKey(XK_v, "KeyV", true);
    rfb.sendKey(XK_v, "KeyV", false);
    rfb.sendKey(0xffe3, "ControlLeft", false);
  };

  // Host→VNC: intercept Ctrl+V/Cmd+V at keydown (capture phase)
  // Must fire BEFORE noVNC's canvas listener to prevent the race condition
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !connected) return;

    const handleKeyDown = async (e: KeyboardEvent) => {
      const isPaste =
        e.key === "v" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey;
      if (!isPaste) return;

      // Block noVNC from sending the keystroke before clipboard is updated
      e.stopPropagation();
      e.preventDefault();

      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          await api.setClipboard(profileId, text);
        }
      } catch (err) {
        console.warn("[clipboard] one-time paste failed:", err);
      }

      sendPasteKeys();
    };

    // capture: true ensures we fire before noVNC's canvas listener
    container.addEventListener("keydown", handleKeyDown, true);
    return () => container.removeEventListener("keydown", handleKeyDown, true);
  }, [profileId, connected]);

  // VNC→Host: listen for noVNC "clipboard" event (fired when proxy converts
  // KasmVNC BinaryClipboard type 180 → standard ServerCutText type 3)
  useEffect(() => {
    const rfb = rfbRef.current;
    if (!rfb || !clipboardSync || !connected) return;

    const handleClipboard = (e: any) => {
      const text = e.detail?.text;
      if (text) {
        navigator.clipboard.writeText(text).catch((err) => {
          console.warn("[clipboard] writeText failed:", err);
        });
      }
    };

    rfb.addEventListener("clipboard", handleClipboard);
    return () => {
      rfb.removeEventListener("clipboard", handleClipboard);
    };
  }, [clipboardSync, connected]);

  // VNC→Host polling: Chrome doesn't write to X11 clipboard under KasmVNC,
  // so type 180 events won't fire for Chrome copies. Poll via Playwright CDP.
  useEffect(() => {
    if (!clipboardSync || !connected) return;

    let cancelled = false;
    let lastText = "";

    const poll = async () => {
      if (cancelled) return;
      try {
        const { text } = await api.getClipboard(profileId);
        if (text && text !== lastText) {
          lastText = text;
          await navigator.clipboard.writeText(text).catch((err) =>
            console.warn("[clipboard] poll writeText failed:", err)
          );
        }
      } catch (err) {
        console.warn("[clipboard] poll error, stopping:", err);
        cancelled = true;
        return;
      }
      if (!cancelled) {
        setTimeout(poll, 2000);
      }
    };

    // Start polling after a short delay
    const timer = setTimeout(poll, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [profileId, clipboardSync, connected]);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setFullscreen(true);
    } else {
      document.exitFullscreen();
      setFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFsChange = () => {
      setFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
    };

    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, []);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Connection failed</p>
          <p className="text-gray-500 text-xs">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-1 border-b border-border">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-yellow-400 animate-pulse"}`} />
          <span className="text-xs text-gray-400">
            {connected ? "Connected" : "Connecting..."}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <div className="flex items-center gap-1 mr-1" title="Viewer quality">
            <Gauge className="h-3.5 w-3.5 text-gray-500" />
            <div className="flex overflow-hidden rounded border border-border">
              {(Object.keys(VIEWER_QUALITY_MODES) as ViewerQualityMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => selectViewerMode(mode)}
                  className={`px-2 py-1 text-[11px] leading-none ${
                    viewerMode === mode
                      ? "bg-accent text-white"
                      : "bg-surface-2 text-gray-400 hover:text-gray-200"
                  }`}
                  title={`${VIEWER_QUALITY_MODES[mode].label} viewer mode`}
                >
                  {VIEWER_QUALITY_MODES[mode].label}
                </button>
              ))}
            </div>
          </div>
          {cdpUrl && (
            <button
              onClick={() => {
                const base = `${window.location.protocol}//${window.location.host}${cdpUrl}`;
                navigator.clipboard?.writeText(base).then(() => {
                  setCdpCopied(true);
                  setTimeout(() => setCdpCopied(false), 2000);
                }).catch((err) => console.warn("[cdp] copy failed:", err));
              }}
              className={`p-1 ${cdpCopied ? "text-emerald-400" : "text-gray-500 hover:text-gray-300"}`}
              title={cdpCopied ? "Copied!" : "Copy CDP endpoint URL"}
            >
              <Code2 className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            onClick={() => setClipboardSync(!clipboardSync)}
            className={`p-1 ${clipboardSync ? "text-accent" : "text-gray-500 hover:text-gray-300"}`}
            title={clipboardSync ? "Disable continuous clipboard sync" : "Enable continuous clipboard sync"}
            disabled={!connected}
          >
            <ClipboardCopy className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="text-gray-500 hover:text-gray-300 p-1"
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* VNC canvas container */}
      <div
        ref={containerRef}
        data-testid="vnc-canvas-container"
        className="flex-1 bg-black overflow-hidden"
        style={{ minHeight: 0 }}
      />
    </div>
  );
}
