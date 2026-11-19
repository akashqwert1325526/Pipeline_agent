from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api import analyze, analyses, feedback, dashboard, analytics, github, health

app = FastAPI(
    title="PipelineMedic API",
    description="Intelligent CI/CD Failure Diagnosis Agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/api/analyze", tags=["Analyze"])
app.include_router(analyses.router, prefix="/api/analyses", tags=["Analyses"])
app.include_router(feedback.router, prefix="/api/diagnoses", tags=["Feedback"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub"])
app.include_router(health.router, prefix="/api/health", tags=["Health"])

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"message": "PipelineMedic API is running. Visit /docs for interactive documentation."}
