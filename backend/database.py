"""SQLite database operations for browser profiles."""

from __future__ import annotations

import datetime
import json
import random
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import research

DATA_DIR = Path("/data")
DB_PATH = DATA_DIR / "profiles.db"
ACCOUNT_STATUSES = {"new", "warming", "active", "limited", "blocked", "retired"}
DOMAIN_CLASSIFICATIONS = {"pass", "review", "reject"}
DOMAIN_REVIEW_LABELS = {"good", "risky", "bad"}
KEYWORD_INTENTS = {"informational", "commercial", "transactional", "navigational", "comparison"}
ARTICLE_TYPES = {"best", "vs", "review", "alternatives", "how_to_choose"}
OPPORTUNITY_PRIORITIES = {"high", "medium", "low"}
MONETIZATION_TYPES = {"affiliate", "lead_gen", "ads", "product", "none"}
CONTENT_STATES = {"idea", "approved", "drafting", "published"}


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
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
                restore_last_session BOOLEAN DEFAULT 1,
                is_archived BOOLEAN DEFAULT 0,
                archived_at TEXT,
                color_scheme TEXT,
                notes TEXT,
                user_data_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profile_tags (
                profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                color TEXT,
                PRIMARY KEY (profile_id, tag)
            );

            CREATE TABLE IF NOT EXISTS account_assets (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                account_identifier TEXT NOT NULL,
                email_or_phone TEXT,
                account_status TEXT NOT NULL DEFAULT 'new',
                platform_status_detail TEXT,
                purpose TEXT,
                last_used_at TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(profile_id, platform, account_identifier)
            );

            CREATE INDEX IF NOT EXISTS idx_account_assets_profile_id
                ON account_assets(profile_id);
            CREATE INDEX IF NOT EXISTS idx_account_assets_status_platform
                ON account_assets(account_status, platform);

            CREATE TABLE IF NOT EXISTS research_domains (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL UNIQUE,
                niche TEXT,
                source TEXT,
                status TEXT NOT NULL DEFAULT 'review',
                score INTEGER NOT NULL DEFAULT 0,
                classification TEXT NOT NULL DEFAULT 'review',
                notes TEXT,
                reviewer_label TEXT,
                reviewed_at TEXT,
                wayback_history_exists BOOLEAN DEFAULT 0,
                wayback_snapshot_count INTEGER DEFAULT 0,
                wayback_first_snapshot_at TEXT,
                wayback_last_snapshot_at TEXT,
                wayback_snapshot_span_days INTEGER DEFAULT 0,
                wayback_title_change_count INTEGER DEFAULT 0,
                wayback_high_risk_terms TEXT DEFAULT '[]',
                wayback_checked_at TEXT,
                scoring_signals TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_research_domains_status_score
                ON research_domains(status, score);
            CREATE INDEX IF NOT EXISTS idx_research_domains_niche
                ON research_domains(niche);

            CREATE TABLE IF NOT EXISTS research_keywords (
                id TEXT PRIMARY KEY,
                niche TEXT NOT NULL,
                seed_keywords TEXT NOT NULL DEFAULT '[]',
                target_country TEXT NOT NULL DEFAULT 'US',
                target_language TEXT NOT NULL DEFAULT 'en',
                keyword TEXT NOT NULL,
                intent TEXT NOT NULL,
                article_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                monetization_type TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(niche, target_country, target_language, keyword)
            );

            CREATE INDEX IF NOT EXISTS idx_research_keywords_niche_priority
                ON research_keywords(niche, priority);

            CREATE TABLE IF NOT EXISTS research_content_opportunities (
                id TEXT PRIMARY KEY,
                keyword_id TEXT REFERENCES research_keywords(id) ON DELETE SET NULL,
                niche TEXT,
                keyword TEXT NOT NULL,
                article_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                monetization_type TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'idea',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_research_content_state_priority
                ON research_content_opportunities(state, priority);
        """)
        conn.commit()

        # Migrations for existing databases
        cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()}
        if "clipboard_sync" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN clipboard_sync BOOLEAN DEFAULT 0")
            conn.commit()
        if "launch_args" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN launch_args TEXT DEFAULT '[]'")
            conn.commit()
        if "auto_launch" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN auto_launch BOOLEAN DEFAULT 0")
            conn.commit()
        if "restore_last_session" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN restore_last_session BOOLEAN DEFAULT 1")
            conn.commit()
        if "is_archived" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN is_archived BOOLEAN DEFAULT 0")
            conn.commit()
        if "archived_at" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN archived_at TEXT")
            conn.commit()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _clean_optional(value: str | None, *, lower: bool = False) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned.lower() if lower else cleaned


def _clean_required(value: str, field: str, *, lower: bool = False) -> str:
    cleaned = _clean_optional(value, lower=lower)
    if not cleaned:
        raise ValueError(f"{field} is required")
    return cleaned


def _clean_status(value: str | None) -> str:
    status = _clean_optional(value, lower=True) or "new"
    if status not in ACCOUNT_STATUSES:
        raise ValueError(f"Invalid account_status '{status}'")
    return status


def _account_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_profile(
    name: str,
    fingerprint_seed: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    profile_id = str(uuid.uuid4())
    seed = fingerprint_seed if fingerprint_seed is not None else random.randint(10000, 99999)
    user_data_dir = str(DATA_DIR / "profiles" / profile_id)
    now = _now()
    tags = fields.pop("tags", None) or []

    with get_db() as conn:
        conn.execute(
            """INSERT INTO profiles (
                id, name, fingerprint_seed, proxy, timezone, locale, platform,
                user_agent, screen_width, screen_height, gpu_vendor, gpu_renderer,
                hardware_concurrency, humanize, human_preset, headless, geoip,
                clipboard_sync, auto_launch, restore_last_session, is_archived, archived_at,
                color_scheme, launch_args, notes,
                user_data_dir, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id, name, seed,
                fields.get("proxy"),
                fields.get("timezone"),
                fields.get("locale"),
                fields.get("platform", "windows"),
                fields.get("user_agent"),
                fields.get("screen_width", 1920),
                fields.get("screen_height", 1080),
                fields.get("gpu_vendor"),
                fields.get("gpu_renderer"),
                fields.get("hardware_concurrency"),
                fields.get("humanize", False),
                fields.get("human_preset", "default"),
                fields.get("headless", False),
                fields.get("geoip", False),
                fields.get("clipboard_sync", False),
                fields.get("auto_launch", False),
                fields.get("restore_last_session", True),
                False,
                None,
                fields.get("color_scheme"),
                json.dumps(fields.get("launch_args") or []),
                fields.get("notes"),
                user_data_dir, now, now,
            ),
        )
        for t in tags:
            conn.execute(
                "INSERT INTO profile_tags (profile_id, tag, color) VALUES (?, ?, ?)",
                (profile_id, t["tag"], t.get("color")),
            )
        conn.commit()

    return get_profile(profile_id)  # type: ignore[return-value]


def get_profile(profile_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            return None
        profile = dict(row)
        profile["launch_args"] = json.loads(profile.get("launch_args") or "[]")
        tags = conn.execute(
            "SELECT tag, color FROM profile_tags WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
        profile["tags"] = [dict(t) for t in tags]
        return profile


def list_profiles() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
        profiles = []
        for row in rows:
            profile = dict(row)
            profile["launch_args"] = json.loads(profile.get("launch_args") or "[]")
            tags = conn.execute(
                "SELECT tag, color FROM profile_tags WHERE profile_id = ?",
                (profile["id"],),
            ).fetchall()
            profile["tags"] = [dict(t) for t in tags]
            profiles.append(profile)
        return profiles


def update_profile(profile_id: str, **fields: Any) -> dict[str, Any] | None:
    existing = get_profile(profile_id)
    if not existing:
        return None

    tags = fields.pop("tags", None)

    # Only update fields that were explicitly provided
    update_cols = []
    update_vals = []
    # Pre-serialize launch_args to JSON before the generic update loop
    if "launch_args" in fields:
        fields["launch_args"] = json.dumps(fields["launch_args"] or [])

    for col in (
        "name", "fingerprint_seed", "proxy", "timezone", "locale", "platform",
        "user_agent", "screen_width", "screen_height", "gpu_vendor", "gpu_renderer",
        "hardware_concurrency", "humanize", "human_preset", "headless", "geoip",
        "clipboard_sync", "auto_launch", "restore_last_session", "color_scheme", "launch_args", "notes",
    ):
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(fields[col])

    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(profile_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE profiles SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()

    if tags is not None:
        with get_db() as conn:
            conn.execute("DELETE FROM profile_tags WHERE profile_id = ?", (profile_id,))
            for t in tags:
                conn.execute(
                    "INSERT INTO profile_tags (profile_id, tag, color) VALUES (?, ?, ?)",
                    (profile_id, t["tag"], t.get("color")),
                )
            conn.commit()

    return get_profile(profile_id)


def delete_profile(profile_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0


def archive_profile(profile_id: str) -> dict[str, Any] | None:
    existing = get_profile(profile_id)
    if not existing:
        return None
    now = _now()
    with get_db() as conn:
        conn.execute(
            """UPDATE profiles
               SET is_archived = 1, archived_at = ?, updated_at = ?
               WHERE id = ?""",
            (now, now, profile_id),
        )
        conn.commit()
    return get_profile(profile_id)


def restore_profile(profile_id: str) -> dict[str, Any] | None:
    existing = get_profile(profile_id)
    if not existing:
        return None
    with get_db() as conn:
        conn.execute(
            """UPDATE profiles
               SET is_archived = 0, archived_at = NULL, updated_at = ?
               WHERE id = ?""",
            (_now(), profile_id),
        )
        conn.commit()
    return get_profile(profile_id)


# ── Account asset inventory ─────────────────────────────────────────────────


def create_account_asset(
    profile_id: str,
    platform: str,
    account_identifier: str,
    **fields: Any,
) -> dict[str, Any] | None:
    """Create an account asset tied to an existing browser profile."""
    now = _now()
    account_id = str(uuid.uuid4())
    platform = _clean_required(platform, "platform", lower=True)
    account_identifier = _clean_required(account_identifier, "account_identifier")
    status = _clean_status(fields.get("account_status"))

    with get_db() as conn:
        exists = conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not exists:
            return None
        conn.execute(
            """INSERT INTO account_assets (
                id, profile_id, platform, account_identifier, email_or_phone,
                account_status, platform_status_detail, purpose, last_used_at,
                notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id,
                profile_id,
                platform,
                account_identifier,
                _clean_optional(fields.get("email_or_phone")),
                status,
                _clean_optional(fields.get("platform_status_detail")),
                _clean_optional(fields.get("purpose")),
                _clean_optional(fields.get("last_used_at")),
                _clean_optional(fields.get("notes")),
                now,
                now,
            ),
        )
        conn.commit()
    return get_account_asset(account_id)


def get_account_asset(account_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM account_assets WHERE id = ?", (account_id,)).fetchone()
        return _account_from_row(row) if row else None


def find_account_asset(
    profile_id: str,
    platform: str,
    account_identifier: str,
) -> dict[str, Any] | None:
    platform = _clean_required(platform, "platform", lower=True)
    account_identifier = _clean_required(account_identifier, "account_identifier")
    with get_db() as conn:
        row = conn.execute(
            """SELECT * FROM account_assets
               WHERE profile_id = ? AND platform = ? AND account_identifier = ?""",
            (profile_id, platform, account_identifier),
        ).fetchone()
        return _account_from_row(row) if row else None


def list_account_assets(profile_id: str | None = None) -> list[dict[str, Any]]:
    with get_db() as conn:
        if profile_id is None:
            rows = conn.execute(
                "SELECT * FROM account_assets ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM account_assets
                   WHERE profile_id = ?
                   ORDER BY updated_at DESC, created_at DESC""",
                (profile_id,),
            ).fetchall()
        return [_account_from_row(row) for row in rows]


def update_account_asset(account_id: str, **fields: Any) -> dict[str, Any] | None:
    existing = get_account_asset(account_id)
    if not existing:
        return None

    update_cols = []
    update_vals = []
    cleaners = {
        "platform": lambda v: _clean_required(v, "platform", lower=True),
        "account_identifier": lambda v: _clean_required(v, "account_identifier"),
        "email_or_phone": _clean_optional,
        "account_status": _clean_status,
        "platform_status_detail": _clean_optional,
        "purpose": _clean_optional,
        "last_used_at": _clean_optional,
        "notes": _clean_optional,
    }
    for col, clean in cleaners.items():
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(clean(fields[col]))

    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(account_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE account_assets SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()

    return get_account_asset(account_id)


def delete_account_asset(account_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM account_assets WHERE id = ?", (account_id,))
        conn.commit()
        return cursor.rowcount > 0


def list_inventory_rows(include_retired: bool = False, include_archived: bool = False) -> list[dict[str, Any]]:
    profiles = list_profiles()
    accounts_by_profile: dict[str, list[dict[str, Any]]] = {}
    for account in list_account_assets():
        accounts_by_profile.setdefault(account["profile_id"], []).append(account)

    rows: list[dict[str, Any]] = []
    for profile in profiles:
        if profile.get("is_archived") and not include_archived:
            continue
        accounts = accounts_by_profile.get(profile["id"], [])
        visible_accounts = [
            a for a in accounts
            if include_retired or a["account_status"] != "retired"
        ]
        if not visible_accounts:
            rows.append(_inventory_row(profile, None))
            continue
        for account in visible_accounts:
            rows.append(_inventory_row(profile, account))
    return rows


def _inventory_row(profile: dict[str, Any], account: dict[str, Any] | None) -> dict[str, Any]:
    row = {
        "profile_id": profile["id"],
        "profile_name": profile["name"],
        "profile_proxy": profile.get("proxy"),
        "profile_platform": profile.get("platform"),
        "profile_tags": profile.get("tags", []),
        "profile_is_archived": bool(profile.get("is_archived")),
        "profile_archived_at": profile.get("archived_at"),
        "profile_status": "stopped",
        "profile_vnc_ws_port": None,
        "profile_cdp_url": None,
        "is_profile_only": account is None,
        "account_id": None,
        "platform": None,
        "account_identifier": None,
        "email_or_phone": None,
        "account_status": None,
        "platform_status_detail": None,
        "purpose": None,
        "last_used_at": None,
        "account_notes": None,
        "account_created_at": None,
        "account_updated_at": None,
    }
    if account:
        row.update({
            "is_profile_only": False,
            "account_id": account["id"],
            "platform": account["platform"],
            "account_identifier": account["account_identifier"],
            "email_or_phone": account.get("email_or_phone"),
            "account_status": account["account_status"],
            "platform_status_detail": account.get("platform_status_detail"),
            "purpose": account.get("purpose"),
            "last_used_at": account.get("last_used_at"),
            "account_notes": account.get("notes"),
            "account_created_at": account.get("created_at"),
            "account_updated_at": account.get("updated_at"),
        })
    return row


# ── Research Center ─────────────────────────────────────────────────────────


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _clean_enum(value: str | None, allowed: set[str], field: str, default: str | None = None) -> str | None:
    cleaned = _clean_optional(value, lower=True)
    if cleaned is None:
        return default
    if cleaned not in allowed:
        raise ValueError(f"Invalid {field} '{cleaned}'")
    return cleaned


def _domain_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["wayback_history_exists"] = bool(item.get("wayback_history_exists"))
    item["wayback_high_risk_terms"] = _json_load(item.get("wayback_high_risk_terms"), [])
    item["scoring_signals"] = _json_load(item.get("scoring_signals"), {})
    return item


def _keyword_from_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["seed_keywords"] = _json_load(item.get("seed_keywords"), [])
    return item


def _content_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_research_domain(
    domain: str,
    niche: str | None = None,
    source: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    normalized = research.normalize_domain(domain)
    scored = research.score_domain(normalized)
    domain_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO research_domains (
                id, domain, niche, source, status, score, classification, notes,
                scoring_signals, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                domain_id,
                normalized,
                _clean_optional(niche, lower=True),
                _clean_optional(source),
                scored.classification,
                scored.score,
                scored.classification,
                _clean_optional(notes),
                json.dumps(scored.signals),
                now,
                now,
            ),
        )
        conn.commit()
    created = get_research_domain(domain_id)
    if created is None:
        raise RuntimeError("Failed to create research domain")
    return created


def get_research_domain(domain_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM research_domains WHERE id = ?", (domain_id,)).fetchone()
        return _domain_from_row(row) if row else None


def get_research_domain_by_domain(domain: str) -> dict[str, Any] | None:
    normalized = research.normalize_domain(domain)
    with get_db() as conn:
        row = conn.execute("SELECT * FROM research_domains WHERE domain = ?", (normalized,)).fetchone()
        return _domain_from_row(row) if row else None


def list_research_domains(
    status: str | None = None,
    niche: str | None = None,
    min_score: int | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if status:
        status = _clean_enum(status, DOMAIN_CLASSIFICATIONS, "status")
        where.append("status = ?")
        params.append(status)
    if niche:
        where.append("niche = ?")
        params.append(_clean_optional(niche, lower=True))
    if min_score is not None:
        where.append("score >= ?")
        params.append(min_score)
    if q:
        term = f"%{q.strip().lower()}%"
        where.append("(domain LIKE ? OR niche LIKE ? OR source LIKE ? OR notes LIKE ?)")
        params.extend([term, term, term, term])
    sql = "SELECT * FROM research_domains"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score DESC, updated_at DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_domain_from_row(row) for row in rows]


def update_research_domain(domain_id: str, **fields: Any) -> dict[str, Any] | None:
    existing = get_research_domain(domain_id)
    if not existing:
        return None

    update_cols = []
    update_vals = []
    cleaners = {
        "niche": lambda v: _clean_optional(v, lower=True),
        "source": _clean_optional,
        "status": lambda v: _clean_enum(v, DOMAIN_CLASSIFICATIONS, "status"),
        "notes": _clean_optional,
        "reviewer_label": lambda v: _clean_enum(v, DOMAIN_REVIEW_LABELS, "reviewer_label"),
    }
    for col, clean in cleaners.items():
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(clean(fields[col]))

    if "reviewer_label" in fields and fields.get("reviewer_label") is not None:
        update_cols.append("reviewed_at = ?")
        update_vals.append(_now())

    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(domain_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE research_domains SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()
    return get_research_domain(domain_id)


def update_research_domain_wayback(domain_id: str, signals: dict[str, Any]) -> dict[str, Any] | None:
    existing = get_research_domain(domain_id)
    if not existing:
        return None
    scored = research.score_domain(existing["domain"], signals)
    status = existing["status"] if existing.get("reviewer_label") else scored.classification
    now = _now()
    with get_db() as conn:
        conn.execute(
            """UPDATE research_domains
               SET status = ?, score = ?, classification = ?, wayback_history_exists = ?,
                   wayback_snapshot_count = ?, wayback_first_snapshot_at = ?,
                   wayback_last_snapshot_at = ?, wayback_snapshot_span_days = ?,
                   wayback_title_change_count = ?, wayback_high_risk_terms = ?,
                   wayback_checked_at = ?, scoring_signals = ?, updated_at = ?
               WHERE id = ?""",
            (
                status,
                scored.score,
                scored.classification,
                bool(signals.get("history_exists")),
                int(signals.get("snapshot_count") or 0),
                signals.get("first_snapshot_at"),
                signals.get("last_snapshot_at"),
                int(signals.get("snapshot_span_days") or 0),
                int(signals.get("title_change_count") or 0),
                json.dumps(signals.get("high_risk_terms") or []),
                now,
                json.dumps(scored.signals),
                now,
                domain_id,
            ),
        )
        conn.commit()
    return get_research_domain(domain_id)


def import_research_domains(text: str, niche: str | None = None, source: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"created": 0, "updated": 0, "skipped": 0, "rejected": 0, "errors": []}
    for row_number, candidate in enumerate(research.parse_candidate_text(text), start=1):
        try:
            normalized = research.normalize_domain(candidate)
            if get_research_domain_by_domain(normalized):
                result["skipped"] += 1
                continue
            create_research_domain(normalized, niche=niche, source=source)
            result["created"] += 1
        except sqlite3.IntegrityError:
            result["skipped"] += 1
        except ValueError as exc:
            result["rejected"] += 1
            result["errors"].append({"row": row_number, "detail": str(exc)})
    return result


def create_research_keywords(
    niche: str,
    seed_keywords: list[str],
    target_country: str = "US",
    target_language: str = "en",
) -> list[dict[str, Any]]:
    niche = _clean_required(niche, "niche", lower=True)
    keywords = []
    for keyword in seed_keywords:
        cleaned = _clean_optional(keyword)
        if cleaned and cleaned not in keywords:
            keywords.append(cleaned)
    if not keywords:
        raise ValueError("seed_keywords is required")
    target_country = (_clean_optional(target_country) or "US").upper()
    target_language = (_clean_optional(target_language) or "en").lower()
    seed_json = json.dumps(keywords)
    now = _now()
    output: list[dict[str, Any]] = []
    with get_db() as conn:
        for keyword in keywords:
            keyword_id = str(uuid.uuid4())
            try:
                conn.execute(
                    """INSERT INTO research_keywords (
                        id, niche, seed_keywords, target_country, target_language,
                        keyword, intent, article_type, priority, monetization_type,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        keyword_id,
                        niche,
                        seed_json,
                        target_country,
                        target_language,
                        keyword,
                        research.infer_keyword_intent(keyword),
                        research.recommended_article_type(keyword),
                        research.recommended_priority(keyword),
                        research.recommended_monetization(keyword),
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                row = conn.execute(
                    """SELECT * FROM research_keywords
                       WHERE niche = ? AND target_country = ? AND target_language = ? AND keyword = ?""",
                    (niche, target_country, target_language, keyword),
                ).fetchone()
                if row:
                    output.append(_keyword_from_row(row))
                continue
            row = conn.execute("SELECT * FROM research_keywords WHERE id = ?", (keyword_id,)).fetchone()
            if row:
                output.append(_keyword_from_row(row))
        conn.commit()
    return output


def list_research_keywords(niche: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if niche:
        where.append("niche = ?")
        params.append(_clean_optional(niche, lower=True))
    if q:
        term = f"%{q.strip().lower()}%"
        where.append("(keyword LIKE ? OR niche LIKE ? OR notes LIKE ?)")
        params.extend([term, term, term])
    sql = "SELECT * FROM research_keywords"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, updated_at DESC"
    with get_db() as conn:
        return [_keyword_from_row(row) for row in conn.execute(sql, params).fetchall()]


def get_research_keyword(keyword_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM research_keywords WHERE id = ?", (keyword_id,)).fetchone()
        return _keyword_from_row(row) if row else None


def update_research_keyword(keyword_id: str, **fields: Any) -> dict[str, Any] | None:
    if not get_research_keyword(keyword_id):
        return None
    cleaners = {
        "intent": lambda v: _clean_enum(v, KEYWORD_INTENTS, "intent"),
        "article_type": lambda v: _clean_enum(v, ARTICLE_TYPES, "article_type"),
        "priority": lambda v: _clean_enum(v, OPPORTUNITY_PRIORITIES, "priority"),
        "monetization_type": lambda v: _clean_enum(v, MONETIZATION_TYPES, "monetization_type"),
        "notes": _clean_optional,
    }
    update_cols = []
    update_vals = []
    for col, clean in cleaners.items():
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(clean(fields[col]))
    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(keyword_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE research_keywords SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()
    return get_research_keyword(keyword_id)


def create_content_opportunity(
    keyword: str,
    keyword_id: str | None = None,
    niche: str | None = None,
    article_type: str | None = None,
    priority: str | None = None,
    monetization_type: str | None = None,
    state: str = "idea",
    notes: str | None = None,
) -> dict[str, Any]:
    keyword = _clean_required(keyword, "keyword")
    source_keyword = get_research_keyword(keyword_id) if keyword_id else None
    if keyword_id and not source_keyword:
        raise ValueError("keyword_id not found")
    niche = _clean_optional(niche, lower=True) or (source_keyword or {}).get("niche")
    article_type = _clean_enum(article_type, ARTICLE_TYPES, "article_type", research.recommended_article_type(keyword))
    priority = _clean_enum(priority, OPPORTUNITY_PRIORITIES, "priority", research.recommended_priority(keyword))
    monetization_type = _clean_enum(
        monetization_type,
        MONETIZATION_TYPES,
        "monetization_type",
        research.recommended_monetization(keyword),
    )
    state = _clean_enum(state, CONTENT_STATES, "state", "idea")
    opportunity_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO research_content_opportunities (
                id, keyword_id, niche, keyword, article_type, priority,
                monetization_type, state, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opportunity_id,
                keyword_id,
                niche,
                keyword,
                article_type,
                priority,
                monetization_type,
                state,
                _clean_optional(notes),
                now,
                now,
            ),
        )
        conn.commit()
    created = get_content_opportunity(opportunity_id)
    if created is None:
        raise RuntimeError("Failed to create content opportunity")
    return created


def get_content_opportunity(opportunity_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM research_content_opportunities WHERE id = ?",
            (opportunity_id,),
        ).fetchone()
        return _content_from_row(row) if row else None


def list_content_opportunities(
    state: str | None = None,
    niche: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if state:
        where.append("state = ?")
        params.append(_clean_enum(state, CONTENT_STATES, "state"))
    if niche:
        where.append("niche = ?")
        params.append(_clean_optional(niche, lower=True))
    if q:
        term = f"%{q.strip().lower()}%"
        where.append("(keyword LIKE ? OR niche LIKE ? OR notes LIKE ?)")
        params.extend([term, term, term])
    sql = "SELECT * FROM research_content_opportunities"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, updated_at DESC"
    with get_db() as conn:
        return [_content_from_row(row) for row in conn.execute(sql, params).fetchall()]


def update_content_opportunity(opportunity_id: str, **fields: Any) -> dict[str, Any] | None:
    if not get_content_opportunity(opportunity_id):
        return None
    cleaners = {
        "niche": lambda v: _clean_optional(v, lower=True),
        "keyword": lambda v: _clean_required(v, "keyword"),
        "article_type": lambda v: _clean_enum(v, ARTICLE_TYPES, "article_type"),
        "priority": lambda v: _clean_enum(v, OPPORTUNITY_PRIORITIES, "priority"),
        "monetization_type": lambda v: _clean_enum(v, MONETIZATION_TYPES, "monetization_type"),
        "state": lambda v: _clean_enum(v, CONTENT_STATES, "state"),
        "notes": _clean_optional,
    }
    update_cols = []
    update_vals = []
    for col, clean in cleaners.items():
        if col in fields:
            update_cols.append(f"{col} = ?")
            update_vals.append(clean(fields[col]))
    if update_cols:
        update_cols.append("updated_at = ?")
        update_vals.append(_now())
        update_vals.append(opportunity_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE research_content_opportunities SET {', '.join(update_cols)} WHERE id = ?",
                update_vals,
            )
            conn.commit()
    return get_content_opportunity(opportunity_id)
