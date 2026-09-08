"""Run alternating, sequential image-version comparisons with resource samples."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def run_case(command, container, output, log, *, capacity_guard=False):
    resources, done = [], threading.Event()
    process, saturated_since, guard = None, None, []
    def observe():
        nonlocal saturated_since
        while not done.is_set():
            try:
                result = subprocess.check_output(["docker", "stats", "--no-stream", "--format", "{{json .}}", container], timeout=12)
                stats = json.loads(result)
                resources.append({"at": time.time(), **{key: stats[key] for key in ("CPUPerc", "MemUsage", "MemPerc", "PIDs")}})
                if capacity_guard:
                    cpu = float(stats["CPUPerc"].rstrip("%"))
                    cpus = len(os.sched_getaffinity(0))
                    if cpu >= cpus*90:
                        saturated_since = saturated_since or time.monotonic()
                    else:
                        saturated_since = None
                    if saturated_since and time.monotonic()-saturated_since >= 60 and process:
                        guard.append("Capacity guard: CPU saturation for 60 seconds")
                        process.terminate()
                        return
            except Exception as exc:
                resources.append({"at": time.time(), "error": type(exc).__name__})
            done.wait(2)
    monitor = threading.Thread(target=observe, daemon=True)
    monitor.start()
    try:
        with log.open("w") as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
            process.wait()
    finally:
        done.set()
        monitor.join(timeout=15)
    report = json.loads(output.read_text()) if output.exists() else {"errors": ["QA process produced no report"]}
    report["resources"] = resources
    report.setdefault("errors", []).extend(guard)
    output.write_text(json.dumps(report, indent=2)+"\n")
    if process.returncode or report.get("errors"):
        raise RuntimeError(f"QA failed; inspect {log}")
    return report


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    bundle = {"baseline": [], "candidate": []}
    for round_index in range(args.rounds):
        labels = ("baseline", "candidate") if round_index % 2 == 0 else ("candidate", "baseline")
        for label in labels:
            container, url = getattr(args, label+"_container"), getattr(args, label+"_url")
            path = output/f"{label}-{round_index+1}.json"
            modes = ["kasm"] if args.comparison == "video" else (
                ["novnc", "kasm"] if round_index % 2 == 0 else ["kasm", "novnc"])
            command = [sys.executable, str(Path(__file__).with_name("qa_kasmvnc.py")),
                       "--base-url", url, "--token-file", args.token_file, "--chromium", args.chromium,
                       "--samples", str(args.samples), "--concurrency", "1", "3", "--modes", *modes,
                       "--container", container, "--output", str(path)]
            if args.comparison == "video":
                command.extend(["--stream-mode", "h264" if label == "candidate" else "image"])
            print(f"Round {round_index+1}/{args.rounds}: {label}", flush=True)
            bundle[label].append(run_case(command, container, path, path.with_suffix(".log")))
            (output/"rounds.json").write_text(json.dumps(bundle, indent=2)+"\n")
            print(f"Completed {label} round {round_index+1}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-url", default="http://127.0.0.1:18982")
    parser.add_argument("--candidate-url", default="http://127.0.0.1:18981")
    parser.add_argument("--baseline-container", default="cloak-kasm13-qa")
    parser.add_argument("--candidate-container", default="cloak-kasm15-qa")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--chromium", default="/usr/bin/google-chrome")
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--comparison", choices=["version", "video"], default="version")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if args.rounds < 1 or args.samples < 1:
        parser.error("Round and sample counts must be positive")
    run(args)
