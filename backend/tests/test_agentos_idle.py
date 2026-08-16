from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend import main


def _configure_reaper(monkeypatch, profiles: dict[str, dict], memory_values: list[int] | None = None):
    running = {profile_id: SimpleNamespace(display=100 + index) for index, profile_id in enumerate(profiles)}
    monkeypatch.setattr(main.browser_mgr, "running", running)
    monkeypatch.setattr(main.db, "get_profile", lambda profile_id: profiles.get(profile_id))
    monkeypatch.setattr(main, "_PROFILE_IDLE_SECONDS", 1200)
    monkeypatch.setattr(main, "_PROFILE_PRESSURE_MIN_AVAILABLE_MB", 2048)
    monkeypatch.setattr(main, "_PROFILE_PRESSURE_GRACE_SECONDS", 120)
    monkeypatch.setattr(main, "_PROFILE_MEMORY_RECHECK_SECONDS", 0)
    values = iter(memory_values or [4096])
    last = (memory_values or [4096])[-1]
    monkeypatch.setattr(main, "_available_memory_mb", lambda: next(values, last))
    main._profile_last_activity.clear()
    main._profile_live_connections.clear()
    return running


@pytest.mark.asyncio
async def test_idle_reaper_stops_all_disconnected_profile_types(monkeypatch):
    profiles = {
        "agentos-profile": {"id": "agentos-profile", "tags": [{"tag": "agentos"}]},
        "personal-profile": {"id": "personal-profile", "tags": [{"tag": "personal"}]},
    }
    running = _configure_reaper(monkeypatch, profiles)
    stop = AsyncMock()
    stop_xclip = AsyncMock()
    update_profile = Mock()
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    monkeypatch.setattr(main, "_stop_xclip_for_display", stop_xclip)
    monkeypatch.setattr(main.db, "update_profile", update_profile)
    main._profile_last_activity.update({profile_id: 100.0 for profile_id in profiles})

    stopped = await main._reap_idle_profiles_once(now=1301.0)

    assert stopped == ["agentos-profile", "personal-profile"]
    assert stop.await_count == 2
    stop_xclip.assert_any_await(running["agentos-profile"].display)
    stop_xclip.assert_any_await(running["personal-profile"].display)
    update_profile.assert_not_called()


@pytest.mark.asyncio
async def test_idle_reaper_preserves_profile_with_live_viewer_or_agent(monkeypatch):
    profiles = {"profile-a": {"id": "profile-a", "tags": []}}
    _configure_reaper(monkeypatch, profiles, [1024])
    stop = AsyncMock()
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    main._profile_last_activity["profile-a"] = 100.0
    main._profile_live_connections["profile-a"] = 1

    stopped = await main._reap_idle_profiles_once(now=5000.0)

    assert stopped == []
    stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_pressure_observes_two_minute_grace(monkeypatch):
    profiles = {"profile-a": {"id": "profile-a", "tags": []}}
    _configure_reaper(monkeypatch, profiles, [1024])
    stop = AsyncMock()
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    main._profile_last_activity["profile-a"] = 100.0

    stopped = await main._reap_idle_profiles_once(now=219.0)

    assert stopped == []
    stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_pressure_stops_oldest_then_rechecks_memory(monkeypatch):
    profiles = {
        "oldest": {"id": "oldest", "fingerprint_seed": 11, "proxy": "proxy-a"},
        "newer": {"id": "newer", "fingerprint_seed": 22, "proxy": "proxy-b"},
    }
    _configure_reaper(monkeypatch, profiles, [1024, 3072])
    stop = AsyncMock()
    stop_xclip = AsyncMock()
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    monkeypatch.setattr(main, "_stop_xclip_for_display", stop_xclip)
    main._profile_last_activity.update({"oldest": 10.0, "newer": 20.0})

    stopped = await main._reap_idle_profiles_once(now=200.0)

    assert stopped == ["oldest"]
    stop.assert_awaited_once_with("oldest")
    assert profiles["oldest"] == {"id": "oldest", "fingerprint_seed": 11, "proxy": "proxy-a"}
    assert profiles["newer"] == {"id": "newer", "fingerprint_seed": 22, "proxy": "proxy-b"}


@pytest.mark.asyncio
async def test_failed_pressure_stop_moves_to_next_idle_profile(monkeypatch):
    profiles = {"first": {"id": "first"}, "second": {"id": "second"}}
    _configure_reaper(monkeypatch, profiles, [1024, 3072])
    stop = AsyncMock(side_effect=[RuntimeError("close failed"), None])
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    monkeypatch.setattr(main, "_stop_xclip_for_display", AsyncMock())
    main._profile_last_activity.update({"first": 10.0, "second": 20.0})

    stopped = await main._reap_idle_profiles_once(now=200.0)

    assert stopped == ["second"]
    assert stop.await_count == 2
    assert main._profile_last_activity["first"] == 200.0


def test_memory_probe_fails_open_without_triggering_pressure(monkeypatch):
    monkeypatch.setattr(main.Path, "read_text", Mock(side_effect=OSError("unavailable")))

    assert main._available_memory_mb() > 2048
