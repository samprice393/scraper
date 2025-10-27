"""Pydantic models used across the social media lead generation agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class PlatformName(str, Enum):
    """Supported social media platforms."""

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"


class PlatformTargetConfig(BaseModel):
    """Validated configuration for a single platform scrape request."""

    platform: PlatformName
    targets: List[str]
    max_items: int = Field(25, alias="maxItems", ge=1, description="Maximum items fetched per target.")
    include_contact_info: bool = Field(
        True,
        alias="includeContactInfo",
        description="Attempt to enrich with contact details when supported.",
    )
    input_overrides: Dict[str, object] = Field(
        default_factory=dict,
        alias="inputOverrides",
        description="Raw overrides merged into the Apify actor input.",
    )

    class Config:
        allow_population_by_field_name = True


class ContactInfo(BaseModel):
    """Optional contact details extracted for a lead."""

    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


class InstagramPost(BaseModel):
    """Subset of fields returned by the Instagram scraper."""

    id: Optional[str] = None
    url: Optional[HttpUrl] = None
    caption: Optional[str] = None
    timestamp: Optional[datetime] = None
    likes_count: Optional[int] = Field(default=None, alias="likesCount")
    comments_count: Optional[int] = Field(default=None, alias="commentsCount")
    owner_username: Optional[str] = Field(default=None, alias="ownerUsername")
    owner_full_name: Optional[str] = Field(default=None, alias="ownerFullName")

    class Config:
        allow_population_by_field_name = True


class FacebookPost(BaseModel):
    """Subset of fields returned by the Facebook posts scraper."""

    id: Optional[str] = None
    url: Optional[HttpUrl] = None
    text: Optional[str] = None
    created_time: Optional[datetime] = Field(default=None, alias="createdTime")
    reactions: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None

    class Config:
        allow_population_by_field_name = True


class TikTokVideo(BaseModel):
    """Subset of fields returned by the TikTok scraper."""

    id: Optional[str] = None
    url: Optional[HttpUrl] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = Field(default=None, alias="createTime")
    likes: Optional[int] = Field(default=None, alias="diggCount")
    comments: Optional[int] = Field(default=None, alias="commentCount")
    shares: Optional[int] = Field(default=None, alias="shareCount")
    views: Optional[int] = Field(default=None, alias="playCount")

    class Config:
        allow_population_by_field_name = True


class Tweet(BaseModel):
    """Subset of fields returned by the X/Twitter scraper."""

    id: Optional[str] = None
    url: Optional[HttpUrl] = None
    text: Optional[str] = None
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    retweets: Optional[int] = Field(default=None, alias="retweetCount")
    replies: Optional[int] = Field(default=None, alias="replyCount")
    likes: Optional[int] = Field(default=None, alias="favoriteCount")
    quotes: Optional[int] = Field(default=None, alias="quoteCount")

    class Config:
        allow_population_by_field_name = True


class LinkedInProfile(BaseModel):
    """Subset of fields returned by the LinkedIn profile scraper."""

    profile_id: Optional[str] = Field(default=None, alias="profileId")
    full_name: Optional[str] = Field(default=None, alias="fullName")
    headline: Optional[str] = None
    url: Optional[HttpUrl] = Field(default=None, alias="publicIdentifier")
    location: Optional[str] = None
    connections: Optional[int] = None
    about: Optional[str] = None
    contact: Optional[ContactInfo] = None

    class Config:
        allow_population_by_field_name = True


class SocialLead(BaseModel):
    """Unified representation of a potential lead across platforms."""

    platform: PlatformName
    name: Optional[str] = None
    profile_url: Optional[HttpUrl] = Field(default=None, alias="profileUrl")
    headline: Optional[str] = None
    recent_activity: Optional[str] = Field(default=None, alias="recentActivity")
    engagement_score: Optional[float] = Field(default=None, alias="engagementScore")
    contact: Optional[ContactInfo] = None
    notes: Optional[str] = None
    source_id: Optional[str] = Field(default=None, alias="sourceId")

    class Config:
        use_enum_values = True
        allow_population_by_field_name = True


class LeadGenerationResult(BaseModel):
    """Structured data pushed into the Apify dataset."""

    query: str
    platforms: List[PlatformName]
    lead_summary: str = Field(alias="leadSummary")
    leads: List[SocialLead] = Field(default_factory=list)
    raw_agent_response: str = Field(alias="rawAgentResponse")

    class Config:
        use_enum_values = True
        allow_population_by_field_name = True
