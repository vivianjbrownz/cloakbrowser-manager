#!/usr/bin/env python3
"""Offline integrity check for the immutable upstream client and recorded patches."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "frontend/src/vendor/kasmvnc"
manifest = json.loads((root / "UPSTREAM.json").read_text())
runtime = json.loads((Path(__file__).resolve().parents[1] / "ops/kasmvnc-runtime.json").read_text())
if runtime["version"] != manifest["server_version"] or runtime["client_commit"] != manifest["commit"]:
    raise SystemExit("KasmVNC server/client lock mismatch")
expected = {**manifest["upstream_files"], **manifest.get("patched_files", {})}
for name, checksum in expected.items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != checksum:
        raise SystemExit(f"KasmVNC source differs from recorded version: {name}")
for folder in ("core", "app"):
    for path in (root/folder).rglob("*"):
        if path.is_file() and str(path.relative_to(root)) not in expected:
            raise SystemExit(f"Unrecorded KasmVNC runtime asset: {path.name}")
print(f"Verified {len(expected)} KasmVNC files at {manifest['commit'][:12]} (server {manifest['server_version']})")
