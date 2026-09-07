#!/usr/bin/env python3
"""Read-only identity of browser binary, fonts and installed dependencies.

Run via docker exec -i CONTAINER python < ops/runtime_fingerprint.py.
No Profile data, environment variables or credentials are read.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess

from cloakbrowser.config import get_binary_path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


binary = Path(get_binary_path())
fonts = {str(path): sha(path) for path in sorted(Path("/usr/share/fonts").rglob("*")) if path.is_file()}
packages = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}=${Version}\n"])
python = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
print(json.dumps({"browser_path": str(binary), "browser_sha256": sha(binary), "font_files": len(fonts),
                  "fonts_sha256": hashlib.sha256(json.dumps(fonts, sort_keys=True).encode()).hexdigest(),
                  "system_packages_sha256": hashlib.sha256(packages).hexdigest(),
                  "python_packages_sha256": hashlib.sha256("\n".join(python).encode()).hexdigest()}, sort_keys=True))
