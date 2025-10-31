# app/github_service.py
import httpx
from typing import Optional

class GitHubService:
    def __init__(self, user_agent: str = "DevEncycloAgent/1.0", token: str | None = None):
        self.headers = {"User-Agent": user_agent}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def fetch_latest_release(self, owner: str, repo: str) -> Optional[dict]:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        async with httpx.AsyncClient(timeout=10.0, headers=self.headers) as client:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return r.json()

                # Fallback: repo has no releases, try tags
                if r.status_code == 404:
                    tags_url = f"https://api.github.com/repos/{owner}/{repo}/tags"
                    r2 = await client.get(tags_url)
                    if r2.status_code == 200 and r2.json():
                        tags = r2.json()
                        return {"name": tags[0]["name"]}

            except httpx.HTTPError:
                return None

        return None

    async def fetch_readme(self, owner: str, repo: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        async with httpx.AsyncClient(timeout=10.0, headers=self.headers) as client:
            try:
                r = await client.get(
                    url,
                    headers={
                        **self.headers,
                        "Accept": "application/vnd.github.v3.raw"
                    }
                )
                if r.status_code == 200:
                    return r.text

            except httpx.HTTPError:
                return None

        return None
