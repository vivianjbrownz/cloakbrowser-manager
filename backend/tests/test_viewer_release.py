"""Protect production mounts/config and refuse an unmeasured default switch."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ops.release_viewer import replacement_spec, validate_acceptance, wait_idle


def test_replacement_preserves_runtime_secrets_limits_and_existing_volumes():
    old = {
        "Id": "old-container-id",
        "Config": {"Image": "old", "Env": ["AUTH_TOKEN=secret", "AGENTOS_SCOPED_AUTH_SECRET=scoped", "CLOAKBROWSER_VIEWER_DEFAULT=kasm"], "Labels": {"managed": "yes"}},
        "HostConfig": {"ShmSize": 64*1024*1024, "Memory": 1024**3, "NetworkMode": "bridge", "RestartPolicy": {"Name": "unless-stopped"}, "Binds": ["/opt/agentos/config:/run/agentos:ro"]},
        "Mounts": [{"Type": "volume", "Name": "cloakprofiles", "Destination": "/data", "RW": True}],
        "NetworkSettings": {"Networks": {"bridge": {"Aliases": ["old-container-id", "browser"], "IPAMConfig": None}}},
    }
    result = replacement_spec(old, "sha256:new", "novnc")
    assert result["Env"] == ["AUTH_TOKEN=secret", "AGENTOS_SCOPED_AUTH_SECRET=scoped", "CLOAKBROWSER_VIEWER_DEFAULT=novnc"]
    assert result["HostConfig"]["Binds"] == ["/opt/agentos/config:/run/agentos:ro", "cloakprofiles:/data:rw"]
    assert result["HostConfig"]["ShmSize"] == old["HostConfig"]["ShmSize"]
    assert result["HostConfig"]["Memory"] == old["HostConfig"]["Memory"]
    assert result["NetworkingConfig"]["EndpointsConfig"]["bridge"]["Aliases"] == ["browser"]
    assert old["Config"]["Image"] == "old"


def test_idle_gate_never_forces_running_profiles_to_stop():
    with patch("ops.release_viewer.status", return_value={"running_count": 2}):
        with pytest.raises(RuntimeError, match="release deferred"):
            wait_idle(8080, 0)


def report():
    return {"errors": [], "soak_seconds": 1800, "cases": [
        {"concurrency": n, "mode": mode, "fingerprint_unchanged": True, "wire": {"closed": 0},
         "functional": {key: True for key in ["chinese_composition", "paste_once_without_sync", "copy_remote_to_host",
                         "quality_fullscreen_session_preserved", "reconnect_without_browser_restart",
                         "mobile_container_resize_without_remote_resize"]},
         "measurements": [{action: {"samples": 50, "p95_ms": latency} for action in ["click", "typing", "scroll"]} for _ in range(n)]}
        for n in [1, 3] for mode, latency in [("novnc", 1000), ("kasm", 300)]
    ]}


def test_default_switch_requires_complete_passing_measurements(tmp_path: Path):
    path = tmp_path/"report.json"
    payload = report()
    path.write_text(json.dumps(payload))
    validate_acceptance(path)
    payload["cases"][1]["measurements"][0]["scroll"]["p95_ms"] = 900
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="performance gate"):
        validate_acceptance(path)


def test_default_switch_requires_stability_run(tmp_path: Path):
    path = tmp_path/"report.json"
    payload = report()
    payload["soak_seconds"] = 0
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="30-minute"):
        validate_acceptance(path)


@pytest.mark.parametrize("case_index", [1, 3])
@pytest.mark.parametrize("failed", [False, True])
def test_good_latency_cannot_override_missing_or_failed_functional_checks(tmp_path: Path, case_index, failed):
    path = tmp_path/"report.json"
    payload = report()
    if failed:
        payload["cases"][case_index]["functional"]["paste_once_without_sync"] = False
    else:
        del payload["cases"][case_index]["functional"]
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="functional gate"):
        validate_acceptance(path)
