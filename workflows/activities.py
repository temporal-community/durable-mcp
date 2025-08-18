# activities.py

from typing import Any
from temporalio import activity
import httpx
from shared.models import HackerNewsParams
from typing import Optional
import asyncio

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
    api_params: dict[str, Any] = {
        "tags": params.tags,
        "numericFilters": params.numeric_filters,
        "hitsPerPage": params.hits_per_page,
        "page": params.page,
    }
    # Include free-text query if provided
    if params.query:
        api_params["query"] = params.query

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

@activity.defn
async def fetch_url_content(url: str) -> str | None:
    """Fetch the raw content of a given URL and return it as text.

    Args:
        url: Absolute URL to fetch.

    Returns:
        The response body as text if the request is successful.
    """
    headers = {
        "User-Agent": "content-fetcher/1.0",
        "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        # Skip images entirely
        if content_type.lower().startswith("image/"):
            return ""
        return response.text

@activity.defn
async def render_url_content(url: str, wait_selector: Optional[str] = None, timeout_seconds: float = 20.0) -> str | None:
    """Render a URL with a headless browser and return the resulting HTML.

    Uses Playwright (Chromium). Optionally waits for a CSS selector to appear.
    """
    try:
        # Import inside activity to avoid loading in workflow sandbox
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Block image and media requests to avoid downloading large assets
            async def _route_handler(route):
                if route.request.resource_type in {"image", "media", "font"}:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", _route_handler)

            await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=int(timeout_seconds * 1000))
                except Exception:
                    pass
            # Give the page a brief moment to settle dynamic content
            try:
                await page.wait_for_load_state("networkidle", timeout=int(timeout_seconds * 1000))
            except Exception:
                pass

            # Try to use Mozilla Readability to extract the main article text
            try:
                await page.add_script_tag(url="https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.min.js")
                content = await page.evaluate(
                    """
                    () => {
                        try {
                            const doc = document.cloneNode(true);
                            const reader = new Readability(doc);
                            const res = reader.parse();
                            if (res && res.textContent) {
                                return res.textContent;
                            }
                        } catch (e) { /* fall through */ }
                        return document.body ? document.body.innerText : '';
                    }
                    """
                )
            except Exception:
                # Fallback to visible text if readability script fails
                content = await page.evaluate("document.body ? document.body.innerText : ''")
            await context.close()
            await browser.close()
            return content
    except Exception:
        return None


