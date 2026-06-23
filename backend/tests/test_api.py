"""Tests for FastAPI routes via TestClient."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backend import main
from backend.browser_manager import RunningProfile


# ── Profile CRUD ─────────────────────────────────────────────────────────────


def test_list_profiles_empty(app_client: TestClient):
    resp = app_client.get("/api/profiles")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_profile(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={"name": "Test"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test"
    assert data["status"] == "stopped"
    assert data["restore_last_session"] is True
    assert "id" in data
    assert len(data["id"]) == 36  # UUID


def test_create_profile_with_all_fields(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={
        "name": "Full",
        "fingerprint_seed": 42,
        "proxy": "http://host:8080",
        "platform": "macos",
        "screen_width": 2560,
        "screen_height": 1440,
        "humanize": True,
        "human_preset": "careful",
        "restore_last_session": False,
        "tags": [{"tag": "work", "color": "#ff0000"}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["fingerprint_seed"] == 42
    assert data["platform"] == "macos"
    assert data["restore_last_session"] is False
    assert len(data["tags"]) == 1


def test_create_profile_invalid_platform(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={"name": "Bad", "platform": "android"})
    assert resp.status_code == 422


def test_get_profile(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Get Me"})
    pid = create.json()["id"]
    resp = app_client.get(f"/api/profiles/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Me"


def test_get_profile_not_found(app_client: TestClient):
    resp = app_client.get("/api/profiles/nonexistent")
    assert resp.status_code == 404


def test_update_profile(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Original"})
    pid = create.json()["id"]
    resp = app_client.put(f"/api/profiles/{pid}", json={"name": "Renamed", "restore_last_session": False})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["restore_last_session"] is False


def test_update_profile_not_found(app_client: TestClient):
    resp = app_client.put("/api/profiles/nonexistent", json={"name": "x"})
    assert resp.status_code == 404


def test_delete_profile(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Delete Me"})
    pid = create.json()["id"]
    resp = app_client.delete(f"/api/profiles/{pid}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # Confirm gone
    assert app_client.get(f"/api/profiles/{pid}").status_code == 404


def test_delete_profile_not_found(app_client: TestClient):
    resp = app_client.delete("/api/profiles/nonexistent")
    assert resp.status_code == 404


def test_delete_profile_stops_running(app_client: TestClient):
    """Deleting a running profile should stop it first."""
    create = app_client.post("/api/profiles", json={"name": "Running"})
    pid = create.json()["id"]

    # Inject mock running profile
    mock_running = MagicMock(spec=RunningProfile)
    mock_running.display = 100
    mock_running.ws_port = 6100
    mock_running.cdp_port = 5100
    main.browser_mgr.running[pid] = mock_running
    main.browser_mgr.stop = AsyncMock()

    resp = app_client.delete(f"/api/profiles/{pid}")
    assert resp.status_code == 200
    main.browser_mgr.stop.assert_called_once_with(pid)


def test_archive_profile_deletes_user_data_dir_and_preserves_inventory(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Archive Me"})
    pid = create.json()["id"]
    user_data_dir = Path(create.json()["user_data_dir"])
    user_data_dir.mkdir(parents=True)
    (user_data_dir / "Cookies").write_text("browser-data")

    account = app_client.post(f"/api/profiles/{pid}/accounts", json={
        "platform": "facebook",
        "account_identifier": "fb-user",
        "account_status": "active",
    }).json()

    resp = app_client.post(f"/api/profiles/{pid}/archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_archived"] is True
    assert data["archived_at"] is not None
    assert not user_data_dir.exists()

    assert app_client.get(f"/api/profiles/{pid}").status_code == 200
    default_rows = app_client.get("/api/inventory/rows").json()
    archived_rows = app_client.get("/api/inventory/rows?include_archived=true").json()
    assert all(row["profile_id"] != pid for row in default_rows)
    row = next(row for row in archived_rows if row["account_id"] == account["id"])
    assert row["profile_id"] == pid
    assert row["profile_is_archived"] is True


def test_archive_running_profile_conflict(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Running Archive"})
    pid = create.json()["id"]
    main.browser_mgr.running[pid] = MagicMock(spec=RunningProfile)
    resp = app_client.post(f"/api/profiles/{pid}/archive")
    assert resp.status_code == 409
    main.browser_mgr.running.pop(pid, None)


def test_restore_archived_profile(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Restore Me"})
    pid = create.json()["id"]
    archived = app_client.post(f"/api/profiles/{pid}/archive")
    assert archived.status_code == 200
    restored = app_client.post(f"/api/profiles/{pid}/restore")
    assert restored.status_code == 200
    assert restored.json()["is_archived"] is False
    assert restored.json()["archived_at"] is None


# ── Inventory / account assets ──────────────────────────────────────────────


def test_inventory_rows_profile_only(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Inventory Empty"})
    pid = create.json()["id"]
    resp = app_client.get("/api/inventory/rows")
    assert resp.status_code == 200
    rows = resp.json()
    row = next(r for r in rows if r["profile_id"] == pid)
    assert row["is_profile_only"] is True
    assert row["account_id"] is None


def test_create_account_asset_and_inventory_row(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Inventory Account"})
    pid = create.json()["id"]
    resp = app_client.post(f"/api/profiles/{pid}/accounts", json={
        "platform": "Facebook",
        "account_identifier": "fb-user",
        "account_status": "active",
        "purpose": "registration",
    })
    assert resp.status_code == 201
    account = resp.json()
    assert account["platform"] == "facebook"
    rows = app_client.get("/api/inventory/rows").json()
    row = next(r for r in rows if r["account_id"] == account["id"])
    assert row["profile_id"] == pid
    assert row["account_status"] == "active"
    assert row["purpose"] == "registration"


def test_update_and_delete_account_asset(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Account Edit"})
    pid = create.json()["id"]
    account = app_client.post(f"/api/profiles/{pid}/accounts", json={
        "platform": "x",
        "account_identifier": "@old",
    }).json()
    update = app_client.put(f"/api/accounts/{account['id']}", json={
        "account_identifier": "@new",
        "account_status": "limited",
    })
    assert update.status_code == 200
    assert update.json()["account_identifier"] == "@new"
    delete = app_client.delete(f"/api/accounts/{account['id']}")
    assert delete.status_code == 200
    assert app_client.delete(f"/api/accounts/{account['id']}").status_code == 404


def test_inventory_hides_retired_by_default(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Retired API"})
    pid = create.json()["id"]
    account = app_client.post(f"/api/profiles/{pid}/accounts", json={
        "platform": "instagram",
        "account_identifier": "ig-user",
        "account_status": "retired",
    }).json()
    default_rows = app_client.get("/api/inventory/rows").json()
    all_rows = app_client.get("/api/inventory/rows?include_retired=true").json()
    assert any(r["profile_id"] == pid and r["is_profile_only"] for r in default_rows)
    assert any(r["account_id"] == account["id"] for r in all_rows)


def test_inventory_csv_export(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "CSV Export"})
    pid = create.json()["id"]
    app_client.post(f"/api/profiles/{pid}/accounts", json={
        "platform": "facebook",
        "account_identifier": "fb-user",
    })
    resp = app_client.get("/api/inventory/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "profile_id,profile_name,profile_is_archived,profile_archived_at,proxy,account_id,platform" in resp.text
    assert "fb-user" in resp.text


def test_inventory_csv_import_dry_run_and_apply(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "CSV Import"})
    pid = create.json()["id"]
    csv_text = (
        "profile_id,profile_name,proxy,account_id,platform,account_identifier,"
        "email_or_phone,account_status,platform_status_detail,purpose,last_used_at,notes,tags\n"
        f"{pid},CSV Import,,,"
        "facebook,fb-user,user@example.com,active,,registration,2026-06-03,ready,\n"
    )
    dry = app_client.post("/api/inventory/import.csv?dry_run=true", content=csv_text)
    assert dry.status_code == 200
    assert dry.json()["created"] == 1
    assert app_client.get("/api/inventory/rows").json()[0]["account_id"] is None
    applied = app_client.post("/api/inventory/import.csv?dry_run=false", content=csv_text)
    assert applied.status_code == 200
    assert applied.json()["created"] == 1
    rows = app_client.get("/api/inventory/rows").json()
    assert any(r["platform"] == "facebook" and r["account_identifier"] == "fb-user" for r in rows)


def test_inventory_csv_import_rejects_sensitive_columns(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Sensitive CSV"})
    pid = create.json()["id"]
    csv_text = f"profile_id,platform,account_identifier,password\n{pid},x,@user,secret\n"
    resp = app_client.post("/api/inventory/import.csv?dry_run=false", content=csv_text)
    assert resp.status_code == 200
    data = resp.json()
    assert data["rejected"] == 1
    assert "Sensitive columns" in data["errors"][0]["detail"]


# ── Profile Status ───────────────────────────────────────────────────────────


def test_get_profile_status_stopped(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Status"})
    pid = create.json()["id"]
    resp = app_client.get(f"/api/profiles/{pid}/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


def test_get_profile_status_not_found(app_client: TestClient):
    resp = app_client.get("/api/profiles/nonexistent/status")
    assert resp.status_code == 404


# ── Launch / Stop ────────────────────────────────────────────────────────────


def test_launch_not_found(app_client: TestClient):
    resp = app_client.post("/api/profiles/nonexistent/launch")
    assert resp.status_code == 404


def test_launch_already_running(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Running"})
    pid = create.json()["id"]
    # Inject into running dict
    main.browser_mgr.running[pid] = MagicMock(spec=RunningProfile)
    resp = app_client.post(f"/api/profiles/{pid}/launch")
    assert resp.status_code == 409
    # Cleanup
    main.browser_mgr.running.pop(pid, None)


def test_launch_archived_profile_conflict(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "Archived Launch"})
    pid = create.json()["id"]
    archived = app_client.post(f"/api/profiles/{pid}/archive")
    assert archived.status_code == 200
    resp = app_client.post(f"/api/profiles/{pid}/launch")
    assert resp.status_code == 409
    assert "Restore archived profile" in resp.json()["detail"]


def test_launch_invalid_proxy_400(app_client: TestClient):
    """ValueError from browser_mgr.launch should map to 400."""
    create = app_client.post("/api/profiles", json={"name": "BadProxy"})
    pid = create.json()["id"]
    main.browser_mgr.launch = AsyncMock(side_effect=ValueError("Invalid proxy scheme 'ftp'"))
    resp = app_client.post(f"/api/profiles/{pid}/launch")
    assert resp.status_code == 400
    assert "ftp" in resp.json()["detail"]


def test_launch_failure_500(app_client: TestClient):
    """Generic exception from browser_mgr.launch should map to 500."""
    create = app_client.post("/api/profiles", json={"name": "Crash"})
    pid = create.json()["id"]
    main.browser_mgr.launch = AsyncMock(side_effect=RuntimeError("Xvnc failed"))
    resp = app_client.post(f"/api/profiles/{pid}/launch")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to launch browser"


def test_stop_not_running(app_client: TestClient):
    resp = app_client.post("/api/profiles/nonexistent/stop")
    assert resp.status_code == 404


# ── System Status ────────────────────────────────────────────────────────────


def test_system_status(app_client: TestClient):
    # Clear any leaked running profiles from prior tests
    main.browser_mgr.running.clear()

    # Create a profile so profiles_total > 0
    app_client.post("/api/profiles", json={"name": "Status Test"})
    resp = app_client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running_count"] == 0
    assert data["binary_version"] == "0.0.0-test"
    assert data["profiles_total"] >= 1


# ── Launch Args ─────────────────────────────────────────────────────────────


def test_profile_launch_args_default_empty(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={"name": "NoArgs"})
    assert resp.status_code == 201
    assert resp.json()["launch_args"] == []


def test_profile_launch_args_create(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={
        "name": "WithArgs",
        "launch_args": ["--load-extension=/data/ext", "--disable-features=Foo"],
    })
    assert resp.status_code == 201
    assert resp.json()["launch_args"] == ["--load-extension=/data/ext", "--disable-features=Foo"]


def test_profile_launch_args_update(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={"name": "UpdateArgs"})
    pid = resp.json()["id"]
    resp = app_client.put(f"/api/profiles/{pid}", json={"launch_args": ["--new-flag"]})
    assert resp.status_code == 200
    assert resp.json()["launch_args"] == ["--new-flag"]


def test_profile_launch_args_get(app_client: TestClient):
    resp = app_client.post("/api/profiles", json={
        "name": "GetArgs",
        "launch_args": ["--flag"],
    })
    pid = resp.json()["id"]
    resp = app_client.get(f"/api/profiles/{pid}")
    assert resp.json()["launch_args"] == ["--flag"]


# ── Clipboard Sync Setting ──────────────────────────────────────────────────


def test_profile_clipboard_sync_default_false(app_client: TestClient):
    """New profiles should keep continuous clipboard sync disabled by default."""
    resp = app_client.post("/api/profiles", json={"name": "Clipboard Test"})
    assert resp.status_code == 201
    assert resp.json()["clipboard_sync"] is False


def test_profile_clipboard_sync_update(app_client: TestClient):
    """clipboard_sync can be toggled per profile."""
    resp = app_client.post("/api/profiles", json={"name": "Clipboard Toggle"})
    pid = resp.json()["id"]
    resp = app_client.put(f"/api/profiles/{pid}", json={"clipboard_sync": False})
    assert resp.status_code == 200
    assert resp.json()["clipboard_sync"] is False
    resp = app_client.put(f"/api/profiles/{pid}", json={"clipboard_sync": True})
    assert resp.json()["clipboard_sync"] is True


# ── Clipboard ────────────────────────────────────────────────────────────────


def test_set_clipboard_not_running(app_client: TestClient):
    resp = app_client.post("/api/profiles/nonexistent/clipboard", json={"text": "hello"})
    assert resp.status_code == 404


def test_get_clipboard_not_running(app_client: TestClient):
    resp = app_client.get("/api/profiles/nonexistent/clipboard")
    assert resp.status_code == 404


def test_set_clipboard_success(app_client: TestClient):
    """Mock a running profile and patch xclip subprocess."""
    create = app_client.post("/api/profiles", json={"name": "Clip"})
    pid = create.json()["id"]

    # Inject mock running profile
    mock_running = MagicMock(spec=RunningProfile)
    mock_running.display = 100
    mock_running.cdp_port = 5100
    main.browser_mgr.running[pid] = mock_running

    # Mock asyncio.create_subprocess_exec to avoid actual xclip
    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.terminate = MagicMock()
    mock_proc.kill = MagicMock()

    with patch("backend.main.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
        resp = app_client.post(f"/api/profiles/{pid}/clipboard", json={"text": "test clipboard"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Cleanup
    main.browser_mgr.running.pop(pid, None)


@pytest.mark.asyncio
async def test_stop_xclip_for_display_terminates_and_waits():
    proc = MagicMock()
    proc.returncode = None
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=0)
    task = asyncio.create_task(asyncio.sleep(60))
    main._xclip_procs[100] = proc
    main._xclip_wait_tasks[100] = task

    await main._stop_xclip_for_display(100)

    proc.terminate.assert_called_once()
    proc.wait.assert_awaited()
    assert 100 not in main._xclip_procs
    assert 100 not in main._xclip_wait_tasks


def test_get_clipboard_from_page(app_client: TestClient):
    """Mock running profile with a page that has clipboard text."""
    create = app_client.post("/api/profiles", json={"name": "ClipRead"})
    pid = create.json()["id"]

    # Mock page with clipboard text
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="copied text")

    mock_context = MagicMock()
    mock_context.pages = [mock_page]

    mock_running = MagicMock(spec=RunningProfile)
    mock_running.display = 100
    mock_running.cdp_port = 5100
    mock_running.context = mock_context
    main.browser_mgr.running[pid] = mock_running

    resp = app_client.get(f"/api/profiles/{pid}/clipboard")
    assert resp.status_code == 200
    assert resp.json()["text"] == "copied text"

    # Cleanup
    main.browser_mgr.running.pop(pid, None)


# ── Response shape ───────────────────────────────────────────────────────────


def test_profile_response_has_status_field(app_client: TestClient):
    app_client.post("/api/profiles", json={"name": "Shape"})
    resp = app_client.get("/api/profiles")
    for profile in resp.json():
        assert "status" in profile
        assert profile["status"] in ("running", "stopped")


def test_profile_response_has_cdp_url_field(app_client: TestClient):
    """Stopped profiles should have cdp_url=null."""
    app_client.post("/api/profiles", json={"name": "CdpShape"})
    resp = app_client.get("/api/profiles")
    for profile in resp.json():
        assert "cdp_url" in profile
        if profile["status"] == "stopped":
            assert profile["cdp_url"] is None


def test_status_stopped_has_cdp_url_null(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "CdpStatus"})
    pid = create.json()["id"]
    resp = app_client.get(f"/api/profiles/{pid}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cdp_url"] is None


def test_running_profile_has_cdp_url(app_client: TestClient):
    """Running profile should have a cdp_url in list/get responses."""
    create = app_client.post("/api/profiles", json={"name": "CdpRunning"})
    pid = create.json()["id"]

    mock_running = MagicMock(spec=RunningProfile)
    mock_running.display = 100
    mock_running.ws_port = 6100
    mock_running.cdp_port = 5100
    mock_running.profile_id = pid
    main.browser_mgr.running[pid] = mock_running

    resp = app_client.get(f"/api/profiles/{pid}")
    data = resp.json()
    assert data["status"] == "running"
    assert data["cdp_url"] == f"/api/profiles/{pid}/cdp"

    # Cleanup
    main.browser_mgr.running.pop(pid, None)


def test_open_url_in_running_profile(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "UrlOpen"})
    pid = create.json()["id"]

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.bring_to_front = AsyncMock()

    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_running = MagicMock(spec=RunningProfile)
    mock_running.display = 100
    mock_running.ws_port = 6100
    mock_running.cdp_port = 5100
    mock_running.profile_id = pid
    mock_running.context = mock_context
    main.browser_mgr.running[pid] = mock_running

    resp = app_client.post(f"/api/profiles/{pid}/open-url", json={"url": "https://www.reddit.com/register/"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_context.new_page.assert_awaited_once()
    mock_page.goto.assert_awaited_once_with("https://www.reddit.com/register/", wait_until="domcontentloaded", timeout=15000)
    mock_page.bring_to_front.assert_awaited_once()

    main.browser_mgr.running.pop(pid, None)


def test_open_url_requires_running_profile(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "StoppedUrlOpen"})
    pid = create.json()["id"]

    resp = app_client.post(f"/api/profiles/{pid}/open-url", json={"url": "https://www.reddit.com/register/"})

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Profile must be running before opening URLs"


def test_open_url_rejects_non_http_url(app_client: TestClient):
    create = app_client.post("/api/profiles", json={"name": "BadUrlOpen"})
    pid = create.json()["id"]

    resp = app_client.post(f"/api/profiles/{pid}/open-url", json={"url": "javascript:alert(1)"})

    assert resp.status_code == 422


# ── CDP Proxy ───────────────────────────────────────────────────────────────


def test_cdp_json_version_not_running(app_client: TestClient):
    resp = app_client.get("/api/profiles/nonexistent/cdp/json/version")
    assert resp.status_code == 404


def test_cdp_json_list_not_running(app_client: TestClient):
    resp = app_client.get("/api/profiles/nonexistent/cdp/json/list")
    assert resp.status_code == 404


def _mock_running_profile(pid: str) -> MagicMock:
    """Create a mock RunningProfile and register it in browser_mgr."""
    mock = MagicMock(spec=RunningProfile)
    mock.display = 100
    mock.ws_port = 6100
    mock.cdp_port = 5100
    mock.profile_id = pid
    main.browser_mgr.running[pid] = mock
    return mock


def test_cdp_json_version_rewrites_ws_url(app_client: TestClient):
    """GET /cdp/json/version rewrites webSocketDebuggerUrl through our proxy."""
    create = app_client.post("/api/profiles", json={"name": "CdpVer"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    chrome_response = MagicMock()
    chrome_response.json.return_value = {
        "webSocketDebuggerUrl": "ws://127.0.0.1:5100/devtools/browser/abc-123",
        "Browser": "Chrome/145.0.0.0",
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=chrome_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = app_client.get(f"/api/profiles/{pid}/cdp/json/version")

    assert resp.status_code == 200
    data = resp.json()
    assert data["webSocketDebuggerUrl"] == f"ws://testserver/api/profiles/{pid}/cdp"
    assert data["Browser"] == "Chrome/145.0.0.0"
    main.browser_mgr.running.pop(pid, None)


def test_cdp_json_version_uses_wss_behind_https(app_client: TestClient):
    """X-Forwarded-Proto: https should produce wss:// URLs."""
    create = app_client.post("/api/profiles", json={"name": "CdpWss"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    chrome_response = MagicMock()
    chrome_response.json.return_value = {
        "webSocketDebuggerUrl": "ws://127.0.0.1:5100/devtools/browser/abc",
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=chrome_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = app_client.get(
            f"/api/profiles/{pid}/cdp/json/version",
            headers={"X-Forwarded-Proto": "https"},
        )

    assert resp.status_code == 200
    assert resp.json()["webSocketDebuggerUrl"].startswith("wss://")
    main.browser_mgr.running.pop(pid, None)


def test_cdp_json_list_rewrites_page_urls(app_client: TestClient):
    """GET /cdp/json/list rewrites per-page webSocketDebuggerUrl."""
    create = app_client.post("/api/profiles", json={"name": "CdpList"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    chrome_response = MagicMock()
    chrome_response.json.return_value = [
        {
            "id": "page1",
            "webSocketDebuggerUrl": "ws://127.0.0.1:5100/devtools/page/DEADBEEF",
        },
        {
            "id": "page2",
            "title": "No WS URL",
        },
    ]
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=chrome_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = app_client.get(f"/api/profiles/{pid}/cdp/json/list")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["webSocketDebuggerUrl"] == (
        f"ws://testserver/api/profiles/{pid}/cdp/devtools/page/DEADBEEF"
    )
    assert "webSocketDebuggerUrl" not in data[1]
    main.browser_mgr.running.pop(pid, None)


def test_cdp_json_version_chrome_unreachable(app_client: TestClient):
    """502 when Chrome CDP endpoint is down."""
    create = app_client.post("/api/profiles", json={"name": "CdpDown"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = app_client.get(f"/api/profiles/{pid}/cdp/json/version")

    assert resp.status_code == 502
    main.browser_mgr.running.pop(pid, None)


# ── Research Center ─────────────────────────────────────────────────────────


def test_research_domain_crud_and_bulk_import(app_client: TestClient):
    create = app_client.post("/api/research/domains", json={
        "domain": "https://www.clearwidgets.com/path",
        "niche": "SaaS",
        "source": "manual",
    })
    assert create.status_code == 201
    domain = create.json()
    assert domain["domain"] == "clearwidgets.com"
    assert domain["classification"] == "pass"

    bulk = app_client.post("/api/research/domains/bulk", json={
        "text": "domain\nclearwidgets.com\nneattools.io\nbad domain\n",
        "niche": "tools",
        "source": "csv",
    })
    assert bulk.status_code == 200
    assert bulk.json()["created"] == 1
    assert bulk.json()["skipped"] == 1
    assert bulk.json()["rejected"] == 1

    update = app_client.put(f"/api/research/domains/{domain['id']}", json={
        "status": "review",
        "reviewer_label": "good",
        "notes": "shortlist",
    })
    assert update.status_code == 200
    assert update.json()["reviewer_label"] == "good"
    assert update.json()["reviewed_at"] is not None

    rows = app_client.get("/api/research/domains?q=neattools").json()
    assert len(rows) == 1
    assert rows[0]["domain"] == "neattools.io"


def test_research_wayback_refresh_uses_no_key_signals(app_client: TestClient):
    create = app_client.post("/api/research/domains", json={"domain": "clearwidgets.com"})
    domain = create.json()
    signals = {
        "history_exists": True,
        "snapshot_count": 8,
        "first_snapshot_at": "2019-01-01T00:00:00+00:00",
        "last_snapshot_at": "2025-01-01T00:00:00+00:00",
        "snapshot_span_days": 2192,
        "title_samples": ["Clear Widgets"],
        "title_change_count": 0,
        "high_risk_terms": [],
    }
    with patch("backend.main.research.fetch_wayback_signals", AsyncMock(return_value=signals)):
        resp = app_client.post(f"/api/research/domains/{domain['id']}/wayback")

    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"]["wayback_history_exists"] is True
    assert data["domain"]["wayback_snapshot_count"] == 8
    assert data["signals"]["snapshot_span_days"] == 2192


def test_research_keywords_and_content_opportunities(app_client: TestClient):
    keywords = app_client.post("/api/research/keywords", json={
        "niche": "hosting",
        "seed_keywords": ["best wordpress hosting", "wordpress hosting alternatives"],
        "target_country": "US",
        "target_language": "en",
    })
    assert keywords.status_code == 201
    rows = keywords.json()
    assert len(rows) == 2
    assert rows[0]["monetization_type"] == "affiliate"

    idea = app_client.post("/api/research/content-opportunities", json={
        "keyword_id": rows[0]["id"],
        "niche": rows[0]["niche"],
        "keyword": rows[0]["keyword"],
        "article_type": rows[0]["article_type"],
        "priority": rows[0]["priority"],
        "monetization_type": rows[0]["monetization_type"],
    })
    assert idea.status_code == 201
    assert idea.json()["state"] == "idea"

    updated = app_client.put(f"/api/research/content-opportunities/{idea.json()['id']}", json={
        "state": "approved",
    })
    assert updated.status_code == 200
    assert updated.json()["state"] == "approved"


# ── WebSocket Origin Validation ──────────────────────────────────────────────


def test_vnc_ws_rejects_cross_origin(app_client: TestClient):
    """VNC WebSocket should reject cross-origin browser connections."""
    create = app_client.post("/api/profiles", json={"name": "OriginVnc"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    with pytest.raises(Exception):
        with app_client.websocket_connect(
            f"/api/profiles/{pid}/vnc",
            headers={"origin": "http://evil.com"},
        ):
            pass
    main.browser_mgr.running.pop(pid, None)


def test_cdp_ws_rejects_cross_origin(app_client: TestClient):
    """CDP WebSocket should reject cross-origin browser connections."""
    create = app_client.post("/api/profiles", json={"name": "OriginCdp"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    with pytest.raises(Exception):
        with app_client.websocket_connect(
            f"/api/profiles/{pid}/cdp",
            headers={"origin": "http://evil.com"},
        ):
            pass
    main.browser_mgr.running.pop(pid, None)


def test_ws_allows_same_origin(app_client: TestClient):
    """WebSocket from same origin should pass Origin check (not get 4403)."""
    create = app_client.post("/api/profiles", json={"name": "OriginOk"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    # Same-origin passes Origin check. VNC proxy then fails to connect to
    # real KasmVNC (not running), but that's fine — we're testing Origin only.
    # The connection is accepted (no 4403), then closes due to VNC connect error.
    try:
        with app_client.websocket_connect(
            f"/api/profiles/{pid}/vnc",
            headers={"origin": "http://testserver"},
        ) as ws:
            pass  # connection accepted = Origin check passed
    except Exception as exc:
        # Any error other than 4403 means Origin check passed
        assert "4403" not in str(exc)
    main.browser_mgr.running.pop(pid, None)


def test_ws_allows_no_origin(app_client: TestClient):
    """WebSocket without Origin header (Playwright/Puppeteer) should be accepted."""
    create = app_client.post("/api/profiles", json={"name": "NoOrigin"})
    pid = create.json()["id"]
    _mock_running_profile(pid)

    try:
        with app_client.websocket_connect(f"/api/profiles/{pid}/vnc") as ws:
            pass
    except Exception as exc:
        assert "4403" not in str(exc)
    main.browser_mgr.running.pop(pid, None)
