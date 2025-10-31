# app/utils.py
import re

def extract_github_owner_repo_from_url(url: str):
    m = re.search(r"github\.com/([^/]+)/([^/]+)/?", url)
    if m:
        return m.group(1), m.group(2)
    return None, None
