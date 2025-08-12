from temporalio.client import Client
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

# Initialize FastMCP server
mcp = FastMCP("hackernews")

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


@mcp.tool
async def get_latest_stories(ctx: Context) -> str:
    """Get a summary of the top 100 newest stories on Hacker News using Algolia API.

    Returns:
        JSON string containing an array of the top 10 newest stories with their main fields.
    """
    # Elicit topic/keyword from the user
    query = await _elicit_topic(ctx)
    await ctx.info("Elicitation completed - topic: " + str(query) + "; starting workflow")

    # The business logic has been moved into the temporal workflow, the mcp tool kicks off the workflow
    client = await get_temporal_client()
    handle = await client.start_workflow(
        "GetLatestStories",
        query,
        id="hackernews-latest-stories",
        task_queue="hackernews-task-queue"
    )
    return await handle.result()

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')