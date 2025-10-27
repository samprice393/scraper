"""Custom Apify-based scraping tools that CrewAI agents can leverage."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from crewai_tools import ApifyActorsTool
from pydantic import BaseModel, Field

from .models import PlatformName


def _merge_inputs(base: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge user-provided overrides into the default actor input."""
    merged: Dict[str, Any] = {**base}
    if not overrides:
        return merged
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


class _PlatformToolInput(BaseModel):
    """Base schema shared by the platform tools."""

    targets: List[str] = Field(..., min_items=1, description="Profile URLs, handles, or search terms.")
    max_items: int = Field(25, alias="maxItems", ge=1, le=500, description="Maximum number of results per target.")
    include_contact_info: bool = Field(
        True,
        alias="includeContactInfo",
        description="Attempt to enrich with contact details when supported.",
    )
    input_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        alias="inputOverrides",
        description="Optional raw overrides merged into the Apify actor input.",
    )

    class Config:
        allow_population_by_field_name = True


class _BasePlatformTool(ApifyActorsTool):
    """Adds friendlier arguments on top of the generic Apify actors tool."""

    ArgsSchema = _PlatformToolInput

    def __init__(self, actor_name: str, platform: PlatformName, friendly_name: str, description: str) -> None:
        self.platform = platform
        super().__init__(actor_name)
        self.name = friendly_name
        self.description = description

        # Override the auto-generated schema with an ergonomic one.
        self.args_schema = self.ArgsSchema

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        raise NotImplementedError

    # pylint: disable=arguments-differ
    def _run(  # type: ignore[override]
        self,
        targets: List[str],
        maxItems: int = 25,  # noqa: N803 (consistent with schema alias)
        includeContactInfo: bool = True,  # noqa: N803
        inputOverrides: Optional[Dict[str, Any]] = None,  # noqa: N803
    ):
        run_input = self._build_run_input(
            targets=targets,
            max_items=maxItems,
            include_contact_info=includeContactInfo,
            overrides=inputOverrides,
        )
        return super()._run(run_input)


class InstagramScraperTool(_BasePlatformTool):
    """Tool wrapper around apify/instagram-scraper."""

    def __init__(self) -> None:
        super().__init__(
            actor_name="apify/instagram-scraper",
            platform=PlatformName.INSTAGRAM,
            friendly_name="instagram_lead_scraper",
            description=(
                "Scrape Instagram profiles, hashtags, or search results to identify potential leads. "
                "Targets can be profile URLs, @handles, #hashtags, or search keywords."
            ),
        )

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        direct_urls: List[str] = []
        usernames: List[str] = []
        hashtags: List[str] = []
        searches: List[str] = []
        for target in targets:
            stripped = target.strip()
            if stripped.startswith("http"):
                direct_urls.append(stripped)
            elif stripped.startswith("@"):
                usernames.append(stripped.lstrip("@"))
            elif stripped.startswith("#"):
                hashtags.append(stripped.lstrip("#"))
            else:
                searches.append(stripped)

        base_input: Dict[str, Any] = {"maxItems": max_items}
        if direct_urls:
            base_input["directUrls"] = direct_urls
        if usernames:
            base_input["usernames"] = usernames
        if hashtags:
            base_input["hashtags"] = hashtags
        if searches:
            base_input["search"] = searches
        if include_contact_info:
            base_input["addUserInfo"] = True

        return _merge_inputs(base_input, overrides)


class FacebookScraperTool(_BasePlatformTool):
    """Tool wrapper around apify/facebook-posts-scraper."""

    def __init__(self) -> None:
        super().__init__(
            actor_name="apify/facebook-posts-scraper",
            platform=PlatformName.FACEBOOK,
            friendly_name="facebook_lead_scraper",
            description=(
                "Scrape Facebook pages and posts for engagement insights. "
                "Targets should be Facebook page URLs or search keywords."
            ),
        )

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        start_urls = [{"url": target.strip()} for target in targets if target.strip().startswith("http")]
        search_terms = [target.strip() for target in targets if not target.strip().startswith("http")]

        base_input: Dict[str, Any] = {"maxItems": max_items}
        if start_urls:
            base_input["startUrls"] = start_urls
        if search_terms:
            base_input["searchTerms"] = search_terms
        if include_contact_info:
            base_input["shouldDownloadVideos"] = False

        return _merge_inputs(base_input, overrides)


