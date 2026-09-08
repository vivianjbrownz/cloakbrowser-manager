"""Refresh provenance after reviewed adapter patches, against the pinned archive."""
import difflib
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

root = Path(__file__).resolve().parents[1] / "frontend/src/vendor/kasmvnc"
manifest = json.loads((root / "UPSTREAM.json").read_text())
url = f"https://codeload.github.com/kasmtech/noVNC/tar.gz/{manifest['commit']}"
data = urllib.request.urlopen(url, timeout=60).read()
assert hashlib.sha256(data).hexdigest() == manifest["archive_sha256"]
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    upstream = {member.name.split("/", 1)[1]: archive.extractfile(member).read()
                for member in archive.getmembers() if member.isfile()}
names = set(manifest["upstream_files"]) | set(manifest["patched_files"])
names.update(str(path.relative_to(root)) for folder in ("core", "app") for path in (root/folder).rglob("*") if path.is_file())
manifest["upstream_files"], manifest["patched_files"] = {}, {}
patch = []
for name in sorted(names):
    current = (root/name).read_bytes()
    original = upstream.get(name, b"")
    if name in upstream:
        manifest["upstream_files"][name] = hashlib.sha256(original).hexdigest()
    if current != original:
        manifest["patched_files"][name] = hashlib.sha256(current).hexdigest()
        patch.extend(difflib.unified_diff(original.decode().splitlines(True), current.decode().splitlines(True),
                     fromfile=f"a/{name}" if name in upstream else "/dev/null", tofile=f"b/{name}"))
(root/"manager.patch").write_text("".join(patch))
(root/"UPSTREAM.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Recorded {len(manifest['patched_files'])} patched files against {manifest['commit']}")
