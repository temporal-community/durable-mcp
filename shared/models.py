from dataclasses import dataclass

# Shared models used across workflows and activities

ALGOLIA_URL_DEFAULT = "https://hn.algolia.com/api/v1/search_by_date"

@dataclass
class HackerNewsParams:
    url: str = ALGOLIA_URL_DEFAULT
    tags: str = "story"
    numeric_filters: str = "points>0"
    hits_per_page: int = 100
    page: int = 0