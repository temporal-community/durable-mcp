from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
import json
import re
from html import unescape
from html.parser import HTMLParser
import re
from html import unescape
import asyncio

retry_policy = RetryPolicy(
    maximum_attempts=0,  # Infinite retries
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(minutes=1),
    backoff_coefficient=1.0,
)

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# Import activities and models, passing them through the sandbox
with workflow.unsafe.imports_passed_through():
    from workflows.activities import make_nws_request, make_hackernews_request, fetch_url_content, render_url_content
    from shared.models import HackerNewsParams
    # Import libraries that are not compatible with the workflow sandbox
    from bs4 import BeautifulSoup
    import trafilatura

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._ignore_depth: int = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._ignore_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._ignore_depth > 0:
            self._ignore_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self._chunks.append(data)

    def handle_comment(self, data: str) -> None:
        # Ignore comments entirely
        pass

    def get_text(self) -> str:
        return "".join(self._chunks)

def _html_to_text(content: str) -> str:
    """Extract main textual content from HTML with trafilatura, with BS4 fallback.

    The goal is to avoid boilerplate: scripts, styles, cookie banners, nav, CSS/JS blobs.
    """
    # If content already looks like plain text (no '<' chars), skip heavy HTML cleaning
    if "<" not in content:
        text = content
    else:
        # First choice: trafilatura main content extraction
        try:
            extracted = trafilatura.extract(
                content,
                include_comments=False,
                include_tables=False,
                favor_recall=False,
                no_fallback=False,
                output="txt",
                with_metadata=False,
            )
            if extracted and extracted.strip():
                text = extracted
            else:
                raise ValueError("empty")
        except Exception:
            # Fallback: clean with BeautifulSoup and keep only main/article/body text
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "img", "picture", "source"]):
                tag.decompose()
            for tag in soup(["header", "nav", "aside", "footer"]):
                tag.decompose()
            main_node = soup.find("article") or soup.find("main") or soup.body
            text = main_node.get_text(" ") if main_node else soup.get_text(" ")

    text = unescape(text)
    # Remove common cookie/consent strings if they slipped through
    text = re.sub(r"(?i)(we use cookies|cookie\s+settings|your\s+privacy|consent)", " ", text)
    # Remove CSS/JS artifacts
    text = re.sub(r"\{[^}]*\}", " ", text)  # CSS blocks
    text = re.sub(r";\s*}", " ", text)
    text = re.sub(r"\b(function|var|let|const|window\.|document\.)\b[\s\S]{0,120}", " ", text)
    # Remove markdown image syntax and data URIs
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", text)
    text = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _html_to_text(content: str) -> str:
    """Convert HTML content to plain text.

    Removes script/style blocks and tags, unescapes entities, and normalizes whitespace.
    """
    # Remove script and style blocks
    content = re.sub(r"(?is)<(script|style)[^>]*>.*?</\\1>", " ", content)
    # Strip all remaining tags
    content = re.sub(r"(?s)<[^>]+>", " ", content)
    # Unescape HTML entities
    content = unescape(content)
    # Collapse whitespace
    content = re.sub(r"\s+", " ", content).strip()
    return content

async def retrieve_content_and_summarize(stories: list[dict]) -> list[dict]:
    """For each story with a URL, fetch content and add a short preview.

    Returns the mutated list for convenience.
    """

    async def _process_story(story: dict) -> None:
        url = story.get("url")
        if not url:
            return
        try:
            # First attempt: render with headless browser for dynamic sites
            rendered_html = await workflow.execute_activity(
                render_url_content,
                url,
                schedule_to_close_timeout=timedelta(seconds=45),
                retry_policy=retry_policy,
            )
            content_source = rendered_html if rendered_html else None
            # Fallback to simple HTTP fetch if rendering failed
            if not content_source:
                content_source = await workflow.execute_activity(
                    fetch_url_content,
                    url,
                    schedule_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
            if content_source:
                text_only = _html_to_text(content_source)
                story["content_preview"] = text_only
        except Exception:
            # If fetching content fails, skip adding preview
            return

    # Kick off processing for all stories concurrently
    tasks = [_process_story(story) for story in stories]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    return stories

@workflow.defn
class GetAlerts:
    @workflow.run
    async def get_alerts(self, state: str) -> str:
        """Get weather alerts for a US state.

        Args:
            state: Two-letter US state code (e.g. CA, NY)
        """
        url = f"{NWS_API_BASE}/alerts/active/area/{state}"
        data = await workflow.execute_activity(
            make_nws_request,
            url,
            schedule_to_close_timeout=timedelta(seconds=40),
            retry_policy=retry_policy,
        )

        if not data or "features" not in data:
            return "Unable to fetch alerts or no alerts found."

        if not data["features"]:
            return "No active alerts for this state."

        alerts = [format_alert(feature) for feature in data["features"]]
        return "\n---\n".join(alerts)

@workflow.defn
class GetForecast:
    @workflow.run
    async def get_forecast(self, latitude: float, longitude: float) -> str:
        """Get weather forecast for a location.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
        """
        # First get the forecast grid endpoint
        points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
        points_data = await workflow.execute_activity(
            make_nws_request,
            points_url,
            schedule_to_close_timeout=timedelta(seconds=40),
            retry_policy=retry_policy,
        )

        if not points_data:
            return "Unable to fetch forecast data for this location."
        
        await workflow.sleep(10)

        # Get the forecast URL from the points response
        forecast_url = points_data["properties"]["forecast"]
        forecast_data = await workflow.execute_activity(
            make_nws_request,
            forecast_url,
            schedule_to_close_timeout=timedelta(seconds=40),
            retry_policy=retry_policy,
        )
        if not forecast_data:
            return "Unable to fetch detailed forecast."

        # Format the periods into a readable forecast
        periods = forecast_data["properties"]["periods"]
        forecasts = []
        for period in periods[:5]:  # Only show next 5 periods
            forecast = f"""
    {period['name']}:
    Temperature: {period['temperature']}°{period['temperatureUnit']}
    Wind: {period['windSpeed']} {period['windDirection']}
    Forecast: {period['detailedForecast']}
    """
            forecasts.append(forecast)

        return "\n---\n".join(forecasts)

@workflow.defn
class GetLatestStories:
    @workflow.run
    async def get_latest_stories(self, query: str | None = None) -> str:
        """Get a summary of the top 100 newest stories on Hacker News using Algolia API.

        Returns:
            JSON string containing an array of the top 10 newest stories with their main fields.
        """
        # Pass a single dataclass instance to the activity
        params = HackerNewsParams(query=query)

        data = await workflow.execute_activity(
            make_hackernews_request,
            params,
            schedule_to_close_timeout=timedelta(seconds=40),
            retry_policy=retry_policy,
        )

        if not data or "hits" not in data:
            return json.dumps({"error": "Failed to fetch stories from Algolia API"})

        hits = data.get("hits", [])

        # Extract the main fields from each story
        stories = []
        for hit in hits:
            story_summary = {
                "id": hit.get("objectID"),
                "title": hit.get("title"),
                "url": hit.get("url"),
                "points": hit.get("points"),
                "author": hit.get("author"),
                "created_at": hit.get("created_at"),
                "num_comments": hit.get("num_comments"),
                "story_text": hit.get("story_text"),
            }
            stories.append(story_summary)

        # For each story that has a URL, fetch a short preview of its contents via activity
        await retrieve_content_and_summarize(stories)

        return json.dumps(stories, indent=2)

    @workflow.update
    def ping(self) -> str:
        """No-op update used for update-with-start to ensure a handle.

        Returns a simple string without mutating workflow state.
        """
        return "ok"