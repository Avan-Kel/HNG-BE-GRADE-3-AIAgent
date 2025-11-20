import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from uuid import uuid4
from .models import JSONRPCRequest, JSONRPCResponse
from .wikipedia_service import WikipediaService
from .github_service import GitHubService
from .registry_service import RegistryService
from .fallback_service import FallbackService
from .cache_service import SQLiteCache
from .formatter import Formatter
from fastapi import Query


load_dotenv()

PORT = int(os.getenv("PORT", 5002))
DB_PATH = os.getenv("CACHE_DB", "./data/agent_cache.db")
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "14"))
USER_AGENT = os.getenv("USER_AGENT", "DevEncycloAgent/1.0")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

app = FastAPI(title="Developer Encyclopedia Agent", version="0.1.0")

# Initialize components (will be created in lifespan)
wiki = None
gh = None
reg = None
fallback = None
cache = None
formatter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global wiki, gh, reg, fallback, cache, formatter
    cache = SQLiteCache(DB_PATH, ttl_days=CACHE_TTL_DAYS)
    wiki = WikipediaService(user_agent=USER_AGENT)
    gh = GitHubService(user_agent=USER_AGENT, token=GITHUB_TOKEN)
    reg = RegistryService(user_agent=USER_AGENT)
    fallback = FallbackService(github=gh, registry=reg)
    formatter = Formatter()
    yield


app.router.lifespan_context = lifespan

@app.get("/")
def root():
    return {"message": "The AI Agent is running successfully, check out the docs for more information by adding /docs to the URL"}



@app.post("/a2a/dev")
async def a2a_dev(request: Request):
    try:
        body = await request.json()

        if body.get("jsonrpc") != "2.0" or "id" not in body:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32600, "message": "Invalid Request"},
                },
            )

        rpc = JSONRPCRequest(**body)

        # Extract messages
        if rpc.method == "message/send":
            messages = [rpc.params.message]
            config = rpc.params.configuration
        elif rpc.method == "execute":
            messages = rpc.params.messages
            config = None
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": rpc.id,
                    "error": {"code": -32601, "message": "Method not found"},
                },
            )

        # Get user query (last message text)
        user_msg = messages[-1] if messages else None
        if not user_msg:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": rpc.id,
                    "error": {"code": -32602, "message": "No message provided"},
                },
            )

        text = ""
        for part in user_msg.parts:
            if part.kind == "text" and part.text:
                text = part.text.strip()
                break

        if not text:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": rpc.id,
                    "error": {"code": -32602, "message": "Empty text"},
                },
            )

        key = text.lower()

        # 1) Check cache
        cached = cache.get(key)
        if cached:
            task_id = rpc.params.message.taskId or str(uuid4())
            context_id = str(uuid4())
            response = formatter.build_taskresult_from_cached(
                rpc.id, task_id, context_id, messages, cached
            )
            return response

        # 2) Try Wikipedia
        wiki_resp = await wiki.fetch_summary(text)

        # 3) Try registries & GitHub
        npm_resp = await reg.fetch_npm_latest(text)
        pypi_resp = await reg.fetch_pypi_info(text)

        gh_resp = None
        if wiki_resp and wiki_resp.get("content_urls"):
            # attempt to extract github link from wiki URL fields
            url = wiki_resp.get("content_urls").get("desktop", {}).get("page")
            if url and "github.com" in url:
                import re

                m = re.search(r"github\.com/([^/]+)/([^/]+)/?", url)
                if m:
                    owner, repo = m.groups()
                    gh_resp = await gh.fetch_latest_release(owner, repo)

        # 4) Fallback: GitHub README or registry descriptions
        fallback_text = None
        if not wiki_resp:
            fallback_text = await fallback.fetch_text(text)

        # 5) Build combined result
        combined = formatter.compose(
            text, wiki_resp, npm_resp, pypi_resp, gh_resp, fallback_text
        )

        # 6) Cache and respond
        cache.set(key, combined)

        task_id = rpc.params.message.taskId or str(uuid4())
        context_id = str(uuid4())
        response = formatter.build_taskresult(
            rpc.id, task_id, context_id, messages, combined
        )
        return response

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in locals() else None,
                "error": {"code": -32603, "message": "Internal error", "data": str(e)},
            },
        )

@app.get("/wikipedia_test")
async def wikipedia_test(title: str = Query(..., description="The topic to fetch from Wikipedia")):
    """
    Test endpoint: fetch summary from Wikipedia for a given title.
    Example: /wikipedia_test?title=Python_(programming_language)
    """
    if not wiki:
        return {"error": "Wikipedia service not initialized"}

    result = await wiki.fetch_summary(title)
    if not result:
        return {"error": f"No Wikipedia summary found for '{title}'"}

    # Only return key fields to avoid too much data
    return {
        "title": result.get("title"),
        "description": result.get("description"),
        "extract": result.get("extract"),
        "url": result.get("content_urls", {}).get("desktop", {}).get("page")
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "dev-encyclo"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)
