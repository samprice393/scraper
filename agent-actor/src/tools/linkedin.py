"""LinkedIn scraping tool wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import PlatformName
from .base import BasePlatformTool, merge_inputs


class LinkedInScraperTool(BasePlatformTool):
    """Tool wrapper around dev_fusion/linkedin-profile-scraper."""

    actor_id = 'dev_fusion/linkedin-profile-scraper'
    platform = PlatformName.LINKEDIN
    tool_name = 'linkedin_lead_scraper'
    tool_description = (
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

        return merge_inputs(base_input, overrides)


__all__ = ["LinkedInScraperTool"]
