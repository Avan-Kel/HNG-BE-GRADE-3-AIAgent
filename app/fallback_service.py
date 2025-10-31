# app/fallback_service.py
from typing import Optional
import re


class FallbackService:
    def __init__(self, github, registry):
        self.github = github
        self.registry = registry

    async def fetch_text(self, query: str) -> Optional[str]:
        """
        Try multiple fallbacks:
        - Try npm description
        - Try PyPI summary
        - Try GitHub README if query resembles 'owner/repo'
        - Return short fallback snippet
        """

        # 1) Try npm description
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
                # return first 1024 chars
                return readme[:1024]

        # Nothing found
        return None
