import httpx
import zipfile
import io
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

def _normalize_repo(repo: str) -> str:
    """Normalize repo name: strip whitespace but preserve original casing and separators."""
    return repo.strip()

def _get_auth_header(token: str) -> str:
    clean = token.strip()
    if clean.startswith("Bearer ") or clean.startswith("token "):
        return clean
    return f"token {clean}"

async def _authed_get(client: httpx.AsyncClient, url: str, headers: dict, params: dict = None) -> httpx.Response:
    """Make a GET request, automatically retrying with alternate auth format on 401."""
    resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 401:
        # Try alternate auth format
        alt_headers = headers.copy()
        current_auth = headers.get("Authorization", "")
        if current_auth.startswith("token "):
            alt_headers["Authorization"] = "Bearer " + current_auth[6:]
        else:
            alt_headers["Authorization"] = "token " + current_auth.replace("Bearer ", "")
        resp = await client.get(url, headers=alt_headers, params=params)
    return resp

async def get_workflow_runs(owner: str, repo: str, token: str, per_page: int = 30) -> List[Dict[str, Any]]:
    clean_owner = owner.strip()
    clean_repo = _normalize_repo(repo)
    clean_token = token.strip()

    headers = {
        "Authorization": _get_auth_header(clean_token),
        "Accept": "application/vnd.github+json",
        "User-Agent": "PipelineMedic-CI-Agent/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{GITHUB_API}/repos/{clean_owner}/{clean_repo}/actions/runs"

        # First try: status=failure (completed runs with failure conclusion)
        resp = await _authed_get(client, url, headers, params={"per_page": per_page})

        if resp.status_code == 404:
            # Try URL-encoding spaces as hyphens as a fallback
            alt_repo = clean_repo.replace(" ", "-")
            resp = await _authed_get(client, f"{GITHUB_API}/repos/{clean_owner}/{alt_repo}/actions/runs", headers, params={"per_page": per_page})

        resp.raise_for_status()
        data = resp.json()

        runs = []
        for run in data.get("workflow_runs", []):
            conclusion = run.get("conclusion", "")
            status = run.get("status", "")
            # Include runs that failed or were cancelled (both are actionable)
            if conclusion in ("failure", "timed_out", "cancelled", "action_required") or status == "failure":
                runs.append({
                    "id": run["id"],
                    "name": run.get("name", ""),
                    "workflow_name": run.get("display_title", run.get("name", "")),
                    "status": status,
                    "conclusion": conclusion,
                    "created_at": run.get("created_at", ""),
                    "html_url": run.get("html_url", ""),
                    "head_commit_message": run.get("head_commit", {}).get("message", ""),
                    "head_branch": run.get("head_branch", ""),
                })
        return runs

async def get_run_logs(owner: str, repo: str, run_id: int, token: str) -> str:
    clean_owner = owner.strip()
    clean_repo = _normalize_repo(repo)
    clean_token = token.strip()

    headers = {
        "Authorization": _get_auth_header(clean_token),
        "Accept": "application/vnd.github+json",
        "User-Agent": "PipelineMedic-CI-Agent/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        url = f"{GITHUB_API}/repos/{clean_owner}/{clean_repo}/actions/runs/{run_id}/logs"
        resp = await _authed_get(client, url, headers)

        if resp.status_code == 404:
            # Try with hyphens
            alt_repo = clean_repo.replace(" ", "-")
            resp = await _authed_get(client, f"{GITHUB_API}/repos/{clean_owner}/{alt_repo}/actions/runs/{run_id}/logs", headers)

        resp.raise_for_status()

        # Extract text from ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                log_texts = []
                for name in sorted(zf.namelist()):
                    if name.endswith(".txt"):
                        try:
                            content = zf.read(name).decode("utf-8", errors="replace")
                            log_texts.append(f"=== {name} ===\n{content}")
                        except Exception:
                            pass
                return "\n\n".join(log_texts)
        except Exception as e:
            logger.error(f"Error extracting log ZIP: {e}")
            return resp.text[:50000]
