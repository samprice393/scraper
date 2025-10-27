"""TikTok scraping tool wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import PlatformName
from .base import BasePlatformTool, merge_inputs


class TikTokScraperTool(BasePlatformTool):
    """Tool wrapper around clockworks/tiktok-scraper."""

    actor_id = 'clockworks/tiktok-scraper'
    platform = PlatformName.TIKTOK
    tool_name = 'tiktok_lead_scraper'
    tool_description = (
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

        return merge_inputs(base_input, overrides)


__all__ = ["TikTokScraperTool"]
