# app/wikipedia_service.py
import httpx
import urllib.parse
from typing import Optional

class WikipediaService:
    def __init__(self, user_agent: str = "DevEncycloAgent/1.0"):
        self.headers = {"User-Agent": user_agent}

    async def fetch_summary(self, title: str) -> Optional[dict]:
        """
        Fetch summary from MediaWiki REST API. Try a few title heuristics.
        Returns the JSON response or None.
        """
        async with httpx.AsyncClient(timeout=10.0, headers=self.headers) as client:
            # Try exact title + common variations
            candidates = [
                title,
                title.replace(" ", "_"),
                title.title().replace(" ", "_")
            ]

            for c in candidates:
                encoded = urllib.parse.quote(c)
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        return r.json()
                except httpx.HTTPError:
                    continue

        return None
