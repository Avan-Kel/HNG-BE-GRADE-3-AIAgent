import re
from urllib.parse import quote
from typing import Optional, Dict, List
import httpx

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories?q={}"
USER_AGENT = {"User-Agent": "FallbackService/1.0"}

TECH_KEYWORDS = [
    "react", "next.js", "vue", "angular", "svelte",
    "node.js", "flutter", "django", "laravel",
    "tailwind", "bootstrap", "express", "flask",
    "redux", "typescript", "vite", "webpack"
]


class FallbackService:
    def __init__(self, github=None, registry=None):
        self.github = github
        self.registry = registry
        self.client = httpx.AsyncClient(timeout=10.0, headers=USER_AGENT)

    async def fetch_text(self, query: str) -> Optional[str]:
        """
        Try multiple async fallbacks:
        1) npm registry
        2) PyPI
        3) GitHub README if query looks like 'owner/repo'
        Returns a short snippet or None if nothing found.
        """
        # 1) npm
        if self.registry:
            npm = await self.registry.fetch_npm_latest(query)
            if npm and npm.get("description"):
                return npm["description"]

        # 2) PyPI
        if self.registry:
            pypi = await self.registry.fetch_pypi_info(query)
            if pypi and pypi.get("info") and pypi["info"].get("summary"):
                return pypi["info"]["summary"]

        # 3) GitHub README
        if self.github and "/" in query:
            owner_repo = query.split("/")[:2]
            owner, repo = owner_repo[0], owner_repo[1]
            readme = await self.github.fetch_readme(owner, repo)
            if readme:
                return readme[:1024]  # limit snippet

        # Nothing found
        return None

    async def wikipedia_summary(self, name: str) -> Optional[Dict]:
        try:
            res = await self.client.get(WIKIPEDIA_API + quote(name))
            if res.status_code == 200:
                data = res.json()
                return {
                    "summary": data.get("extract"),
                    "history": data.get("description"),
                    "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page")
                }
        except:
            pass
        return None

    async def github_readme(self, name: str) -> Optional[Dict]:
        try:
            search = await self.client.get(GITHUB_SEARCH_API.format(quote(name)))
            items = search.json().get("items", [])
            if not items:
                return None

            first_repo = items[0]
            owner = first_repo["owner"]["login"]
            repo = first_repo["name"]

            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            readme = await self.client.get(readme_url)

            if readme.status_code == 200:
                text = readme.text
                install_matches = re.findall(
                    r"(npm install.*|yarn add.*|pip install.*|composer require.*)",
                    text, re.IGNORECASE
                )
                installation = list(set(install_matches))[:5] if install_matches else []

                return {
                    "summary": text[:1000] if text else None,
                    "installation": installation,
                    "github_url": first_repo["html_url"]
                }
        except:
            return None

    def detect_technology_name(self, query: str) -> str:
        query_lower = query.lower()
        for tech in TECH_KEYWORDS:
            if tech in query_lower:
                return tech

        match = re.findall(r"[A-Z][a-zA-Z0-9\.\+\-]+", query)
        return match[0] if match else query.strip()

    def detect_source(self, wiki: Optional[Dict], github: Optional[Dict]) -> str:
        sources: List[str] = []
        if wiki and wiki.get("summary"):
            sources.append("wikipedia")
        if github and github.get("summary"):
            sources.append("github")
        if self.registry:
            sources.append("registry")
        if not sources:
            sources.append("fallback")
        return "|".join(sources)

    async def build_structured_response(self, name: str) -> Dict:
        wiki = await self.wikipedia_summary(name)
        github = await self.github_readme(name)

        result = {
            "name": name,
            "history": wiki.get("history") if wiki else "",
            "usage": wiki.get("summary") if wiki else "",
            "installation": github.get("installation") if github else [],
            "latest_version": None,
            "wiki_url": wiki.get("wiki_url") if wiki else None,
            "github_url": github.get("github_url") if github else None,
            "source": self.detect_source(wiki, github)
        }

        if not wiki and not github:
            result["usage"] = "No summary available. Please try a clearer query or specify a technology."
            result["source"] = "fallback"

        return result

    async def get_framework_details(self, query: str) -> Dict:
        name = self.detect_technology_name(query)
        return await self.build_structured_response(name)

    async def close(self):
        await self.client.aclose()
