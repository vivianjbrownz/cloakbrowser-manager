from copy import deepcopy
from uuid import uuid4

from ops.kasm_upgrade_acceptance import evaluate, FUNCTIONAL


def evidence():
    identity = {"browser_path": "/chrome", "browser_sha256": "browser", "font_files": 1,
                "fonts_sha256": "fonts", "python_packages_sha256": "python"}
    before = {**identity, "system_packages": {"kasmvncserver": "1.3.3-1"}}
    after = {**identity, "system_packages": {"kasmvncserver": "1.5.0-1"}}
    def run(image):
        return {"run_id": uuid4().hex, "image_id": image, "errors": [], "soak_seconds": 1800,
                "soak_painted_feedback": [{"samples": 60}] * 3, "cases": [
            {"mode": mode, "concurrency": n, "stream_mode": "image", "wire": {"closed": 0},
             "fingerprint_unchanged": True, "fingerprints": [{"canvas": str(i)} for i in range(n)],
             "functional": {key: True for key in (*FUNCTIONAL, "concurrent_input_clipboard_isolation")},
             "measurements": [{action: {"samples": 50, "p95_ms": 200} for action in ("click", "typing", "scroll")} for _ in range(n)]}
            for mode in ("novnc", "kasm") for n in (1, 3)]}
    return {"baseline_image_id": "old", "runtime_before": before, "runtime_after": after, "baseline": [run("old") for _ in range(3)],
            "candidate": [run("new") for _ in range(3)], "stability": run("new")}


def test_upgrade_does_not_imply_default_promotion():
    result = evaluate(evidence(), "new")
    assert result["passed"] and not result["default_promotion"]


def test_wrong_image_and_partial_rounds_are_rejected():
    report = evidence()
    assert not evaluate(report, "another-image")["passed"]
    report["candidate"].pop()
    assert not evaluate(report, "new")["passed"]


def test_reused_rounds_or_changed_production_baseline_are_rejected():
    report = evidence()
    assert not evaluate(report, "new", "other-production-image")["passed"]
    report["candidate"] = [report["candidate"][0]] * 3
    assert not evaluate(report, "new")["passed"]


def test_new_fingerprint_or_consistent_latency_regression_blocks_release():
    report = evidence()
    changed = deepcopy(report)
    changed["candidate"][0]["cases"][0]["fingerprints"][0]["canvas"] = "changed"
    assert not evaluate(changed, "new")["passed"]
    for run in report["candidate"]:
        run["cases"][0]["measurements"][0]["click"]["p95_ms"] = 230
    assert not evaluate(report, "new")["passed"]
