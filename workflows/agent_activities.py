from typing import Any, Dict
from temporalio import activity
from mcp_clients.simple_client import SimpleMCPClient
import json
from tabulate import tabulate


@activity.defn
async def call_mcp_tool(tool_name: str) -> Any:
    """Call an MCP server tool using the simple client.

    This activity is intended for use from workflows that need to invoke MCP tools.
    Currently targets the HackerNews server where the tool "get_latest_stories" is defined.
    """
    client = SimpleMCPClient(
        "HackerNews",
        "mcp_servers/hackernews.py",
    )
    try:
        await client.connect()
        result = await client.call_tool(tool_name, None)
        return getattr(result, "structured_content", {}).get("result", None)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

# The following activity is used to convert the JSON output of the MCP tool to markdown.
# It was heavily vibe coded so it surely not optimal.
@activity.defn
async def convert_json_to_markdown(json_text: str) -> str:
    """Convert the specific Hacker News stories JSON format into markdown.

    Expected input shape (double-encoded array):
        ["[{...}, {...}, ...]"]

    Output format (for each story):
        - **Title**: <title>
            - **author**: <author>
            - **created_at**: <created_at>

    Notes:
    - Output must not start with brackets or quotes.
    - This implementation is intentionally tailored for the provided input structure.
    """

    def _safe_str(value: object, fallback: str = "") -> str:
        return str(value) if value is not None else fallback

    try:
        # print(f"converting json to markdown")
        # First parse the outer JSON which should be a list containing a single string
        outer = json.loads(json_text)

        inner_list = None

        # If the first element is a string, parse it as JSON to get the list of stories
        if isinstance(outer, list) and len(outer) > 0 and isinstance(outer[0], str):
            try:
                inner_list = json.loads(outer[0])
            except Exception:
                inner_list = []

        # If it's already a list, use it as is
        if inner_list is None and isinstance(outer, list):
            inner_list = outer

        # If it's a single dict, wrap it in a list
        if inner_list is None and isinstance(outer, dict):
            inner_list = [outer]

        if not isinstance(inner_list, list):
            return ""

        lines: list[str] = []

        for item in inner_list:
            if not isinstance(item, dict):
                continue

            title = _safe_str(item.get("title"), "Untitled")
            author = _safe_str(item.get("author"), "unknown")
            id = _safe_str(item.get("created_at"), "unknown")
            created_at = _safe_str(item.get("created_at"), "unknown")
            num_comments = _safe_str(item.get("num_comments"), "unknown")
            points = _safe_str(item.get("points"), "unknown")
            summary = _safe_str(item.get("summary"), "unknown")

            lines.append(f"- **Title**: {title}")
            lines.append(f"    - **author**: {author}")
            lines.append(f"    - **created_at**: {created_at}")
            lines.append(f"    - **id**: {id}")
            lines.append(f"    - **num_comments**: {num_comments}")
            lines.append(f"    - **points**: {points}")
            lines.append(f"    - **summary**: {summary}")
            lines.append("")  # blank line between stories

        # Join lines and strip to avoid leading/trailing whitespace or blank lines
        markdown_result = "\n".join(lines).strip()
        # print(f"markdown_result: {markdown_result}")
        return markdown_result

    except Exception:
        # On any parsing error, return an empty string to avoid starting with [ or "
        return ""
    