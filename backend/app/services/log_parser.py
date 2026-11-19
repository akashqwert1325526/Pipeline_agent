"""
log_parser.py – CI/CD expert log parsing engine.

Responsibilities:
  1. Extract structured environment context (Python/Node versions, OS, Docker, CI config).
  2. Identify primary root-cause errors with high precision patterns.
  3. Merge cascading/secondary messages into the same incident.
  4. Skip warning-only and success-only logs gracefully.
  5. Preserve rich evidence (stack traces, context lines) for the AI agent.
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from app.models.schemas import ParsedFailure

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[mGKHF]|\x1b\[[?][0-9;]*[hl]|\x1b\]0;[^\x07]*\x07')

# ─── Platform detection patterns ─────────────────────────────────────────────
GITHUB_PATTERNS = [
    "##[error]", "##[group]", "::error::", "::warning::", "::set-output",
    "Run actions/", "actions/checkout@", "GITHUB_WORKSPACE", "github.com/actions",
]
JENKINS_PATTERNS = [
    "[Pipeline]", "hudson.plugins", "jenkins.model", "org.jenkinsci.plugins",
    "Started by user", "Finished: FAILURE", "Finished: SUCCESS",
]
GITLAB_PATTERNS = [
    "$ gitlab-runner", "Running with gitlab-runner", "section_start:",
    "section_end:", "gitlab-ci.yml", "CI_JOB_ID",
]
CIRCLECI_PATTERNS = ["CircleCI", "circle-ci", "CIRCLE_", "circleci.com"]
AZURE_PATTERNS = ["##vso[", "Azure Pipelines", "SYSTEM_TEAMPROJECT", "Build.SourceBranch"]

# ─── Environment context extraction ──────────────────────────────────────────
ENV_PATTERNS = {
    "python_version":   re.compile(r'[Pp]ython\s+(\d+\.\d+(?:\.\d+)?)', re.IGNORECASE),
    "node_version":     re.compile(r'[Nn]ode(?:\.js)?\s+v?(\d+\.\d+(?:\.\d+)?)', re.IGNORECASE),
    "npm_version":      re.compile(r'npm\s+(\d+\.\d+(?:\.\d+)?)', re.IGNORECASE),
    "os":               re.compile(r'(?:ubuntu|debian|alpine|centos|rhel|windows|macos|darwin)[- ]\S+', re.IGNORECASE),
    "docker_image":     re.compile(r'(?:FROM|from)\s+(\S+:\S+)'),
    "runner_arch":      re.compile(r'\b(amd64|arm64|x86_64|aarch64)\b'),
    "java_version":     re.compile(r'[Jj]ava\s+version\s+"?(\d+(?:\.\d+)*)"?'),
    "pip_version":      re.compile(r'pip\s+(\d+\.\d+(?:\.\d+)?)'),
    "poetry_version":   re.compile(r'[Pp]oetry\s+(\d+\.\d+(?:\.\d+)?)'),
    "node_env":         re.compile(r'NODE_ENV\s*=\s*(\S+)'),
    "ci_flag":          re.compile(r'\bCI\s*=\s*(true|1)\b'),
}

# ─── Primary root-cause patterns (ordered by priority) ───────────────────────
# Format: (pattern, error_type, category, ecosystem)
PRIMARY_PATTERNS = [
    # Node / JavaScript / TypeScript – Dependencies
    (r"Cannot find module ['\"]([^'\"]+)['\"]",                       "CannotFindModule",        "DEPENDENCY",      "node"),
    (r"Module not found: Error: Can't resolve ['\"]([^'\"]+)['\"]",   "ModuleNotFound",          "DEPENDENCY",      "node"),
    (r"ERESOLVE unable to resolve dependency tree",                    "NpmEResolve",             "DEPENDENCY",      "node"),
    (r"Could not resolve dependencies",                                "NpmDependencyResolution", "DEPENDENCY",      "node"),
    (r"npm ERR! code (E[A-Z0-9_]+)\b",                                "NpmError",                "DEPENDENCY",      "node"),
    (r"error TS(\d+): (.+)",                                           "TypeScriptError",         "CODE_DEFECT",     "node"),
    (r"● (.+) › (.+)",                                                 "JestFailure",             "CODE_DEFECT",     "node"),
    (r"FAIL (.+\.test\.[jt]sx?)",                                      "JestTestFail",            "CODE_DEFECT",     "node"),
    (r"ReferenceError: (.+) is not defined",                           "ReferenceError",          "CODE_DEFECT",     "node"),
    (r"TypeError: (.+) is not a function",                             "JsTypeError",             "CODE_DEFECT",     "node"),
    (r"SyntaxError: (.+)\s+\(<anonymous>\)",                           "JsSyntaxError",           "CODE_DEFECT",     "node"),
    (r"ERR_INVALID_ARG_TYPE",                                          "NodeArgTypeError",        "CODE_DEFECT",     "node"),

    # Python – Dependencies
    (r"ModuleNotFoundError: No module named ['\"]?([^'\" ]+)['\"]?",  "ModuleNotFoundError",     "DEPENDENCY",      "python"),
    (r"ImportError: (.+)",                                             "ImportError",             "DEPENDENCY",      "python"),
    (r"No matching distribution found for (.+)",                       "NoMatchingDistribution",  "DEPENDENCY",      "python"),
    (r"Could not find a version that satisfies the requirement (.+)",  "NoMatchingDistribution",  "DEPENDENCY",      "python"),
    (r"PackageNotFoundError: No package '(.+)' found",                 "PackageNotFoundError",    "DEPENDENCY",      "python"),

    # Python – Code Defects
    (r"SyntaxError: (.+)",                                             "SyntaxError",             "CODE_DEFECT",     "python"),
    (r"IndentationError: (.+)",                                        "IndentationError",        "CODE_DEFECT",     "python"),
    (r"AssertionError: (.+)",                                          "AssertionError",          "CODE_DEFECT",     "python"),
    (r"FAILED (.+) - (.+)",                                            "PytestFailure",           "CODE_DEFECT",     "python"),
    (r"E\s+(.+Error.+)",                                               "PytestError",             "CODE_DEFECT",     "python"),
    (r"AttributeError: (.+)",                                          "AttributeError",          "CODE_DEFECT",     "python"),
    (r"TypeError: (.+)",                                               "TypeError",               "CODE_DEFECT",     "python"),
    (r"ValueError: (.+)",                                              "ValueError",              "CODE_DEFECT",     "python"),
    (r"KeyError: (.+)",                                                "KeyError",                "CODE_DEFECT",     "python"),
    (r"NameError: (.+)",                                               "NameError",               "CODE_DEFECT",     "python"),
    (r"RuntimeError: (.+)",                                            "RuntimeError",            "CODE_DEFECT",     "python"),
    (r"RecursionError: (.+)",                                          "RecursionError",          "CODE_DEFECT",     "python"),
    (r"FileNotFoundError: \[Errno 2\] No such file or directory: '(.+)'", "PythonFileNotFound",  "CONFIGURATION",   "python"),
    (r"PermissionError: \[Errno 13\] Permission denied: '(.+)'",       "PythonPermissionError",   "CONFIGURATION",   "python"),

    # Java / JVM
    (r"java\.lang\.NullPointerException",                              "NullPointerException",    "CODE_DEFECT",     "java"),
    (r"java\.lang\.ClassNotFoundException: (.+)",                      "ClassNotFoundException",  "DEPENDENCY",      "java"),
    (r"java\.lang\.NoSuchMethodError: (.+)",                           "NoSuchMethodError",       "CODE_DEFECT",     "java"),
    (r"COMPILATION ERROR",                                             "CompilationError",        "CODE_DEFECT",     "java"),
    (r"error: (.+\.java:\d+: error: .+)",                              "JavaCompileError",        "CODE_DEFECT",     "java"),
    (r"Could not find artifact (.+)",                                  "MavenArtifactNotFound",   "DEPENDENCY",      "java"),
    (r"BeanDefinitionParsingException: (.+)",                          "SpringBeanError",         "CONFIGURATION",   "java"),

    # Resource & OOM
    (r"(OOMKilled|command was killed by OOM-killer|Killed process \d+ \((.+)\) total-vm:\d+kB|container .+ was oom killed|JavaScript heap out of memory|fatal error: runtime: out of memory|java\.lang\.OutOfMemoryError)", "OOMKilled", "INFRASTRUCTURE", "system"),
    (r"SIGKILL",                                                       "ProcessKilled",           "INFRASTRUCTURE",  "system"),
    (r"signal: killed",                                                "ProcessKilled",           "INFRASTRUCTURE",  "system"),
    (r"disk quota exceeded",                                           "DiskQuotaExceeded",       "INFRASTRUCTURE",  "system"),
    (r"no space left on device",                                       "NoSpaceLeft",             "INFRASTRUCTURE",  "system"),

    # Infrastructure & Network
    (r"(dial tcp .+: connect: connection refused|Connection refused)",  "ConnectionRefused",      "INFRASTRUCTURE",  "infra"),
    (r"(Connection timed out|connect: connection timed out|operation timed out)", "ConnectionTimeout", "INFRASTRUCTURE", "infra"),
    (r"(Could not resolve host: (.+)|Name or service not known|Temporary failure in name resolution)", "DnsFailure", "INFRASTRUCTURE", "infra"),
    (r"No such runner",                                                "RunnerUnavailable",       "INFRASTRUCTURE",  "infra"),
    (r"Cannot connect to the Docker daemon",                           "DockerDaemonUnreachable", "INFRASTRUCTURE",  "docker"),
    (r"Error response from daemon: (.+)",                              "DockerDaemonError",       "INFRASTRUCTURE",  "docker"),
    (r"toomanyrequests: (.+)",                                         "DockerRateLimit",         "INFRASTRUCTURE",  "docker"),
    (r"context deadline exceeded",                                     "ContextDeadlineExceeded", "INFRASTRUCTURE",  "infra"),
    (r"i/o timeout",                                                   "IOTimeout",               "INFRASTRUCTURE",  "infra"),

    # Configuration, Auth & Docker Build
    (r"failed to solve: (.+)",                                         "DockerBuildFail",         "CONFIGURATION",   "docker"),
    (r"pull access denied for (.+)",                                   "DockerPullDenied",        "CONFIGURATION",   "docker"),
    (r"unauthorized: authentication required",                         "DockerAuthFail",          "CONFIGURATION",   "docker"),
    (r"manifest unknown",                                              "DockerManifestUnknown",   "CONFIGURATION",   "docker"),
    (r"Missing required environment variable: (.+)",                   "MissingEnvVar",           "CONFIGURATION",   "config"),
    (r"No such file or directory: '([^']+)'",                          "FileNotFound",            "CONFIGURATION",   "config"),
    (r"(Permission denied: '([^']+)'|Permission denied \(publickey\)|Permission denied)", "PermissionDenied", "CONFIGURATION", "config"),
    (r"(?i)authentication failed",                                     "AuthFailed",              "CONFIGURATION",   "config"),
    (r"fatal: repository '(.+)' not found",                            "RepoNotFound",            "CONFIGURATION",   "config"),
    (r"fatal: unable to access '(.+)': (.+)",                          "GitAccessFailed",         "CONFIGURATION",   "config"),
    (r"error: failed to push some refs",                               "GitPushFailed",           "CONFIGURATION",   "config"),
    (r"(?i)secret or key is not set",                                  "SecretMissing",           "CONFIGURATION",   "config"),
    (r"(?i)invalid token",                                             "InvalidToken",            "CONFIGURATION",   "config"),
    (r"(?i)(api key|access key|secret key|token)\s*(is\s*)?(invalid|expired|missing|not found)", "CredentialError", "CONFIGURATION", "config"),
]

# ─── Secondary / cascading patterns (absorbed into primary incident) ──────────
SECONDARY_PATTERNS = [
    (r"Process completed with exit code (\d+)",          "NonZeroExit"),
    (r"exit code: \d+",                                  "ExitCode"),
    (r"Command failed with exit code \d+",               "CommandFailedExit"),
    (r"returned a non-zero code: \d+",                   "NonZeroCodeExit"),
    (r"npm ERR! code \d+",                               "NpmGenericCode"),
    (r"npm ERR! errno \d+",                              "NpmGenericErrno"),
    (r"npm ERR! Lifecycle script `([^`]+)` failed",      "NpmLifecycleScript"),
    (r"npm ERR! A complete log of this run",             "NpmLogPath"),
    (r"npm ERR! (.+)",                                   "NpmGenericError"),
    (r"BUILD FAILURE",                                   "MavenBuildFailure"),
    (r"FAILURE: Build failed with an exception\.",       "GradleFailure"),
    (r"make: \*\*\* \[.*\] Error \d+",                  "MakeError"),
    (r"Error: Process completed with exit code",         "ErrorProcessExit"),
    (r"\[error\] TESTS RUN FAILED",                      "TestRunFailed"),
    (r"The build exited with error",                     "BuildExitError"),
    (r"Build exited with code \d+",                      "BuildExitCode"),
]

# ─── Warning-only patterns (never become a failure) ──────────────────────────
WARNING_ONLY_PATTERNS = [
    re.compile(r'^\s*WARNING', re.IGNORECASE),
    re.compile(r'^\s*WARN\s', re.IGNORECASE),
    re.compile(r'\bDeprecationWarning\b'),
    re.compile(r'\bPendingDeprecationWarning\b'),
    re.compile(r'npm warn', re.IGNORECASE),
]

FLAKY_INDICATORS = [
    r"flaky", r"intermittent", r"timing", r"timeout", r"timed out", r"retry",
    r"race.condition", r"randomly.fail", r"sometimes.fail", r"connection.reset",
    r"eof", r"network.error", r"socket hang", r"epipe",
]

TRACEBACK_START = re.compile(r'^Traceback \(most recent call last\):', re.MULTILINE)
JAVA_TRACE_START = re.compile(r'^\s+at [\w\$\.]+\([\w\$\.]+:\d+\)', re.MULTILINE)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub('', text)


def is_warning_only(line: str) -> bool:
    return any(p.search(line) for p in WARNING_ONLY_PATTERNS)


def is_success_line(line: str) -> bool:
    lower = line.lower()
    return any(k in lower for k in [
        "passed", "succeeded", "build successful", "tests passed",
        "✓", "✔", "all checks passed",
    ]) and not any(k in lower for k in ["failed", "error", "warn"])


def detect_platform(text: str) -> str:
    """Detect CI platform with high precision. Returns 'generic' if evidence is insufficient."""
    if any(pat in text for pat in GITHUB_PATTERNS):
        return "github_actions"
    if any(pat in text for pat in JENKINS_PATTERNS):
        return "jenkins"
    if any(pat in text for pat in GITLAB_PATTERNS):
        return "gitlab"
    if any(pat in text for pat in CIRCLECI_PATTERNS):
        return "circleci"
    if any(pat in text for pat in AZURE_PATTERNS):
        return "azure_devops"
    return "generic"


def extract_environment_context(text: str) -> Dict[str, str]:
    """
    Extract runtime versions, OS, Docker image and CI environment flags.
    Returns a dict of discovered context keys.
    """
    ctx: Dict[str, str] = {}
    for key, pattern in ENV_PATTERNS.items():
        m = pattern.search(text)
        if m:
            ctx[key] = m.group(1) if m.lastindex else m.group(0)
    # Detect CI=true flag for NODE_ENV defaulting issues
    if re.search(r'\bCI\s*=\s*(?:true|1)\b', text):
        ctx["ci"] = "true"
    return ctx


def extract_step_name(line: str, platform: str) -> Optional[str]:
    # npm lifecycle
    npm_match = re.search(r'Lifecycle script\s+[`\'"]?([a-zA-Z0-9_\-:]+)', line)
    if npm_match:
        return f"npm run {npm_match.group(1)}"

    if platform in ("github_actions",):
        m = re.search(r'##\[group\]Run (.+)', line)
        if m:
            return m.group(1).strip()[:80]
        m = re.search(r'##\[group\](.+)', line)
        if m:
            return m.group(1).strip()[:80]
    elif platform == "jenkins":
        m = re.search(r'\[Pipeline\] stage \((.+)\)', line)
        if m:
            return m.group(1).strip()
    elif platform == "gitlab":
        m = re.search(r'section_start:\d+:(\w+)', line)
        if m:
            return m.group(1).strip()
    return None


def is_flaky_indicator(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pat, lower) for pat in FLAKY_INDICATORS)


def extract_traceback(lines: List[str], start_idx: int) -> Tuple[str, int]:
    tb_lines = [lines[start_idx]]
    i = start_idx + 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == '' and i + 1 < len(lines) and not lines[i + 1].startswith(' '):
            break
        tb_lines.append(line)
        i += 1
        if i - start_idx > 60:
            break
    return '\n'.join(tb_lines), i


def _find_matching_incident(
    failures: List[ParsedFailure],
    error_type: str,
    error_msg: str,
    line_no: int,
    step: Optional[str],
) -> Optional[ParsedFailure]:
    """Find an existing incident that this error belongs to (cascading / duplicate)."""
    for existing in failures:
        # Same OOM → always merge
        if error_type == "OOMKilled" and existing.error_type == "OOMKilled":
            return existing

        # npm dependency / ERESOLVE grouping
        if (
            existing.error_type in ("NpmEResolve", "NpmDependencyResolution", "NpmError")
            and error_type in ("NpmEResolve", "NpmDependencyResolution", "NpmError")
        ):
            if error_type == "NpmEResolve":
                existing.error_type = "NpmEResolve"
                existing.error_message = error_msg
            return existing

        # Same test file (pytest, jest)
        tf_ex = re.search(r'(tests?/[\w\./\\]+\.py)', existing.error_message)
        tf_new = re.search(r'(tests?/[\w\./\\]+\.py)', error_msg)
        if tf_ex and tf_new and tf_ex.group(1) == tf_new.group(1):
            return existing

        # pytest: same assertion body
        if (
            existing.error_type in ("AssertionError", "PytestError", "PytestFailure",
                                    "KeyError", "AttributeError", "TypeError", "ValueError")
            and error_type in ("AssertionError", "PytestError", "PytestFailure",
                               "KeyError", "AttributeError", "TypeError", "ValueError")
        ):
            if "assert " in existing.error_message and "assert " in error_msg:
                s1 = existing.error_message.split("assert ")[-1].strip()
                s2 = error_msg.split("assert ")[-1].strip()
                if s1 and s2 and (s1 in s2 or s2 in s1):
                    return existing
            q1 = re.search(r"['\"]([^'\"]{3,})['\"]", existing.error_message)
            q2 = re.search(r"['\"]([^'\"]{3,})['\"]", error_msg)
            if q1 and q2 and q1.group(1) == q2.group(1):
                if not step or not existing.step_name or existing.step_name == step:
                    return existing

        # Same missing module
        if "Cannot find module" in existing.error_message and "Cannot find module" in error_msg:
            m1 = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", existing.error_message)
            m2 = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", error_msg)
            if m1 and m2 and m1.group(1) == m2.group(1):
                return existing

        # Same error type, same step, within 15 lines
        if existing.error_type == error_type and existing.step_name == step:
            if existing.line_number and abs(existing.line_number - line_no) <= 15:
                return existing

        # Identical message
        if existing.error_message.strip() == error_msg.strip():
            return existing

    return None


# ─── Main parser ─────────────────────────────────────────────────────────────

def parse_logs(raw_log: str) -> List[ParsedFailure]:
    """
    Expert CI/CD log parser:
    1. Strips ANSI codes.
    2. Extracts environment context (versions, OS, Docker, CI flags).
    3. Detects CI platform.
    4. Identifies primary root-cause errors (highest priority first).
    5. Merges cascading / secondary messages into the same incident.
    6. Preserves multiple cards only for genuinely independent failures.
    7. Skips warning-only and success-only logs.
    """
    cleaned = strip_ansi(raw_log)
    lines = cleaned.splitlines()
    platform = detect_platform(cleaned)
    env_ctx = extract_environment_context(cleaned)

    # Pre-scan: infer npm lifecycle step name
    inferred_step: Optional[str] = None
    for line in lines:
        m = re.search(r'Lifecycle script\s+[`\'"]?([a-zA-Z0-9_\-:]+)', line)
        if m:
            inferred_step = f"npm run {m.group(1)}"
            break

    primary_failures: List[ParsedFailure] = []
    secondary_messages: List[Dict[str, Any]] = []
    current_step: Optional[str] = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # Update current step
        step = extract_step_name(line, platform)
        if step:
            current_step = step

        # Skip pure warning lines (don't create false failures)
        if is_warning_only(line) and not any(
            re.search(p, line) for p, *_ in PRIMARY_PATTERNS
        ):
            i += 1
            continue

        # ── Traceback block ────────────────────────────────────────────────
        if TRACEBACK_START.match(line):
            tb, end_i = extract_traceback(lines, i)
            error_line: Optional[str] = None
            error_type = "PythonException"

            # Walk traceback lines for a known error signature
            for tb_line in tb.splitlines():
                for pattern, etype, *_ in PRIMARY_PATTERNS:
                    m = re.search(pattern, tb_line)
                    if m:
                        error_line = tb_line.strip()
                        error_type = etype
                        break
                if error_line:
                    break

            if not error_line:
                tb_list = [l.strip() for l in tb.splitlines() if l.strip()]
                error_line = tb_list[-1] if tb_list else "Unknown Python exception"
                for pattern, etype, *_ in PRIMARY_PATTERNS:
                    if re.search(pattern, error_line):
                        error_type = etype
                        break

            existing = _find_matching_incident(
                primary_failures, error_type, error_line, i + 1,
                current_step or inferred_step
            )
            if existing:
                existing.context_lines.append(error_line)
                if not existing.stack_trace:
                    existing.stack_trace = tb
            else:
                ctx_start = max(0, i - 4)
                ctx_lines = [l for l in lines[ctx_start:i] if l.strip() and not is_warning_only(l)]
                pf = ParsedFailure(
                    step_name=current_step or inferred_step,
                    platform=platform,
                    error_type=error_type,
                    error_message=error_line,
                    stack_trace=tb,
                    context_lines=ctx_lines,
                    line_number=i + 1,
                )
                # Attach env context
                pf.context_lines.insert(0, f"[ENV] {_format_env(env_ctx)}" if env_ctx else "")
                pf.context_lines = [c for c in pf.context_lines if c.strip()]
                primary_failures.append(pf)

            i = end_i
            continue

        # ── Primary root-cause patterns ────────────────────────────────────
        matched_primary = False
        for pattern, error_type, *_ in PRIMARY_PATTERNS:
            m = re.search(pattern, line)
            if m:
                error_msg = line.strip()
                existing = _find_matching_incident(
                    primary_failures, error_type, error_msg, i + 1,
                    current_step or inferred_step
                )
                if existing:
                    existing.context_lines.append(error_msg)
                else:
                    ctx_start = max(0, i - 5)
                    ctx_end = min(len(lines), i + 7)
                    ctx_lines = (
                        [l for l in lines[ctx_start:i] if l.strip() and not is_warning_only(l)]
                        + [l for l in lines[i + 1:ctx_end] if l.strip() and not is_warning_only(l)]
                    )

                    # Collect Java stack trace immediately following
                    stack: Optional[str] = None
                    if error_type in ("NullPointerException", "JavaCompileError",
                                      "ClassNotFoundException", "NoSuchMethodError"):
                        st_lines = [line]
                        j = i + 1
                        while j < len(lines) and j < i + 25:
                            if JAVA_TRACE_START.match(lines[j]):
                                st_lines.append(lines[j])
                                j += 1
                            else:
                                break
                        if len(st_lines) > 1:
                            stack = '\n'.join(st_lines)

                    pf = ParsedFailure(
                        step_name=current_step or inferred_step,
                        platform=platform,
                        error_type=error_type,
                        error_message=error_msg,
                        stack_trace=stack,
                        context_lines=ctx_lines,
                        line_number=i + 1,
                    )
                    if env_ctx:
                        pf.context_lines.insert(0, f"[ENV] {_format_env(env_ctx)}")
                        pf.context_lines = [c for c in pf.context_lines if c.strip()]
                    primary_failures.append(pf)

                matched_primary = True
                break

        if matched_primary:
            i += 1
            continue

        # ── Secondary / cascading patterns ─────────────────────────────────
        for pattern, sec_type in SECONDARY_PATTERNS:
            m = re.search(pattern, line)
            if m:
                secondary_messages.append({
                    "type": sec_type,
                    "message": line.strip(),
                    "line_number": i + 1,
                    "step": current_step or inferred_step,
                })
                break

        i += 1

    # ── Error grouping ────────────────────────────────────────────────────
    if primary_failures:
        # Attach secondary context to relevant primary failures
        for sec in secondary_messages:
            sec_text = f"[Cascading] {sec['message']}"
            # Attach to the primary failure in the same step if possible
            target = None
            for pf in primary_failures:
                if pf.step_name == sec.get("step"):
                    target = pf
                    break
            if target is None:
                target = primary_failures[-1]  # fallback: last primary
            if sec_text not in target.context_lines:
                target.context_lines.append(sec_text)
            if not target.step_name and sec.get("step"):
                target.step_name = sec["step"]
        return primary_failures

    # ── Fallback: generic failure from secondary messages ─────────────────
    if secondary_messages:
        best_sec = secondary_messages[0]
        for sec in secondary_messages:
            if any(k in sec["message"] for k in ["Lifecycle script", "npm ERR! code", "FAILURE"]):
                best_sec = sec
                break
        return [ParsedFailure(
            step_name=best_sec.get("step") or inferred_step,
            platform=platform,
            error_type="GenericExit",
            error_message=best_sec["message"],
            stack_trace=None,
            context_lines=[s["message"] for s in secondary_messages[:5]],
            line_number=best_sec["line_number"],
        )]

    return []


def _format_env(ctx: Dict[str, str]) -> str:
    """Format env context as a compact evidence string."""
    parts = []
    if "python_version" in ctx:
        parts.append(f"Python {ctx['python_version']}")
    if "node_version" in ctx:
        parts.append(f"Node {ctx['node_version']}")
    if "npm_version" in ctx:
        parts.append(f"npm {ctx['npm_version']}")
    if "java_version" in ctx:
        parts.append(f"Java {ctx['java_version']}")
    if "os" in ctx:
        parts.append(f"OS: {ctx['os']}")
    if "docker_image" in ctx:
        parts.append(f"Docker: {ctx['docker_image']}")
    if "node_env" in ctx:
        parts.append(f"NODE_ENV={ctx['node_env']}")
    if "ci" in ctx:
        parts.append("CI=true")
    return " | ".join(parts) if parts else ""
