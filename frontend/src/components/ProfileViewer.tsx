import { useEffect, useRef, useState } from "react";
import { ClipboardCopy, Code2, Gauge, Maximize2, Minimize2 } from "lucide-react";
import { api, ApiError, type ViewerImplementation } from "../lib/api";
import { createViewer, VIEWER_QUALITY_MODES, ViewerVersionError, type ViewerConnection, type ViewerQualityMode, type ViewerStreamMode, type ViewerStreamState } from "../lib/viewer";

interface ProfileViewerProps {
  profileId: string;
  cdpUrl: string | null;
  clipboardSync: boolean;
  onDisconnect: () => void;
  defaultImplementation?: ViewerImplementation;
}

// X11 keysym for V key (Ctrl is already held in VNC by the time we intercept)
const XK_v = 0x0076;
const VIEWER_MODE_STORAGE_KEY = "cloakbrowser.viewer.qualityMode";

const IMPLEMENTATION_STORAGE_KEY = "cloakbrowser.viewer.implementation";
const STREAM_STORAGE_KEY = "cloakbrowser.viewer.streamMode";
const RETRY_DELAYS = [1000, 2000, 4000, 8000, 8000];

function loadImplementation(fallback: ViewerImplementation): ViewerImplementation {
  try {
    const saved = localStorage.getItem(IMPLEMENTATION_STORAGE_KEY);
    if (saved === "kasm" || saved === "novnc") return saved;
  } catch { /* Storage may be disabled. */ }
  return fallback;
}

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

