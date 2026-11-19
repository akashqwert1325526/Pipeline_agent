import uuid
import tempfile
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.analysis import Analysis, Diagnosis
from app.models.schemas import AnalysisResponse, DiagnosisCard, LogTextRequest, FailureCategory, ResolutionStatus, SimilarFailure
from app.services.ai_agent import run_ai_diagnosis
from app.config import settings
from datetime import datetime
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_SIZE = settings.max_log_size_mb * 1024 * 1024

def _run_analysis(log_content: str, filename: str, db: Session) -> AnalysisResponse:
    result = run_ai_diagnosis(log_content, filename)
    
    analysis = Analysis(
        id=str(uuid.uuid4()),
        filename=filename,
        platform=result.get("platform"),
        raw_log_preview=log_content[:500],
        failure_count=result.get("failure_count", 0),
        status="completed",
    )
    db.add(analysis)
    
    diagnosis_cards = []
    for d in result.get("diagnoses", []):
        diag = Diagnosis(
            id=d["id"],
            analysis_id=analysis.id,
            pipeline_name=d.get("pipeline_name"),
            failed_step=d.get("failed_step"),
            failure_category=d.get("failure_category", "UNKNOWN"),
            error_message=d.get("error_message", "")[:1000] if d.get("error_message") else None,
            root_cause=d.get("root_cause"),
            confidence_score=d.get("confidence_score", 0.5),
            recommended_fix=d.get("recommended_fix"),
            commands=json.dumps(d.get("commands", [])),
            reasoning=d.get("reasoning"),
            log_evidence=d.get("log_evidence", "")[:1000] if d.get("log_evidence") else None,
            similar_failures=json.dumps(d.get("similar_failures", [])),
            is_flaky=d.get("is_flaky", False),
            rerun_recommended=d.get("rerun_recommended", False),
            resolution_status=d.get("resolution_status", "PENDING"),
        )
        db.add(diag)
        
        similar = [SimilarFailure(**s) for s in d.get("similar_failures", [])]
        diagnosis_cards.append(DiagnosisCard(
            id=diag.id,
            analysis_id=analysis.id,
            pipeline_name=diag.pipeline_name,
            failed_step=diag.failed_step,
            failure_category=FailureCategory(diag.failure_category),
            error_message=diag.error_message,
            root_cause=diag.root_cause,
            confidence_score=diag.confidence_score,
            recommended_fix=diag.recommended_fix,
            commands=d.get("commands", []),
            reasoning=diag.reasoning,
            log_evidence=diag.log_evidence,
            similar_failures=similar,
            is_flaky=diag.is_flaky,
            rerun_recommended=diag.rerun_recommended,
            resolution_status=ResolutionStatus(diag.resolution_status),
        ))
    
    db.commit()
    
    return AnalysisResponse(
        analysis_id=analysis.id,
        filename=filename,
        platform=result.get("platform"),
        failure_count=result.get("failure_count", 0),
        diagnoses=diagnosis_cards,
        created_at=analysis.created_at or datetime.utcnow(),
    )

@router.post("/upload", response_model=AnalysisResponse)
async def upload_log(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith((".txt", ".log")):
        raise HTTPException(status_code=400, detail="Only .txt and .log files are supported.")
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_log_size_mb}MB limit.")
    try:
        log_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            log_text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Cannot decode file content.")
    
    return _run_analysis(log_text, file.filename, db)

@router.post("/text", response_model=AnalysisResponse)
def analyze_text(request: LogTextRequest, db: Session = Depends(get_db)):
    if not request.log_content.strip():
        raise HTTPException(status_code=400, detail="Log content cannot be empty.")
    return _run_analysis(request.log_content, request.filename or "manual_input.log", db)
