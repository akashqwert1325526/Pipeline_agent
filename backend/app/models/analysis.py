import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.database import Base
from app.models.schemas import FailureCategory, ResolutionStatus

class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    filename: Mapped[str] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=True)
    raw_log_preview: Mapped[str] = mapped_column(Text, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    diagnoses: Mapped[list["Diagnosis"]] = relationship("Diagnosis", back_populates="analysis", cascade="all, delete-orphan")

class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id"))
    pipeline_name: Mapped[str] = mapped_column(String(255), nullable=True)
    failed_step: Mapped[str] = mapped_column(String(255), nullable=True)
    failure_category: Mapped[str] = mapped_column(String(50), default="UNKNOWN")
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    recommended_fix: Mapped[str] = mapped_column(Text, nullable=True)
    commands: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list
    reasoning: Mapped[str] = mapped_column(Text, nullable=True)
    log_evidence: Mapped[str] = mapped_column(Text, nullable=True)
    similar_failures: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list
    is_flaky: Mapped[bool] = mapped_column(Boolean, default=False)
    rerun_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="diagnoses")

class HistoricalFailure(Base):
    __tablename__ = "historical_failures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    error_pattern: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    fix: Mapped[str] = mapped_column(Text)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
