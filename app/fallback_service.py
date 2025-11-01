import requests
import re

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories?q={}"
USER_AGENT = {"User-Agent": "FallbackService/1.0"}

TECH_KEYWORDS = [
    "react", "next.js", "vue", "angular", "svelte",
    "node.js", "flutter", "django", "laravel",
    "tailwind", "bootstrap", "express", "flask",
    "redux", "typescript", "vite", "webpack"
]


def detect_technology_name(query: str):
    query_lower = query.lower()
    for tech in TECH_KEYWORDS:
        if tech in query_lower:
            return tech
    # if user says "Explain React framework fully"
    # extract first capitalized word
    match = re.findall(r"[A-Z][a-zA-Z0-9\.\+\-]+", query)
    return match[0] if match else query


def wikipedia_summary(name: str):
    try:
        res = requests.get(WIKIPEDIA_API + name, headers=USER_AGENT, timeout=10)
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


def github_readme(name: str):
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

            # Try to infer installation instructions
            install_matches = re.findall(r"(npm install.*|yarn add.*|pip install.*|composer require.*)", text, re.IGNORECASE)
            installation = list(set(install_matches))[:5] if install_matches else []

            return {
                "summary": text[:1000],  # first 1000 chars
                "installation": installation,
                "github_url": first_repo["html_url"]
            }
    except:
        return None


def build_structured_response(name: str, wiki=None, github=None):
    return {
        "name": name,
        "history": (wiki.get("history") if wiki else None),
        "usage": (wiki.get("summary") if wiki else None),
        "installation": (github.get("installation") if github else []),
        "latest_version": None,
        "wiki_url": (wiki.get("wiki_url") if wiki else None),
        "github_url": (github.get("github_url") if github else None),
        "source": detect_source(wiki, github)
    }


def detect_source(wiki, github):
    if wiki and github:
        return "wikipedia|github"
    if wiki:
        return "wikipedia"
    if github:
        return "github"
    return "fallback"


def fallback_search(query: str):
    name = detect_technology_name(query)

    wikipedia_data = wikipedia_summary(name)
    github_data = github_readme(name)

    result = build_structured_response(name, wikipedia_data, github_data)

    # If everything failed, return minimal fallback
    if not wikipedia_data and not github_data:
        result["usage"] = "No data found. Provide a clearer name or try again."
        result["source"] = "fallback"

    return result
