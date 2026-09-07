#!/usr/bin/env python3
"""Read-only, finite post-release observation; never restarts or changes Profiles."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def run(args):
    os.umask(0o077)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    deadline = time.monotonic()+args.duration
    while True:
        record = {"at": datetime.now(timezone.utc).isoformat()}
        try:
            for key, path in [("status", "/api/status"), ("viewer", "/api/auth/status")]:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.port}{path}", timeout=5) as response:
                    body = json.load(response)
                    record[key] = body if key == "status" else body.get("viewer_default", "novnc")
            raw = subprocess.check_output(["docker", "stats", "--no-stream", "--format", "{{json .}}", args.name], timeout=15)
            stats = json.loads(raw)
            record["resources"] = {key: stats[key] for key in ["CPUPerc", "MemUsage", "MemPerc", "NetIO", "PIDs"]}
            logs = subprocess.check_output(["docker", "logs", "--since", started, args.name], stderr=subprocess.STDOUT, timeout=10).decode(errors="replace")
            record["native_proxy_errors_since_release"] = logs.count("Native VNC proxy failed")
            record["ok"] = True
        except Exception as exc:
            record.update(ok=False, error=type(exc).__name__)
        remaining = deadline-time.monotonic()
        record["observation_complete"] = remaining <= 0
        with output.open("a") as stream:
            stream.write(json.dumps(record)+"\n")
        print(json.dumps(record), flush=True)
        if remaining <= 0:
            return
        time.sleep(min(300, remaining))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="cloakbrowser-manager")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--duration", type=int, default=86400)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
