"""Instagram scraping tool wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..models import PlatformName
from .base import BasePlatformTool, merge_inputs


class InstagramScraperTool(BasePlatformTool):
    """Tool wrapper around apify/instagram-scraper."""

    actor_id = 'apify/instagram-scraper'
    platform = PlatformName.INSTAGRAM
    tool_name = 'instagram_lead_scraper'
    tool_description = (
        'Scrape Instagram profiles, hashtags, or search results to identify potential leads. '
        'Targets can be profile URLs, @handles, #hashtags, or search keywords.'
    )

    @staticmethod
    def _categorize_targets(targets: List[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
        direct_urls: List[str] = []
        usernames: List[str] = []
        hashtags: List[str] = []
        searches: List[str] = []
        for target in targets:
            stripped = target.strip()
            if not stripped:
                continue
            if stripped.startswith("http"):
                direct_urls.append(stripped)
            elif stripped.startswith("@"):
                usernames.append(stripped.lstrip("@"))
            elif stripped.startswith("#"):
                hashtags.append(stripped.lstrip("#"))
            else:
                searches.append(stripped)
        return direct_urls, usernames, hashtags, searches

    @staticmethod
    def _base_payload(max_items: int, include_contact_info: bool) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"maxItems": max_items}
        if include_contact_info:
            payload["addUserInfo"] = True
        return payload

    def _dispatch(self, payload: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        run_input = merge_inputs(payload, overrides)
        if 'proxyConfiguration' not in run_input:
            proxy_configuration = self._default_proxy_configuration()
            if proxy_configuration:
                run_input['proxyConfiguration'] = proxy_configuration
        return self._call_actor(run_input)

    def _build_run_input(
        self,
        targets: List[str],
        max_items: int,
        include_contact_info: bool,
        overrides: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        direct_urls, usernames, hashtags, searches = self._categorize_targets(targets)
        base_input = self._base_payload(max_items=max_items, include_contact_info=include_contact_info)
        if direct_urls:
            base_input["directUrls"] = direct_urls
        if usernames:
            base_input["usernames"] = usernames
        if hashtags:
            base_input["hashtags"] = hashtags
        if searches:
            # Actor expects a single string; fall back to the first search term when using the generic builder.
            base_input["search"] = searches[0]
        return merge_inputs(base_input, overrides)

    # pylint: disable=arguments-differ
    def _run(  # type: ignore[override]
        self,
        targets: List[str],
        max_items: int = 25,
        include_contact_info: bool = True,
        input_overrides: Optional[Dict[str, Any]] = None,
    ):
        direct_urls, usernames, hashtags, searches = self._categorize_targets(targets)
        overrides = input_overrides or {}

        results: List[Dict[str, Any]] = []

        if direct_urls or usernames or hashtags:
            payload = self._base_payload(max_items=max_items, include_contact_info=include_contact_info)
            if direct_urls:
                payload["directUrls"] = direct_urls
            if usernames:
                payload["usernames"] = usernames
            if hashtags:
                payload["hashtags"] = hashtags
            results.extend(self._dispatch(payload, overrides))

        for search_query in searches:
            payload = self._base_payload(max_items=max_items, include_contact_info=include_contact_info)
            payload["search"] = search_query
            results.extend(self._dispatch(payload, overrides))

        if results:
            return results

        # If all targets were filtered out (e.g., empty strings), fall back to a single dispatch.
        fallback_payload = self._build_run_input(
            targets=targets,
            max_items=max_items,
            include_contact_info=include_contact_info,
            overrides=overrides,
        )
        if 'proxyConfiguration' not in fallback_payload:
            proxy_configuration = self._default_proxy_configuration()
            if proxy_configuration:
                fallback_payload['proxyConfiguration'] = proxy_configuration
        return self._call_actor(fallback_payload)


__all__ = ["InstagramScraperTool"]
