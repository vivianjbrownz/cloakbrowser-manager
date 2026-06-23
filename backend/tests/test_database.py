"""Tests for SQLite CRUD operations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from backend import database as db


# ── init_db ──────────────────────────────────────────────────────────────────


def test_init_db_creates_tables(tmp_db: Path):
    with db.get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
    assert "profiles" in names
    assert "profile_tags" in names
    assert "account_assets" in names
    assert "research_domains" in names
    assert "research_keywords" in names
    assert "research_content_opportunities" in names


def test_init_db_idempotent(tmp_db: Path):
    # Second call should not crash
    db.init_db()
    with db.get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    assert len(tables) >= 2


# ── create_profile ───────────────────────────────────────────────────────────


def test_create_profile_minimal(tmp_db: Path):
    p = db.create_profile("Test")
    assert p["name"] == "Test"
    assert isinstance(p["id"], str) and len(p["id"]) == 36  # UUID
    assert 10000 <= p["fingerprint_seed"] <= 99999  # random default
    assert p["user_data_dir"].startswith(str(tmp_db))
    assert p["platform"] == "windows"
    assert p["created_at"] is not None
    assert p["updated_at"] is not None


def test_create_profile_with_seed(tmp_db: Path):
    p = db.create_profile("Seeded", fingerprint_seed=42)
    assert p["fingerprint_seed"] == 42


def test_create_profile_all_fields(tmp_db: Path):
    p = db.create_profile(
        "Full",
        fingerprint_seed=99999,
        proxy="http://host:8080",
        timezone="America/New_York",
        locale="en-US",
        platform="macos",
        user_agent="Test UA",
        screen_width=2560,
        screen_height=1440,
        gpu_vendor="NVIDIA",
        gpu_renderer="RTX 3070",
        hardware_concurrency=16,
        humanize=True,
        human_preset="careful",
        headless=True,
        geoip=True,
        color_scheme="dark",
        notes="test note",
    )
    assert p["proxy"] == "http://host:8080"
    assert p["platform"] == "macos"
    assert p["gpu_vendor"] == "NVIDIA"
    assert p["hardware_concurrency"] == 16
    assert p["humanize"] == 1  # SQLite stores bool as int
    assert p["human_preset"] == "careful"
    assert p["color_scheme"] == "dark"


def test_create_profile_with_tags(tmp_db: Path):
    p = db.create_profile(
        "Tagged",
        tags=[
            {"tag": "work", "color": "#ff0000"},
            {"tag": "dev", "color": "#00ff00"},
        ],
    )
    assert len(p["tags"]) == 2
    tag_names = {t["tag"] for t in p["tags"]}
    assert tag_names == {"work", "dev"}


def test_create_profile_defaults(tmp_db: Path):
    p = db.create_profile("Defaults")
    assert p["platform"] == "windows"
    assert p["screen_width"] == 1920
    assert p["screen_height"] == 1080
    assert p["humanize"] == 0
    assert p["headless"] == 0
    assert p["geoip"] == 0
    assert p["clipboard_sync"] == 0
    assert p["restore_last_session"] == 1
    assert p["is_archived"] == 0
    assert p["archived_at"] is None
    assert p["human_preset"] == "default"
    assert p["launch_args"] == []


def test_create_profile_with_restore_last_session_disabled(tmp_db: Path):
    p = db.create_profile("No Restore", restore_last_session=False)
    assert p["restore_last_session"] == 0


def test_create_profile_with_launch_args(tmp_db: Path):
    p = db.create_profile("WithArgs", launch_args=["--load-extension=/tmp/ext", "--disable-features=Foo"])
    assert p["launch_args"] == ["--load-extension=/tmp/ext", "--disable-features=Foo"]


def test_get_profile_launch_args_roundtrip(tmp_db: Path):
    p = db.create_profile("Args", launch_args=["--flag1", "--flag2"])
    fetched = db.get_profile(p["id"])
    assert fetched["launch_args"] == ["--flag1", "--flag2"]


def test_update_profile_launch_args(tmp_db: Path):
    p = db.create_profile("Args")
    assert p["launch_args"] == []
    updated = db.update_profile(p["id"], launch_args=["--new-flag"])
    assert updated["launch_args"] == ["--new-flag"]


def test_update_profile_launch_args_none_becomes_empty(tmp_db: Path):
    p = db.create_profile("Args", launch_args=["--flag"])
    updated = db.update_profile(p["id"], launch_args=None)
    assert updated["launch_args"] == []


def test_update_profile_restore_last_session(tmp_db: Path):
    p = db.create_profile("Restore")
    updated = db.update_profile(p["id"], restore_last_session=False)
    assert updated["restore_last_session"] == 0


def test_list_profiles_includes_launch_args(tmp_db: Path):
    db.create_profile("A", launch_args=["--arg1"])
    db.create_profile("B")
    profiles = db.list_profiles()
    args_by_name = {p["name"]: p["launch_args"] for p in profiles}
    assert args_by_name["A"] == ["--arg1"]
    assert args_by_name["B"] == []


def test_init_db_migrates_restore_last_session_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "profiles.db"
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)

    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                fingerprint_seed INTEGER NOT NULL,
                proxy TEXT,
                timezone TEXT,
                locale TEXT,
                platform TEXT DEFAULT 'windows',
                user_agent TEXT,
                screen_width INTEGER DEFAULT 1920,
                screen_height INTEGER DEFAULT 1080,
                gpu_vendor TEXT,
                gpu_renderer TEXT,
                hardware_concurrency INTEGER,
                humanize BOOLEAN DEFAULT 0,
                human_preset TEXT DEFAULT 'default',
                headless BOOLEAN DEFAULT 0,
                geoip BOOLEAN DEFAULT 0,
                clipboard_sync BOOLEAN DEFAULT 0,
                auto_launch BOOLEAN DEFAULT 0,
                color_scheme TEXT,
                notes TEXT,
                user_data_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO profiles (
                id, name, fingerprint_seed, user_data_dir, created_at, updated_at
            ) VALUES (
                'old-profile', 'Old', 12345, ?, '2026-06-05T00:00:00Z', '2026-06-05T00:00:00Z'
            )
        """, (str(tmp_path / "profiles" / "old-profile"),))
        conn.commit()

    db.init_db()

    profile = db.get_profile("old-profile")
    assert profile is not None
    assert profile["restore_last_session"] == 1
    assert profile["is_archived"] == 0
    assert profile["archived_at"] is None


