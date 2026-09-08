"""Bounded 5/10/20-browser calibration with three streamed desktop viewers."""
import argparse
import json
from pathlib import Path
import sys

from qa_kasm_suite import run_case


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {"workload": "One tab per Profile; background DOM update every 5 seconds; 3 active viewers",
               "steps": [], "completed_20": False}
    for total in (5, 10, 20):
        path = output/f"capacity-{total}.json"
        command = [sys.executable, str(Path(__file__).with_name("qa_kasmvnc.py")),
                   "--base-url", args.base_url, "--token-file", args.token_file, "--chromium", args.chromium,
                   "--samples", "5", "--concurrency", "3", "--modes", "kasm", "--soak-seconds", "60",
                   "--background-profiles", str(total-3), "--container", args.container, "--output", str(path)]
        print(f"Capacity calibration: {total} browsers / 3 viewers", flush=True)
        try:
            report = run_case(command, args.container, path, path.with_suffix(".log"), capacity_guard=True)
            summary["steps"].append({"total": total, "passed": True, "report": path.name})
            summary["completed_20"] = total == 20
        except Exception as exc:
            summary["steps"].append({"total": total, "passed": False, "error": str(exc), "report": path.name})
            break
        finally:
            (output/"capacity-summary.json").write_text(json.dumps(summary, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18981")
    parser.add_argument("--container", default="cloak-kasm15-qa")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--chromium", default="/usr/bin/google-chrome")
    parser.add_argument("--output-dir", required=True)
    run(parser.parse_args())