class TikTokScraperTool(_BasePlatformTool):
    """Tool wrapper around clockworks/tiktok-scraper."""

    def __init__(self) -> None:
        super().__init__(
            actor_name="clockworks/tiktok-scraper",
            platform=PlatformName.TIKTOK,
            friendly_name="tiktok_lead_scraper",
            description=(
                "Scrape TikTok profiles, hashtags, or search results. "
                "Targets can be profile URLs, @handles, #hashtags, or keywords."
            ),
        )

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        profile_urls: List[str] = []
        handles: List[str] = []
        hashtags: List[str] = []
        keywords: List[str] = []
        for target in targets:
            stripped = target.strip()
            if stripped.startswith("http"):
                profile_urls.append(stripped)
            elif stripped.startswith("@"):
                handles.append(stripped.lstrip("@"))
            elif stripped.startswith("#"):
                hashtags.append(stripped.lstrip("#"))
            else:
                keywords.append(stripped)

        base_input: Dict[str, Any] = {"maxItems": max_items}
        if profile_urls:
            base_input["startUrls"] = [{"url": url} for url in profile_urls]
        if handles:
            base_input["handles"] = handles
        if hashtags:
            base_input["hashtags"] = hashtags
        if keywords:
            base_input["searchTerms"] = keywords
        if include_contact_info:
            base_input["shouldDownloadCaptions"] = True

        return _merge_inputs(base_input, overrides)


class TwitterScraperTool(_BasePlatformTool):
    """Tool wrapper around apidojo/tweet-scraper."""

    def __init__(self) -> None:
        super().__init__(
            actor_name="apidojo/tweet-scraper",
            platform=PlatformName.TWITTER,
            friendly_name="twitter_lead_scraper",
            description=(
                "Scrape X/Twitter timelines or search results. "
                "Targets can be @handles for timelines or raw search queries."
            ),
        )

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        handles: List[str] = []
        queries: List[str] = []
        for target in targets:
            stripped = target.strip()
            if stripped.startswith("@"):
                handles.append(stripped.lstrip("@"))
            else:
                queries.append(stripped)

        base_input: Dict[str, Any] = {
            "maxItems": max_items,
        }
        if handles:
            base_input["handles"] = handles
        if queries:
            base_input["queries"] = queries
        if include_contact_info:
            base_input["includeRetweet"] = True

        return _merge_inputs(base_input, overrides)


class LinkedInScraperTool(_BasePlatformTool):
    """Tool wrapper around dev_fusion/linkedin-profile-scraper."""

    def __init__(self) -> None:
        super().__init__(
            actor_name="dev_fusion/linkedin-profile-scraper",
            platform=PlatformName.LINKEDIN,
            friendly_name="linkedin_lead_scraper",
            description=(
                "Scrape LinkedIn profiles or company pages for lead details. "
                "Targets should be LinkedIn profile or company URLs."
            ),
        )

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        profile_urls = [target.strip() for target in targets if target.strip().startswith("http")]

        base_input: Dict[str, Any] = {"profileUrls": profile_urls or targets, "maxDepth": 1}
        if include_contact_info:
            base_input["shouldFetchContact"] = True
        base_input["maxItems"] = max_items

        return _merge_inputs(base_input, overrides)


__all__ = [
    "InstagramScraperTool",
    "FacebookScraperTool",
    "TikTokScraperTool",
    "TwitterScraperTool",
    "LinkedInScraperTool",
]
