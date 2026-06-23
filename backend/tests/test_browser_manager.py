"""Tests for browser_manager pure functions — proxy parsing, fingerprint args, profile defaults."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import socket
from unittest.mock import AsyncMock, MagicMock

from backend.browser_manager import (
    BASE_CDP_PORT,
    CDP_PORT_RANGE,
    _configure_session_restore,
    _init_profile_defaults,
    _normalize_proxy,
    _restore_last_session_enabled,
    _validate_proxy,
    BrowserManager,
    RunningProfile,
)


# ── _normalize_proxy ─────────────────────────────────────────────────────────


def test_normalize_already_http():
    assert _normalize_proxy("http://user:pass@host:8080") == "http://user:pass@host:8080"


def test_normalize_already_https():
    assert _normalize_proxy("https://host:443") == "https://host:443"


def test_normalize_already_socks5():
    assert _normalize_proxy("socks5://host:1080") == "socks5://host:1080"


def test_normalize_host_port_user_pass():
    assert _normalize_proxy("proxy.com:8080:myuser:mypass") == "http://myuser:mypass@proxy.com:8080"


def test_normalize_host_port_only():
    assert _normalize_proxy("proxy.com:8080") == "http://proxy.com:8080"


def test_normalize_three_parts():
    # 3 parts doesn't match any pattern — returned as-is
    assert _normalize_proxy("a:b:c") == "a:b:c"


def test_normalize_five_parts():
    # 5 parts doesn't match — returned as-is
    assert _normalize_proxy("a:b:c:d:e") == "a:b:c:d:e"


def test_normalize_empty_parts():
    # host:port:user:pass with empty parts
    result = _normalize_proxy(":8080:user:pass")
    assert result == "http://user:pass@:8080"


# ── _validate_proxy ──────────────────────────────────────────────────────────


def test_validate_valid_http():
    _validate_proxy("http://proxy.com:8080")  # should not raise


def test_validate_valid_socks5():
    _validate_proxy("socks5://proxy.com:1080")  # should not raise


def test_validate_valid_with_auth():
    _validate_proxy("http://user:pass@proxy.com:8080")  # should not raise


def test_validate_bad_scheme():
    with pytest.raises(ValueError, match="Invalid proxy scheme 'ftp'"):
        _validate_proxy("ftp://host:80")


def test_validate_no_hostname():
    with pytest.raises(ValueError, match="missing hostname"):
        _validate_proxy("http://:8080")


def test_validate_no_port():
    with pytest.raises(ValueError, match="missing port"):
        _validate_proxy("http://host")


# ── _build_fingerprint_args ──────────────────────────────────────────────────

# Use the BrowserManager instance to call the method
_mgr = BrowserManager()


def test_build_args_always_includes_base():
    args = _mgr._build_fingerprint_args({})
    assert "--disable-infobars" in args
    assert "--test-type" in args
    assert "--use-angle=swiftshader" in args


def test_build_args_seed():
    args = _mgr._build_fingerprint_args({"fingerprint_seed": 42})
    assert "--fingerprint=42" in args


def test_build_args_no_seed():
    args = _mgr._build_fingerprint_args({"fingerprint_seed": None})
    assert not any(a.startswith("--fingerprint=") for a in args)


def test_build_args_platform():
    args = _mgr._build_fingerprint_args({"platform": "macos"})
    assert "--fingerprint-platform=macos" in args


def test_build_args_gpu():
    args = _mgr._build_fingerprint_args({
        "gpu_vendor": "NVIDIA Corporation",
        "gpu_renderer": "NVIDIA GeForce RTX 3070",
    })
    assert "--fingerprint-gpu-vendor=NVIDIA Corporation" in args
    assert "--fingerprint-gpu-renderer=NVIDIA GeForce RTX 3070" in args


def test_build_args_hardware_concurrency():
    args = _mgr._build_fingerprint_args({"hardware_concurrency": 8})
    assert "--fingerprint-hardware-concurrency=8" in args


def test_build_args_screen():
    args = _mgr._build_fingerprint_args({"screen_width": 2560, "screen_height": 1440})
    assert "--fingerprint-screen-width=2560" in args
    assert "--fingerprint-screen-height=1440" in args


def test_build_args_empty_profile():
    args = _mgr._build_fingerprint_args({})
    # Only the 3 base args
    assert len(args) == 3


# ── launch_args appended to extra_args ────────────────────────────────────────


def test_launch_args_appended_to_fingerprint_args():
    """launch_args from profile should appear in the args list after fingerprint args."""
    profile = {
        "fingerprint_seed": 42,
        "platform": "windows",
        "launch_args": ["--load-extension=/tmp/ext", "--disable-features=Foo"],
    }
    args = _mgr._build_fingerprint_args(profile)
    args += profile.get("launch_args") or []
    assert "--load-extension=/tmp/ext" in args
    assert "--disable-features=Foo" in args
    # Fingerprint args still present
    assert "--fingerprint=42" in args


def test_launch_args_empty_no_effect():
    profile = {"launch_args": []}
    args = _mgr._build_fingerprint_args(profile)
    base_count = len(args)
    args += profile.get("launch_args") or []
    assert len(args) == base_count


def test_launch_args_none_no_effect():
    profile = {"launch_args": None}
    args = _mgr._build_fingerprint_args(profile)
    base_count = len(args)
    args += profile.get("launch_args") or []
    assert len(args) == base_count


# ── clipboard init script ───────────────────────────────────────────────────


def _profile_for_launch(
    tmp_path: Path,
    *,
    clipboard_sync: bool,
    restore_last_session: bool = True,
) -> dict:
    return {
        "id": f"profile-{int(clipboard_sync)}",
        "user_data_dir": str(tmp_path / f"profile-{int(clipboard_sync)}"),
        "screen_width": 1366,
        "screen_height": 768,
        "headless": False,
        "humanize": False,
        "human_preset": "default",
        "geoip": False,
        "launch_args": [],
        "proxy": None,
        "clipboard_sync": clipboard_sync,
        "restore_last_session": restore_last_session,
    }


@pytest.mark.asyncio
async def test_launch_skips_clipboard_init_when_sync_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend import browser_manager as browser_manager_module

    mgr = BrowserManager()
    monkeypatch.setattr(mgr.vnc, "start_vnc", AsyncMock())
    monkeypatch.setattr(mgr.vnc, "stop_vnc", AsyncMock())

    context = MagicMock()
    context.add_init_script = AsyncMock()
    context.pages = []
    context.on = MagicMock()
    monkeypatch.setattr(
        browser_manager_module,
        "launch_persistent_context_async",
        AsyncMock(return_value=context),
    )

    await mgr.launch(_profile_for_launch(tmp_path, clipboard_sync=False))

    context.add_init_script.assert_not_awaited()


@pytest.mark.asyncio
async def test_launch_injects_clipboard_init_when_sync_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend import browser_manager as browser_manager_module

    mgr = BrowserManager()
    monkeypatch.setattr(mgr.vnc, "start_vnc", AsyncMock())
    monkeypatch.setattr(mgr.vnc, "stop_vnc", AsyncMock())

    page = MagicMock()
    page.evaluate = AsyncMock()
    context = MagicMock()
    context.add_init_script = AsyncMock()
    context.pages = [page]
    context.on = MagicMock()
    monkeypatch.setattr(
        browser_manager_module,
        "launch_persistent_context_async",
        AsyncMock(return_value=context),
    )

    await mgr.launch(_profile_for_launch(tmp_path, clipboard_sync=True))

    context.add_init_script.assert_awaited_once()
    page.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_launch_adds_restore_last_session_arg_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend import browser_manager as browser_manager_module

    mgr = BrowserManager()
    monkeypatch.setattr(mgr.vnc, "start_vnc", AsyncMock())
    monkeypatch.setattr(mgr.vnc, "stop_vnc", AsyncMock())

    context = MagicMock()
    context.add_init_script = AsyncMock()
    context.pages = []
    context.on = MagicMock()
    launch_mock = AsyncMock(return_value=context)
    monkeypatch.setattr(browser_manager_module, "launch_persistent_context_async", launch_mock)

    await mgr.launch(_profile_for_launch(tmp_path, clipboard_sync=False))

    args = launch_mock.await_args.kwargs["args"]
    assert "--restore-last-session" in args


@pytest.mark.asyncio
async def test_launch_skips_restore_last_session_arg_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend import browser_manager as browser_manager_module

    mgr = BrowserManager()
    monkeypatch.setattr(mgr.vnc, "start_vnc", AsyncMock())
    monkeypatch.setattr(mgr.vnc, "stop_vnc", AsyncMock())

    context = MagicMock()
    context.add_init_script = AsyncMock()
    context.pages = []
    context.on = MagicMock()
    launch_mock = AsyncMock(return_value=context)
    monkeypatch.setattr(browser_manager_module, "launch_persistent_context_async", launch_mock)

    await mgr.launch(_profile_for_launch(tmp_path, clipboard_sync=False, restore_last_session=False))

    args = launch_mock.await_args.kwargs["args"]
    assert "--restore-last-session" not in args


@pytest.mark.asyncio
async def test_browser_closed_event_closes_context_and_stops_vnc(monkeypatch: pytest.MonkeyPatch):
    mgr = BrowserManager()
    monkeypatch.setattr(mgr.vnc, "stop_vnc", AsyncMock())

    context = MagicMock()
    context.close = AsyncMock()
    mgr.running["profile-1"] = RunningProfile(
        profile_id="profile-1",
        context=context,
        display=100,
        ws_port=6100,
        cdp_port=5100,
    )

    await mgr._on_browser_closed("profile-1")

    context.close.assert_awaited_once()
    mgr.vnc.stop_vnc.assert_awaited_once_with(100)
    assert "profile-1" not in mgr.running


@pytest.mark.asyncio
async def test_launch_failure_cleans_failed_playwright_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend import browser_manager as browser_manager_module

    mgr = BrowserManager()
    monkeypatch.setattr(mgr.vnc, "start_vnc", AsyncMock())
    monkeypatch.setattr(mgr.vnc, "stop_vnc", AsyncMock())
    cleanup = AsyncMock()
    monkeypatch.setattr(mgr, "_cleanup_failed_launch", cleanup)
    monkeypatch.setattr(browser_manager_module, "_direct_child_pids", MagicMock(return_value={123}))
    monkeypatch.setattr(
        browser_manager_module,
        "launch_persistent_context_async",
        AsyncMock(side_effect=TimeoutError("launch timed out")),
    )

    with pytest.raises(TimeoutError):
        await mgr.launch(_profile_for_launch(tmp_path, clipboard_sync=False))

    cleanup.assert_awaited_once()
    mgr.vnc.stop_vnc.assert_awaited_once_with(100)


@pytest.mark.asyncio
async def test_cleanup_failed_launch_targets_new_playwright_and_profile_chrome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from backend import browser_manager as browser_manager_module

    mgr = BrowserManager()
    user_data_dir = tmp_path / "profile"
    cmdlines = {
        10: "playwright/driver/package/cli.js run-driver",
        11: "playwright/driver/package/cli.js run-driver",
        12: f"chrome --user-data-dir={user_data_dir} --remote-debugging-port=5100",
        13: "unrelated-worker",
        20: "chrome --type=renderer",
    }
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(browser_manager_module, "_direct_child_pids", MagicMock(return_value=set(cmdlines)))
    monkeypatch.setattr(browser_manager_module, "_read_proc_cmdline", lambda pid: cmdlines[pid])
    monkeypatch.setattr(browser_manager_module, "_descendant_pids", lambda _pids: {20})
    monkeypatch.setattr(browser_manager_module, "_pid_exists", lambda _pid: False)
    monkeypatch.setattr(browser_manager_module, "_reap_exited_children", MagicMock(return_value=0))

    async def no_sleep(_seconds: float):
        return None

    monkeypatch.setattr(browser_manager_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(browser_manager_module.os, "kill", lambda pid, sig: killed.append((pid, sig)))

    await mgr._cleanup_failed_launch(user_data_dir, 5100, children_before_launch={10})

    term_pids = {pid for pid, sig in killed if sig == browser_manager_module.signal.SIGTERM}
    assert term_pids == {11, 12, 20}
    assert 10 not in term_pids
    assert 13 not in term_pids


# ── _allocate_cdp_port ───────────────────────────────────────────────────────


def test_allocate_cdp_port_returns_free_port():
    mgr = BrowserManager()
    port = mgr._allocate_cdp_port()
    assert BASE_CDP_PORT <= port < BASE_CDP_PORT + CDP_PORT_RANGE


def test_allocate_cdp_port_skips_occupied():
    mgr = BrowserManager()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", BASE_CDP_PORT))
        blocker.listen(1)
        port = mgr._allocate_cdp_port()
        assert port == BASE_CDP_PORT + 1


def test_allocate_cdp_port_advances_counter():
    mgr = BrowserManager()
    p1 = mgr._allocate_cdp_port()
    p2 = mgr._allocate_cdp_port()
    assert p2 == p1 + 1


def test_allocate_cdp_port_wraps_around():
    mgr = BrowserManager()
    mgr._next_cdp_port = BASE_CDP_PORT + CDP_PORT_RANGE - 1
    p1 = mgr._allocate_cdp_port()
    assert p1 == BASE_CDP_PORT + CDP_PORT_RANGE - 1
    p2 = mgr._allocate_cdp_port()
    assert p2 == BASE_CDP_PORT


def test_allocate_cdp_port_all_occupied_raises():
    mgr = BrowserManager()
    blockers = []
    try:
        for i in range(CDP_PORT_RANGE):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", BASE_CDP_PORT + i))
            s.listen(1)
            blockers.append(s)
        with pytest.raises(ValueError, match="No free CDP ports"):
            mgr._allocate_cdp_port()
    finally:
        for s in blockers:
            s.close()


# ── _init_profile_defaults ───────────────────────────────────────────────────


def test_init_creates_bookmarks(tmp_path: Path):
    _init_profile_defaults(tmp_path)
    bookmarks_path = tmp_path / "Default" / "Bookmarks"
    assert bookmarks_path.exists()
    data = json.loads(bookmarks_path.read_text())
    children = data["roots"]["bookmark_bar"]["children"]
    assert len(children) == 4  # 4 folders
    folder_names = {f["name"] for f in children}
    assert folder_names == {"Detection Tests", "Fingerprint", "Headers & TLS", "reCAPTCHA"}


def test_init_creates_preferences(tmp_path: Path):
    _init_profile_defaults(tmp_path)
    prefs_path = tmp_path / "Default" / "Preferences"
    assert prefs_path.exists()
    data = json.loads(prefs_path.read_text())
    assert "default_search_provider_data" in data
    assert "DuckDuckGo" in data["default_search_provider_data"]["template_url_data"]["short_name"]


def test_init_idempotent(tmp_path: Path):
    _init_profile_defaults(tmp_path)
    bookmarks_path = tmp_path / "Default" / "Bookmarks"
    original = bookmarks_path.read_text()

    # Write a sentinel to the file
    bookmarks_path.write_text("SENTINEL")

    # Second call should NOT overwrite (file already exists)
    _init_profile_defaults(tmp_path)
    assert bookmarks_path.read_text() == "SENTINEL"


def test_restore_last_session_defaults_to_enabled():
    assert _restore_last_session_enabled({}) is True
    assert _restore_last_session_enabled({"restore_last_session": None}) is True
    assert _restore_last_session_enabled({"restore_last_session": 1}) is True
    assert _restore_last_session_enabled({"restore_last_session": 0}) is False


def test_configure_session_restore_enables_preference_without_overwriting_existing(tmp_path: Path):
    prefs_path = tmp_path / "Default" / "Preferences"
    prefs_path.parent.mkdir(parents=True)
    prefs_path.write_text(json.dumps({"default_search_provider": {"enabled": True}}))

    _configure_session_restore(tmp_path, True)

    prefs = json.loads(prefs_path.read_text())
    assert prefs["session"]["restore_on_startup"] == 1
    assert prefs["default_search_provider"]["enabled"] is True


def test_configure_session_restore_disables_manager_forced_restore(tmp_path: Path):
    prefs_path = tmp_path / "Default" / "Preferences"
    prefs_path.parent.mkdir(parents=True)
    prefs_path.write_text(json.dumps({"session": {"restore_on_startup": 1}}))

    _configure_session_restore(tmp_path, False)

    prefs = json.loads(prefs_path.read_text())
    assert "session" not in prefs


def test_configure_session_restore_does_not_remove_custom_startup_urls(tmp_path: Path):
    prefs_path = tmp_path / "Default" / "Preferences"
    prefs_path.parent.mkdir(parents=True)
    prefs_path.write_text(json.dumps({
        "session": {
            "restore_on_startup": 4,
            "startup_urls": ["https://example.com"],
        }
    }))

    _configure_session_restore(tmp_path, False)

    prefs = json.loads(prefs_path.read_text())
    assert prefs["session"]["restore_on_startup"] == 4
    assert prefs["session"]["startup_urls"] == ["https://example.com"]
