import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.database import SessionLocal, init_db
from app.api.health import health
from app.api.analyze import analyze_text
from app.api.analyses import list_analyses, get_analysis
from app.api.feedback import submit_feedback
from app.api.dashboard import get_dashboard_stats
from app.api.analytics import get_trends
from app.models.schemas import LogTextRequest, FeedbackRequest
from main import root

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_root_endpoint():
    data = root()
    assert "message" in data
    assert "PipelineMedic" in data["message"]

def test_health_endpoint():
    data = health()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "ai_provider" in data

def test_analyze_text_with_error(db):
    log = "ModuleNotFoundError: No module named 'pandas'"
    req = LogTextRequest(log_content=log, filename="test.log")
    res = analyze_text(req, db)
    assert res.analysis_id is not None
    assert res.failure_count >= 1
    assert len(res.diagnoses) >= 1
    diag = res.diagnoses[0]
    assert diag.failure_category.value == "DEPENDENCY"
    assert "pip install" in diag.recommended_fix

def test_get_analyses(db):
    analyses = list_analyses(skip=0, limit=20, db=db)
    assert isinstance(analyses, list)
    assert len(analyses) >= 1
    analysis_id = analyses[0].id
    single = get_analysis(analysis_id, db=db)
    assert single.id == analysis_id

def test_dashboard_stats(db):
    stats = get_dashboard_stats(db=db)
    assert stats.total_analyses >= 1
    assert stats.total_failures >= 1
    assert isinstance(stats.category_distribution, dict)

def test_analytics_trends(db):
    trends = get_trends(db=db)
    assert hasattr(trends, "failures_by_day")
    assert hasattr(trends, "top_errors")
    assert hasattr(trends, "category_trends")
    assert hasattr(trends, "fix_success_rate")

def test_feedback_endpoint(db):
    analyses = list_analyses(skip=0, limit=10, db=db)
    assert len(analyses) > 0
    if analyses[0].diagnoses:
        diag_id = analyses[0].diagnoses[0].id
        fb = FeedbackRequest(worked=True)
        res = submit_feedback(diag_id, fb, db=db)
        assert res["status"] == "ok"
        assert res["resolution_status"] == "RESOLVED"
