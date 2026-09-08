import RFB from "@novnc/novnc/core/rfb.js";

export default class KasmRFB extends RFB {
  constructor(target: HTMLElement, input: HTMLTextAreaElement, url: string, options: Record<string, unknown>, codecs: number[], primary: boolean);
  streamMode: number;
  threading: boolean;
  gop: number;
  videoStreamQuality: number;
  videoCodecConfigurations: Record<number, { presets: number[] }>;
  keyboard: { enableIME: boolean };
  mouseButtonMapper: Map<number, number>;
  translateShortcuts: boolean;
  clipboardUp: boolean;
  clipboardDown: boolean;
  clipboardSeamless: boolean;
  clipboardBinary: boolean;
  enableWebRTC: boolean;
  enableHiDpi: boolean;
  enableWebP: boolean;
  videoQuality: number;
  frameRate: number;
  dynamicQualityMin: number;
  dynamicQualityMax: number;
  jpegVideoQuality: number;
  webpVideoQuality: number;
  maxVideoResolutionX: number;
  maxVideoResolutionY: number;
  treatLossless: number;
  videoTime: number;
  videoArea: number;
  videoScaling: number;
  videoOutTime: number;
  forcedResolutionX: number | null;
  forcedResolutionY: number | null;
  updateConnectionSettings(): void;
}
