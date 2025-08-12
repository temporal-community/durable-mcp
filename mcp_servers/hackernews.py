from temporalio.client import Client
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("hackernews")

# Temporal client setup (do this once, then reuse)
temporal_client = None

async def get_temporal_client():
    global temporal_client
    if not temporal_client:
        temporal_client = await Client.connect("localhost:7233")
    return temporal_client

@mcp.tool
async def get_latest_stories() -> str:
    """Get a summary of the top 100 newest stories on Hacker News using Algolia API.

    Returns:
        JSON string containing an array of the top 10 newest stories with their main fields.
    """
    # The business logic has been moved into the temporal workflow, the mcp tool kicks off the workflow
    client = await get_temporal_client()
    handle = await client.start_workflow(
        "GetLatestStories",
        id="hackernews-latest-stories",
        task_queue="hackernews-task-queue"
    )
    return await handle.result()

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')