"""Compare frozen browser identity and the exact display-server package delta."""
import argparse
import json
from pathlib import Path


def compare(before, after, *, video=False):
    errors = []
    for key in ("browser_path", "browser_sha256", "font_files", "fonts_sha256", "python_packages_sha256"):
        if key not in before or before[key] != after.get(key):
            errors.append(f"Runtime identity changed: {key}")
    old, new = before["system_packages"], after["system_packages"]
    changes = {name: [old.get(name), new.get(name)] for name in sorted(old.keys() | new.keys()) if old.get(name) != new.get(name)}
    for name, (previous, current) in changes.items():
        if name == "kasmvncserver" and current == "1.5.0-1":
            continue
        # Video dependencies may only be added, never upgrade/remove the pinned
        # graphics foundation. The exact additions remain in the evidence.
        if video and previous is None:
            video_lock = json.loads(Path(__file__).with_name("kasmvnc-video-packages.json").read_text())
            if current is not None and video_lock.get(name) == current:
                continue
        errors.append(f"Unexpected package change: {name}")
    if new.get("kasmvncserver") != "1.5.0-1":
        errors.append("Candidate is not KasmVNC 1.5.0-1")
    return {"passed": not errors, "errors": errors, "package_changes": changes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    result = compare(json.loads(Path(args.baseline).read_text()), json.loads(Path(args.candidate).read_text()), video=args.video)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
