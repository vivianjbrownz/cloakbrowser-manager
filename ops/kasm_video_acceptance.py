"""Assess optional software AVC independently of the image-mode version release."""
import argparse
import json
from pathlib import Path
import statistics


def evaluate(bundle):
    errors, comparisons = [], []
    if any(len(bundle.get(label, [])) < 3 for label in ("baseline", "candidate")):
        errors.append("Three rounds in each stream mode are required")
    identities = {run.get("image_id") for label in ("baseline", "candidate") for run in bundle[label]}
    if len(identities) != 1 or None in identities:
        errors.append("Both modes must use the same video-capable image")
    groups = {}
    for label in ("baseline", "candidate"):
        expected_mode = "image" if label == "baseline" else "h264"
        runs = bundle.get(label, [])
        if len({r.get("run_id") for r in runs}) != len(runs) or any(not r.get("run_id") for r in runs):
            errors.append("Repeated or unidentified video QA rounds")
        for run in bundle[label]:
            if run.get("errors") or run.get("stream_mode") != expected_mode:
                errors.append(f"{label}: incomplete or wrong-mode QA")
            for case in run.get("cases", []):
                if case["mode"] != "kasm":
                    continue
                if len(case["measurements"]) != case["concurrency"] or any(
                    m[action]["samples"] < 50 for m in case["measurements"] for action in ("click", "typing", "scroll")
                ):
                    errors.append("Video comparison requires 50 samples per action and Profile")
                resources = [float(r["CPUPerc"].rstrip("%")) for r in run.get("resources", [])
                             if "CPUPerc" in r and case["measurement_started_at"] <= r["at"] <= case["measurement_ended_at"]]
                if len(resources) < 3:
                    errors.append("Insufficient CPU samples during measurement")
                groups.setdefault((label, case["concurrency"]), []).append((case, statistics.mean(resources) if resources else 0))
    for concurrency in (1, 3):
        old, new = groups.get(("baseline", concurrency), []), groups.get(("candidate", concurrency), [])
        if len(old) < 3 or len(new) < 3:
            errors.append(f"Missing three rounds at concurrency {concurrency}")
            continue
        for action in ("click", "typing", "scroll"):
            before, after = [statistics.median(max(m[action]["p95_ms"] for m in c["measurements"]) for c, _ in group) for group in (old, new)]
            passed = after <= before*(.8 if action == "scroll" else 1.1)
            comparisons.append({"concurrency": concurrency, "metric": action, "image_p95_ms": before, "video_p95_ms": after, "passed": passed})
            if not passed:
                errors.append(f"Video latency gate failed: {concurrency}/{action}")
        before, after = [statistics.median(cpu for _, cpu in group) for group in (old, new)]
        comparisons.append({"concurrency": concurrency, "metric": "container_cpu", "image_mean_percent": before, "video_mean_percent": after, "passed": after <= before*1.1})
        if after > before*1.1:
            errors.append(f"Video CPU increase exceeds 10%: {concurrency}")
    # Visual legibility and all functional checks are reviewed separately. This
    # helper never enables a feature flag, even when its quantitative gates pass.
    return {"quantitative_passed": not errors, "errors": sorted(set(errors)), "comparisons": comparisons, "enables_video": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    args = parser.parse_args()
    result = evaluate(json.loads(Path(args.report).read_text()))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["quantitative_passed"] else 1)