export function ProfileViewer({ profileId, cdpUrl, clipboardSync: initialClipboardSync, onDisconnect, defaultImplementation = "novnc" }: ProfileViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputScopeRef = useRef<HTMLDivElement>(null);
  const keyboardRef = useRef<HTMLTextAreaElement>(null);
  const connectionRef = useRef<ViewerConnection | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [clipboardSync, setClipboardSync] = useState(initialClipboardSync);
  const [cdpCopied, setCdpCopied] = useState(false);
  const [viewerMode, setViewerMode] = useState<ViewerQualityMode>(loadViewerQualityMode);
  const [implementation, setImplementation] = useState(() => loadImplementation(defaultImplementation));
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [reconnectKey, setReconnectKey] = useState(0);
  const qualityRef = useRef(viewerMode);
  const [streamState, setStreamState] = useState<ViewerStreamState>({ enabled: false, available: false, mode: "image" });
  const streamRef = useRef<ViewerStreamMode>("image");
  const onDisconnectRef = useRef(onDisconnect);
  onDisconnectRef.current = onDisconnect;

  useEffect(() => setClipboardSync(initialClipboardSync), [profileId, initialClipboardSync]);

  useEffect(() => {
    const controller = new AbortController();
    let connection: ViewerConnection | null = null;
    let detach = () => {};
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let connectTimer: ReturnType<typeof setTimeout> | undefined;
    let stableTimer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    setConnected(false);
    setError(null);
    setRetryAttempt(0);
    setStreamState({ enabled: false, available: false, mode: "image" });
    try { streamRef.current = localStorage.getItem(STREAM_STORAGE_KEY) === "h264" ? "h264" : "image"; } catch { streamRef.current = "image"; }

    function disposeConnection() {
      clearTimeout(connectTimer);
      clearTimeout(stableTimer);
      detach();
      const old = connection;
      connection = null;
      if (connectionRef.current === old) connectionRef.current = null;
      try { old?.rfb.disconnect(); } catch (err) {
        console.debug("[vnc] disconnect cleanup failed:", err);
      }
      old?.dispose?.();
    }

    function fail(message: string) {
      if (controller.signal.aborted) return;
      disposeConnection();
      setConnected(false);
      setError(message);
    }

    function retry() {
      if (controller.signal.aborted) return;
      disposeConnection();
      setConnected(false);
      const delay = RETRY_DELAYS[attempts++];
      if (delay === undefined) {
        fail("Unable to reconnect. Retry or select Compatibility mode.");
        return;
      }
      setRetryAttempt(attempts);
      retryTimer = setTimeout(() => void connect(true), delay);
    }

    async function connect(checkStatus = false) {
      try {
        if (checkStatus) {
          // This protected endpoint checks authentication AND Profile assignment.
          const status = await api.getProfileStatus(profileId, AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]));
          if (controller.signal.aborted) return;
          if (status.status !== "running") {
            fail("Profile stopped. Start it from the profile controls.");
            onDisconnectRef.current();
            return;
          }
        }
        if (controller.signal.aborted) return;
        const created = await createViewer(implementation, containerRef.current!, keyboardRef.current!, profileId, controller.signal, {
          streamMode: streamRef.current,
          onStreamState: (state) => { if (!controller.signal.aborted) setStreamState(state); },
        });
        if (!created) return;
        connection = created;
        connectionRef.current = created;
        created.applyQuality(qualityRef.current);
        const handleConnect = () => {
          if (controller.signal.aborted || connection !== created) return;
          clearTimeout(connectTimer);
          setConnected(true);
          setRetryAttempt(0);
          // A flapping connection must not reset the bounded retry budget.
          stableTimer = setTimeout(() => { attempts = 0; }, 30000);
        };
        const handleDisconnect = () => {
          if (connection !== created) return;
          retry();
          onDisconnectRef.current();
        };
        const handleSecurity = () => fail("Viewer access denied. Sign in again or select Compatibility mode.");
        const handleEncodingFailure = () => {
          streamRef.current = "image";
          retry();
        };
        const listeners: Array<[string, () => void]> = [
          ["connect", handleConnect], ["disconnect", handleDisconnect],
          ["securityfailure", handleSecurity], ["credentialsrequired", handleSecurity],
          ["badencoding", handleEncodingFailure],
          ["imagemode", () => { streamRef.current = "image"; }],
        ];
        for (const [type, listener] of listeners) created.rfb.addEventListener(type, listener);
        detach = () => {
          for (const [type, listener] of listeners) created.rfb.removeEventListener(type, listener);
        };
        connectTimer = setTimeout(retry, 12000);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ViewerVersionError) {
          fail(err.message);
        } else if (err instanceof ApiError && [401, 403, 404].includes(err.status)) {
          fail(err.status === 404 ? "Profile no longer exists." : "Access expired or this Profile is no longer assigned to you.");
        } else {
          retry();
        }
      }
    }

    void connect();
    return () => {
      controller.abort();
      clearTimeout(retryTimer);
      disposeConnection();
    };
  }, [profileId, implementation, reconnectKey]);

  const selectViewerMode = (mode: ViewerQualityMode) => {
    setViewerMode(mode);
    qualityRef.current = mode;
    saveViewerQualityMode(mode);
    connectionRef.current?.applyQuality(mode);
  };

  const selectImplementation = (value: ViewerImplementation) => {
    try { localStorage.setItem(IMPLEMENTATION_STORAGE_KEY, value); } catch { /* Optional preference. */ }
    setImplementation(value);
  };

  const sendPasteKeys = (connection: ViewerConnection) => {
    const rfb = connection.rfb;
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
    const container = inputScopeRef.current;
    if (!container || !connected) return;
    let cancelled = false;
    let pasting = false;

    const handleKeyDown = async (e: KeyboardEvent) => {
      const isPaste =
        e.key.toLowerCase() === "v" && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey;
      if (!isPaste) return;

      // Block noVNC from sending the keystroke before clipboard is updated
      e.stopPropagation();
      e.preventDefault();
      if (pasting || e.repeat) return;
      const connection = connectionRef.current;
      if (!connection) return;
      pasting = true;
      let writingClipboard = false;

      try {
        const text = await navigator.clipboard.readText();
        if (cancelled || connectionRef.current !== connection) return;
        if (text) {
          writingClipboard = true;
          await api.setClipboard(profileId, text);
        }
      } catch (err) {
        console.warn("[clipboard] one-time paste failed:", err);
        if (writingClipboard) {
          pasting = false;
          if (!cancelled) setError("Could not update the remote clipboard. Try pasting again.");
          return;
        }
      }

      if (!cancelled && connectionRef.current === connection) sendPasteKeys(connection);
      pasting = false;
    };

    // capture: true ensures we fire before noVNC's canvas listener
    container.addEventListener("keydown", handleKeyDown, true);
    return () => {
      cancelled = true;
      container.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [profileId, connected, implementation]);

  // VNC→Host: listen for noVNC "clipboard" event (fired when proxy converts
  // KasmVNC BinaryClipboard type 180 → standard ServerCutText type 3)
  useEffect(() => {
    const rfb = connectionRef.current?.rfb;
    if (!rfb || !clipboardSync || !connected || implementation !== "novnc") return;

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
  }, [clipboardSync, connected, implementation]);

  // VNC→Host polling: Chrome doesn't write to X11 clipboard under KasmVNC,
  // so type 180 events won't fire for Chrome copies. Poll via Playwright CDP.
  useEffect(() => {
    if (!clipboardSync || !connected) return;

    let cancelled = false;
    let lastText = "";
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (cancelled) return;
      try {
        const { text } = await api.getClipboard(profileId);
        if (cancelled) return;
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
        timer = setTimeout(poll, 2000);
      }
    };

    // Start polling after a short delay
    timer = setTimeout(poll, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [profileId, clipboardSync, connected]);

  const toggleFullscreen = () => {
    if (!inputScopeRef.current) return;
    if (!document.fullscreenElement) {
      inputScopeRef.current.requestFullscreen().catch(() => setError("Fullscreen is unavailable in this browser."));
    } else {
      void document.exitFullscreen();
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

  return (
    <div className="relative h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-surface-1 border-b border-border">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : error ? "bg-red-400" : "bg-yellow-400"}`} />
          <span className="text-xs text-gray-400" role="status">
            {connected ? "Connected" : error ? "Disconnected" : retryAttempt ? `Reconnecting (${retryAttempt}/5)…` : "Connecting..."}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <select
            aria-label="Viewer client"
            value={implementation}
            onChange={(event) => selectImplementation(event.target.value as ViewerImplementation)}
            className="rounded border border-border bg-surface-2 px-2 py-1 text-xs text-gray-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <option value="kasm">KasmVNC</option>
            <option value="novnc">Compatibility</option>
          </select>
          {implementation === "kasm" && streamState.enabled && (
            <select
              aria-label="Stream mode"
              value={streamState.mode}
              onChange={(event) => {
                const mode = event.target.value as ViewerStreamMode;
                streamRef.current = mode;
                try { localStorage.setItem(STREAM_STORAGE_KEY, mode); } catch { /* Optional preference. */ }
                connectionRef.current?.applyStream?.(mode);
              }}
              className="rounded border border-border bg-surface-2 px-2 py-1 text-xs text-gray-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              <option value="image">Image mode</option>
              <option value="h264" disabled={!streamState.available}>Smooth video</option>
            </select>
          )}
          <div className="flex items-center gap-1 mr-1" title="Viewer quality">
            <Gauge className="h-3.5 w-3.5 text-gray-500" />
            <div className="flex overflow-hidden rounded border border-border">
              {(Object.keys(VIEWER_QUALITY_MODES) as ViewerQualityMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => selectViewerMode(mode)}
                  aria-pressed={viewerMode === mode}
                  className={`px-2 py-1 text-[11px] leading-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
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

      {streamState.message && implementation === "kasm" && (
        <p role="status" className="px-3 py-1 text-xs text-gray-400">{streamState.message}</p>
      )}
      {error && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-1 px-3 py-2">
          <p role="alert" className="text-sm text-gray-300">{error}</p>
          <button type="button" className="btn-secondary" onClick={() => setReconnectKey((key) => key + 1)}>Reconnect</button>
        </div>
      )}

      {/* VNC canvas container */}
      <div ref={inputScopeRef} className="relative flex-1 min-h-0 bg-black overflow-hidden">
        <div ref={containerRef} data-testid="vnc-canvas-container" className="absolute inset-0" />
        <textarea
          ref={keyboardRef}
          aria-label="Remote browser keyboard"
          className="sr-only"
          tabIndex={-1}
          autoCapitalize="off"
          autoComplete="off"
          spellCheck={false}
        />
      </div>
    </div>
  );
}
