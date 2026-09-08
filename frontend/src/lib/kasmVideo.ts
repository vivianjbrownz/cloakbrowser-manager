import avcSample from "../vendor/kasmvnc/core/assets/avc.bin?url";

/** A real, bounded decode test. No cached result survives a browser upgrade. */
export async function supportsH264(signal: AbortSignal): Promise<boolean> {
  if (!window.isSecureContext || typeof VideoDecoder === "undefined") return false;
  try {
    const config: VideoDecoderConfig = { codec: "avc1.64001F", optimizeForLatency: true };
    if (!(await VideoDecoder.isConfigSupported(config)).supported || signal.aborted) return false;
    const response = await fetch(avcSample, { signal: AbortSignal.any([signal, AbortSignal.timeout(3000)]) });
    if (!response.ok) return false;
    const data = await response.arrayBuffer();
    return await new Promise<boolean>((resolve) => {
      let decoder: VideoDecoder | undefined;
      const finish = (supported: boolean) => {
        clearTimeout(timer);
        signal.removeEventListener("abort", abort);
        if (decoder && decoder.state !== "closed") decoder.close();
        resolve(supported && !signal.aborted);
      };
      const abort = () => finish(false);
      const timer = setTimeout(() => finish(false), 3000);
      signal.addEventListener("abort", abort, { once: true });
      try {
        decoder = new VideoDecoder({
          output: (frame) => { frame.close(); finish(true); },
          error: () => finish(false),
        });
        if (signal.aborted) { finish(false); return; }
        decoder.configure(config);
        decoder.decode(new EncodedVideoChunk({ type: "key", timestamp: 0, data }));
        void decoder.flush().catch(() => finish(false));
      } catch { finish(false); }
    });
  } catch { return false; }
}