# ── get_profile ──────────────────────────────────────────────────────────────


def test_get_profile_exists(sample_profile: dict):
    p = db.get_profile(sample_profile["id"])
    assert p is not None
    assert p["name"] == "Test Profile"
    assert p["fingerprint_seed"] == 12345


def test_get_profile_not_found(tmp_db: Path):
    assert db.get_profile("nonexistent") is None


def test_get_profile_includes_tags(tmp_db: Path):
    p = db.create_profile("Tagged", tags=[{"tag": "test", "color": "#aaa"}])
    fetched = db.get_profile(p["id"])
    assert len(fetched["tags"]) == 1
    assert fetched["tags"][0]["tag"] == "test"


# ── list_profiles ────────────────────────────────────────────────────────────


def test_list_profiles_empty(tmp_db: Path):
    assert db.list_profiles() == []


def test_list_profiles_ordered(tmp_db: Path):
    db.create_profile("First")
    time.sleep(0.01)  # ensure different timestamps
    db.create_profile("Second")
    profiles = db.list_profiles()
    assert len(profiles) == 2
    assert profiles[0]["name"] == "Second"  # newest first


def test_list_profiles_includes_tags(tmp_db: Path):
    db.create_profile("Tagged", tags=[{"tag": "x"}])
    profiles = db.list_profiles()
    assert len(profiles[0]["tags"]) == 1


# ── update_profile ───────────────────────────────────────────────────────────


def test_update_profile_partial(sample_profile: dict):
    updated = db.update_profile(sample_profile["id"], name="Renamed")
    assert updated["name"] == "Renamed"
    assert updated["fingerprint_seed"] == 12345  # unchanged


def test_update_profile_tags_replace(tmp_db: Path):
    p = db.create_profile("Tagged", tags=[{"tag": "old"}])
    updated = db.update_profile(p["id"], tags=[{"tag": "new", "color": "#fff"}])
    assert len(updated["tags"]) == 1
    assert updated["tags"][0]["tag"] == "new"


