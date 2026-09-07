# KasmVNC client provenance

This is KasmVNC **1.3.3**'s `kasmweb` submodule, from the official
[kasmtech/noVNC repository](https://github.com/kasmtech/noVNC/tree/bce2d6a7048025c6e6c05df9d98b206c23f6dbab).
It is the Kasm fork, not the generic `@novnc/novnc` compatibility client.
Only runtime `core/`, `vendor/` and upstream attribution/package metadata are
vendored. Its package scripts/development dependencies are not installed.

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

`core/rfb.d.ts` describes the integration surface; it is not upstream code.
Rendering, pointer, key, IME, encoding and binary RFB implementations are from
the pinned upstream version. Encoding presets are applied by the Manager
adapter in Custom mode so Low/Static cannot change Profile dimensions.

Licenses: see `LICENSE.txt`, `AUTHORS`, and notices in `vendor/` and source files.
The manager bundles MPL-2.0 source in its public repository; preserve these
notices and the modified source when redistributing the client.
