"""Tests for log_parser service."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.log_parser import (
    parse_logs,
    strip_ansi,
    detect_platform,
    is_flaky_indicator,
)


def test_strip_ansi():
    raw = "\x1b[32mHello\x1b[0m World"
    assert strip_ansi(raw) == "Hello World"


def test_detect_platform_github():
    log = "Run actions/checkout@v3\n::error::something failed"
    assert detect_platform(log) == "github_actions"


def test_detect_platform_jenkins():
    log = "[Pipeline] stage (Build)\nBUILD FAILURE"
    assert detect_platform(log) == "jenkins"


def test_detect_platform_gitlab():
    log = "Running with gitlab-runner 15.0\nsection_start:123:build"
    assert detect_platform(log) == "gitlab"


def test_detect_platform_generic():
    log = "some random log output with no CI markers"
    assert detect_platform(log) == "generic"


def test_parse_python_module_not_found():
    log = "ModuleNotFoundError: No module named 'requests'"
    failures = parse_logs(log)
    assert len(failures) == 1
    assert failures[0].error_type == "ModuleNotFoundError"
    assert "requests" in failures[0].error_message


def test_parse_npm_error():
    log = "npm ERR! code ENOTFOUND\nnpm ERR! errno ENOTFOUND"
    failures = parse_logs(log)
    assert len(failures) >= 1
    assert any(f.error_type == "NpmError" for f in failures)


def test_parse_docker_pull_denied():
    log = "pull access denied for myimage/private, repository does not exist or may require 'docker login'"
    failures = parse_logs(log)
    assert len(failures) == 1
    assert failures[0].error_type == "DockerPullDenied"


def test_parse_docker_connection():
    log = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
    failures = parse_logs(log)
    assert len(failures) == 1
    assert failures[0].error_type == "DockerDaemonUnreachable"


def test_parse_infrastructure_timeout():
    log = "curl: (28) Connection timed out after 30001 milliseconds"
    failures = parse_logs(log)
    assert len(failures) == 1
    assert failures[0].error_type == "ConnectionTimeout"


def test_parse_python_traceback():
    log = """Traceback (most recent call last):
  File "app.py", line 42, in <module>
    result = do_something()
  File "app.py", line 10, in do_something
    raise ValueError("bad input")
ValueError: bad input"""
    failures = parse_logs(log)
    assert len(failures) == 1
    assert "ValueError" in failures[0].error_message
    assert failures[0].stack_trace is not None


def test_parse_jest_failure():
    log = "FAIL src/components/Button.test.tsx\n● Button › renders correctly"
    failures = parse_logs(log)
    assert len(failures) >= 1
    assert any(f.error_type in ("JestTestFail", "JestFailure") for f in failures)


def test_flaky_detection_timeout():
    assert is_flaky_indicator("connection timed out after retry") is True


def test_flaky_detection_race_condition():
    assert is_flaky_indicator("race condition detected in test") is True


def test_flaky_detection_normal():
    assert is_flaky_indicator("ModuleNotFoundError: No module named 'foo'") is False


def test_dedup_errors():
    log = "\n".join([
        "npm ERR! code ENOTFOUND",
        "npm ERR! code ENOTFOUND",
        "npm ERR! code ENOTFOUND",
    ])
    failures = parse_logs(log)
    # Should deduplicate identical errors
    messages = [f.error_message for f in failures]
    assert len(messages) == len(set(messages))


def test_ansi_stripped_before_parsing():
    log = "\x1b[31mModuleNotFoundError: No module named 'boto3'\x1b[0m"
    failures = parse_logs(log)
    assert len(failures) == 1
    assert "boto3" in failures[0].error_message


def test_parse_permission_denied():
    log = "Permission denied: '/etc/secrets/key.pem'"
    failures = parse_logs(log)
    assert len(failures) == 1
    assert failures[0].error_type == "PermissionDenied"


def test_parse_typescript_error():
    log = "error TS2345: Argument of type 'string' is not assignable to parameter of type 'number'."
    failures = parse_logs(log)
    assert len(failures) == 1
    assert failures[0].error_type == "TypeScriptError"


def test_empty_log():
    failures = parse_logs("")
    assert failures == []


def test_no_errors_log():
    log = "Build started...\nCompiling...\nTests passed.\nBuild successful."
    failures = parse_logs(log)
    assert failures == []