def test_update_profile_not_found(tmp_db: Path):
    assert db.update_profile("nonexistent", name="x") is None


def test_update_profile_no_fields(sample_profile: dict):
    # No-op update — profile should be unchanged
    updated = db.update_profile(sample_profile["id"])
    assert updated["name"] == sample_profile["name"]


def test_update_profile_updates_timestamp(sample_profile: dict):
    time.sleep(0.01)
    updated = db.update_profile(sample_profile["id"], name="New")
    assert updated["updated_at"] > sample_profile["created_at"]


# ── delete_profile ───────────────────────────────────────────────────────────


def test_delete_profile_exists(sample_profile: dict):
    assert db.delete_profile(sample_profile["id"]) is True
    assert db.get_profile(sample_profile["id"]) is None


def test_delete_profile_not_found(tmp_db: Path):
    assert db.delete_profile("nonexistent") is False


def test_delete_profile_cascades_tags(tmp_db: Path):
    p = db.create_profile("Tagged", tags=[{"tag": "a"}, {"tag": "b"}])
    db.delete_profile(p["id"])
    # Verify tags are gone
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM profile_tags WHERE profile_id = ?", (p["id"],)
        ).fetchall()
    assert len(rows) == 0


# ── archive / restore ───────────────────────────────────────────────────────


def test_archive_and_restore_profile_state(tmp_db: Path):
    profile = db.create_profile("Archive")
    archived = db.archive_profile(profile["id"])
    assert archived is not None
    assert archived["is_archived"] == 1
    assert archived["archived_at"] is not None
    assert archived["updated_at"] >= profile["updated_at"]

    restored = db.restore_profile(profile["id"])
    assert restored is not None
    assert restored["is_archived"] == 0
    assert restored["archived_at"] is None


def test_archive_restore_missing_profile_returns_none(tmp_db: Path):
    assert db.archive_profile("missing") is None
    assert db.restore_profile("missing") is None


# ── account asset inventory ─────────────────────────────────────────────────


def test_create_multiple_account_assets_for_profile(tmp_db: Path):
    profile = db.create_profile("Accounts")
    first = db.create_account_asset(
        profile["id"],
        platform="Facebook",
        account_identifier="fb-user",
        account_status="active",
    )
    second = db.create_account_asset(
        profile["id"],
        platform="x",
        account_identifier="@handle",
        account_status="warming",
    )
    assert first is not None
    assert second is not None
    assert first["platform"] == "facebook"
    accounts = db.list_account_assets(profile["id"])
    assert {a["account_identifier"] for a in accounts} == {"fb-user", "@handle"}


def test_create_account_asset_missing_profile_returns_none(tmp_db: Path):
    assert db.create_account_asset("missing", platform="facebook", account_identifier="fb-user") is None


def test_inventory_rows_include_profile_only_rows(tmp_db: Path):
    profile = db.create_profile("Empty")
    rows = db.list_inventory_rows()
    assert len(rows) == 1
    assert rows[0]["profile_id"] == profile["id"]
    assert rows[0]["is_profile_only"] is True
    assert rows[0]["account_id"] is None


def test_inventory_rows_hide_retired_by_default(tmp_db: Path):
    profile = db.create_profile("Retired")
    account = db.create_account_asset(
        profile["id"],
        platform="instagram",
        account_identifier="ig-user",
        account_status="retired",
    )
    assert account is not None
    default_rows = db.list_inventory_rows()
    all_rows = db.list_inventory_rows(include_retired=True)
    assert default_rows[0]["is_profile_only"] is True
    assert all_rows[0]["account_id"] == account["id"]
    assert all_rows[0]["account_status"] == "retired"


def test_inventory_rows_hide_archived_by_default(tmp_db: Path):
    profile = db.create_profile("Archived")
    account = db.create_account_asset(
        profile["id"],
        platform="instagram",
        account_identifier="ig-user",
        account_status="active",
    )
    assert account is not None
    db.archive_profile(profile["id"])

    default_rows = db.list_inventory_rows()
    archived_rows = db.list_inventory_rows(include_archived=True)
    assert all(row["profile_id"] != profile["id"] for row in default_rows)
    row = next(row for row in archived_rows if row["profile_id"] == profile["id"])
    assert row["account_id"] == account["id"]
    assert row["profile_is_archived"] is True
    assert row["profile_archived_at"] is not None


