from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.schemas import GithubWorkflowRequest, AnalysisResponse
from app.services.github_service import get_workflow_runs, get_run_logs
from app.api.analyze import _run_analysis
import httpx
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/workflows")
async def list_workflows(request: GithubWorkflowRequest):
    try:
        runs = await get_workflow_runs(request.owner, request.repo, request.token)
        return {"workflows": runs}
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = ""
        try:
            body = e.response.json().get("message", e.response.text[:300])
        except Exception:
            body = e.response.text[:300]
        if status == 401:
            detail = (
                "GitHub authentication failed (401). Your Personal Access Token is invalid, expired, or lacks permissions. "
                "Go to GitHub → Settings → Developer settings → Personal access tokens → Generate new token. "
                "Make sure to select the 'repo' scope (or at minimum 'actions:read' for Actions)."
            )
        elif status == 404:
            owner = request.owner.strip()
            repo = request.repo.strip()
            detail = (
                f"Repository not found (404): '{owner}/{repo}' does not exist or is not accessible with this token. "
                f"Check the exact URL: https://github.com/{owner}/{repo}. "
                "If the repo is private, your token must have 'repo' scope."
            )
        elif status == 403:
            detail = f"GitHub access forbidden (403): {body}. Your token may lack 'repo' or 'actions:read' scope."
        else:
            detail = f"GitHub API error ({status}): {body}"
        logger.error(f"GitHub API error {status}: {body}")
        raise HTTPException(status_code=status, detail=detail)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot reach GitHub API. Check your internet connection.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="GitHub API request timed out. Try again.")
    except Exception as e:
        logger.error(f"GitHub workflows error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/{run_id}", response_model=AnalysisResponse)
async def analyze_github_run(run_id: int, request: GithubWorkflowRequest, db: Session = Depends(get_db)):
    try:
        log_content = await get_run_logs(request.owner, request.repo, run_id, request.token)
        if not log_content.strip():
            raise HTTPException(status_code=404, detail="No log content found for this run.")
        filename = f"github_{request.owner}_{request.repo}_run_{run_id}.log"
        return _run_analysis(log_content, filename, db)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            raise HTTPException(status_code=401, detail="GitHub authentication failed. Check your token.")
        elif status == 410:
            raise HTTPException(status_code=410, detail="Logs have expired (GitHub retains logs for 90 days).")
        raise HTTPException(status_code=status, detail=f"GitHub API error ({status})")
    except Exception as e:
        logger.error(f"GitHub analyze run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/{run_id}", response_model=AnalysisResponse)
async def analyze_github_run(run_id: int, request: GithubWorkflowRequest, db: Session = Depends(get_db)):
    try:
        log_content = await get_run_logs(request.owner, request.repo, run_id, request.token)
        if not log_content.strip():
            raise HTTPException(status_code=404, detail="No log content found for this run.")
        filename = f"github_{request.owner}_{request.repo}_run_{run_id}.log"
        return _run_analysis(log_content, filename, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
