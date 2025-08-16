from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
import json
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
    # Import scraping helper that relies on non-sandbox libraries
    from workflows.scraping import html_to_text


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
        await self.retrieve_content_and_summarize(stories)

        return json.dumps(stories, indent=2)


    async def retrieve_content_and_summarize(self, stories: list[dict]) -> list[dict]:
        """For each story with a URL, fetch content and add a short preview.
        
        Returns the mutated list for convenience.
        """
        async def _process_story(story: dict) -> None:
            url = story.get("url")
            if not url:
                # No URL; fallback to story_text if present
                fallback_text = (story.get("story_text") or "").strip()
                story["content_preview"] = fallback_text
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
                text_only = ""
                if isinstance(content_source, str) and content_source:
                    try:
                        text_only = html_to_text(content_source)
                    except Exception:
                        text_only = ""
                # Final fallback chain: story_text -> raw content -> empty string
                if not isinstance(text_only, str) or not text_only.strip():
                    text_only = (story.get("story_text") or "").strip() or (content_source or "")
                story["content_preview"] = text_only
            except Exception:
                # If fetching content fails, fallback to story_text if available
                story["content_preview"] = (story.get("story_text") or "").strip()
                return

        # Kick off processing for all stories concurrently
        tasks = [_process_story(story) for story in stories]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return stories

    @workflow.update
    def ping(self) -> str:
        """No-op update used for update-with-start to ensure a handle.

        Returns a simple string without mutating workflow state.
        """
        return "ok"