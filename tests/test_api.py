# tests/test_api.py
import asyncio
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json().get("status") == "healthy"


def test_lookup_returns_combined(monkeypatch):
    async def fake_wiki(self, q: str):
        await asyncio.sleep(0)
        return {
            "title": "React",
            "description": "A JS library for building UIs",
            "extract": "React makes it painless to create interactive UIs.",
            "url": "https://en.wikipedia.org/wiki/React_(JavaScript_library)",
        }

    async def fake_reg(self, q: str):
        await asyncio.sleep(0)
        return {
            "name": "react",
            "version": "18.2.0",
            "description": "React library",
            "homepage": "https://reactjs.org",
        }

    async def fake_gh(self, q: str):
        await asyncio.sleep(0)
        return {
            "name": "react",
            "url": "https://github.com/facebook/react",
            "stars": 200000,
            "description": "A declarative JS library for building UIs",
        }

    monkeypatch.setattr(
        "app.wikipedia_service.WikipediaService.fetch_summary", fake_wiki
    )
    monkeypatch.setattr(
        "app.registry_service.RegistryService.fetch_npm_latest", fake_reg
    )
    monkeypatch.setattr(
        "app.github_service.GithubService.fetch_repo_info", fake_gh
    )

    res = client.get("/lookup/react")
    assert res.status_code == 200

    body = res.json()
    assert body.get("query") == "react"
    assert "wikipedia" in body
    assert "registry" in body or "npm_registry" in body
    assert "github" in body

    assert body["wikipedia"]["title"].lower().startswith("react")
    reg = body.get("registry") or body.get("npm_registry")
    assert reg["version"] == "18.2.0"
    assert body["github"]["stars"] > 1000


def test_lookup_not_found(monkeypatch):
    async def none(*args, **kwargs):
        await asyncio.sleep(0)
        return {"error": "not found"}

    monkeypatch.setattr(
        "app.wikipedia_service.WikipediaService.fetch_summary", none
    )
    monkeypatch.setattr(
        "app.registry_service.RegistryService.fetch_npm_latest", none
    )
    monkeypatch.setattr(
        "app.github_service.GithubService.fetch_repo_info", none
    )

    res = client.get("/lookup/some-unknown-package-xyz")
    assert res.status_code == 200
    body = res.json()

    # Nothing should be found, but response should still include query and structure
    assert body.get("query")
    assert "wikipedia" in body
    assert "github" in body
    assert "registry" in body
    assert body["wikipedia"]["error"] == "not found"
