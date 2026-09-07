import type RFB from "@novnc/novnc/core/rfb.js";
import type { ViewerImplementation } from "./api";

export type ViewerQualityMode = "fast" | "balanced" | "sharp";
export const VIEWER_QUALITY_MODES = {
  fast: { label: "Fast", qualityLevel: 4, compressionLevel: 7 },
  balanced: { label: "Balanced", qualityLevel: 6, compressionLevel: 5 },
  sharp: { label: "Sharp", qualityLevel: 9, compressionLevel: 2 },
};

export interface ViewerConnection {
  rfb: RFB;
  applyQuality: (quality: ViewerQualityMode) => void;
}

// Coalesce imports when several Profile viewers mount in the same render.
let kasmModule: Promise<typeof import("../vendor/kasmvnc/core/rfb.js")> | undefined;

export async function createViewer(
  implementation: ViewerImplementation,
  target: HTMLElement,
  input: HTMLTextAreaElement,
  profileId: string,
  signal: AbortSignal,
): Promise<ViewerConnection | null> {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const endpoint = implementation === "kasm" ? "vnc-native" : "vnc";
  const url = `${protocol}//${window.location.host}/api/profiles/${encodeURIComponent(profileId)}/${endpoint}`;

  if (implementation === "kasm") {
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
      enableWebRTC: false,
    }, true);
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

    return {
      rfb,
      applyQuality(mode) {
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
        rfb.updateConnectionSettings();
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
