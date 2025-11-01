import requests
import re
from urllib.parse import quote
import asyncio
from typing import Optional

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
    def __init__(self, github, registry):
        self.github = github
        self.registry = registry

    async def fetch_text(self, query: str) -> Optional[str]:
        """
        Fetch a short description from npm, PyPI, or GitHub README.
        """
        # 1) Try npm registry
        npm = await self.registry.fetch_npm_latest(query)
        if npm and npm.get("description"):
            return npm.get("description")

        # 2) Try PyPI
        pypi = await self.registry.fetch_pypi_info(query)
        if pypi and pypi.get("info") and pypi["info"].get("summary"):
            return pypi["info"]["summary"]

        # 3) Try GitHub README if query looks like "owner/repo"
        if "/" in query:
            owner_repo = query.split("/")[:2]
            owner, repo = owner_repo[0], owner_repo[1]
            readme = await self.github.fetch_readme(owner, repo)
            if readme:
                return readme[:1024]

        return None

    def detect_technology_name(self, query: str) -> str:
        query_lower = query.lower()
        for tech in TECH_KEYWORDS:
            if tech in query_lower:
                return tech
        # fallback: extract first capitalized word
        match = re.findall(r"[A-Z][a-zA-Z0-9\.\+\-]+", query)
        return match[0] if match else query

    def wikipedia_summary(self, name: str):
        try:
            res = requests.get(WIKIPEDIA_API + quote(name), headers=USER_AGENT, timeout=10)
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

    def github_readme(self, name: str):
        try:
            search = requests.get(GITHUB_SEARCH_API.format(name), headers=USER_AGENT, timeout=10)
            items = search.json().get("items", [])
            if not items:
                return None

            first_repo = items[0]
            owner = first_repo["owner"]["login"]
            repo = first_repo["name"]

            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            readme = requests.get(readme_url, headers=USER_AGENT, timeout=10)
            if readme.status_code == 200:
                text = readme.text
                install_matches = re.findall(r"(npm install.*|yarn add.*|pip install.*|composer require.*)", text, re.IGNORECASE)
                installation = list(set(install_matches))[:5] if install_matches else []

                return {
                    "summary": text[:1000],
                    "installation": installation,
                    "github_url": first_repo["html_url"]
                }
        except:
            return None

    def detect_source(self, wiki, github):
        if wiki and github:
            return "wikipedia|github"
        if wiki:
            return "wikipedia"
        if github:
            return "github"
        return "fallback"

    def build_structured_response(self, name: str, wiki=None, github=None):
        return {
            "name": name,
            "history": wiki.get("history") if wiki else None,
            "usage": wiki.get("summary") if wiki else None,
            "installation": github.get("installation") if github else [],
            "latest_version": None,
            "wiki_url": wiki.get("wiki_url") if wiki else None,
            "github_url": github.get("github_url") if github else None,
            "source": self.detect_source(wiki, github)
        }

    async def get_framework_details(self, query: str):
        # Detect likely tech keyword
        name = self.detect_technology_name(query)

        # Run Wikipedia and GitHub in parallel
        loop = asyncio.get_event_loop()
        wiki_task = loop.run_in_executor(None, self.wikipedia_summary, name)
        github_task = loop.run_in_executor(None, self.github_readme, name)
        wiki_data, github_data = await asyncio.gather(wiki_task, github_task)

        result = self.build_structured_response(name, wiki_data, github_data)

        # Fallback if nothing found
        if not wiki_data and not github_data:
            fallback_text = await self.fetch_text(name)
            result["usage"] = fallback_text or "No summary available."
            result["source"] = "wikipedia|registry|github|fallback"

        return result
