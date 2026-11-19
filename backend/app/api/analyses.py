from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.database import get_db
from app.models.analysis import Analysis, Diagnosis
from app.models.schemas import AnalysisSummary, DiagnosisCard, FailureCategory, ResolutionStatus, SimilarFailure
from typing import List, Optional
import json

router = APIRouter()

def _map_diagnosis(d: Diagnosis, analysis_id: str) -> DiagnosisCard:
    similar = []
    if d.similar_failures:
        try:
            similar = [SimilarFailure(**s) for s in json.loads(d.similar_failures)]
        except Exception:
            pass
    return DiagnosisCard(
        id=d.id,
        analysis_id=analysis_id,
        pipeline_name=d.pipeline_name,
        failed_step=d.failed_step,
        failure_category=FailureCategory(d.failure_category) if d.failure_category else FailureCategory.UNKNOWN,
        error_message=d.error_message,
        root_cause=d.root_cause,
        confidence_score=d.confidence_score or 0.5,
        recommended_fix=d.recommended_fix,
        commands=json.loads(d.commands) if d.commands else [],
        reasoning=d.reasoning,
        log_evidence=d.log_evidence,
        similar_failures=similar,
        is_flaky=d.is_flaky or False,
        rerun_recommended=d.rerun_recommended or False,
        resolution_status=ResolutionStatus(d.resolution_status) if d.resolution_status else ResolutionStatus.PENDING,
        resolved_at=d.resolved_at,
    )

@router.get("", response_model=List[AnalysisSummary])
def list_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    platform: Optional[str] = None,
    db: Session = Depends(get_db)
):
    stmt = select(Analysis).order_by(desc(Analysis.created_at)).offset(skip).limit(limit)
    if platform:
        stmt = stmt.where(Analysis.platform == platform)
    result = db.execute(stmt)
    analyses = result.scalars().all()
    
    output = []
    for a in analyses:
        diag_stmt = select(Diagnosis).where(Diagnosis.analysis_id == a.id)
        diag_result = db.execute(diag_stmt)
        diagnoses = [_map_diagnosis(d, a.id) for d in diag_result.scalars().all()]
        output.append(AnalysisSummary(
            id=a.id,
            created_at=a.created_at,
            filename=a.filename,
            platform=a.platform,
            failure_count=a.failure_count,
            status=a.status,
            diagnoses=diagnoses,
        ))
    return output

@router.get("/{analysis_id}", response_model=AnalysisSummary)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    result = db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    diag_result = db.execute(select(Diagnosis).where(Diagnosis.analysis_id == analysis_id))
    diagnoses = [_map_diagnosis(d, analysis_id) for d in diag_result.scalars().all()]
    return AnalysisSummary(
        id=analysis.id,
        created_at=analysis.created_at,
        filename=analysis.filename,
        platform=analysis.platform,
        failure_count=analysis.failure_count,
        status=analysis.status,
        diagnoses=diagnoses,
    )
