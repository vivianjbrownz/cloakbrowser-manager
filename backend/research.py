"""Research Center scoring and no-key signal helpers."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
CDX_URL = "https://web.archive.org/cdx/search/cdx"

TRUSTED_TLDS = {
    "com": 15,
    "org": 11,
    "net": 10,
    "io": 10,
    "co": 9,
    "ai": 9,
    "app": 8,
    "dev": 8,
    "blog": 7,
    "info": 5,
}

TRADEMARK_TERMS = {
    "adidas",
    "amazon",
    "apple",
    "chatgpt",
    "facebook",
    "google",
    "instagram",
    "meta",
    "microsoft",
    "netflix",
    "nike",
    "openai",
    "paypal",
    "reddit",
    "stripe",
    "tesla",
    "tiktok",
    "twitter",
    "youtube",
}

HIGH_RISK_TERMS = {
    "adult",
    "bet",
    "casino",
    "cialis",
    "crypto",
    "escort",
    "gambling",
    "loan",
    "pills",
    "porn",
    "sex",
    "slot",
    "viagra",
    "xxx",
}

PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "backlinks": {
        "enabled": False,
        "provider": None,
        "ready_for": ["DataForSEO"],
        "requires_api_key": True,
    },
    "domain_info": {
        "enabled": False,
        "provider": None,
        "ready_for": ["WhoisXML API"],
        "requires_api_key": True,
    },
    "serp_keyword": {
        "enabled": False,
        "provider": None,
        "ready_for": ["DataForSEO"],
        "requires_api_key": True,
    },
}


class BacklinksProvider(Protocol):
    async def lookup_backlinks(self, domain: str) -> dict[str, Any]:
        """Return backlink signals for a domain."""


class DomainInfoProvider(Protocol):
    async def lookup_domain_info(self, domain: str) -> dict[str, Any]:
        """Return domain registration and DNS signals."""


class SerpKeywordProvider(Protocol):
    async def lookup_keywords(self, keyword: str, country: str, language: str) -> dict[str, Any]:
        """Return keyword/SERP signals."""


@dataclass(frozen=True)
class DomainScore:
    score: int
    classification: str
    signals: dict[str, Any]


def normalize_domain(value: str) -> str:
    domain = (value or "").strip().lower()
    if not domain:
        raise ValueError("domain is required")
    if "://" not in domain:
        domain = f"http://{domain}"
    parsed = urlparse(domain)
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    host = host.rstrip(".")
    if not host or not DOMAIN_RE.match(host):
        raise ValueError("domain must be a valid hostname")
    return host


def domain_label(domain: str) -> str:
    return domain.split(".")[0]


def domain_tld(domain: str) -> str:
    return domain.rsplit(".", 1)[-1]


def score_domain(domain: str, wayback: dict[str, Any] | None = None) -> DomainScore:
    label = domain_label(domain)
    tld = domain_tld(domain)
    reasons: list[str] = []
    penalties: list[str] = []
    score = 35

    length = len(label)
    if 5 <= length <= 12:
        score += 16
        reasons.append("short brandable length")
    elif 13 <= length <= 16:
        score += 10
        reasons.append("acceptable length")
    elif length < 4:
        score += 4
        penalties.append("very short label may be unclear")
    else:
        score -= 10
        penalties.append("long domain label")

    if "-" not in label:
        score += 8
        reasons.append("no hyphen")
    else:
        score -= min(label.count("-") * 8, 20)
        penalties.append("hyphenated label")

    digit_ratio = sum(1 for ch in label if ch.isdigit()) / max(length, 1)
    if digit_ratio == 0:
        score += 6
    elif digit_ratio <= 0.2:
        score -= 4
        penalties.append("some digits")
    else:
        score -= 16
        penalties.append("digit-heavy label")

    vowel_ratio = sum(1 for ch in label if ch in "aeiou") / max(sum(1 for ch in label if ch.isalpha()), 1)
    if 0.25 <= vowel_ratio <= 0.6:
        score += 8
        reasons.append("pronounceable pattern")
    else:
        score -= 8
        penalties.append("weak pronounceability")

    score += TRUSTED_TLDS.get(tld, 2)
    if tld in TRUSTED_TLDS:
        reasons.append(f".{tld} tld")
    else:
        penalties.append(f"low-confidence .{tld} tld")

    found_trademarks = sorted(term for term in TRADEMARK_TERMS if term in label)
    if found_trademarks:
        score -= 38
        penalties.append("possible trademark term")

    found_risk_terms = sorted(term for term in HIGH_RISK_TERMS if term in label)
    if found_risk_terms:
        score -= 28
        penalties.append("high-risk term in domain")

    if re.search(r"(.)\1{3,}", label):
        score -= 10
        penalties.append("repeated character pattern")
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", label):
        score -= 8
        penalties.append("consonant-heavy spam pattern")

    if wayback:
        if wayback.get("history_exists"):
            score += 10
            reasons.append("Wayback history exists")
        else:
            score -= 6
            penalties.append("no Wayback history")
        span_days = int(wayback.get("snapshot_span_days") or 0)
        if span_days >= 365:
            score += min(span_days // 365, 6)
            reasons.append("multi-year snapshot span")
        title_changes = int(wayback.get("title_change_count") or 0)
        if title_changes >= 5:
            score -= 8
            penalties.append("many homepage title changes")
        wayback_risk_terms = sorted(set(wayback.get("high_risk_terms") or []))
        if wayback_risk_terms:
            score -= 22
            penalties.append("high-risk terms in Wayback history")
            found_risk_terms = sorted(set(found_risk_terms) | set(wayback_risk_terms))

    score = max(0, min(100, score))
    if score >= 70 and not found_trademarks and not found_risk_terms:
        classification = "pass"
    elif score >= 45 and not found_trademarks:
        classification = "review"
    else:
        classification = "reject"

    return DomainScore(
        score=score,
        classification=classification,
        signals={
            "length": length,
            "tld": tld,
            "brandability_reasons": reasons,
            "penalties": penalties,
            "trademark_terms": found_trademarks,
            "high_risk_terms": found_risk_terms,
        },
    )


def infer_keyword_intent(keyword: str) -> str:
    text = keyword.lower()
    if any(token in text for token in ("best", "top", "alternative", "vs", "review")):
        return "commercial"
    if any(token in text for token in ("buy", "price", "coupon", "deal")):
        return "transactional"
    if any(token in text for token in ("how", "what", "why", "guide", "choose")):
        return "informational"
    return "commercial"


def recommended_article_type(keyword: str) -> str:
    text = keyword.lower()
    if " vs " in f" {text} " or "versus" in text:
        return "vs"
    if "alternative" in text:
        return "alternatives"
    if "review" in text:
        return "review"
    if "how" in text or "choose" in text:
        return "how_to_choose"
    return "best"


def recommended_priority(keyword: str) -> str:
    text = keyword.lower()
    if any(token in text for token in ("best", "review", "alternative", "vs")):
        return "high"
    if any(token in text for token in ("guide", "choose", "software", "tool")):
        return "medium"
    return "low"


def recommended_monetization(keyword: str) -> str:
    text = keyword.lower()
    if any(token in text for token in ("best", "review", "alternative", "vs", "software", "tool", "service")):
        return "affiliate"
    if any(token in text for token in ("agency", "consultant", "quote")):
        return "lead_gen"
    return "ads"


def parse_candidate_text(text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower() in {"domain", "url", "hostname"}:
            continue
        if "," in line:
            parts = [part.strip() for part in line.split(",") if part.strip()]
            if parts and parts[0].lower() in {"domain", "url", "hostname"}:
                continue
            candidates.extend(parts[:1])
        else:
            candidates.append(line)
    return candidates


def _parse_wayback_timestamp(value: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def _clean_title(html: str) -> str | None:
    match = TITLE_RE.search(html)
    if not match:
        return None
    title = TAG_RE.sub("", match.group(1))
    title = " ".join(title.split())
    return title[:160] if title else None


def _find_high_risk_terms(values: list[str]) -> list[str]:
    haystack = " ".join(values).lower()
    return sorted(term for term in HIGH_RISK_TERMS if term in haystack)


async def fetch_wayback_signals(domain: str) -> dict[str, Any]:
    normalized = normalize_domain(domain)
    params = {
        "url": normalized,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "collapse": "digest",
        "limit": "40",
    }
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        response = await client.get(CDX_URL, params=params)
        response.raise_for_status()
        payload = response.json()

        records = payload[1:] if isinstance(payload, list) and payload else []
        captures: list[dict[str, str]] = []
        for row in records:
            if not isinstance(row, list) or len(row) < 5:
                continue
            captures.append({
                "timestamp": str(row[0]),
                "original": str(row[1]),
                "statuscode": str(row[2]),
                "mimetype": str(row[3]),
                "digest": str(row[4]),
            })

        title_samples: list[str] = []
        sample_captures = []
        if captures:
            sample_captures = [captures[0], captures[len(captures) // 2], captures[-1]]
        seen_samples: set[tuple[str, str]] = set()
        for capture in sample_captures:
            key = (capture["timestamp"], capture["original"])
            if key in seen_samples:
                continue
            seen_samples.add(key)
            try:
                snapshot_url = f"https://web.archive.org/web/{capture['timestamp']}id_/{capture['original']}"
                snapshot = await client.get(snapshot_url)
                if snapshot.status_code < 400:
                    title = _clean_title(snapshot.text)
                    if title:
                        title_samples.append(title)
            except httpx.HTTPError:
                continue

    timestamps = [capture["timestamp"] for capture in captures]
    parsed_dates = [d for d in (_parse_wayback_timestamp(ts) for ts in timestamps) if d]
    first = min(parsed_dates) if parsed_dates else None
    last = max(parsed_dates) if parsed_dates else None
    span_days = (last - first).days if first and last else 0
    title_change_count = max(0, len(set(title_samples)) - 1)
    high_risk_terms = _find_high_risk_terms([normalized, *[c["original"] for c in captures], *title_samples])

    return {
        "history_exists": bool(captures),
        "snapshot_count": len(captures),
        "first_snapshot_at": first.isoformat() if first else None,
        "last_snapshot_at": last.isoformat() if last else None,
        "snapshot_span_days": span_days,
        "title_samples": title_samples,
        "title_change_count": title_change_count,
        "high_risk_terms": high_risk_terms,
    }
