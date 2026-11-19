import os
import json
import uuid
import re
import logging
from typing import List, Optional, Dict, Any
from app.config import settings
from app.models.schemas import SimilarFailure

logger = logging.getLogger(__name__)

# Configurable minimum similarity threshold (Task 3)
SIMILARITY_THRESHOLD = 0.55

# Patterns for generic exit-code messages to EXCLUDE from vector memory
GENERIC_EXIT_PATTERNS = [
    r"process completed with exit code",
    r"exit code: \d+",
    r"command failed with exit code",
    r"npm err! code \d+",
    r"npm err! errno \d+",
    r"lifecycle script",
    r"error: process completed",
    r"make: \*\*\* \[.*\] error \d+",
    r"npm err! a complete log of this run",
]

def is_generic_exit_code(text: str) -> bool:
    if not text:
        return True
    lower = text.lower().strip()
    return any(re.search(pat, lower) for pat in GENERIC_EXIT_PATTERNS)

def infer_ecosystem(text: str) -> str:
    """Infer the technology ecosystem from the error text."""
    lower = text.lower()
    if any(k in lower for k in ["npm", "node", "vite", "yarn", "pnpm", "cannot find module", "package.json", "node_modules", "typescript", "ts"]):
        return "node"
    if any(k in lower for k in ["python", "pip", "pytest", "modulenotfound", "importerror", "syntaxerror", "assertionerror", "traceback", "pyproject"]):
        return "python"
    if any(k in lower for k in ["docker", "daemon", "dockerfile", "container", "oomkilled", "pull access denied"]):
        return "docker"
    if any(k in lower for k in ["java", "maven", "gradle", "nullpointerexception", "pom.xml", "compilation error"]):
        return "java"
    if any(k in lower for k in ["connection", "timeout", "dns", "runner", "dial tcp", "network"]):
        return "infra"
    return "general"

# Check if chromadb is available
CHROMADB_AVAILABLE = False
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    logger.warning("chromadb not installed; utilizing persistent local JSON vector memory fallback.")

_client = None
_collection = None
_fallback_file = os.path.join(settings.chroma_persist_dir, "fallback_failures.json")

