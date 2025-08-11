import httpx
import json
from temporalio.client import Client
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("hackernews")

# Temporal client setup (do this once, then reuse)
temporal_client = None

async def get_temporal_client():
    global temporal_client
    if not temporal_client:
        temporal_client = await Client.connect("localhost:7233")
    return temporal_client

@mcp.tool()
async def get_latest_stories() -> str:
    """Get a summary of the top 100 newest stories on Hacker News using Algolia API.

    Returns:
        JSON string containing an array of the top 10 newest stories with their main fields.
    """
    try:
        # Algolia Hacker News API endpoint
        algolia_url = "https://hn.algolia.com/api/v1/search_by_date"
        
        # Parameters for newest stories
        params = {
            "tags": "story",
            "numericFilters": "points>0",  # Only stories with points
            "hitsPerPage": 100,
            "page": 0
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(algolia_url, params=params)
            
            if response.status_code != 200:
                return json.dumps({"error": "Failed to fetch stories from Algolia API"})
            
            data = response.json()
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
                    "story_text": hit.get("story_text")
                }
                stories.append(story_summary)
            
            return json.dumps(stories, indent=2)
            
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch stories: {str(e)}"})


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')