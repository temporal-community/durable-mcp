from temporalio.client import Client
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from typing import List
import json

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


async def _classify_with_sampling(ctx: Context, items: list[dict], buckets: List[str]) -> dict:
    """Ask the MCP client (via sampling) to classify items into the provided buckets.

    Returns a dict in the shape {"categories": {bucket_label: [items...]}}.
    """
    instructions = {
        "task": "Classify items into the given categories",
        "categories": buckets,
        "requirements": [
            "Return only JSON with keys: categories",
            "categories must be an object mapping category label to an array of items",
            "Each item in output must be one of the original items without modification",
            "Every item should appear in exactly one category",
            "Do not include markdown code fences",
        ],
        "items": items,
    }

    # Single-message prompt that includes system-style guidance and the JSON payload
    prompt_text = (
        "You are a helpful assistant that strictly outputs valid JSON in the Output format specified. "
        "Classify the provided Hacker News items into exactly the provided categories.\n\n"
        f"INPUT:\n{json.dumps(instructions)}\n\n"
        "OUTPUT FORMAT:\n{\n  \"categories\": { \"<bucket>\": [ <original items> ] }\n}\n"
    )

    content = await ctx.sample("Please classify the following Hacker News items into the provided categories.", system_prompt=prompt_text, temperature=0.0, max_tokens=1200)
    await ctx.info("Classification completed " + str(content))
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
    await ctx.info("Classification completed text = " + str(text))

    # Try strict JSON parsing; if it fails, attempt to extract a JSON object
    def _extract_json(text_in: str) -> str | None:
        t = text_in.strip()
        if t.startswith("```"):
            lines = [ln for ln in t.splitlines() if not ln.strip().startswith("```")]
            t = "\n".join(lines).strip()
        try:
            start = t.index("{")
            end = t.rindex("}") + 1
            return t[start:end]
        except ValueError:
            return None

    try:
        parsed = json.loads(text)
    except Exception:
        json_text = _extract_json(text) or "{}"
        parsed = json.loads(json_text)

    categories = parsed.get("categories") if isinstance(parsed, dict) else None
    if not isinstance(categories, dict):
        categories = {label: [] for label in buckets}
    return {"categories": categories}


DEFAULT_BUCKETS: List[str] = [
    "Model Context Protocol (MCP)",
    "Agents",
    "Context Engineering",
    "Ambient AI",
    "Other",
]


@mcp.tool
async def get_latest_stories(ctx: Context) -> str:
    """Get newest Hacker News stories, then classify them into 5 buckets using sampling.

    Returns:
        JSON string: {"categories": {"<bucket>": [items...]}}
    """

    

    # Elicit topic/keyword from the user
    query = await _elicit_topic(ctx)
    await ctx.info("Elicitation completed - topic: " + str(query) + "; starting workflow")

    # The business logic has been moved into the temporal workflow; start via update-with-start
    client = await get_temporal_client()
    # Use Update-With-Start to ensure we get a handle even if the workflow does not exist yet
    from temporalio.client import WithStartWorkflowOperation
    from temporalio.common import WorkflowIDConflictPolicy
    start_op = WithStartWorkflowOperation(
        "GetLatestStories",
        query,
        id="hackernews-latest-stories",
        task_queue="hackernews-task-queue",
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING
    )
    # Execute a no-op update that exists on the workflow to trigger start-if-needed
    await client.execute_update_with_start_workflow(
        update="ping",
        args=[],
        start_workflow_operation=start_op,
    )
    # Retrieve a handle for future interactions and to get the result now
    handle = await start_op.workflow_handle()
    raw_result = await handle.result()

    # Parse workflow result (expected to be a JSON array of story objects)
    try:
        stories: list[dict] = json.loads(raw_result)
        if not isinstance(stories, list):
            raise ValueError("Expected a list of story objects")
    except Exception:
        return json.dumps({
            "error": "Workflow returned invalid JSON for stories",
            "raw": raw_result,
        })

    # Ask the MCP client (via sampling) to classify stories into the provided buckets
    try:
        classified = await _classify_with_sampling(ctx, stories, DEFAULT_BUCKETS)
        return json.dumps(classified)
    except Exception as e:
        await ctx.info(f"Classification failed: {e}")
        # Fallback: return unclassified structure
        return json.dumps({
            "categories": {label: [] for label in DEFAULT_BUCKETS},
            "error": f"classification_failed: {e}",
        })

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')