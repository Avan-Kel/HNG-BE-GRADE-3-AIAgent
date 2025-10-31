#!/usr/bin/env bash
 export PORT=5002
 export CACHE_DB=./data/agent_cache.db
 python-m uvicorn app.main:app--host 0.0.0.0--port $PORT--reload