# KasmVNC client provenance

This is KasmVNC **1.5.0**'s `kasmweb` submodule, from the official
[kasmtech/noVNC repository](https://github.com/kasmtech/noVNC/tree/475ecfa5356579ef222983c7ce4619a7576a3bce).
It is the Kasm fork, not the generic `@novnc/novnc` compatibility client.
Runtime `core/`, two required `app/` modules and upstream attribution/package
metadata are vendored. Its package scripts/development dependencies are not
installed. Compression uses the application's locked pako 2.1.0 dependency.

`UPSTREAM.json` records the upstream commit, archive hash, original file hashes,
and hashes of local modifications. `manager.patch` is the source diff. Verify
offline with `python ops/verify_kasm_vendor.py` from the repository root.

Local changes in `core/rfb.js`:

- Accept an explicit per-Profile/per-viewer connection ID instead of sharing a
  BroadcastChannel across all Profile viewers on the SPA's base URL.
- A fixed-desktop option prevents remote resize requests from this client.
- Honor disabled WebRTC before allocating an RTC peer/channel.
- Release BroadcastChannel, RTC and missing window listeners on disconnect;
  tolerate broadcasting after cleanup.
- Resolve the iOS keyboard input through this instance rather than a global ID.
- Observe container size changes so sidebar/fullscreen layout changes rescale
  the local canvas; disconnect the observer with the viewer.
- Disable additional monitors and printer/smart-card relays in the Manager.
- Correct signed codec IDs, rewind incomplete codec records, and continue
  parsing coalesced framebuffer messages after codec negotiation. Real-buffer
  tests cover every fragmentation boundary and the former black-screen case.

Other patches remove the upstream singleton UI dependency from `display.js`,
stop delayed rendering/decoder work on disconnect, close late video frames, and
resolve the QOI worker's WASM through Vite. Video uses Canvas2D and a real AVC
decode probe; unsupported clients fall back to JPEG/WebP.

`core/rfb.d.ts` describes the integration surface; it is not upstream code.
Rendering, pointer, key, IME, encoding and binary RFB implementations derive from
the pinned upstream version with the patches above. Encoding presets are applied by the Manager
adapter in Custom mode so Low/Static cannot change Profile dimensions.

Licenses: see `LICENSE.txt`, `AUTHORS`, and notices in source files.
The manager bundles MPL-2.0 source in its public repository; preserve these
notices and the modified source when redistributing the client.
