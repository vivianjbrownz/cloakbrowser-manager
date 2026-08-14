from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend import main


def test_profile_is_agentos_accepts_database_tag_shapes():
    assert main._profile_is_agentos({"tags": [{"tag": "AgentOS"}]})
    assert main._profile_is_agentos({"tags": ["agentos"]})
    assert not main._profile_is_agentos({"tags": [{"tag": "personal"}]})


@pytest.mark.asyncio
async def test_idle_reaper_stops_only_disconnected_agentos_profiles(monkeypatch):
    running = SimpleNamespace(display=100)
    monkeypatch.setattr(main.browser_mgr, "running", {"profile-a": running})
    monkeypatch.setattr(main.db, "get_profile", lambda profile_id: {
        "id": profile_id, "tags": [{"tag": "agentos"}],
    })
    stop = AsyncMock()
    stop_xclip = AsyncMock()
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    monkeypatch.setattr(main, "_stop_xclip_for_display", stop_xclip)
    monkeypatch.setattr(main, "_AGENTOS_PROFILE_IDLE_SECONDS", 1800)
    main._profile_last_activity.clear()
    main._profile_live_connections.clear()
    main._profile_last_activity["profile-a"] = 100.0

    stopped = await main._reap_idle_agentos_profiles_once(now=1901.0)

    assert stopped == ["profile-a"]
    stop_xclip.assert_awaited_once_with(100)
    stop.assert_awaited_once_with("profile-a")


@pytest.mark.asyncio
async def test_idle_reaper_preserves_profile_with_live_viewer(monkeypatch):
    running = SimpleNamespace(display=100)
    monkeypatch.setattr(main.browser_mgr, "running", {"profile-a": running})
    monkeypatch.setattr(main.db, "get_profile", lambda profile_id: {
        "id": profile_id, "tags": [{"tag": "agentos"}],
    })
    stop = AsyncMock()
    monkeypatch.setattr(main.browser_mgr, "stop", stop)
    monkeypatch.setattr(main, "_AGENTOS_PROFILE_IDLE_SECONDS", 1800)
    main._profile_last_activity.clear()
    main._profile_live_connections.clear()
    main._profile_last_activity["profile-a"] = 100.0
    main._profile_live_connections["profile-a"] = 1

    stopped = await main._reap_idle_agentos_profiles_once(now=5000.0)

    assert stopped == []
    stop.assert_not_awaited()
