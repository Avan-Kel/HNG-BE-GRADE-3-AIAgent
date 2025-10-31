# app/formatter.py
from uuid import uuid4
from datetime import datetime

class Formatter:
    def __init__(self):
        pass

    def compose(self, query, wiki_resp, npm_resp, pypi_resp, gh_resp, fallback_text) -> dict:
        """
        Compose a single canonical payload (dictionary) that contains
        purpose, usage, installation list, history, latest_version, summary, wiki_url
        """
        name = query
        purpose = ""
        usage = ""
        installation = []
        history = ""
        latest_version = None
        wiki_url = None
        summary_text = None

        # Wikipedia data
        if wiki_resp:
            purpose = wiki_resp.get("description") or ""
            summary_text = wiki_resp.get("extract")
            wiki_url = wiki_resp.get("content_urls", {}).get("desktop", {}).get("page")

        # NPM info
        if npm_resp:
            latest_version = latest_version or npm_resp.get("version")
            installation.append(f"npm install {query}")
            installation.append(f"yarn add {query}")
            if not summary_text and npm_resp.get("description"):
                summary_text = npm_resp.get("description")

        # PyPI info
        if pypi_resp:
            info = pypi_resp.get("info", {})
            latest_version = latest_version or info.get("version")
            installation.append(f"pip install {query}")
            if not summary_text:
                summary_text = info.get("summary")

        # Github info
        if gh_resp:
            latest_version = latest_version or gh_resp.get("tag_name") or gh_resp.get("name")

        # Fallback text
        if not summary_text and fallback_text:
            summary_text = fallback_text

        summary_text = summary_text or "No summary available."

        return {
            "name": name,
            "purpose": purpose,
            "usage": summary_text,
            "installation": installation,
            "history": history,
            "latest_version": latest_version,
            "wiki_url": wiki_url,
            "source": "wikipedia|registry|github|fallback"
        }

    def build_taskresult(self, req_id, task_id, context_id, history_msgs, payload) -> dict:
        message_text_lines = [f"📌 {payload.get('name')}"]

        if payload.get("purpose"):
            message_text_lines.append(f"\n✅ Purpose:\n{payload.get('purpose')}")
        if payload.get("usage"):
            message_text_lines.append(f"\n✅ Usage / Summary:\n{payload.get('usage')}")
        if payload.get("installation"):
            message_text_lines.append(f"\n✅ Installation:\n" + "\n".join(payload.get('installation')))
        if payload.get("history"):
            message_text_lines.append(f"\n✅ History:\n{payload.get('history')}")
        if payload.get("latest_version"):
            message_text_lines.append(f"\n✅ Latest Version:\n{payload.get('latest_version')}")
        if payload.get("wiki_url"):
            message_text_lines.append(
                f"\nData source: Wikipedia ({payload.get('wiki_url')}) — content reuse may require attribution (CC BY SA)."
            )

        text = "\n".join(message_text_lines)

        msg_part = {"kind": "text", "text": text}

        agent_msg = {
            "kind": "message",
            "role": "agent",
            "parts": [msg_part],
            "messageId": str(uuid4()),
            "taskId": task_id
        }

        artifact = {
            "artifactId": str(uuid4()),
            "name": "summary-json",
            "parts": [{"kind": "data", "data": payload}]
        }

        result = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "id": task_id,
                "contextId": context_id,
                "status": {
                    "state": "completed",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "message": agent_msg
                },
                "artifacts": [artifact],
                "history": [],
                "kind": "task"
            }
        }
        return result

    def build_taskresult_from_cached(self, req_id, task_id, context_id, history_msgs, cached_payload) -> dict:
        payload = {**cached_payload, "_cached": True}
        return self.build_taskresult(req_id, task_id, context_id, history_msgs, payload)
