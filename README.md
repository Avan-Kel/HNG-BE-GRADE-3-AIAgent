 # Developer Encyclopedia Agent (A2A)
 This project is a **Developer Encyclopedia** A2A agent that answers questions 
about libraries and frameworks. It implements JSON-RPC 2.0 A2A endpoints 
compatible with Telex and other A2A platforms.
 ## Features- Fetches summaries from Wikipedia

 - Fetches version & install hints from npm and PyPI- Uses GitHub for releases and README fallback- Caches responses in SQLite- Returns JSON-RPC 2.0 `TaskResult` objects with `A2AMessage` and `Artifact`- No LLM / No OpenAI used
 ## Run locally
 ```bash
 python -m venv venv
 source venv/bin/activate
 pip install -r requirements.txt
 ./run.sh