def test_update_account_asset(tmp_db: Path):
    profile = db.create_profile("Update Account")
    account = db.create_account_asset(profile["id"], platform="x", account_identifier="old")
    assert account is not None
    updated = db.update_account_asset(
        account["id"],
        account_identifier="new",
        account_status="limited",
        notes="needs review",
    )
    assert updated is not None
    assert updated["account_identifier"] == "new"
    assert updated["account_status"] == "limited"
    assert updated["notes"] == "needs review"


def test_delete_profile_cascades_account_assets(tmp_db: Path):
    profile = db.create_profile("Cascade")
    account = db.create_account_asset(profile["id"], platform="facebook", account_identifier="fb-user")
    assert account is not None
    db.delete_profile(profile["id"])
    assert db.get_account_asset(account["id"]) is None


# ── Research Center ─────────────────────────────────────────────────────────


def test_create_research_domain_scores_and_normalizes(tmp_db: Path):
    domain = db.create_research_domain(
        "https://www.clearwidgets.com/path",
        niche="SaaS",
        source="drop list",
    )
    assert domain["domain"] == "clearwidgets.com"
    assert domain["niche"] == "saas"
    assert domain["score"] >= 70
    assert domain["classification"] == "pass"
    assert domain["status"] == "pass"
    assert domain["scoring_signals"]["tld"] == "com"


def test_import_research_domains_counts_duplicates_and_invalid_rows(tmp_db: Path):
    db.create_research_domain("clearwidgets.com")
    result = db.import_research_domains(
        "domain\nclearwidgets.com\nbad domain\nneattools.io\n",
        niche="tools",
        source="txt",
    )
    assert result["created"] == 1
    assert result["skipped"] == 1
    assert result["rejected"] == 1
    created = db.get_research_domain_by_domain("neattools.io")
    assert created is not None
    assert created["niche"] == "tools"


def test_update_research_domain_manual_review(tmp_db: Path):
    domain = db.create_research_domain("clearwidgets.com")
    updated = db.update_research_domain(
        domain["id"],
        status="review",
        reviewer_label="good",
        notes="brandable shortlist",
    )
    assert updated is not None
    assert updated["status"] == "review"
    assert updated["reviewer_label"] == "good"
    assert updated["reviewed_at"] is not None
    assert updated["notes"] == "brandable shortlist"


def test_update_research_domain_wayback_merges_signals(tmp_db: Path):
    domain = db.create_research_domain("clearwidgets.com")
    updated = db.update_research_domain_wayback(domain["id"], {
        "history_exists": True,
        "snapshot_count": 12,
        "first_snapshot_at": "2018-01-01T00:00:00+00:00",
        "last_snapshot_at": "2025-01-01T00:00:00+00:00",
        "snapshot_span_days": 2557,
        "title_change_count": 1,
        "high_risk_terms": [],
    })
    assert updated is not None
    assert updated["wayback_history_exists"] is True
    assert updated["wayback_snapshot_count"] == 12
    assert updated["wayback_snapshot_span_days"] == 2557
    assert updated["score"] >= domain["score"]


def test_create_research_keywords_and_content_opportunity(tmp_db: Path):
    keywords = db.create_research_keywords(
        niche="hosting",
        seed_keywords=["best wordpress hosting", "wordpress hosting alternatives"],
        target_country="us",
        target_language="en",
    )
    assert len(keywords) == 2
    assert keywords[0]["target_country"] == "US"
    assert {item["article_type"] for item in keywords} == {"best", "alternatives"}

    idea = db.create_content_opportunity(
        keyword_id=keywords[0]["id"],
        niche=keywords[0]["niche"],
        keyword=keywords[0]["keyword"],
        article_type=keywords[0]["article_type"],
        priority=keywords[0]["priority"],
        monetization_type=keywords[0]["monetization_type"],
    )
    assert idea["keyword_id"] == keywords[0]["id"]
    assert idea["state"] == "idea"
    assert idea["monetization_type"] == "affiliate"
