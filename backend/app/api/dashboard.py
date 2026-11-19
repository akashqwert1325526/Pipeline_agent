from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models.analysis import Analysis, Diagnosis
from app.models.schemas import DashboardStats, AnalysisSummary, DiagnosisCard, FailureCategory, ResolutionStatus, SimilarFailure
import json

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_analyses = db.execute(select(func.count()).select_from(Analysis)).scalar() or 0
    total_failures = db.execute(select(func.count()).select_from(Diagnosis)).scalar() or 0
    
    # Category distribution
    cat_result = db.execute(
        select(Diagnosis.failure_category, func.count().label("cnt"))
        .group_by(Diagnosis.failure_category)
        .order_by(desc("cnt"))
    )
    cat_rows = cat_result.all()
    category_distribution = {row[0]: row[1] for row in cat_rows}
    most_common_category = cat_rows[0][0] if cat_rows else None
    
    # Recurring failures: same error_message appearing > 1 time
    recurring = db.execute(
        select(func.count()).select_from(
            select(Diagnosis.error_message)
            .group_by(Diagnosis.error_message)
            .having(func.count() > 1)
            .subquery()
        )
    ).scalar() or 0
    
    # Recent analyses
    recent_result = db.execute(
        select(Analysis).order_by(desc(Analysis.created_at)).limit(5)
    )
    recent = recent_result.scalars().all()
    recent_summaries = []
    for a in recent:
        diag_result = db.execute(select(Diagnosis).where(Diagnosis.analysis_id == a.id))
        diagnoses = []
        for d in diag_result.scalars().all():
            similar = []
            if d.similar_failures:
                try:
                    similar = [SimilarFailure(**s) for s in json.loads(d.similar_failures)]
                except Exception:
                    pass
            diagnoses.append(DiagnosisCard(
                id=d.id, analysis_id=a.id,
                pipeline_name=d.pipeline_name, failed_step=d.failed_step,
                failure_category=FailureCategory(d.failure_category) if d.failure_category else FailureCategory.UNKNOWN,
                error_message=d.error_message, root_cause=d.root_cause,
                confidence_score=d.confidence_score or 0.5, recommended_fix=d.recommended_fix,
                commands=json.loads(d.commands) if d.commands else [],
                reasoning=d.reasoning, log_evidence=d.log_evidence,
                similar_failures=similar, is_flaky=d.is_flaky or False,
                rerun_recommended=d.rerun_recommended or False,
                resolution_status=ResolutionStatus(d.resolution_status) if d.resolution_status else ResolutionStatus.PENDING,
            ))
        recent_summaries.append(AnalysisSummary(
            id=a.id, created_at=a.created_at, filename=a.filename, platform=a.platform,
            failure_count=a.failure_count, status=a.status, diagnoses=diagnoses
        ))
    
    return DashboardStats(
        total_analyses=total_analyses,
        total_failures=total_failures,
        most_common_category=most_common_category,
        recurring_failures=recurring,
        category_distribution=category_distribution,
        recent_analyses=recent_summaries,
    )
