"""Evaluate version-upgrade evidence separately from the stricter default switch."""
import argparse
import json
from pathlib import Path
import statistics

try:
    from ops.verify_runtime_upgrade import compare
except ModuleNotFoundError:
    from verify_runtime_upgrade import compare

FUNCTIONAL = ("chinese_composition", "paste_once_without_sync", "copy_remote_to_host",
              "quality_fullscreen_session_preserved", "reconnect_without_browser_restart",
              "mobile_container_resize_without_remote_resize")


def evaluate(report, image_id, baseline_image_id=None):
    errors, results = [], []
    expected_baseline = baseline_image_id or report.get("baseline_image_id")
    if not expected_baseline:
        errors.append("Baseline image identity is required")
    runtime = compare(report["runtime_before"], report["runtime_after"])
    errors.extend(runtime["errors"])
    groups = {}
    for label in ("baseline", "candidate"):
        runs = report[label]
        if len(runs) < 3:
            errors.append(f"{label}: three independent rounds are required")
        if len({r.get("run_id") for r in runs}) != len(runs) or any(not r.get("run_id") for r in runs):
            errors.append(f"{label}: repeated or unidentified QA rounds")
        for run in runs:
            if run.get("errors"):
                errors.append(f"{label}: failed QA run")
            if label == "candidate" and run.get("image_id") != image_id:
                errors.append("Candidate evidence belongs to another image")
            if label == "baseline" and run.get("image_id") != expected_baseline:
                errors.append("Baseline evidence belongs to another image")
            cases = {(c["concurrency"], c["mode"]): c for c in run["cases"]}
            for n in (1, 3):
                for mode in ("novnc", "kasm"):
                    case = cases.get((n, mode))
                    if not case or len(case["measurements"]) != n:
                        errors.append(f"{label}: missing {n}/{mode} measurements")
                        continue
                    if case.get("stream_mode") != "image" or not case.get("fingerprint_unchanged") or case["wire"]["closed"]:
                        errors.append(f"{label}: mode, fingerprint or connection gate failed")
                    if mode == "kasm" and not all(case.get("functional", {}).get(key) is True for key in FUNCTIONAL):
                        errors.append(f"{label}: functional gate failed")
                    groups.setdefault((label, n, mode), []).append(case)
                    for measurement in case["measurements"]:
                        for action in ("click", "typing", "scroll"):
                            if measurement[action]["samples"] < 50:
                                errors.append("At least 50 samples per action are required")
    for n in (1, 3):
        for mode in ("novnc", "kasm"):
            old, new = groups.get(("baseline", n, mode), []), groups.get(("candidate", n, mode), [])
            if not old or not new:
                continue
            fingerprints = old[0].get("fingerprints")
            if not fingerprints or any(c.get("fingerprints") != fingerprints for c in old+new):
                errors.append(f"Browser fingerprint differs across versions/rounds: {n}/{mode}")
            for action in ("click", "typing", "scroll"):
                # Median of three rounds; each round uses the worst Profile P95.
                before = statistics.median(max(m[action]["p95_ms"] for m in c["measurements"]) for c in old)
                after = statistics.median(max(m[action]["p95_ms"] for m in c["measurements"]) for c in new)
                passed = after <= before * 1.1
                results.append({"concurrency": n, "mode": mode, "action": action,
                                "baseline_p95_ms": before, "candidate_p95_ms": after, "passed": passed})
                if not passed:
                    errors.append(f"P95 regression exceeds 10%: {n}/{mode}/{action}")
    soak = report.get("stability", {})
    if soak.get("image_id") != image_id or soak.get("errors") or soak.get("soak_seconds", 0) < 1800:
        errors.append("A successful 30-minute run on this image is required")
    stable = next((c for c in soak.get("cases", []) if c["concurrency"] == 3 and c["mode"] == "kasm"), None)
    if not stable or stable["wire"]["closed"] or not all(stable.get("functional", {}).get(k) is True for k in FUNCTIONAL):
        errors.append("Three-viewer stability/functional evidence is incomplete")
    if not stable or stable.get("functional", {}).get("concurrent_input_clipboard_isolation") is not True:
        errors.append("Concurrent input/clipboard isolation evidence is required")
    if len(soak.get("soak_painted_feedback", [])) != 3 or any(
        m.get("samples", 0) < 50 for m in soak.get("soak_painted_feedback", [])
    ):
        errors.append("Stability must verify painted feedback throughout the run")
    return {"passed": not errors, "errors": sorted(set(errors)), "image_id": image_id, "comparisons": results,
            "runtime": runtime, "default_promotion": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(Path(args.report).read_text()), args.image_id)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