def _load_fallback_db() -> List[Dict[str, Any]]:
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    if os.path.exists(_fallback_file):
        try:
            with open(_fallback_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_fallback_db(data: List[Dict[str, Any]]):
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    with open(_fallback_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _text_similarity(t1: str, t2: str, eco1: str = "", eco2: str = "") -> float:
    """Calculate token similarity with ecosystem weighting."""
    # Clean tokens (ignore numbers/punctuation)
    s1 = set(re.findall(r'[a-zA-Z]{3,}', t1.lower()))
    s2 = set(re.findall(r'[a-zA-Z]{3,}', t2.lower()))
    if not s1 or not s2:
        return 0.0
    intersection = len(s1.intersection(s2))
    union = len(s1.union(s2))
    base_sim = intersection / union if union > 0 else 0.0

    # Ecosystem alignment
    if eco1 and eco2:
        if eco1 == eco2:
            base_sim += 0.15
        else:
            base_sim -= 0.25

    return max(0.0, min(1.0, base_sim))

def get_chroma_client():
    global _client
    if not CHROMADB_AVAILABLE:
        return None
    if _client is None:
        try:
            _client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        except Exception as e:
            logger.error(f"ChromaDB persistent init error: {e}")
            try:
                _client = chromadb.Client()
            except Exception as e2:
                logger.error(f"ChromaDB ephemeral init error: {e2}")
                _client = None
    return _client

def get_collection():
    global _collection
    if not CHROMADB_AVAILABLE:
        return None
    if _collection is None:
        client = get_chroma_client()
        if client is None:
            return None
        try:
            _collection = client.get_or_create_collection(
                name="pipeline_failures",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"ChromaDB collection error: {e}")
            return None
    return _collection

def search_similar(error_text: str, n_results: int = 3, threshold: float = SIMILARITY_THRESHOLD) -> List[SimilarFailure]:
    """
    Search ChromaDB/fallback memory for similar historical failures.
    - Excludes generic exit codes.
    - Prioritizes matches from the same ecosystem.
    - Filters out matches below the similarity threshold.
    """
    if is_generic_exit_code(error_text):
        return []

    query_ecosystem = infer_ecosystem(error_text)

    # 1. Try ChromaDB
    if CHROMADB_AVAILABLE:
        try:
            collection = get_collection()
            if collection is not None:
                count = collection.count()
                if count > 0:
                    actual_n = min(n_results * 2, count)
                    results = collection.query(
                        query_texts=[error_text],
                        n_results=actual_n,
                        include=["documents", "metadatas", "distances"]
                    )
                    similar = []
                    if results and results.get("documents") and results["documents"][0]:
                        for i, doc in enumerate(results["documents"][0]):
                            meta = results["metadatas"][0][i] if results["metadatas"] else {}
                            dist = results["distances"][0][i] if results["distances"] else 1.0
                            raw_similarity = max(0.0, 1.0 - dist)
                            item_eco = meta.get("ecosystem", "general")

                            # Adjust similarity by ecosystem
                            adjusted_sim = raw_similarity
                            if item_eco == query_ecosystem and query_ecosystem != "general":
                                adjusted_sim = min(1.0, adjusted_sim + 0.10)
                            elif item_eco != query_ecosystem and item_eco != "general" and query_ecosystem != "general":
                                adjusted_sim = max(0.0, adjusted_sim - 0.20)

                            if adjusted_sim >= threshold:
                                similar.append(SimilarFailure(
                                    error_pattern=doc[:200],
                                    category=meta.get("category", "UNKNOWN"),
                                    fix=meta.get("fix", "No fix recorded"),
                                    similarity_score=round(adjusted_sim, 3)
                                ))

                        # Sort by adjusted similarity descending
                        similar.sort(key=lambda s: s.similarity_score, reverse=True)
                        return similar[:n_results]
        except Exception as e:
            logger.error(f"ChromaDB search error: {e}")

    # 2. Fallback local memory
    try:
        db = _load_fallback_db()
        if not db:
            return []

        scored = []
        for item in db:
            doc_text = item.get("error_pattern", "")
            if is_generic_exit_code(doc_text):
                continue
            item_meta = item.get("metadata", {})
            item_eco = item_meta.get("ecosystem") or infer_ecosystem(doc_text)
            sim = _text_similarity(error_text, doc_text, query_ecosystem, item_eco)
            if sim >= threshold:
                scored.append((sim, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SimilarFailure(
                error_pattern=item["error_pattern"][:200],
                category=item.get("category", "UNKNOWN"),
                fix=item.get("fix", "No fix recorded"),
                similarity_score=round(score, 3)
            )
            for score, item in scored[:n_results]
        ]
    except Exception as e:
        logger.error(f"Fallback search error: {e}")
        return []

def store_failure(error_text: str, category: str, fix: str, metadata: dict = None) -> str:
    """
    Stores failure in memory with:
    - Exclusion of generic exit codes.
    - Automatic deduplication of identical historical incidents.
    - Ecosystem classification.
    """
    if is_generic_exit_code(error_text):
        return ""

    ecosystem = infer_ecosystem(error_text)
    meta = {
        "category": category,
        "fix": fix,
        "ecosystem": ecosystem,
        "success_count": 0,
        "total_count": 1
    }
    if metadata:
        meta.update(metadata)

    doc_id = str(uuid.uuid4())
    normalized_incoming = error_text.strip()[:300]

    # Deduplicate in fallback local store
    try:
        db = _load_fallback_db()
        duplicate_found = False
        for item in db:
            existing_pattern = item.get("error_pattern", "").strip()
            # If normalized text matches or similarity > 0.90 within same ecosystem
            if existing_pattern == normalized_incoming or _text_similarity(existing_pattern, normalized_incoming, ecosystem, item.get("metadata", {}).get("ecosystem")) > 0.90:
                item_meta = item.get("metadata", {})
                item_meta["total_count"] = item_meta.get("total_count", 1) + 1
                if fix and fix != item.get("fix"):
                    item["fix"] = fix
                    item_meta["fix"] = fix
                item["metadata"] = item_meta
                duplicate_found = True
                doc_id = item.get("id", doc_id)
                break

        if not duplicate_found:
            db.append({
                "id": doc_id,
                "error_pattern": normalized_incoming,
                "category": category,
                "fix": fix,
                "metadata": meta,
            })
        _save_fallback_db(db)
    except Exception as e:
        logger.error(f"Fallback store error: {e}")

    # Store in ChromaDB
    if CHROMADB_AVAILABLE:
        try:
            collection = get_collection()
            if collection is not None:
                collection.add(
                    documents=[normalized_incoming],
                    metadatas=[meta],
                    ids=[doc_id]
                )
        except Exception as e:
            logger.error(f"ChromaDB store error: {e}")

    return doc_id

def update_success(chroma_id: str, success: bool):
    if not chroma_id:
        return
    if CHROMADB_AVAILABLE:
        try:
            collection = get_collection()
            if collection is not None:
                result = collection.get(ids=[chroma_id], include=["metadatas"])
                if result and result.get("metadatas"):
                    meta = result["metadatas"][0].copy()
                    meta["total_count"] = meta.get("total_count", 0) + 1
                    if success:
                        meta["success_count"] = meta.get("success_count", 0) + 1
                    collection.update(ids=[chroma_id], metadatas=[meta])
        except Exception as e:
            logger.error(f"ChromaDB update error: {e}")

    # Update in fallback
    try:
        db = _load_fallback_db()
        for item in db:
            if item.get("id") == chroma_id:
                meta = item.get("metadata", {})
                meta["total_count"] = meta.get("total_count", 0) + 1
                if success:
                    meta["success_count"] = meta.get("success_count", 0) + 1
                item["metadata"] = meta
        _save_fallback_db(db)
    except Exception as e:
        logger.error(f"Fallback update error: {e}")
