"""Twitter scraping tool wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import PlatformName
from .base import BasePlatformTool, merge_inputs


class TwitterScraperTool(BasePlatformTool):
    """Tool wrapper around apidojo/tweet-scraper."""

    actor_id = 'apidojo/tweet-scraper'
    platform = PlatformName.TWITTER
    tool_name = 'twitter_lead_scraper'
    tool_description = (
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

        return merge_inputs(base_input, overrides)


__all__ = ["TwitterScraperTool"]
