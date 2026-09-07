#!/usr/bin/env python3
"""Release only the Manager container, preserving its actual Docker runtime spec.

Run on the Docker host as a maintenance user. Default is a read-only preflight;
--apply performs the release. Backups contain secrets and must stay host-local.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import socket
import time
from urllib.parse import quote
import urllib.request


class DockerConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=120)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/var/run/docker.sock")


def docker(method, path, payload=None):
    connection = DockerConnection()
    try:
        connection.request(method, "/v1.45"+path,
                           body=json.dumps(payload) if payload is not None else None,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read()
        if response.status >= 400:
            # Never print the request payload (it contains environment secrets).
            raise RuntimeError(f"Docker operation failed: {method} {path} (HTTP {response.status})")
        return json.loads(data) if data else None
    finally:
        connection.close()


def status(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5) as response:
        return json.load(response)


def wait_idle(port, seconds):
    deadline = time.monotonic()+seconds
    while True:
        count = status(port)["running_count"]
        if count == 0:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Manager still has {count} running Profiles; release deferred")
        print(f"Waiting for {count} running Profiles to stop", flush=True)
        time.sleep(min(30, max(0, deadline-time.monotonic())))


def replacement_spec(old, image, default):
    config = deepcopy(old["Config"])
    config["Image"] = image
    config["Env"] = [item for item in config.get("Env", []) if not item.startswith("CLOAKBROWSER_VIEWER_DEFAULT=")]
    config["Env"].append(f"CLOAKBROWSER_VIEWER_DEFAULT={default}")
    host = deepcopy(old["HostConfig"])
    if host.get("AutoRemove"):
        raise ValueError("AutoRemove containers cannot be retained for rollback")
    if host.get("NetworkMode", "").startswith("container:"):
        raise ValueError("Shared container network namespaces require a separate release procedure")
    # Bind anonymous/image-declared volumes back to their existing named volume.
    binds = host.get("Binds") or []
    bound = {item.split(":")[1] for item in binds}
    bound.update(item["Target"] for item in host.get("Mounts", []))
    for mount in old["Mounts"]:
        if mount["Type"] == "volume" and mount["Destination"] not in bound:
            binds.append(f"{mount['Name']}:{mount['Destination']}:{'rw' if mount['RW'] else 'ro'}")
    host["Binds"] = binds
    endpoints = {}
    for network, endpoint in old["NetworkSettings"]["Networks"].items():
        endpoints[network] = {key: deepcopy(endpoint[key]) for key in ["IPAMConfig", "Links", "DriverOpts"] if endpoint.get(key)}
        # Keep service aliases but discard the previous container's generated ID.
        aliases = [alias for alias in endpoint.get("Aliases") or [] if alias not in {old["Id"], old["Id"][:12]}]
        if aliases:
            endpoints[network]["Aliases"] = aliases
    return {**config, "HostConfig": host, "NetworkingConfig": {"EndpointsConfig": endpoints}}


def validate_acceptance(path):
    if not path:
        raise ValueError("A measured --acceptance-report is required to make KasmVNC the default")
    report = json.loads(Path(path).read_text())
    if report.get("errors"):
        raise ValueError("Acceptance report contains errors")
    cases = {(case["concurrency"], case["mode"]): case for case in report["cases"]}
    for concurrency in (1, 3):
        old, new = cases[(concurrency, "novnc")], cases[(concurrency, "kasm")]
        if len(old["measurements"]) != concurrency or len(new["measurements"]) != concurrency:
            raise ValueError("Incomplete concurrent viewer measurements")
        if not new.get("fingerprint_unchanged") or new["wire"]["closed"]:
            raise ValueError("Fingerprint or connection stability check failed")
        for baseline, native in zip(old["measurements"], new["measurements"], strict=True):
            for action in ("click", "typing", "scroll"):
                if min(baseline[action]["samples"], native[action]["samples"]) < 50:
                    raise ValueError("At least 50 measured samples per action are required")
                latency = native[action]["p95_ms"]
                if latency > 800 or latency > baseline[action]["p95_ms"]*.5:
                    raise ValueError(f"KasmVNC performance gate not met: concurrency={concurrency}, action={action}")
    if report.get("soak_seconds", 0) < 1800:
        raise ValueError("30-minute KasmVNC stability test is required")


def wait_healthy(name, port, default):
    deadline = time.monotonic()+90
    while time.monotonic() < deadline:
        try:
            current = docker("GET", f"/containers/{name}/json")
            health = current["State"].get("Health", {}).get("Status", "healthy")
            if current["State"]["Running"] and health == "healthy":
                status(port)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/auth/status", timeout=5) as response:
                    if json.load(response).get("viewer_default", "novnc") == default:
                        return
        except (OSError, RuntimeError):
            pass
        time.sleep(2)
    raise RuntimeError("Replacement Manager did not become healthy")


def rollback(state, port, idle_wait):
    name, previous = state["name"], state["previous_name"]
    current = docker("GET", f"/containers/{name}/json")
    if current["Id"] != state["new_id"]:
        raise RuntimeError("A different release is active; refusing to overwrite it")
    wait_idle(port, idle_wait)
    docker("POST", f"/containers/{name}/stop?t=30")
    docker("POST", f"/containers/{name}/update", {"RestartPolicy": {"Name": "no"}})
    docker("POST", f"/containers/{name}/rename?name={quote(state['failed_name'])}")
    docker("POST", f"/containers/{previous}/rename?name={quote(name)}")
    docker("POST", f"/containers/{name}/update", {"RestartPolicy": state["previous_restart"]})
    docker("POST", f"/containers/{name}/start")
    wait_healthy(name, port, state["previous_default"])
    print("Previous Manager restored; persistent volumes were not rolled back", flush=True)


def main(args):
    os.umask(0o077)
    if args.rollback:
        state = json.loads((Path(args.rollback)/"release.json").read_text())
        if not args.apply:
            print("Rollback preflight only; --apply restores the saved container")
            return
        rollback(state, args.port, args.idle_wait)
        return
    if not args.image:
        raise ValueError("--image is required")
    old = docker("GET", f"/containers/{args.name}/json")
    image = docker("GET", f"/images/{quote(args.image, safe='')}/json")
    spec = replacement_spec(old, image["Id"], args.default)
    if args.default == "kasm":
        validate_acceptance(args.acceptance_report)
    if not old["State"]["Running"]:
        raise RuntimeError("Expected the current Manager to be running")
    print(json.dumps({"container": args.name, "old_image": old["Image"], "new_image": image["Id"],
                      "default": args.default, "running_profiles": status(args.port)["running_count"],
                      "shm_bytes": spec["HostConfig"]["ShmSize"], "mounts_preserved": len(old["Mounts"])}), flush=True)
    if not args.apply:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(args.backup_root)/stamp
    backup.mkdir(parents=True, mode=0o700)
    (backup/"inspect.json").write_text(json.dumps(old, indent=2))
    (backup/"create.json").write_text(json.dumps(spec, indent=2))
    wait_idle(args.port, args.idle_wait)
    # Re-read just before stopping, so a concurrent release cannot be overwritten.
    if docker("GET", f"/containers/{args.name}/json")["Id"] != old["Id"]:
        raise RuntimeError("Manager changed after preflight")
    previous = f"{args.name}-pre-kasm-{stamp}"
    state = {"name": args.name, "previous_name": previous, "failed_name": f"{args.name}-failed-{stamp}",
             "previous_restart": old["HostConfig"]["RestartPolicy"],
             "previous_default": next((e.split("=", 1)[1] for e in old["Config"]["Env"] if e.startswith("CLOAKBROWSER_VIEWER_DEFAULT=")), "novnc")}
    docker("POST", f"/containers/{args.name}/stop?t=30")
    docker("POST", f"/containers/{args.name}/rename?name={quote(previous)}")
    docker("POST", f"/containers/{previous}/update", {"RestartPolicy": {"Name": "no"}})
    new_id = None
    try:
        created = docker("POST", f"/containers/create?name={quote(args.name)}", spec)
        new_id = created["Id"]
        state["new_id"] = new_id
        (backup/"release.json").write_text(json.dumps(state, indent=2))
        docker("POST", f"/containers/{new_id}/start")
        wait_healthy(args.name, args.port, args.default)
    except BaseException:
        if new_id:
            docker("POST", f"/containers/{new_id}/stop?t=10")
            docker("POST", f"/containers/{new_id}/update", {"RestartPolicy": {"Name": "no"}})
            docker("POST", f"/containers/{new_id}/rename?name={quote(state['failed_name'])}")
        docker("POST", f"/containers/{previous}/rename?name={quote(args.name)}")
        docker("POST", f"/containers/{args.name}/update", {"RestartPolicy": state["previous_restart"]})
        docker("POST", f"/containers/{args.name}/start")
        raise
    print(f"Manager release healthy; private rollback state: {backup}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="cloakbrowser-manager")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--image")
    parser.add_argument("--default", choices=["novnc", "kasm"], default="novnc")
    parser.add_argument("--acceptance-report")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback")
    parser.add_argument("--idle-wait", type=int, default=600)
    parser.add_argument("--backup-root", default="/opt/cloakbrowser-manager/releases")
    main(parser.parse_args())
