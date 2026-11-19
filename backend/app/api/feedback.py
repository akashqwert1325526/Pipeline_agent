from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.analysis import Diagnosis
from app.models.schemas import FeedbackRequest
from app.services.vector_memory import update_success
from datetime import datetime

router = APIRouter()

@router.post("/{diagnosis_id}/feedback")
def submit_feedback(diagnosis_id: str, feedback: FeedbackRequest, db: Session = Depends(get_db)):
    result = db.execute(select(Diagnosis).where(Diagnosis.id == diagnosis_id))
    diagnosis = result.scalar_one_or_none()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found.")
    
    diagnosis.resolution_status = "RESOLVED" if feedback.worked else "UNRESOLVED"
    if feedback.worked:
        diagnosis.resolved_at = datetime.utcnow()
    
    db.commit()
    return {"status": "ok", "resolution_status": diagnosis.resolution_status}
