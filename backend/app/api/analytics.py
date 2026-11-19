from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models.analysis import Analysis, Diagnosis
from app.models.schemas import AnalyticsTrends
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/trends", response_model=AnalyticsTrends)
def get_trends(db: Session = Depends(get_db)):
    # Failures by day (last 30 days)
    cutoff = datetime.utcnow() - timedelta(days=30)
    day_result = db.execute(
        select(
            func.date(Analysis.created_at).label("date"),
            func.sum(Analysis.failure_count).label("count")
        )
        .where(Analysis.created_at >= cutoff)
        .group_by(func.date(Analysis.created_at))
        .order_by(func.date(Analysis.created_at))
    )
    failures_by_day = [{"date": str(row[0]), "count": int(row[1] or 0)} for row in day_result.all()]

    # Top errors
    top_errors_result = db.execute(
        select(Diagnosis.error_message, func.count().label("cnt"))
        .where(Diagnosis.error_message.isnot(None))
        .group_by(Diagnosis.error_message)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_errors = [{"error_message": row[0] or "Unknown", "count": row[1]} for row in top_errors_result.all()]

    # Category trends
    cat_result = db.execute(
        select(Diagnosis.failure_category, func.count().label("cnt"))
        .group_by(Diagnosis.failure_category)
        .order_by(desc("cnt"))
    )
    category_trends = [{"category": row[0], "count": row[1]} for row in cat_result.all()]

    # Fix success rate
    total_feedback = db.execute(
        select(func.count()).select_from(Diagnosis).where(
            Diagnosis.resolution_status.in_(["RESOLVED", "UNRESOLVED"])
        )
    ).scalar() or 0
    resolved = db.execute(
        select(func.count()).select_from(Diagnosis).where(
            Diagnosis.resolution_status == "RESOLVED"
        )
    ).scalar() or 0
    fix_success_rate = (resolved / total_feedback) if total_feedback > 0 else 0.0

    # Flaky tests
    flaky_count = db.execute(
        select(func.count()).select_from(Diagnosis).where(Diagnosis.is_flaky == True)
    ).scalar() or 0

    return AnalyticsTrends(
        failures_by_day=failures_by_day,
        top_errors=top_errors,
        category_trends=category_trends,
        fix_success_rate=round(fix_success_rate, 3),
        flaky_test_count=flaky_count,
    )
