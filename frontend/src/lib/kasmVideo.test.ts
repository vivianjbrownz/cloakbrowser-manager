import { afterEach, describe, expect, it, vi } from "vitest";
import { supportsH264 } from "./kasmVideo";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

function decoderFixture(output: boolean) {
  const close = vi.fn();
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) }));
  vi.stubGlobal("EncodedVideoChunk", class { constructor(_options: unknown) {} });
  vi.stubGlobal("VideoDecoder", class {
    static isConfigSupported = async () => ({ supported: true });
    state = "configured";
    constructor(private options: { output: (frame: { close: () => void }) => void }) {}
    configure() {}
    decode() { if (output) queueMicrotask(() => this.options.output({ close: vi.fn() })); }
    flush() { return new Promise(() => {}); }
    close() { this.state = "closed"; close(); }
  });
  return close;
}

describe("H.264 capability probe", () => {
  it("requires an actual decoded frame and releases the probe decoder", async () => {
    const close = decoderFixture(true);
    expect(await supportsH264(new AbortController().signal)).toBe(true);
    expect(close).toHaveBeenCalledTimes(1);
  });
  it("bounds a stalled decoder and closes it on timeout", async () => {
    vi.useFakeTimers();
    const close = decoderFixture(false);
    const result = supportsH264(new AbortController().signal);
    await vi.advanceTimersByTimeAsync(3100);
    expect(await result).toBe(false);
    expect(close).toHaveBeenCalledTimes(1);
  });
  it("does not try video outside a secure context", async () => {
    decoderFixture(true);
    vi.stubGlobal("isSecureContext", false);
    expect(await supportsH264(new AbortController().signal)).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
  });
});
