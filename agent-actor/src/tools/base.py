"""Shared helpers and base classes for platform scraping tools."""

from __future__ import annotations

import os
import uuid
from typing import Any, ClassVar, Dict, List, Optional, Type

from apify_client import ApifyClient
from crewai.tools.base_tool import BaseTool, EnvVar
from pydantic import BaseModel, ConfigDict, Field

from ..models import PlatformName


def merge_inputs(base: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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


_merge_inputs = merge_inputs


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

    def _default_proxy_configuration(self) -> Optional[Dict[str, Any]]:
        """Build the default residential proxy configuration if enabled."""
        use_proxy = (os.getenv('APIFY_USE_PROXY', 'true') or '').strip().lower()
        if use_proxy in {'0', 'false', 'no', 'off'}:
            return None

        groups_raw = os.getenv('APIFY_PROXY_GROUPS')
        if groups_raw is not None:
            groups = [group.strip() for group in groups_raw.split(',') if group.strip()]
        else:
            groups = ['RESIDENTIAL']

        if not groups:
            return None

        proxy_conf: Dict[str, Any] = {
            'useApifyProxy': True,
            'groups': groups,
        }

        country_env = os.getenv('APIFY_PROXY_COUNTRY_CODE') or os.getenv('APIFY_PROXY_COUNTRY')
        if country_env:
            proxy_conf['countryCode'] = country_env.strip().upper()

        session_mode = (os.getenv('APIFY_PROXY_SESSION_MODE') or 'rotate').strip().lower()
        if session_mode == 'sticky':
            session_prefix = (os.getenv('APIFY_PROXY_SESSION_PREFIX') or self.platform.value).strip()
            session_prefix = session_prefix or self.platform.value
            proxy_conf['session'] = f"{session_prefix}-{uuid.uuid4().hex}"

        return proxy_conf

    def _call_actor(self, run_input: Dict[str, Any]) -> List[Dict[str, Any]]:
        from apify import Actor as ApifyLogger

        try:
            ApifyLogger.log.info(f'Calling {self.actor_id} with input: {run_input}')
            run = self._client.actor(self.actor_id).call(run_input=run_input)
        except Exception as exc:  # noqa: BLE001
            msg = f'Failed to call Apify actor {self.actor_id}: {exc}'
            raise RuntimeError(msg) from exc

        if not run:
            ApifyLogger.log.warning(f'{self.actor_id} returned no run data')
            return []

        dataset_id = (
            run.get('defaultDatasetId')
            or run.get('default_dataset_id')
            or run.get('datasetId')
            or run.get('outputDatasetId')
        )

        if dataset_id:
            items = self._client.dataset(dataset_id).list_items(clean=True).items
            ApifyLogger.log.info(f'{self.actor_id} returned {len(items or [])} items from dataset {dataset_id}')
            if items:
                ApifyLogger.log.info(f'Sample item keys: {list(items[0].keys()) if items else "none"}')
            return items or []

        if (items := run.get('items')) is not None:
            ApifyLogger.log.info(f'{self.actor_id} returned {len(items)} items from run.items')
            return items

        output = run.get('output', {})
        if isinstance(output, dict) and 'items' in output:
            maybe_items = output.get('items') or []
            ApifyLogger.log.info(f'{self.actor_id} returned {len(maybe_items)} items from output.items')
            return maybe_items

        ApifyLogger.log.warning(f'{self.actor_id} completed but no items found in response')
        return []

    # pylint: disable=arguments-differ
    def _run(  # type: ignore[override]
        self,
        targets: List[str],
        max_items: int = 25,
        include_contact_info: bool = True,
        input_overrides: Optional[Dict[str, Any]] = None,
    ):
        run_input = self._build_run_input(
            targets=targets,
            max_items=max_items,
            include_contact_info=include_contact_info,
            overrides=input_overrides,
        )
        if 'proxyConfiguration' not in run_input:
            proxy_configuration = self._default_proxy_configuration()
            if proxy_configuration:
                run_input['proxyConfiguration'] = proxy_configuration
        return self._call_actor(run_input)


__all__ = ["BasePlatformTool", "PlatformToolInput", "merge_inputs"]
