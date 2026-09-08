"""Tests for VNCManager — allocation logic and get_ws_port."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
import websockets

from backend.vnc_manager import VNCInstance, VNCManager


@pytest.fixture()
def vnc() -> VNCManager:
    return VNCManager()


@pytest.mark.asyncio
async def test_start_waits_for_actual_rfb_service(vnc, monkeypatch):
    proc = MagicMock()
    proc.poll.return_value = None
    monkeypatch.setattr("backend.vnc_manager.subprocess.Popen", lambda *a, **kw: proc)
    async def greeting(socket):
        await socket.send(b"RFB 003.008\n")
        await socket.wait_closed()
    display, _ = await vnc.allocate()
    async with websockets.serve(greeting, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        assert await vnc.start_vnc(display, port) is proc
    assert vnc._allocated[display].process is proc
    proc.terminate.assert_not_called()


@pytest.mark.asyncio
async def test_failed_start_releases_display(vnc, monkeypatch):
    proc = MagicMock()
    proc.poll.return_value = 1
    monkeypatch.setattr("backend.vnc_manager.subprocess.Popen", lambda *a, **kw: proc)
    display, port = await vnc.allocate()
    with pytest.raises(RuntimeError, match="failed readiness"):
        await vnc.start_vnc(display, port)
    assert vnc.active_displays == []
    assert (await vnc.allocate())[0] == display


# ── allocate ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_allocate_first(vnc: VNCManager):
    display, ws_port = await vnc.allocate()
    assert display == 100
    assert ws_port == 6100


@pytest.mark.asyncio
async def test_allocate_sequential(vnc: VNCManager):
    d1, p1 = await vnc.allocate()
    d2, p2 = await vnc.allocate()
    d3, p3 = await vnc.allocate()
    assert (d1, d2, d3) == (100, 101, 102)
    assert (p1, p2, p3) == (6100, 6101, 6102)


@pytest.mark.asyncio
async def test_allocate_fills_gap(vnc: VNCManager):
    """After freeing display 100, next allocate should reuse it."""
    await vnc.allocate()  # 100
    await vnc.allocate()  # 101
    # Simulate freeing display 100 (like stop_vnc would)
    vnc._allocated.pop(100)
    d, p = await vnc.allocate()
    assert d == 100  # gap filled
    assert p == 6100


@pytest.mark.asyncio
async def test_allocate_tracks_instances(vnc: VNCManager):
    await vnc.allocate()
    await vnc.allocate()
    assert len(vnc._allocated) == 2
    assert 100 in vnc._allocated
    assert 101 in vnc._allocated


@pytest.mark.asyncio
async def test_allocate_instance_fields(vnc: VNCManager):
    await vnc.allocate()
    instance = vnc._allocated[100]
    assert isinstance(instance, VNCInstance)
    assert instance.display == 100
    assert instance.ws_port == 6100
    assert instance.process is None  # not started yet


# ── get_ws_port ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ws_port_allocated(vnc: VNCManager):
    await vnc.allocate()
    assert vnc.get_ws_port(100) == 6100


def test_get_ws_port_not_allocated(vnc: VNCManager):
    assert vnc.get_ws_port(999) is None


# ── active_displays ──────────────────────────────────────────────────────────


def test_active_displays_empty(vnc: VNCManager):
    assert vnc.active_displays == []


@pytest.mark.asyncio
async def test_active_displays_after_allocate(vnc: VNCManager):
    await vnc.allocate()
    await vnc.allocate()
    assert sorted(vnc.active_displays) == [100, 101]


# ── BrowserManager.get_status ────────────────────────────────────────────────


def test_get_status_stopped():
    from backend.browser_manager import BrowserManager
    mgr = BrowserManager()
    status = mgr.get_status("nonexistent")
    assert status == {"status": "stopped", "vnc_ws_port": None, "display": None, "cdp_url": None}


def test_get_status_running():
    from backend.browser_manager import BrowserManager, RunningProfile
    from unittest.mock import MagicMock
    mgr = BrowserManager()
    mgr.running["abc"] = RunningProfile(
        profile_id="abc",
        context=MagicMock(),
        display=100,
        ws_port=6100,
        cdp_port=5100,
    )
    status = mgr.get_status("abc")
    assert status == {
        "status": "running",
        "vnc_ws_port": 6100,
        "display": ":100",
        "cdp_url": "/api/profiles/abc/cdp",
    }
