import type RFB from "@novnc/novnc/core/rfb.js";
import { api, type ViewerImplementation } from "./api";
import { supportsH264 } from "./kasmVideo";

export type ViewerQualityMode = "fast" | "balanced" | "sharp";
export type ViewerStreamMode = "image" | "h264";
export interface ViewerStreamState {
  enabled: boolean;
  available: boolean;
  mode: ViewerStreamMode;
  message?: string;
}
export class ViewerVersionError extends Error {}
export const VIEWER_QUALITY_MODES = {
  fast: { label: "Fast", qualityLevel: 4, compressionLevel: 7 },
  balanced: { label: "Balanced", qualityLevel: 6, compressionLevel: 5 },
  sharp: { label: "Sharp", qualityLevel: 9, compressionLevel: 2 },
};

export interface ViewerConnection {
  rfb: RFB;
  applyQuality: (quality: ViewerQualityMode) => void;
  applyStream?: (mode: ViewerStreamMode) => void;
  dispose?: () => void;
}

// Coalesce imports when several Profile viewers mount in the same render.
let kasmModule: Promise<typeof import("../vendor/kasmvnc/core/rfb.js")> | undefined;

export async function createViewer(
  implementation: ViewerImplementation,
  target: HTMLElement,
  input: HTMLTextAreaElement,
  profileId: string,
  signal: AbortSignal,
  options: { streamMode?: ViewerStreamMode; onStreamState?: (state: ViewerStreamState) => void } = {},
): Promise<ViewerConnection | null> {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const endpoint = implementation === "kasm" ? "vnc-native" : "vnc";
  const url = `${protocol}//${window.location.host}/api/profiles/${encodeURIComponent(profileId)}/${endpoint}`;

  if (implementation === "kasm") {
    const runtime = await api.authStatus(AbortSignal.any([signal, AbortSignal.timeout(10000)]));
    if (signal.aborted) return null;
    if (runtime.kasmvnc_version !== "1.5.0") {
      throw new ViewerVersionError("The viewer version has changed. Refresh this page or select Compatibility.");
    }
    const videoEnabled = runtime.kasm_video_enabled === true;
    const canDecodeVideo = videoEnabled && await supportsH264(signal);
    const { default: KasmRFB } = await (kasmModule ??= import("../vendor/kasmvnc/core/rfb.js").catch((error) => {
      kasmModule = undefined;
      throw error;
    }));
    if (signal.aborted) return null;
    const rfb = new KasmRFB(target, input, url, {
      wsProtocols: ["binary"],
      shared: true,
      connectionID: `cloakbrowser:${profileId}:${crypto.randomUUID()}`,
      allowRemoteResize: false,
      allowMultiMonitor: false,
      enableWebRTC: false,
      videoRenderingMode: "canvas2d",
    }, canDecodeVideo ? [-1026] : [], true); // Advertise the AVC family; select software after negotiation.
    rfb.mouseButtonMapper = new Map([[0, 1], [1, 2], [2, 3], [3, 8], [4, 9]]);
    rfb.scaleViewport = true;
    rfb.resizeSession = false;
    rfb.forcedResolutionX = null;
    rfb.forcedResolutionY = null;
    rfb.enableHiDpi = false;
    rfb.enableWebRTC = false;
    rfb.enableWebP = true;
    rfb.showDotCursor = true;
    rfb.translateShortcuts = true;
    rfb.keyboard.enableIME = true;
    // Manager owns text clipboard transfer. Native seamless handling would
    // compete with the capture-phase paste handler and duplicate Ctrl+V.
    rfb.clipboardUp = false;
    rfb.clipboardDown = false;
    rfb.clipboardSeamless = false;
    rfb.clipboardBinary = false;
    rfb.threading = true;
    rfb.streamMode = -1025; // Official JPEG/WebP pseudo encoding.
    rfb.gop = 30;

    let requestedStream = options.streamMode ?? "image";
    let currentQuality: ViewerQualityMode = "fast";
    let available = false;
    let failed = false;
    let receivedCodecs = false;
    const updateStream = () => {
      const video = requestedStream === "h264" && available && !failed;
      rfb.streamMode = video ? -1027 : -1025;
      if (video) {
        const presets = rfb.videoCodecConfigurations[-1027]!.presets;
        rfb.videoStreamQuality = presets[currentQuality === "fast" ? 3 : currentQuality === "balanced" ? 2 : 1]!;
      }
      rfb.updateConnectionSettings();
      options.onStreamState?.({ enabled: videoEnabled, available: available && !failed,
        mode: video ? "h264" : "image",
        message: requestedStream !== "h264" || video ? undefined : failed
          ? "Video could not be decoded. Switched to image mode."
          : receivedCodecs || !canDecodeVideo ? "Video is unavailable on this connection. Using image mode."
          : "Checking video support…" });
    };
    const codecsChanged = () => {
      receivedCodecs = true;
      available = canDecodeVideo && (rfb.videoCodecConfigurations?.[-1027]?.presets?.length ?? 0) >= 4;
      updateStream();
    };
    const imageFallback = () => { failed = true; updateStream(); };
    rfb.addEventListener("videocodecschange", codecsChanged);
    rfb.addEventListener("imagemode", imageFallback);
    // ProfileViewer owns the bounded reconnect after badencoding; mark this
    // connection ineligible for video first, so it cannot loop in the codec.
    rfb.addEventListener("badencoding", imageFallback);

    return {
      rfb,
      applyStream(mode) { requestedStream = mode; updateStream(); },
      dispose() {
        rfb.removeEventListener("videocodecschange", codecsChanged);
        rfb.removeEventListener("imagemode", imageFallback);
        rfb.removeEventListener("badencoding", imageFallback);
      },
      applyQuality(mode) {
        currentQuality = mode;
        // Official Low/Medium/High encoding values, applied in Custom mode:
        // Low/Static modes themselves can cap the remote desktop resolution.
        const high = mode === "sharp";
        rfb.videoQuality = 10;
        rfb.qualityLevel = VIEWER_QUALITY_MODES[mode].qualityLevel;
        rfb.compressionLevel = 2;
        rfb.dynamicQualityMin = high ? 7 : mode === "balanced" ? 4 : 3;
        rfb.dynamicQualityMax = mode === "fast" ? 7 : 9;
        rfb.jpegVideoQuality = high ? 8 : mode === "balanced" ? 7 : 5;
        rfb.webpVideoQuality = high ? 8 : mode === "balanced" ? 7 : 4;
        rfb.maxVideoResolutionX = high ? 1920 : 960;
        rfb.maxVideoResolutionY = high ? 1080 : 540;
        rfb.treatLossless = high ? 8 : 7;
        rfb.frameRate = 30;
        rfb.videoTime = 5;
        rfb.videoArea = 65;
        rfb.videoScaling = 0;
        rfb.videoOutTime = 3;
        updateStream();
      },
    };
  }

  const { default: NoVncRFB } = await import("@novnc/novnc/core/rfb.js");
  if (signal.aborted) return null;
  const rfb = new NoVncRFB(target, url, { wsProtocols: ["binary"] });
  rfb.scaleViewport = true;
  rfb.resizeSession = false;
  rfb.showDotCursor = true;
  return {
    rfb,
    applyQuality(mode) {
      rfb.qualityLevel = VIEWER_QUALITY_MODES[mode].qualityLevel;
      rfb.compressionLevel = VIEWER_QUALITY_MODES[mode].compressionLevel;
    },
  };
}
