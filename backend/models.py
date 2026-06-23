"""Pydantic models for profile CRUD operations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ProfileCreate(BaseModel):
    name: str
    fingerprint_seed: int | None = None  # random if not set
    proxy: str | None = None  # "http://user:pass@host:port" or null
    timezone: str | None = None  # "America/New_York"
    locale: str | None = None  # "en-US"
    platform: Literal["windows", "macos", "linux"] = "windows"
    user_agent: str | None = None
    screen_width: int = 1920
    screen_height: int = 1080
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = None
    humanize: bool = False
    human_preset: Literal["default", "careful"] = "default"
    headless: bool = False
    geoip: bool = False
    clipboard_sync: bool = False
    auto_launch: bool = False
    restore_last_session: bool = True
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    launch_args: list[str] = Field(default_factory=list)
    notes: str | None = None
    tags: list[TagCreate] | None = None


class ProfileUpdate(BaseModel):
    name: str | None = None
    fingerprint_seed: int | None = None
    proxy: str | None = Field(default=None)
    timezone: str | None = Field(default=None)
    locale: str | None = Field(default=None)
    platform: Literal["windows", "macos", "linux"] | None = None
    user_agent: str | None = Field(default=None)
    screen_width: int | None = None
    screen_height: int | None = None
    gpu_vendor: str | None = Field(default=None)
    gpu_renderer: str | None = Field(default=None)
    hardware_concurrency: int | None = Field(default=None)
    humanize: bool | None = None
    human_preset: Literal["default", "careful"] | None = None
    headless: bool | None = None
    geoip: bool | None = None
    clipboard_sync: bool | None = None
    auto_launch: bool | None = None
    restore_last_session: bool | None = None
    color_scheme: Literal["light", "dark", "no-preference"] | None = Field(default=None)
    launch_args: list[str] | None = None
    notes: str | None = Field(default=None)
    tags: list[TagCreate] | None = None


class TagCreate(BaseModel):
    tag: str
    color: str | None = None  # hex color


class TagResponse(BaseModel):
    tag: str
    color: str | None = None


AccountStatus = Literal["new", "warming", "active", "limited", "blocked", "retired"]


def _strip_optional(value: object) -> object:
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


class AccountAssetCreate(BaseModel):
    platform: str
    account_identifier: str
    email_or_phone: str | None = None
    account_status: AccountStatus = "new"
    platform_status_detail: str | None = None
    purpose: str | None = None
    last_used_at: str | None = None
    notes: str | None = None

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().lower()
        if not v:
            raise ValueError("platform is required")
        return v

    @field_validator("account_identifier", mode="before")
    @classmethod
    def normalize_account_identifier(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("account_identifier is required")
        return v

    @field_validator(
        "email_or_phone",
        "platform_status_detail",
        "purpose",
        "last_used_at",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, v: object) -> object:
        return _strip_optional(v)


class AccountAssetUpdate(BaseModel):
    platform: str | None = None
    account_identifier: str | None = None
    email_or_phone: str | None = Field(default=None)
    account_status: AccountStatus | None = None
    platform_status_detail: str | None = Field(default=None)
    purpose: str | None = Field(default=None)
    last_used_at: str | None = Field(default=None)
    notes: str | None = Field(default=None)

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().lower()
        if not v:
            raise ValueError("platform cannot be empty")
        return v

    @field_validator("account_identifier", mode="before")
    @classmethod
    def normalize_account_identifier(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("account_identifier cannot be empty")
        return v

    @field_validator(
        "email_or_phone",
        "platform_status_detail",
        "purpose",
        "last_used_at",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, v: object) -> object:
        return _strip_optional(v)


class AccountAssetResponse(BaseModel):
    id: str
    profile_id: str
    platform: str
    account_identifier: str
    email_or_phone: str | None = None
    account_status: AccountStatus
    platform_status_detail: str | None = None
    purpose: str | None = None
    last_used_at: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class InventoryRowResponse(BaseModel):
    profile_id: str
    profile_name: str
    profile_proxy: str | None = None
    profile_platform: str | None = None
    profile_tags: list[TagResponse] = []
    profile_is_archived: bool = False
    profile_archived_at: str | None = None
    profile_status: str = "stopped"
    profile_vnc_ws_port: int | None = None
    profile_cdp_url: str | None = None
    is_profile_only: bool = False
    account_id: str | None = None
    platform: str | None = None
    account_identifier: str | None = None
    email_or_phone: str | None = None
    account_status: AccountStatus | None = None
    platform_status_detail: str | None = None
    purpose: str | None = None
    last_used_at: str | None = None
    account_notes: str | None = None
    account_created_at: str | None = None
    account_updated_at: str | None = None


class CsvImportError(BaseModel):
    row: int
    detail: str


class CsvImportResult(BaseModel):
    dry_run: bool
    created: int
    updated: int
    skipped: int
    rejected: int
    errors: list[CsvImportError] = []


class ProfileResponse(BaseModel):
    id: str
    name: str
    fingerprint_seed: int
    proxy: str | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: str = "windows"
    user_agent: str | None = None
    screen_width: int = 1920
    screen_height: int = 1080
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = None
    humanize: bool = False
    human_preset: str = "default"
    headless: bool = False
    geoip: bool = False
    clipboard_sync: bool = False
    auto_launch: bool = False
    restore_last_session: bool = True
    is_archived: bool = False
    archived_at: str | None = None

    @field_validator("clipboard_sync", "restore_last_session", "is_archived", mode="before")
    @classmethod
    def coerce_boolean_defaults(cls, v: object, info) -> bool:
        if v is not None:
            return v
        return True if info.field_name == "restore_last_session" else False

    color_scheme: str | None = None
    launch_args: list[str] = []
    notes: str | None = None
    user_data_dir: str
    created_at: str
    updated_at: str
    tags: list[TagResponse] = []
    status: str = "stopped"  # "running" | "stopped"
    vnc_ws_port: int | None = None
    cdp_url: str | None = None


class LaunchResponse(BaseModel):
    profile_id: str
    status: str = "running"
    vnc_ws_port: int
    display: str
    cdp_url: str | None = None


class StatusResponse(BaseModel):
    running_count: int
    binary_version: str
    profiles_total: int


class ProfileStatusResponse(BaseModel):
    status: str  # "running" | "stopped"
    vnc_ws_port: int | None = None
    display: str | None = None
    cdp_url: str | None = None


class ClipboardRequest(BaseModel):
    text: str = Field(max_length=1_048_576)  # 1MB max


class ProfileOpenUrlRequest(BaseModel):
    url: str = Field(max_length=2048)

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("url is required")
        url = value.strip()
        if not url:
            raise ValueError("url is required")
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return url


class LoginRequest(BaseModel):
    token: str


DomainClassification = Literal["pass", "review", "reject"]
DomainReviewLabel = Literal["good", "risky", "bad"]
KeywordIntent = Literal["informational", "commercial", "transactional", "navigational", "comparison"]
ArticleType = Literal["best", "vs", "review", "alternatives", "how_to_choose"]
OpportunityPriority = Literal["high", "medium", "low"]
MonetizationType = Literal["affiliate", "lead_gen", "ads", "product", "none"]
ContentState = Literal["idea", "approved", "drafting", "published"]


class ResearchImportError(BaseModel):
    row: int
    detail: str


class ResearchImportResult(BaseModel):
    created: int
    updated: int = 0
    skipped: int
    rejected: int
    errors: list[ResearchImportError] = Field(default_factory=list)


class ResearchDomainCreate(BaseModel):
    domain: str
    niche: str | None = None
    source: str | None = None
    notes: str | None = None

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain_input(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("domain is required")
        return value

    @field_validator("niche", "source", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _strip_optional(value)


class ResearchDomainBulkCreate(BaseModel):
    text: str
    niche: str | None = None
    source: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("text is required")
        return value

    @field_validator("niche", "source", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _strip_optional(value)


class ResearchDomainUpdate(BaseModel):
    niche: str | None = Field(default=None)
    source: str | None = Field(default=None)
    status: DomainClassification | None = None
    notes: str | None = Field(default=None)
    reviewer_label: DomainReviewLabel | None = Field(default=None)

    @field_validator("niche", "source", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _strip_optional(value)


class ResearchDomainResponse(BaseModel):
    id: str
    domain: str
    niche: str | None = None
    source: str | None = None
    status: DomainClassification
    score: int
    classification: DomainClassification
    notes: str | None = None
    reviewer_label: DomainReviewLabel | None = None
    reviewed_at: str | None = None
    wayback_history_exists: bool = False
    wayback_snapshot_count: int = 0
    wayback_first_snapshot_at: str | None = None
    wayback_last_snapshot_at: str | None = None
    wayback_snapshot_span_days: int = 0
    wayback_title_change_count: int = 0
    wayback_high_risk_terms: list[str] = Field(default_factory=list)
    wayback_checked_at: str | None = None
    scoring_signals: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class WaybackSignalsResponse(BaseModel):
    domain: ResearchDomainResponse
    signals: dict[str, Any]


class ResearchProviderConfigResponse(BaseModel):
    providers: dict[str, dict[str, Any]]


class ResearchKeywordTaskCreate(BaseModel):
    niche: str
    seed_keywords: list[str]
    target_country: str = "US"
    target_language: str = "en"

    @field_validator("niche", mode="before")
    @classmethod
    def normalize_niche(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("niche is required")
        return value

    @field_validator("seed_keywords", mode="before")
    @classmethod
    def normalize_seed_keywords(cls, value: object) -> object:
        if isinstance(value, str):
            value = [part.strip() for part in value.replace(",", "\n").splitlines()]
        if not isinstance(value, list):
            raise ValueError("seed_keywords must be a list")
        keywords = [str(item).strip() for item in value if str(item).strip()]
        if not keywords:
            raise ValueError("seed_keywords is required")
        return keywords

    @field_validator("target_country", "target_language", mode="before")
    @classmethod
    def normalize_target(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value or None


class ResearchKeywordUpdate(BaseModel):
    intent: KeywordIntent | None = None
    article_type: ArticleType | None = None
    priority: OpportunityPriority | None = None
    monetization_type: MonetizationType | None = None
    notes: str | None = Field(default=None)

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        return _strip_optional(value)


class ResearchKeywordResponse(BaseModel):
    id: str
    niche: str
    seed_keywords: list[str]
    target_country: str
    target_language: str
    keyword: str
    intent: KeywordIntent
    article_type: ArticleType
    priority: OpportunityPriority
    monetization_type: MonetizationType
    notes: str | None = None
    created_at: str
    updated_at: str


class ContentOpportunityCreate(BaseModel):
    keyword_id: str | None = None
    niche: str | None = None
    keyword: str
    article_type: ArticleType | None = None
    priority: OpportunityPriority | None = None
    monetization_type: MonetizationType | None = None
    state: ContentState = "idea"
    notes: str | None = None

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("keyword is required")
        return value

    @field_validator("keyword_id", "niche", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _strip_optional(value)


class ContentOpportunityUpdate(BaseModel):
    niche: str | None = Field(default=None)
    keyword: str | None = None
    article_type: ArticleType | None = None
    priority: OpportunityPriority | None = None
    monetization_type: MonetizationType | None = None
    state: ContentState | None = None
    notes: str | None = Field(default=None)

    @field_validator("niche", "keyword", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _strip_optional(value)


class ContentOpportunityResponse(BaseModel):
    id: str
    keyword_id: str | None = None
    niche: str | None = None
    keyword: str
    article_type: ArticleType
    priority: OpportunityPriority
    monetization_type: MonetizationType
    state: ContentState
    notes: str | None = None
    created_at: str
    updated_at: str
