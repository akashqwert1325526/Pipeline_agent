from fastapi import APIRouter
from app.config import settings
from datetime import datetime

router = APIRouter()

@router.get("")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "ai_provider": settings.ai_provider,
        "version": "1.0.0"
    }
