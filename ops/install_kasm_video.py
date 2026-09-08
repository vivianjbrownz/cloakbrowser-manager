"""Install the separately locked software-video runtime, without package drift."""
import json
from pathlib import Path
import subprocess


def installed():
    result = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}=${Version}\n"], text=True)
    return dict(line.split("=", 1) for line in result.splitlines())


lock = json.loads(Path(__file__).with_name("kasmvnc-video-packages.json").read_text())
before = installed()
subprocess.run(["apt-get", "update"], check=True)
subprocess.run(["apt-get", "install", "-y", "--no-install-recommends",
                *[f"{name}={version}" for name, version in lock.items()]], check=True)
after = installed()
assert all(after.get(name) == version for name, version in before.items()), "Existing runtime package drift"
assert {name: version for name, version in after.items() if name not in before} == {name: version for name, version in lock.items() if name not in before}, "Unrecorded video dependencies"
assert all(after.get(name) == version for name, version in lock.items()), "Video runtime version mismatch"
