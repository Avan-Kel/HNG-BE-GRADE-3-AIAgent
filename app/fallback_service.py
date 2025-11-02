import re
from urllib.parse import quote
from typing import Optional

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories?q={}"
USER_AGENT = {"User-Agent": "FallbackService/1.0"}


TECH_SYNONYMS = {
    "react": "react",
    "reactjs": "react",
    "react js": "react",
    "react library": "react",

    "next": "next.js",
    "nextjs": "next.js",
    "next js": "next.js",

    "vue": "vue.js",
    "vuejs": "vue.js",
    "vue js": "vue.js",

    "angular": "angular",
    "angularjs": "angular",
    "angular js": "angular",

    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",

    "flutter": "flutter",
    "django": "django",
    "laravel": "laravel",
    "redux": "redux",
    "express": "express.js",
    "expressjs": "express.js",
    "tailwind": "tailwind css",
    "tailwindcss": "tailwind css",
    "bootstrap": "bootstrap",
    "typescript": "typescript",
    "vite": "vite",
    "webpack": "webpack"
}

TECH_MAP = {
    "react": "React (software)",
    "next.js": "Next.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "svelte": "Svelte",
    "node.js": "Node.js",
    "flutter": "Flutter (software)",
    "django": "Django (web framework)",
    "laravel": "Laravel",
    "redux": "Redux (JavaScript library)",
    "express.js": "Express.js",
    "tailwind css": "Tailwind CSS",
    "bootstrap": "Bootstrap (front-end framework)",
    "typescript": "TypeScript",
    "vite": "Vite",
    "webpack": "Webpack"
}


class FallbackService:
    def __init__(self, github=None, registry=None):
        self.github = github
        self.registry = registry

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

    def resolve_term(term: str) -> str:
        term = term.lower().strip()

        if term in TECH_SYNONYMS:
            term = TECH_SYNONYMS[term]

        if term in TECH_MAP:
            return TECH_MAP[term]

        return term

    

    def fetch_text_from_wikipedia(search_term: str):
        page_title = resolve_term(search_term)
        encoded = quote(page_title)
        url = f"https://en.wikipedia.org/wiki/{encoded}"

        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            paragraphs = soup.select("p")
            if not paragraphs:
                return None

            # Get the first meaningful paragraph
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 40:
                    return text
        
            return None

        except Exception:
            return None


    def detect_technology_name(self, query: str) -> str:
        query_lower = query.lower()
        for key, wiki_name in TECH_MAP.items():
            if key in query_lower:
                return wiki_name
        return query

    def wikipedia_summary(self, name: str) -> Optional[dict]:
        try:
            res = requests.get(WIKIPEDIA_API + quote(name), headers=USER_AGENT, timeout=10)
            res.raise_for_status()
            data = res.json()
            return {
                "summary": data.get("extract"),
                "history": data.get("description"),
                "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page")
            }
        except requests.RequestException:
            return None

    def github_readme(self, name: str) -> Optional[dict]:
        try:
            search = requests.get(GITHUB_SEARCH_API.format(name), headers=USER_AGENT, timeout=10)
            items = search.json().get("items", [])
            if not items:
                return None

            # Prefer exact match repo name
            repo_data = next((r for r in items if r["name"].lower() == name.lower()), items[0])
            owner = repo_data["owner"]["login"]
            repo = repo_data["name"]
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            readme = requests.get(readme_url, headers=USER_AGENT, timeout=10)

            if readme.status_code == 200:
                text = readme.text
                install_matches = re.findall(
                    r"(npm install.*|yarn add.*|pip install.*|composer require.*)", text, re.IGNORECASE
                )
                installation = list(set(install_matches))[:5] if install_matches else []
                return {
                    "summary": text[:1000],
                    "installation": installation,
                    "github_url": repo_data["html_url"]
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

    def get_framework_details(self, query: str):
        # Detect proper tech name for Wikipedia
        name = self.detect_technology_name(query)

        # Fetch data from Wikipedia
        wikipedia_data = self.wikipedia_summary(name)

        # Fetch data from GitHub as fallback
        github_data = self.github_readme(name)

        # Build structured response
        result = self.build_structured_response(name, wikipedia_data, github_data)

        # Ultimate fallback
        if not wikipedia_data and not github_data:
            result["usage"] = "No summary available. Try using a more specific framework name."
            result["source"] = "fallback"

        return result
