from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class FailureCategory(str, Enum):
    CODE_DEFECT = "CODE_DEFECT"
    FLAKY_TEST = "FLAKY_TEST"
    DEPENDENCY = "DEPENDENCY"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"

class ResolutionStatus(str, Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"

class SimilarFailure(BaseModel):
    error_pattern: str
    category: str
    fix: str
    similarity_score: float

class DiagnosisCard(BaseModel):
    id: str
    analysis_id: str
    pipeline_name: Optional[str] = None
    failed_step: Optional[str] = None
    failure_category: FailureCategory = FailureCategory.UNKNOWN
    error_message: Optional[str] = None
    root_cause: Optional[str] = None
    confidence_score: float = 0.5
    recommended_fix: Optional[str] = None
    commands: List[str] = []
    reasoning: Optional[str] = None
    log_evidence: Optional[str] = None
    similar_failures: List[SimilarFailure] = []
    is_flaky: bool = False
    rerun_recommended: bool = False
    resolution_status: ResolutionStatus = ResolutionStatus.PENDING
    resolved_at: Optional[datetime] = None

class AnalysisResponse(BaseModel):
    analysis_id: str
    filename: Optional[str] = None
    platform: Optional[str] = None
    failure_count: int
    diagnoses: List[DiagnosisCard]
    created_at: datetime

class AnalysisSummary(BaseModel):
    id: str
    created_at: datetime
    filename: Optional[str] = None
    platform: Optional[str] = None
    failure_count: int
    status: str
    diagnoses: List[DiagnosisCard] = []

class FeedbackRequest(BaseModel):
    worked: bool
    notes: Optional[str] = None

class DashboardStats(BaseModel):
    total_analyses: int
    total_failures: int
    most_common_category: Optional[str] = None
    recurring_failures: int
    category_distribution: Dict[str, int]
    recent_analyses: List[AnalysisSummary]

class AnalyticsTrends(BaseModel):
    failures_by_day: List[Dict[str, Any]]
    top_errors: List[Dict[str, Any]]
    category_trends: List[Dict[str, Any]]
    fix_success_rate: float
    flaky_test_count: int

class LogTextRequest(BaseModel):
    log_content: str
    filename: Optional[str] = "manual_input.log"

class GithubWorkflowRequest(BaseModel):
    owner: str
    repo: str
    token: str

class ParsedFailure(BaseModel):
    step_name: Optional[str] = None
    platform: Optional[str] = None
    error_type: Optional[str] = None
    error_message: str
    stack_trace: Optional[str] = None
    context_lines: List[str] = []
    line_number: Optional[int] = None
