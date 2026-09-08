import { describe, expect, it, vi } from "vitest";
import KasmRFB from "../vendor/kasmvnc/core/rfb.js";
import Websock from "../vendor/kasmvnc/core/websock.js";
import KasmVideoDecoder from "../vendor/kasmvnc/core/decoders/kasmvideo.js";

const handle = (KasmRFB.prototype as any)._handleServerVideoEncoders;
function fixture(bytes: Uint8Array) {
  const socket = new Websock();
  socket._allocateBuffers();
  socket._rQ.set(bytes);
  socket._rQlen = bytes.length;
  socket._rQi = 1; // The normal RFB dispatcher has consumed message type 184.
  return { _sock: socket, dispatchEvent: vi.fn(), videoCodecs: [] as number[], videoCodecConfigurations: {} as any };
}

describe("KasmVNC encoder negotiation", () => {
  it("continues with a coalesced framebuffer message when no video encoders exist", () => {
    const client = fixture(new Uint8Array([184, 0, 0, 0, 0, 1]));
    expect(handle.call(client)).toBe(true);
    expect(client._sock._rQi).toBe(2);
    expect(client.dispatchEvent).toHaveBeenCalledTimes(1);
  });

  it("preserves signed codec IDs and rewinds at every possible frame split", () => {
    const message = new Uint8Array(35);
    const data = new DataView(message.buffer);
    message.set([184, 1]); data.setInt32(2, -1027); data.setInt32(6, 0); data.setInt32(10, 50);
    message[14] = 5;
    [9, 18, 25, 39, 50].forEach((quality, i) => data.setInt32(15+i*4, quality));
    for (let length = 1; length < message.length; length++) {
      const client = fixture(message.slice(0, length));
      expect(handle.call(client)).toBe(false);
      expect(client._sock._rQi).toBe(0);
      expect(client.dispatchEvent).not.toHaveBeenCalled();
      client._sock._rQ.set(message);
      client._sock._rQlen = message.length;
      expect(client._sock.rQshift8()).toBe(184);
      expect(handle.call(client)).toBe(true);
      expect(client.videoCodecs).toEqual([-1027]);
      expect(client.videoCodecConfigurations[-1027].presets).toEqual([9, 18, 25, 39, 50]);
    }
  });
});

it("releases video resources on fallback and closes late frames without repainting", () => {
  const rfb = { dispatchEvent: vi.fn() };
  const display = { videoFrameRect: vi.fn() };
  const decoder = new KasmVideoDecoder(rfb, display);
  const close = vi.fn();
  decoder._decoders.set(0, { decoder: { state: "configured", close } });
  decoder._decoders.set(1, { decoder: { state: "closed", close } });
  decoder._timestampMap.set(42, { screenId: 0 });
  decoder._handleDecoderError();
  expect(close).toHaveBeenCalledTimes(1);
  expect(decoder._timestampMap.size).toBe(0);
  expect(rfb.dispatchEvent.mock.calls[0][0].type).toBe("imagemode");
  const frame = { timestamp: 42, close: vi.fn() };
  decoder._handleProcessVideoChunk(frame);
  expect(frame.close).toHaveBeenCalledOnce();
  expect(display.videoFrameRect).not.toHaveBeenCalled();
});
