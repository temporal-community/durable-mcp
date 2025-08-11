# activities.py

from typing import Any
from temporalio import activity
import httpx
from models import HackerNewsParams

USER_AGENT = "weather-app/1.0"

# External calls happen via activities now
@activity.defn
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:

        response = await client.get(url, headers=headers, timeout=5.0)
        response.raise_for_status()
        return response.json()

@activity.defn
async def make_hackernews_request(params: HackerNewsParams) -> dict[str, Any] | None:
    """Make a request to the Hacker News Algolia API with proper error handling.

    Expects a single `HackerNewsParams` dataclass argument.
    """
    api_params = {
        "tags": params.tags,
        "numericFilters": params.numeric_filters,
        "hitsPerPage": params.hits_per_page,
        "page": params.page,
    }

    headers = {
        "User-Agent": "hackernews-app/1.0",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            params.url,
            params=api_params,
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
