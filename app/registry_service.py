# app/registry_service.py
import httpx
from typing import Optional


class RegistryService:
    def __init__(self, user_agent: str = "DevEncycloAgent/1.0"):
        self.headers = {"User-Agent": user_agent}

    async def fetch_npm_latest(self, pkg_name: str) -> Optional[dict]:
        url = f"https://registry.npmjs.org/{pkg_name}/latest"
        async with httpx.AsyncClient(timeout=8.0, headers=self.headers) as client:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return r.json()
            except httpx.HTTPError:
                return None
        return None

    async def fetch_pypi_info(self, pkg_name: str) -> Optional[dict]:
        url = f"https://pypi.org/pypi/{pkg_name}/json"
        async with httpx.AsyncClient(timeout=8.0, headers=self.headers) as client:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return r.json()
            except httpx.HTTPError:
                return None
        return None
