from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
import json
import asyncio
from shared.models import SummaryInput

retry_policy = RetryPolicy(
    maximum_attempts=0,  # Infinite retries
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(minutes=1),
    backoff_coefficient=1.0,
)
# Import activities and models, passing them through the sandbox
with workflow.unsafe.imports_passed_through():
    from workflows.hackernews_activities import make_hackernews_request, fetch_url_content, render_url_content
    from shared.models import HackerNewsParams
    # Import scraping helper that relies on non-sandbox libraries
    from workflows.scraping import html_to_text

@workflow.defn
class GetLatestStories:

    def __init__(self):
        self.content_preview: dict[str, str] = {}
        self.summary: dict[str, str] = {}
        self.stories: list[dict[str, str]] = []
        self.final_result_ready = False
        self.topic = None

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
                # add the text_only to the content_preview
                self.content_preview[story["id"]] = text_only
                # wait for the summary to be ready (this will come through sampling (via workflow update))
                await workflow.wait_condition(lambda: self.summary.get(story["id"]) is not None)
                # received the summary for this story
                story["summary"] = self.summary[story["id"]]
                return

            except Exception as e:
                # TODO: delete this
                print(f"error processing story {story['id']}: {e}")
                # If fetching content fails, fallback to story_text if available
                story["summary"] = "Summary not available - unable to scrape content"
                return

        # Kick off processing for all stories concurrently
        tasks = [_process_story(story) for story in stories]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # set the final result to true
        self.final_result_ready = True
        return self.stories

    def _parse_hits_into_stories(self, data: dict) -> list[dict]:
        """Extract story summaries from Algolia API response data.

        Returns a list of story dicts with the main fields we care about.
        """
        hits = data.get("hits", [])
        stories: list[dict] = []
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
        return stories

    @workflow.run
    async def get_latest_stories(self) -> str:
        """Get a summary of the top 100 newest stories on Hacker News using Algolia API.

        Returns:
            JSON string containing an array of the top 10 newest stories with their main fields
            and a summary of the content.
        """

        while True:

            await workflow.wait_condition(
                lambda: self.topic is not None
                and self.final_result_ready is False
            )

            # Pass a single dataclass instance to the activity
            params = HackerNewsParams(query=self.topic)
            # TODO: delete this
            print(f"getting stories for topic {self.topic}")

            data = await workflow.execute_activity(
                make_hackernews_request,
                params,
                schedule_to_close_timeout=timedelta(seconds=40),
                retry_policy=retry_policy,
            )

            if not data or "hits" not in data:
                return json.dumps({"error": "Failed to fetch stories from Algolia API"})

            parsed_stories = self._parse_hits_into_stories(data)
            self.stories.extend(parsed_stories)

            # For each story that has a URL, fetch a short preview of its contents via 
            # activity. This will also wait for the summary to be ready for each story.
            await self.retrieve_content_and_summarize(self.stories)

        return json.dumps(self.stories, indent=2)



    @workflow.update
    def reset_final_result_ready(self) -> None:
        """This resets some variables to start a new summary of new articles
        """
        self.final_result_ready = False
        self.content_preview = {}
        self.summary = {}
        self.stories = []
        return

    @workflow.update
    def set_topic(self, topic: str) -> None:
        """Set the topic for the workflow.

        Returns the mutated list for convenience.
        """
        self.topic = topic
        return
    
    @workflow.update
    def update_story_summary(self, summary_input: SummaryInput) -> None:
        """Update the stories with the summary of the content.

        Returns the mutated list for convenience.
        """
        story_id = summary_input.story_id
        summary = summary_input.summary

        # add the summary to the summary dictionary
        self.summary[story_id] = summary
        # remove the content_preview for this story
        del self.content_preview[story_id]

        return 
    
    @workflow.query
    def get_content_preview(self) -> dict[str, str]:
        """Get the content preview for all stories.

        Returns a dictionary of story IDs to content previews.
        """
        return self.content_preview
    
    @workflow.query
    def get_final_result_ready(self) -> bool:
        """Get the final result ready flag.

        Returns a boolean indicating if the final result is ready.
        """
        return self.final_result_ready
    
    @workflow.query
    def get_final_result(self) -> list[dict]:
        """Get the final result for all stories.

        Returns a list of stories with their summaries.
        """

        # TODO: delete this
        print("returning the final result from the workflow")
        return self.stories
    
    @workflow.query
    def get_topic(self) -> str:
        """Get the topic for the workflow.

        Returns the topic.
        """
        return self.topic
    