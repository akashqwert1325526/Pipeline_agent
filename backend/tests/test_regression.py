import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.ai_agent import run_ai_diagnosis
from app.services.log_parser import parse_logs
from app.services.vector_memory import (
    store_failure,
    search_similar,
    is_generic_exit_code,
    _load_fallback_db,
    _save_fallback_db
)
from app.models.schemas import FailureCategory

def test_one_missing_vite_dependency_produces_exactly_one_diagnosis():
    """TASK 1, 2, 4: Vite missing dependency produces exactly one structured diagnosis."""
    log = (
        "Error: Cannot find module 'vite'\n"
        "npm ERR! Lifecycle script `build` failed with error\n"
        "npm ERR! code 1\n"
        "Error: Process completed with exit code 1."
    )
    result = run_ai_diagnosis(log, "frontend_ci.log")

    # Exactly 1 failure isolated
    assert result["failure_count"] == 1
    assert len(result["diagnoses"]) == 1

    diag = result["diagnoses"][0]
    # Correct category
    assert diag["failure_category"] == FailureCategory.DEPENDENCY.value
    # Primary error prioritized
    assert "Cannot find module 'vite'" in diag["error_message"]
    # Root cause
    assert "Vite is unavailable in the build environment" in diag["root_cause"]
    # Failed step extracted from npm lifecycle
    assert diag["failed_step"] == "npm run build"
    # Actionable fixes provided (Task 4)
    assert "package.json" in diag["recommended_fix"]
    assert "npm ci" in diag["recommended_fix"]
    assert "development dependencies" in diag["recommended_fix"]
    assert any("npm install -D vite" in cmd for cmd in diag["commands"])

def test_one_python_syntax_error_produces_exactly_one_diagnosis():
    """TASK 1 & 2: One Python syntax error produces exactly one diagnosis."""
    log = (
        "##[group]Run pytest\n"
        "  File \"app/main.py\", line 42\n"
        "    def calculate_tax(amount\n"
        "                           ^\n"
        "SyntaxError: '(' was never closed\n"
        "Process completed with exit code 1.\n"
        "##[endgroup]"
    )
    result = run_ai_diagnosis(log, "python_ci.log")

    assert result["failure_count"] == 1
    diag = result["diagnoses"][0]
    assert diag["failure_category"] == FailureCategory.CODE_DEFECT.value
    assert "SyntaxError" in diag["error_message"]

def test_one_docker_oom_failure_produces_exactly_one_diagnosis():
    """TASK 1 & 2: One Docker OOM failure produces exactly one diagnosis."""
    log = (
        "Step 8/12 : RUN cargo build --release\n"
        "Compiling core v1.0.0\n"
        "Killed process 1234 (cargo) total-vm:4194304kB, anon-rss:3900000kB\n"
        "command was killed by OOM-killer\n"
        "The command '/bin/sh -c cargo build --release' returned a non-zero code: 137\n"
        "Process completed with exit code 137."
    )
    result = run_ai_diagnosis(log, "docker_build.log")

    assert result["failure_count"] == 1
    diag = result["diagnoses"][0]
    assert diag["failure_category"] == FailureCategory.INFRASTRUCTURE.value
    assert "OOM" in diag["root_cause"] or "memory" in diag["root_cause"].lower()

def test_two_independent_errors_produce_two_diagnoses():
    """TASK 1: Genuinely independent errors produce separate diagnosis cards."""
    log = (
        "##[group]Run test suite\n"
        "tests/test_auth.py:25: AssertionError: assert False is True\n"
        "FAILED tests/test_auth.py::test_login - AssertionError: assert False is True\n"
        "\n"
        "tests/test_billing.py:50: KeyError: 'STRIPE_API_KEY'\n"
        "FAILED tests/test_billing.py::test_charge - KeyError: 'STRIPE_API_KEY'\n"
        "Process completed with exit code 1.\n"
        "##[endgroup]"
    )
    result = run_ai_diagnosis(log, "test_suite.log")

    # Two genuinely independent test failures should produce 2 diagnoses
    assert result["failure_count"] == 2
    err_msgs = [d["error_message"] for d in result["diagnoses"]]
    assert any("AssertionError" in m for m in err_msgs)
    assert any("KeyError" in m for m in err_msgs)

def test_generic_exit_code_does_not_become_independent_failure():
    """TASK 2: Generic exit-code messages do not become independent failure cards."""
    log_with_primary = (
        "ImportError: cannot import name 'load_weights' from 'models'\n"
        "Process completed with exit code 1.\n"
        "exit code: 1"
    )
    res1 = run_ai_diagnosis(log_with_primary, "import_err.log")
    # Only 1 card (primary), exit codes are absorbed
    assert res1["failure_count"] == 1
    assert "ImportError" in res1["diagnoses"][0]["error_message"]

    log_only_exit_code = "Process completed with exit code 1."
    res2 = run_ai_diagnosis(log_only_exit_code, "unknown.log")
    # When no root cause exists, at most 1 generic card with low confidence
    assert res2["failure_count"] == 1
    assert res2["diagnoses"][0]["confidence_score"] <= 0.35
    assert res2["diagnoses"][0]["failure_category"] == FailureCategory.UNKNOWN.value

def test_duplicate_chromadb_incidents_are_filtered():
    """TASK 3: Duplicate incidents in vector memory are filtered/deduplicated."""
    # Reset fallback db for clean test
    _save_fallback_db([])

    error_text = "Cannot find module 'lodash'"
    id1 = store_failure(error_text, "DEPENDENCY", "npm install lodash")
    id2 = store_failure(error_text, "DEPENDENCY", "npm install lodash")

    db = _load_fallback_db()
    # Should not duplicate the entry in the list
    matching_entries = [item for item in db if item.get("error_pattern") == error_text]
    assert len(matching_entries) == 1
    # total_count should have incremented
    assert matching_entries[0]["metadata"]["total_count"] >= 2

def test_irrelevant_historical_failures_are_excluded():
    """TASK 3: Vector memory excludes generic exit codes and irrelevant items below threshold."""
    # Generic exit codes are excluded from memory
    assert is_generic_exit_code("Process completed with exit code 1.") is True
    assert is_generic_exit_code("npm ERR! code 1") is True
    assert is_generic_exit_code("Cannot find module 'vite'") is False

    # Store a Java failure
    _save_fallback_db([])
    store_failure("java.lang.NullPointerException at com.app.Service.run", "CODE_DEFECT", "Add null check")

    # Search with a completely unrelated query
    results = search_similar("Permission denied when writing to /var/log/app.log", threshold=0.70)
    # The unrelated Java NullPointerException must NOT be returned
    assert len(results) == 0
