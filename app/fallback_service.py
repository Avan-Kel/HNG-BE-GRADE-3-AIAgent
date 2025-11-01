import requests
import re
from urllib.parse import quote
from tinydb import TinyDB, Query
from typing import Optional

# APIs
WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories?q={}"
USER_AGENT = {"User-Agent": "FallbackService/1.0"}

# Known tech keywords
TECH_KEYWORDS = [
    "react", "next.js", "vue", "angular", "svelte",
    "node.js", "flutter", "django", "laravel",
    "tailwind", "bootstrap", "express", "flask",
    "redux", "typescript", "vite", "webpack"
]

# Map to correct Wikipedia pages
WIKI_OVERRIDES = {
    "react": "React_(software)",
    "vue": "Vue.js",
    "angular": "Angular_(web_framework)",
    "svelte": "Svelte",
    "next.js": "Next.js",
    "node.js": "Node.js",
    "django": "Django_(web_framework)",
    "laravel": "Laravel",
    "flutter": "Flutter_(software)",
    "tailwind": "Tailwind_CSS",
    "express": "Express.js",
    "flask": "Flask_(web_framework)",
    "redux": "Redux_(JavaScript_library)",
    "typescript": "TypeScript",
    "vite": "Vite_(software)",
    "webpack": "Webpack"
}


class FallbackService:
    def __init__(self, db_path: str = "fallback_cache.json"):
        self.db = TinyDB(db_path)

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
                return WIKI_OVERRIDES.get(tech, tech)

        match = re.findall(r"[A-Z][a-zA-Z0-9\.\+\-]+", query)
        return WIKI_OVERRIDES.get(match[0], match[0]) if match else query

    def wikipedia_summary(self, name: str) -> Optional[dict]:
        # Check cache first
        cached = self.db.get(Query().name == name)
        if cached:
            return cached["wikipedia"]

        try:
            res = requests.get(WIKIPEDIA_API + quote(name), headers=USER_AGENT, timeout=10)
            if res.status_code == 200:
                data = res.json()
                wiki_data = {
                    "summary": data.get("extract"),
                    "history": data.get("description"),
                    "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page")
                }
                # Save to cache
                self.db.insert({"name": name, "wikipedia": wiki_data})
                return wiki_data
        except Exception:
            pass
        return None

    def github_readme(self, name: str) -> Optional[dict]:
        # Check cache first
        cached = self.db.get(Query().name == name)
        if cached:
            return cached.get("github")

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
                install_matches = re.findall(
                    r"(npm install.*|yarn add.*|pip install.*|composer require.*)",
                    text,
                    re.IGNORECASE
                )
                installation = list(set(install_matches))[:5] if install_matches else []

                github_data = {
                    "summary": text[:1000],
                    "installation": installation,
                    "github_url": first_repo["html_url"]
                }
                # Save to cache
                self.db.insert({"name": name, "github": github_data})
                return github_data
        except Exception:
            return None

    def detect_source(self, wiki, github):
        if wiki and github:
            return "wikipedia|github"
        if wiki:
            return "wikipedia"
        if github:
            return "github"
        return "fallback"

    def build_structured_response(self, name: str, wiki=None, github=None) -> dict:
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

    def get_framework_details(self, query: str) -> dict:
        name = self.detect_technology_name(query)
        wikipedia_data = self.wikipedia_summary(name)
        github_data = self.github_readme(name)
        result = self.build_structured_response(name, wikipedia_data, github_data)

        if not wikipedia_data and not github_data:
            result["usage"] = "No data found. Provide a clearer name or try again."
            result["source"] = "fallback"

        return result
