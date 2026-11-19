import pytest
from app.services.ai_agent import run_ai_diagnosis
from app.services.log_parser import parse_logs, extract_environment_context
from app.services.vector_memory import store_failure, update_success, _load_fallback_db
from app.models.schemas import FailureCategory

def test_environment_context_extraction():
    """Verify parser extracts Python, Node, OS, Docker, and CI flags."""
    log = (
        "Runner image: ubuntu-22.04\n"
        "Python 3.10.12 (main, Jun 11 2023)\n"
        "Node.js v18.17.0\n"
        "npm 9.6.7\n"
        "CI=true\n"
        "NODE_ENV=production\n"
    )
    ctx = extract_environment_context(log)
    assert "python_version" in ctx
    assert ctx["python_version"] == "3.10.12"
    assert ctx["node_version"] == "18.17.0"
    assert ctx["npm_version"] == "9.6.7"
    assert "ubuntu" in ctx["os"].lower()
    assert ctx["ci"] == "true"
    assert ctx["node_env"] == "production"

def test_docker_hub_rate_limit_diagnosis():
    """Verify Docker rate limit detection with specific authenticated login remedy."""
    log = (
        "##[group]Build and push Docker image\n"
        "Step 1/8 : FROM python:3.11-slim\n"
        "toomanyrequests: You have reached your pull rate limit. You may increase the limit by authenticating.\n"
        "Process completed with exit code 1."
    )
    result = run_ai_diagnosis(log, "docker_ci.log")
    assert result["failure_count"] == 1
    diag = result["diagnoses"][0]
    assert diag["failure_category"] == FailureCategory.INFRASTRUCTURE.value
    assert "rate limit" in diag["root_cause"].lower()
    assert any("docker login" in cmd for cmd in diag["commands"])

def test_npm_peer_dependency_eresolve_diagnosis():
    """Verify npm ERESOLVE peer dependency conflict provides targeted --legacy-peer-deps advice."""
    log = (
        "npm ERR! code ERESOLVE\n"
        "npm ERR! ERESOLVE unable to resolve dependency tree\n"
        "npm ERR! While resolving: react-scripts@5.0.1\n"
        "npm ERR! Found: typescript@5.3.3\n"
        "npm ERR! Could not resolve dependencies\n"
        "Process completed with exit code 1."
    )
    result = run_ai_diagnosis(log, "frontend.log")
    assert result["failure_count"] == 1
    diag = result["diagnoses"][0]
    assert diag["failure_category"] == FailureCategory.DEPENDENCY.value
    assert "peer" in diag["root_cause"].lower() or "dependency" in diag["root_cause"].lower()
    assert any("--legacy-peer-deps" in cmd for cmd in diag["commands"])

def test_warning_and_success_logs_do_not_produce_false_failures():
    """Verify warnings and successful test runs do not trigger false failure diagnoses."""
    log = (
        "##[group]Run test suite\n"
        "WARNING: The package is deprecated.\n"
        "npm warn deprecated inflight@1.0.6: This module is not supported.\n"
        "DeprecationWarning: Buffer() is deprecated due to security and usability issues.\n"
        "✔ 42 tests passed (4.2s)\n"
        "Build successful!\n"
        "##[endgroup]"
    )
    result = run_ai_diagnosis(log, "success.log")
    assert result["failure_count"] == 0
    assert len(result["diagnoses"]) == 0

def test_feedback_mechanism_updates_vector_memory():
    """Verify that submitting positive feedback increments the memory success counter."""
    error_msg = "UniqueTestError: failed connection to test database cluster"
    fix_msg = "Verify test database host and port bindings"
    doc_id = store_failure(error_msg, "INFRASTRUCTURE", fix_msg)
    assert doc_id != ""

    # Simulate user clicking "Worked"
    update_success(doc_id, success=True)
    db = _load_fallback_db()
    matched = [item for item in db if item.get("id") == doc_id]
    assert len(matched) == 1
    assert matched[0]["metadata"]["success_count"] >= 1
