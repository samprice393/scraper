"""Module defines the main entry point for the Apify Actor.

Feel free to modify this file to suit your specific needs.

To build Apify Actors, utilize the Apify SDK toolkit, read more at the official documentation:
https://docs.apify.com/sdk/python
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Set, Type

from apify import Actor
from crewai import Agent, Crew, Task
from dotenv import load_dotenv
from pydantic import ValidationError

from .models import (
    LeadGenerationResult,
    PlatformName,
    PlatformTargetConfig,
    SocialLead,
)
from .tools import (
    FacebookScraperTool,
    InstagramScraperTool,
    LinkedInScraperTool,
    TikTokScraperTool,
    TwitterScraperTool,
    BasePlatformTool,
)


load_dotenv('.env.local')
load_dotenv()


TOOL_BUILDERS: Dict[PlatformName, Type[BasePlatformTool]] = {
    PlatformName.INSTAGRAM: InstagramScraperTool,
    PlatformName.FACEBOOK: FacebookScraperTool,
    PlatformName.TIKTOK: TikTokScraperTool,
    PlatformName.TWITTER: TwitterScraperTool,
    PlatformName.LINKEDIN: LinkedInScraperTool,
}


async def main() -> None:
    """Actor entry point."""
    async with Actor:
        apify_token = os.getenv('APIFY_TOKEN')
        if not apify_token:
            raise ValueError('APIFY_TOKEN environment variable must be set for authentication.')
        # Set the env var that ApifyActorsTool expects
        os.environ['APIFY_API_TOKEN'] = apify_token

        # Charge for Actor start
        await Actor.charge('actor-start')

        actor_input = await Actor.get_input() or {}
        query = actor_input.get('query')
        model_name = actor_input.get('modelName', 'gpt-4o-mini')
        debug = bool(actor_input.get('debug', False))
        max_leads = int(actor_input.get('maxLeads', 100))
        raw_platforms = actor_input.get('platforms', [])

        if not query:
            raise ValueError('Missing "query" attribute in input!')
        if not raw_platforms:
            raise ValueError('At least one platform configuration is required.')

        platform_configs: List[PlatformTargetConfig] = []
        for raw_platform in raw_platforms:
            try:
                platform_configs.append(PlatformTargetConfig.model_validate(raw_platform))
            except ValidationError as exc:
                raise ValueError(f'Invalid platform configuration: {exc}') from exc

        requested_platforms: List[PlatformName] = [cfg.platform for cfg in platform_configs]
        unique_platforms: Set[PlatformName] = set(requested_platforms)

        Actor.log.info('Requested platforms: %s', ', '.join(platform.value for platform in unique_platforms))

        tool_instances = []
        for platform in unique_platforms:
            tool_cls = TOOL_BUILDERS.get(platform)
            if not tool_cls:
                Actor.log.warning('No tool configured for platform: %s', platform.value)
                continue
            tool_instances.append(tool_cls())

        if not tool_instances:
            raise ValueError('No tools available for the requested platforms.')

        platform_prompt_lines = [
            f"- {cfg.platform.value}: targets={cfg.targets}, maxItems={cfg.max_items}, "
            f"includeContactInfo={cfg.include_contact_info}"
            for cfg in platform_configs
        ]
        platform_prompt = '\n'.join(platform_prompt_lines)

        task_description = (
            f"{query}\n\n"
            "Focus on generating high-quality leads from the following platform configs:\n"
            f"{platform_prompt}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "1. Use the provided tools to scrape data from each platform\n"
            "2. For Instagram: The tool returns POSTS with owner information. Extract UNIQUE USERS from these posts.\n"
            "   - Use 'ownerUsername' as the lead identifier\n"
            "   - Use 'ownerFullName' as the name\n"
            "   - Build profileUrl as 'https://www.instagram.com/{ownerUsername}'\n"
            "   - Use post caption as recentActivity\n"
            "   - Calculate engagementScore from likesCount and commentsCount\n"
            "   - Add notes about why this user is a potential lead based on the query\n"
            "3. Deduplicate leads by username/profile URL\n"
            f"4. Return up to {max_leads} unique leads with the highest engagement or relevance\n"
        )
        expected_output = (
            "Return VALID JSON only (no code block). Schema:\n"
            "{\n"
            '  "leadSummary": string,\n'
            '  "leads": [\n'
            "    {\n"
            '      "platform": "instagram|facebook|tiktok|twitter|linkedin",\n'
            '      "name": string,\n'
            '      "profileUrl": string,\n'
            '      "headline": string,\n'
            '      "recentActivity": string,\n'
            '      "engagementScore": number,\n'
            '      "contact": {"email": string, "phone": string, "website": string},\n'
            '      "notes": string,\n'
            '      "sourceId": string\n'
            "    }\n"
            "  ]\n"
            "}\n"
            f"Cap the total leads to {max_leads} and populate missing optional fields with null."
        )

        agent = Agent(
            role='Multichannel Growth Strategist',
            goal='Source and synthesize actionable social media leads.',
            backstory=(
                'You are an expert growth strategist skilled at extracting lead data from social platforms and '
                'distilling them into concise opportunities for sales and partnerships.'
            ),
            tools=tool_instances,
            verbose=debug,
            llm=model_name,
        )

        task = Task(
            description=task_description,
            expected_output=expected_output,
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=debug)

        crew_output = crew.kickoff()
        raw_response = crew_output.raw if hasattr(crew_output, 'raw') else str(crew_output)
        raw_response_str = raw_response if isinstance(raw_response, str) else str(raw_response)

        structured_payload: Dict[str, Any]
        try:
            structured_payload = json.loads(raw_response_str)
        except json.JSONDecodeError:
            Actor.log.warning('Agent response was not valid JSON, storing raw text.')
            structured_payload = {
                'leadSummary': raw_response_str,
                'leads': [],
            }

        lead_summary: str = (
            structured_payload.get('leadSummary')
            or structured_payload.get('lead_summary')
            or raw_response_str
        )
        leads_raw = structured_payload.get('leads', [])

        parsed_leads: List[SocialLead] = []
        for lead in leads_raw:
            try:
                parsed_leads.append(SocialLead.model_validate(lead))
            except ValidationError as exc:
                Actor.log.warning('Skipping malformed lead payload: %s', exc)

        if len(parsed_leads) > max_leads:
            parsed_leads = parsed_leads[:max_leads]

        result_payload = LeadGenerationResult(
            query=query,
            platforms=requested_platforms,
            lead_summary=lead_summary,
            leads=parsed_leads,
            raw_agent_response=raw_response_str,
        )

        # Charge for task completion
        await Actor.charge('task-completed')

        await Actor.push_data(result_payload.dict(by_alias=True))
        Actor.log.info('Pushed %s leads into the dataset.', len(parsed_leads))
