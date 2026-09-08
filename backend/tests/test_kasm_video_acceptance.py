from ops.kasm_video_acceptance import evaluate


def evidence(cpu=105):
    return {label: [
        {"run_id": f"{label}-{i}", "image_id": "same-image", "errors": [],
         "stream_mode": "image" if label == "baseline" else "h264",
         "resources": [{"at": at, "CPUPerc": f"{100 if label == 'baseline' else cpu}%"} for at in (2, 4, 6)],
         "cases": [{"mode": "kasm", "concurrency": n, "measurement_started_at": 0, "measurement_ended_at": 10,
                    "measurements": [{action: {"p95_ms": 70 if action == "scroll" and label == "candidate" else 100,
                                                 "samples": 50} for action in ("click", "typing", "scroll")} for _ in range(n)]}
                   for n in (1, 3)]}
        for i in range(3)] for label in ("baseline", "candidate")}


def test_video_latency_gain_cannot_override_cpu_regression():
    assert evaluate(evidence())["quantitative_passed"]
    assert not evaluate(evidence(cpu=111))["quantitative_passed"]
    assert not evaluate(evidence())["enables_video"]


def test_video_requires_same_image_independent_rounds_and_enough_samples():
    bundle = evidence()
    bundle["candidate"][0]["image_id"] = "untested-image"
    assert not evaluate(bundle)["quantitative_passed"]
    bundle = evidence()
    bundle["candidate"][1] = bundle["candidate"][0]
    assert not evaluate(bundle)["quantitative_passed"]
    bundle = evidence()
    bundle["candidate"][0]["cases"][0]["measurements"][0]["scroll"]["samples"] = 49
    assert not evaluate(bundle)["quantitative_passed"]
