"""Facebook scraping tool wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import PlatformName
from .base import BasePlatformTool, merge_inputs


class FacebookScraperTool(BasePlatformTool):
    """Tool wrapper around apify/facebook-posts-scraper."""

    actor_id = 'apify/facebook-posts-scraper'
    platform = PlatformName.FACEBOOK
    tool_name = 'facebook_lead_scraper'
    tool_description = (
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

        return merge_inputs(base_input, overrides)


__all__ = ["FacebookScraperTool"]
