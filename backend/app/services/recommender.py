"""
Recommender service - placeholder for future ML-based fix recommendation.
Currently delegates to rule-based logic in ai_agent.py.
"""
from typing import List, Dict, Any
from app.models.schemas import SimilarFailure


def rank_fixes(similar: List[SimilarFailure], error_type: str) -> List[SimilarFailure]:
    """Rank similar failures by similarity score descending."""
    return sorted(similar, key=lambda s: s.similarity_score, reverse=True)


def suggest_fix(error_type: str, similar: List[SimilarFailure]) -> str:
    """Return the best fix suggestion from similar failures or a generic message."""
    ranked = rank_fixes(similar, error_type)
    if ranked and ranked[0].similarity_score > 0.7:
        return ranked[0].fix
    return "Review the full log for more context and retry the pipeline."
