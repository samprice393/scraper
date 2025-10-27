"""Custom Apify-based scraping tools that CrewAI agents can leverage."""

from __future__ import annotations

import os
from typing import Any, ClassVar, Dict, List, Optional, Type

from apify_client import ApifyClient
from crewai.tools.base_tool import BaseTool, EnvVar
from pydantic import BaseModel, ConfigDict, Field

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


class PlatformToolInput(BaseModel):
    """Base schema shared by the platform tools."""

    model_config = ConfigDict(populate_by_name=True)

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


class BasePlatformTool(BaseTool):
    """Adds friendlier arguments on top of the generic Apify actors tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    actor_id: ClassVar[str]
    platform: ClassVar[PlatformName]
    tool_name: ClassVar[str]
    tool_description: ClassVar[str]
    ArgsSchema: ClassVar[Type[PlatformToolInput]] = PlatformToolInput

    _client: ApifyClient

    def __init__(self) -> None:
        api_token = os.getenv('APIFY_API_TOKEN') or os.getenv('APIFY_TOKEN')
        if not api_token:
            raise ValueError('APIFY_API_TOKEN environment variable must be set for Apify access.')

        client = ApifyClient(token=api_token)
        super().__init__(
            name=self.tool_name,
            description=self.tool_description,
            args_schema=self.ArgsSchema,
            env_vars=[
                EnvVar(
                    name='APIFY_API_TOKEN',
                    description='API token for Apify platform access',
                    required=True,
                )
            ],
        )
        object.__setattr__(self, '_client', client)

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def _call_actor(self, run_input: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            run = self._client.actor(self.actor_id).call(run_input=run_input)
        except Exception as exc:  # noqa: BLE001
            msg = f'Failed to call Apify actor {self.actor_id}: {exc}'
            raise RuntimeError(msg) from exc

        if not run:
            return []

        dataset_id = (
            run.get('defaultDatasetId')
            or run.get('default_dataset_id')
            or run.get('datasetId')
            or run.get('outputDatasetId')
        )

        if dataset_id:
            items = self._client.dataset(dataset_id).list_items(clean=True).items
            return items or []

        if (items := run.get('items')) is not None:
            return items

        output = run.get('output', {})
        if isinstance(output, dict) and 'items' in output:
            maybe_items = output.get('items') or []
            return maybe_items

        return []

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
        return self._call_actor(run_input)


class InstagramScraperTool(BasePlatformTool):
    """Tool wrapper around apify/instagram-scraper."""

    actor_id: ClassVar[str] = 'apify/instagram-scraper'
    platform: ClassVar[PlatformName] = PlatformName.INSTAGRAM
    tool_name: ClassVar[str] = 'instagram_lead_scraper'
    tool_description: ClassVar[str] = (
        'Scrape Instagram profiles, hashtags, or search results to identify potential leads. '
        'Targets can be profile URLs, @handles, #hashtags, or search keywords.'
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


class FacebookScraperTool(BasePlatformTool):
    """Tool wrapper around apify/facebook-posts-scraper."""

    actor_id: ClassVar[str] = 'apify/facebook-posts-scraper'
    platform: ClassVar[PlatformName] = PlatformName.FACEBOOK
    tool_name: ClassVar[str] = 'facebook_lead_scraper'
    tool_description: ClassVar[str] = (
        'Scrape Facebook pages and posts for engagement insights. '
        'Targets should be Facebook page URLs or search keywords.'
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


class TikTokScraperTool(BasePlatformTool):
    """Tool wrapper around clockworks/tiktok-scraper."""

    actor_id: ClassVar[str] = 'clockworks/tiktok-scraper'
    platform: ClassVar[PlatformName] = PlatformName.TIKTOK
    tool_name: ClassVar[str] = 'tiktok_lead_scraper'
    tool_description: ClassVar[str] = (
        'Scrape TikTok profiles, hashtags, or search results. '
        'Targets can be profile URLs, @handles, #hashtags, or keywords.'
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


class TwitterScraperTool(BasePlatformTool):
    """Tool wrapper around apidojo/tweet-scraper."""

    actor_id: ClassVar[str] = 'apidojo/tweet-scraper'
    platform: ClassVar[PlatformName] = PlatformName.TWITTER
    tool_name: ClassVar[str] = 'twitter_lead_scraper'
    tool_description: ClassVar[str] = (
        'Scrape X/Twitter timelines or search results. '
        'Targets can be @handles for timelines or raw search queries.'
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


class LinkedInScraperTool(BasePlatformTool):
    """Tool wrapper around dev_fusion/linkedin-profile-scraper."""

    actor_id: ClassVar[str] = 'dev_fusion/linkedin-profile-scraper'
    platform: ClassVar[PlatformName] = PlatformName.LINKEDIN
    tool_name: ClassVar[str] = 'linkedin_lead_scraper'
    tool_description: ClassVar[str] = (
        'Scrape LinkedIn profiles or company pages for lead details. '
        'Targets should be LinkedIn profile or company URLs.'
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
    "BasePlatformTool",
    "InstagramScraperTool",
    "FacebookScraperTool",
    "TikTokScraperTool",
    "TwitterScraperTool",
    "LinkedInScraperTool",
]
