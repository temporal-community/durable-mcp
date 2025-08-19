import asyncio
from temporalio.client import Client
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from typing import List
import json

from workflows.workflows import GetLatestStories
from shared.models import SummaryInput, WORKFLOW_ID

# Initialize FastMCP server
mcp = FastMCP("hackernews")

# Note: LLM access is handled by the MCP client via sampling. This server only requests sampling.

# Temporal client setup (do this once, then reuse)
temporal_client = None

async def get_temporal_client():
    global temporal_client
    if not temporal_client:
        temporal_client = await Client.connect("localhost:7233")
    return temporal_client

class TopicSchema(BaseModel):
    topic: str = Field(description="Topic or keyword to filter Hacker News stories (e.g., 'AI', 'Python')", min_length=1, max_length=100)


async def _elicit_topic(ctx: Context) -> str | None:
    """Ask the user for a topic via MCP elicitation and return it, or None if cancelled/declined."""
    try:
        result = await ctx.elicit(message="What topic are you interested in for Hacker News?", response_type=TopicSchema)
        if getattr(result, "action", None) == "accept" and getattr(result, "data", None):
            return getattr(result.data, "topic", None)
        return None
    except Exception as e:
        await ctx.info(f"Error eliciting topic " + str(e))
        return None


async def _summarize_with_sampling(ctx: Context, preview: str) -> str:
    """Ask the MCP client (via sampling) to classify items into the provided buckets.

    Returns a dict in the shape {"categories": {bucket_label: [items...]}} with full original items.
    """

    instructions = """You are a helpful assistant that summarizes Hacker News stories.
    You will be given a preview of a Hacker News story.
    Please summarize the story in a few sentences.
    Do not include markdown code fences.
    Do not include any other text than the summary.
    The summary should be in the same language as the story.
    The summary should be concise and to the point.
    
    The preview is: """ + preview
    

    content = await ctx.sample(
        "Please summarize the following Hacker News story:",
        system_prompt=instructions,
        temperature=0.0,
        max_tokens=800,
    )
    # await ctx.info("Summarization completed " + str(content))

    # Normalize to string; content may be a TextContent-like object
    if isinstance(content, str):
        text = content.strip()
    elif hasattr(content, "text"):
        try:
            text = str(getattr(content, "text", "")).strip()
        except Exception:
            text = str(content)
    elif isinstance(content, dict):
        if content.get("type") == "text" and isinstance(content.get("text"), str):
            text = content.get("text", "").strip()
        else:
            text = json.dumps(content)
    else:
        text = str(content)
    # await ctx.info("Summarization completed text = " + str(text))

    return text


@mcp.tool
async def get_latest_stories(ctx: Context) -> str:
    """Get newest Hacker News stories, then classify them into 5 buckets using sampling.

    Returns:
        JSON string: {"stories": [story_id, story_title, story_url, story_summary]}
    """

    
    # The business logic has been moved into the temporal workflow; start via update-with-start
    client = await get_temporal_client()
    # Use Update-With-Start to ensure we get a handle even if the workflow does not exist yet
    from temporalio.client import WithStartWorkflowOperation
    from temporalio.common import WorkflowIDConflictPolicy

    start_op = WithStartWorkflowOperation(
        "GetLatestStories",
        id=WORKFLOW_ID,
        task_queue="hackernews-task-queue",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING
    )

    # Execute a no-op update that exists on the workflow to trigger start-if-needed
    await client.execute_update_with_start_workflow(
        update="reset_final_result_ready",
        args=[],
        start_workflow_operation=start_op,
    )

    # Retrieve a handle for future interactions and to get the result now
    handle = await start_op.workflow_handle()

    # start the workflow running
    handle.result()
    final_result = None

    # First, if there isn't already a topic, elicit topic/keyword from the user
    topic = await handle.query(GetLatestStories.get_topic)
    if not topic:
        query = await _elicit_topic(ctx)
        # await ctx.info("Elicitation completed - topic: " + str(query) + "; starting workflow")
        await handle.execute_update(GetLatestStories.set_topic, query)

    # This is a long running workflow - an entity workflow - so it will not
    # exit. So we will loop until the final result is ready. When it is, the
    # client will exit, but the workflow will continue running.
    # We can run the client again and it will NOT start a new workflow, but it will 
    while True:

        # First check if the final result is ready
        # get the final result
        final_result_ready = await handle.query(GetLatestStories.get_final_result_ready)
        if final_result_ready:
            final_result = await handle.query(GetLatestStories.get_final_result)
            break

        # Then check if the content preview is ready
        content_preview = await handle.query(GetLatestStories.get_content_preview)
        if content_preview:
            # for each content preview, supply the summary via workflow update
            for story_id, preview in content_preview.items():
                # get the summary for this story via MCP sampling
                summary = await _summarize_with_sampling(ctx, preview)
                # supply content summary via workflow update
                await handle.execute_update(GetLatestStories.update_story_summary, SummaryInput(story_id=story_id, summary=summary))

        # wait for 10 seconds
        await asyncio.sleep(10)

    return json.dumps(final_result)

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')