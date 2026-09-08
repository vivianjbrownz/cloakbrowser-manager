"""Install the verified KasmVNC package without updating other installed packages."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

lock = json.loads(Path(__file__).with_name("kasmvnc-runtime.json").read_text())
assert subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip() == lock["architecture"]
assert f'VERSION_CODENAME={lock["distribution"]}' in Path("/etc/os-release").read_text()
with tempfile.TemporaryDirectory(prefix="kasm-package-") as directory:
    package = Path(directory) / "kasmvnc.deb"
    with urllib.request.urlopen(lock["url"], timeout=90) as response:
        package.write_bytes(response.read())
    assert hashlib.sha256(package.read_bytes()).hexdigest() == lock["sha256"], "KasmVNC package checksum mismatch"
    subprocess.run(["dpkg", "--force-confold", "-i", str(package)], check=True)
assert subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "kasmvncserver"], text=True) == lock["package_version"]
assert not subprocess.check_output(["dpkg", "--audit"], text=True).strip(), "Incomplete package installation"
Path("/etc/cloakbrowser-kasmvnc.json").write_text(json.dumps(lock) + "\n")
