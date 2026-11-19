from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def deduplicate_failures(failures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate failures by error message."""
    seen = set()
    unique = []
    for f in failures:
        key = (f.get("error_message", "") or "")[:100]
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique

def truncate(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    return text[:max_len] + ("..." if len(text) > max_len else "")

def safe_json_loads(value: str, default=None):
    import json
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default
