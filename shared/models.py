from dataclasses import dataclass
from pydantic import BaseModel

# Shared models used across workflows and activities

ALGOLIA_URL_DEFAULT = "https://hn.algolia.com/api/v1/search_by_date"

@dataclass
class HackerNewsParams:
    url: str = ALGOLIA_URL_DEFAULT
    tags: str = "story"
    numeric_filters: str = "points>0"
    hits_per_page: int = 5
    page: int = 0
    # Optional free-text query to filter results by topic/keyword
    query: str | None = None

class SummaryInput(BaseModel):
    """Input for initial user research query"""

    story_id: str
    summary: str