"""
ai_agent.py – Expert CI/CD diagnosis engine.

Acts as a senior CI/CD debugging expert:
  - Correlates errors with environment (Python/Node version, OS, CI config, Docker).
  - Provides evidence-based root causes extracted directly from log content.
  - Generates specific, concrete commands rather than generic advice.
  - Distinguishes root causes from cascading/secondary failures.
  - Evidence-based confidence scoring with explanation.
  - Improved feedback loop via vector memory success tracking.
"""

import json
import logging
import re
import httpx
from typing import List, Optional, Tuple, Dict, Any
from app.models.schemas import ParsedFailure, DiagnosisCard, FailureCategory, SimilarFailure, ResolutionStatus
from app.services.log_parser import parse_logs, is_flaky_indicator, extract_environment_context, strip_ansi
from app.services.vector_memory import search_similar, store_failure
from app.config import settings
import uuid

logger = logging.getLogger(__name__)

# ─── Failure taxonomy ─────────────────────────────────────────────────────────
CATEGORY_RULES: Dict[str, FailureCategory] = {
    # Dependencies
    "CannotFindModule":        FailureCategory.DEPENDENCY,
    "ModuleNotFound":          FailureCategory.DEPENDENCY,
    "ModuleNotFoundError":     FailureCategory.DEPENDENCY,
    "ImportError":             FailureCategory.DEPENDENCY,
    "NoMatchingDistribution":  FailureCategory.DEPENDENCY,
    "PackageNotFoundError":    FailureCategory.DEPENDENCY,
    "NpmEResolve":             FailureCategory.DEPENDENCY,
    "NpmDependencyResolution": FailureCategory.DEPENDENCY,
    "NpmError":                FailureCategory.DEPENDENCY,
    "MavenArtifactNotFound":   FailureCategory.DEPENDENCY,
    "ClassNotFoundException":  FailureCategory.DEPENDENCY,

    # Code Defects
    "AssertionError":          FailureCategory.CODE_DEFECT,
    "SyntaxError":             FailureCategory.CODE_DEFECT,
    "IndentationError":        FailureCategory.CODE_DEFECT,
    "PytestFailure":           FailureCategory.CODE_DEFECT,
    "PytestError":             FailureCategory.CODE_DEFECT,
    "JestFailure":             FailureCategory.CODE_DEFECT,
    "JestTestFail":            FailureCategory.CODE_DEFECT,
    "ReferenceError":          FailureCategory.CODE_DEFECT,
    "JsTypeError":             FailureCategory.CODE_DEFECT,
    "JsSyntaxError":           FailureCategory.CODE_DEFECT,
    "NodeArgTypeError":        FailureCategory.CODE_DEFECT,
    "NullPointerException":    FailureCategory.CODE_DEFECT,
    "NoSuchMethodError":       FailureCategory.CODE_DEFECT,
    "CompilationError":        FailureCategory.CODE_DEFECT,
    "JavaCompileError":        FailureCategory.CODE_DEFECT,
    "TypeScriptError":         FailureCategory.CODE_DEFECT,
    "AttributeError":          FailureCategory.CODE_DEFECT,
    "TypeError":               FailureCategory.CODE_DEFECT,
    "ValueError":              FailureCategory.CODE_DEFECT,
    "KeyError":                FailureCategory.CODE_DEFECT,
    "NameError":               FailureCategory.CODE_DEFECT,
    "RuntimeError":            FailureCategory.CODE_DEFECT,
    "RecursionError":          FailureCategory.CODE_DEFECT,
    "SpringBeanError":         FailureCategory.CODE_DEFECT,

    # Infrastructure & OOM
    "OOMKilled":               FailureCategory.INFRASTRUCTURE,
    "ProcessKilled":           FailureCategory.INFRASTRUCTURE,
    "DiskQuotaExceeded":       FailureCategory.INFRASTRUCTURE,
    "NoSpaceLeft":             FailureCategory.INFRASTRUCTURE,
    "ConnectionTimeout":       FailureCategory.INFRASTRUCTURE,
    "ConnectionRefused":       FailureCategory.INFRASTRUCTURE,
    "DnsFailure":              FailureCategory.INFRASTRUCTURE,
    "RunnerUnavailable":       FailureCategory.INFRASTRUCTURE,
    "DockerDaemonUnreachable": FailureCategory.INFRASTRUCTURE,
    "DockerDaemonError":       FailureCategory.INFRASTRUCTURE,
    "DockerRateLimit":         FailureCategory.INFRASTRUCTURE,
    "ContextDeadlineExceeded": FailureCategory.INFRASTRUCTURE,
    "IOTimeout":               FailureCategory.INFRASTRUCTURE,

    # Configuration
    "DockerBuildFail":         FailureCategory.CONFIGURATION,
    "DockerPullDenied":        FailureCategory.CONFIGURATION,
    "DockerAuthFail":          FailureCategory.CONFIGURATION,
    "DockerManifestUnknown":   FailureCategory.CONFIGURATION,
    "FileNotFound":            FailureCategory.CONFIGURATION,
    "PythonFileNotFound":      FailureCategory.CONFIGURATION,
    "PythonPermissionError":   FailureCategory.CONFIGURATION,
    "PermissionDenied":        FailureCategory.CONFIGURATION,
    "AuthFailed":              FailureCategory.CONFIGURATION,
    "MissingEnvVar":           FailureCategory.CONFIGURATION,
    "RepoNotFound":            FailureCategory.CONFIGURATION,
    "GitAccessFailed":         FailureCategory.CONFIGURATION,
    "GitPushFailed":           FailureCategory.CONFIGURATION,
    "SecretMissing":           FailureCategory.CONFIGURATION,
    "InvalidToken":            FailureCategory.CONFIGURATION,
    "CredentialError":         FailureCategory.CONFIGURATION,

    # Generic
    "GenericExit":             FailureCategory.UNKNOWN,
}


def classify_failure(failure: ParsedFailure) -> FailureCategory:
    if failure.error_type in CATEGORY_RULES:
        return CATEGORY_RULES[failure.error_type]
    msg = (failure.error_message or "").lower()
    if any(w in msg for w in ["timeout", "network", "connection", "dns", "runner", "oom", "disk"]):
        return FailureCategory.INFRASTRUCTURE
    if any(w in msg for w in ["not found", "no module", "cannot find", "no matching distribution", "enoent"]):
        return FailureCategory.DEPENDENCY
    if any(w in msg for w in ["permission", "auth", "env var", "config", "secret", "denied", "unauthorized"]):
        return FailureCategory.CONFIGURATION
    if any(w in msg for w in ["syntaxerror", "compilation", "assert", "nullpointer", "typeerror"]):
        return FailureCategory.CODE_DEFECT
    return FailureCategory.UNKNOWN


# ─── Root cause + fix generation ─────────────────────────────────────────────

def _extract_env_from_context(context_lines: List[str]) -> Dict[str, str]:
    """Pull env hints embedded in context lines (the [ENV] prefix)."""
    env: Dict[str, str] = {}
    for line in context_lines:
        if line.startswith("[ENV]"):
            # e.g. "[ENV] Python 3.8.10 | Node 16.14.2 | CI=true"
            rest = line[5:].strip()
            for part in rest.split("|"):
                part = part.strip()
                if part.startswith("Python"):
                    env["python"] = part
                elif part.startswith("Node"):
                    env["node"] = part
                elif part.startswith("npm"):
                    env["npm"] = part
                elif part.startswith("Java"):
                    env["java"] = part
                elif part.startswith("OS:"):
                    env["os"] = part[3:].strip()
                elif part.startswith("Docker:"):
                    env["docker"] = part[7:].strip()
                elif "NODE_ENV=" in part:
                    env["node_env"] = part.split("=")[1]
                elif part == "CI=true":
                    env["ci"] = "true"
    return env


def generate_root_cause_and_fix(
    failure: ParsedFailure,
    category: FailureCategory,
    raw_log: str = "",
) -> Tuple[str, str, List[str]]:
    """
    Expert-level root-cause analysis and fix generation.
    Uses log context, environment data, and error signatures to produce
    specific, evidence-backed recommendations.
    """
    etype = failure.error_type or ""
    emsg = failure.error_message or ""
    env = _extract_env_from_context(failure.context_lines)
    full_text = raw_log or " ".join(failure.context_lines)

    # ── Node / JS: Missing module ──────────────────────────────────────────
    if etype in ("CannotFindModule", "ModuleNotFound"):
        mod = _extract_quoted(emsg, r"Cannot find module|Can't resolve") or "dependency"
        is_dev_dep = any(k in full_text for k in ["devDependencies", "--save-dev", "-D"])
        node_env = env.get("node_env", "")

        if "vite" in mod.lower():
            root_cause = (
                "Vite is unavailable in the build environment. "
                "In CI, `NODE_ENV=production` causes npm/yarn to skip devDependencies by default, "
                "so Vite (a devDependency) is never installed."
            )
            fix = (
                "1. Verify that vite is declared in package.json under devDependencies.\n"
                "2. Install vite if missing: npm install -D vite\n"
                "3. Run npm ci in CI for clean, reproducible installations.\n"
                "4. Ensure development dependencies are installed during the build (do not set NODE_ENV=production before build).\n"
                "5. Verify the correct working directory in the CI step."
            )
            commands = [
                "npm install -D vite",
                "npm ci --include=dev",
                "npm run build",
            ]
        elif "@" in mod:
            # Scoped / versioned package
            root_cause = (
                f"Scoped package `{mod}` is missing from node_modules. "
                "This often happens when `npm ci` is not run, or when package-lock.json is out of sync."
            )
            fix = (
                f"1. Install the missing package: npm install {mod}\n"
                "2. Commit the updated package-lock.json.\n"
                "3. Use `npm ci` (not `npm install`) in CI for reproducible installs.\n"
                "4. If the package is a devDependency, ensure CI does not set NODE_ENV=production."
            )
            commands = [f"npm install {mod}", "npm ci", "npm run build"]
        else:
            root_cause = (
                f"Module `{mod}` is missing from node_modules. "
                f"{'NODE_ENV=production causes npm ci to skip devDependencies.' if node_env == 'production' else 'The package may not be declared in package.json or npm ci was not run.'}"
            )
            fix = (
                f"1. Add `{mod}` to package.json if missing.\n"
                "2. Run `npm ci` in CI (reproduces exact lock file, includes devDeps).\n"
                f"3. If `{mod}` is a build tool, add it to devDependencies, not dependencies.\n"
                "4. Remove NODE_ENV=production from the install step if set."
            )
            commands = [f"npm install {mod}", "npm ci", "npm ls"]
        return root_cause, fix, commands

    # ── npm dependency resolution ──────────────────────────────────────────
    if etype == "NpmEResolve":
        peer_match = re.search(r"peer (.+?) from (.+?)@", full_text)
        if peer_match:
            root_cause = (
                f"npm cannot resolve peer dependency `{peer_match.group(1)}` "
                f"required by `{peer_match.group(2)}`. "
                "Peer dependency conflicts often arise when upgrading a major version of one package "
                "without updating its dependents."
            )
        else:
            root_cause = (
                "npm cannot resolve the dependency tree due to conflicting peer requirements. "
                "This is common after upgrading React, Angular, or other framework major versions."
            )
        fix = (
            "1. Run `npm install --legacy-peer-deps` to bypass strict peer checks temporarily.\n"
            "2. Identify the conflicting packages: npm ls\n"
            "3. Update all dependent packages to compatible versions.\n"
            "4. Consider using `overrides` in package.json to pin conflicting transitive deps."
        )
        commands = [
            "npm install --legacy-peer-deps",
            "npm ls 2>&1 | grep UNMET",
            "npm dedupe",
        ]
        return root_cause, fix, commands

    # ── TypeScript ─────────────────────────────────────────────────────────
    if etype == "TypeScriptError":
        ts_code = re.search(r"error TS(\d+)", emsg)
        code_num = ts_code.group(1) if ts_code else ""
        # Map common TS error codes
        ts_hints = {
            "2304": "Cannot find name — likely a missing import or type declaration (@types/...).",
            "2345": "Argument type mismatch — check function signature and call site.",
            "2322": "Type assignment error — the assigned value does not match the declared type.",
            "2307": "Cannot find module — missing @types package or tsconfig paths misconfigured.",
            "2339": "Property does not exist on type — check interface/type definition.",
            "7006": "Parameter implicitly has 'any' type — add explicit type annotation.",
            "2554": "Expected N arguments, got M — wrong number of arguments passed.",
        }
        hint = ts_hints.get(code_num, "Review the type error at the referenced file and line.")
        node_ver = env.get("node", "")
        root_cause = f"TypeScript compilation failed with error TS{code_num}. {hint}"
        fix = (
            f"1. Fix the type error: {emsg}\n"
            f"2. Hint: {hint}\n"
            "3. Run `npx tsc --noEmit` locally to see all errors before pushing.\n"
            "4. If using @types packages, ensure they match the library version."
        )
        commands = ["npx tsc --noEmit", "npm run typecheck"]
        return root_cause, fix, commands

    # ── Python: Missing module ─────────────────────────────────────────────
    if etype == "ModuleNotFoundError":
        mod = re.search(r"No module named ['\"]?([^'\" ]+)['\"]?", emsg)
        mod_name = mod.group(1) if mod else "package"
        py_ver = env.get("python", "")
        root_cause = (
            f"Python module `{mod_name}` is not installed in the active environment. "
            f"{'(Running ' + py_ver + ')' if py_ver else ''} "
            "In CI, the virtual environment may not be activated, or requirements.txt was not installed."
        )
        fix = (
            f"1. Add `{mod_name}` to requirements.txt or pyproject.toml.\n"
            "2. Ensure your CI step runs:\n"
            "   pip install -r requirements.txt\n"
            "   before executing tests.\n"
            "3. If using poetry: `poetry install --no-root`\n"
            "4. Verify that the correct Python interpreter is used: `which python` / `python --version`"
        )
        commands = [
            f"pip install {mod_name}",
            "pip install -r requirements.txt",
            "python -m pytest --tb=short",
        ]
        return root_cause, fix, commands

    if etype == "ImportError":
        mod_m = re.search(r"cannot import name '([^']+)' from '([^']+)'", emsg)
        if mod_m:
            root_cause = (
                f"Cannot import `{mod_m.group(1)}` from `{mod_m.group(2)}`. "
                "This usually means the installed version of the package is different "
                "from what the code expects — a version mismatch."
            )
            fix = (
                f"1. Check which version of `{mod_m.group(2)}` is installed: pip show {mod_m.group(2)}\n"
                "2. Pin the correct version in requirements.txt.\n"
                "3. Regenerate requirements.txt: pip freeze > requirements.txt\n"
                f"4. Verify `{mod_m.group(1)}` exists in that version's public API."
            )
            commands = [f"pip show {mod_m.group(2)}", "pip install -r requirements.txt --upgrade"]
        else:
            root_cause = f"Import failed: {emsg}. The package may be installed under a different name or version."
            fix = "Check the installed version of the package and ensure requirements.txt is up to date."
            commands = ["pip install -r requirements.txt", "pip list"]
        return root_cause, fix, commands

    if etype == "NoMatchingDistribution":
        req_m = re.search(r"(?:No matching distribution found|satisfies the requirement) for (.+)", emsg)
        req = req_m.group(1).strip() if req_m else "package"
        py_ver = env.get("python", "")
        root_cause = (
            f"pip cannot find a distribution for `{req}` compatible with the current environment. "
            f"{'Python ' + py_ver + ' may not be supported by this package. ' if py_ver else ''}"
            "This often happens when specifying a version that doesn't exist on PyPI, "
            "or when the package only supports newer/older Python versions."
        )
        fix = (
            f"1. Verify the exact package name and version: pip index versions {req.split('==')[0].split('>=')[0]}\n"
            f"2. Remove strict version pinning from requirements.txt if unnecessarily tight.\n"
            f"3. Check the package's PyPI page for supported Python versions.\n"
            f"4. Update pip: pip install --upgrade pip setuptools"
        )
        commands = ["pip install --upgrade pip", "pip install -r requirements.txt"]
        return root_cause, fix, commands

    # ── Python: Syntax errors ──────────────────────────────────────────────
    if etype in ("SyntaxError", "IndentationError"):
        file_m = re.search(r'File "([^"]+)", line (\d+)', failure.stack_trace or emsg)
        location = f" in `{file_m.group(1)}` at line {file_m.group(2)}" if file_m else ""
        root_cause = (
            f"Python {etype}{location}. "
            "The interpreter could not parse the source file — this blocks the entire module from loading."
        )
        fix = (
            f"1. Open `{file_m.group(1) if file_m else 'the referenced file'}` at line "
            f"{file_m.group(2) if file_m else 'shown in the traceback'}.\n"
            "2. Correct the syntax: missing colon, unclosed bracket, wrong indentation.\n"
            "3. Validate locally: python -m py_compile <file>\n"
            "4. Add a pre-commit lint hook: flake8 or ruff"
        )
        fname = file_m.group(1) if file_m else "<file>"
        commands = [
            f"python -m py_compile {fname}",
            "python -m flake8 --select=E9,F63,F7,F82 .",
        ]
        return root_cause, fix, commands

    # ── Python: Test failures ─────────────────────────────────────────────
    if etype in ("AssertionError", "PytestFailure", "PytestError"):
        test_m = re.search(r'(tests?/[\w/\.]+\.py)(?:::(\w+))?', emsg)
        test_ref = test_m.group(0) if test_m else "the failing test"
        assert_m = re.search(r'assert (.+)', emsg)
        assert_detail = f" Assertion: `{assert_m.group(1)}`" if assert_m else ""
        root_cause = (
            f"Test assertion failed in `{test_ref}`.{assert_detail} "
            "Either the implementation does not match the test's expectation, "
            "or the test fixture/mock is returning unexpected data."
        )
        fix = (
            f"1. Run the failing test locally to see the full diff:\n"
            f"   pytest {test_ref} -v --tb=long\n"
            "2. If the behavior is correct, update the test assertion.\n"
            "3. If the implementation is wrong, fix the production code.\n"
            "4. Check for missing fixtures or environment-specific mocks."
        )
        commands = [f"pytest {test_ref} -v --tb=long", "pytest --lf -v"]
        return root_cause, fix, commands

    if etype == "KeyError":
        key_m = re.search(r"KeyError: '?([^'\"]+)'?", emsg)
        key = key_m.group(1) if key_m else "key"
        root_cause = (
            f"Dictionary key `{key}` does not exist at runtime. "
            "Either the key name changed (e.g. API response schema change, env var rename), "
            "or the data source returned an unexpected structure."
        )
        fix = (
            f"1. Add a check before access: `value = data.get('{key}', default_value)`\n"
            f"2. Log the actual dict keys to debug: `print(data.keys())`\n"
            f"3. If `{key}` is an env var, verify it is set in CI secrets/environment."
        )
        commands = ["pytest --tb=long -v", "python -c \"import os; print(os.environ.get('KEY'))\""]
        return root_cause, fix, commands

    # ── OOM / Resource ─────────────────────────────────────────────────────
    if etype in ("OOMKilled", "ProcessKilled"):
        mem_m = re.search(r'anon-rss:(\d+)kB', " ".join(failure.context_lines))
        mem_mb = int(mem_m.group(1)) // 1024 if mem_m else None
        node_ver = env.get("node", "")
        java_ver = env.get("java", "")

        if "JavaScript heap" in emsg or node_ver:
            root_cause = (
                f"Node.js process exhausted the V8 heap memory and was killed. "
                f"{'Approximate RSS at kill: ~' + str(mem_mb) + 'MB. ' if mem_mb else ''}"
                "Default V8 heap limit is ~1.5GB on 64-bit; CI runners may impose stricter limits."
            )
            fix = (
                "1. Increase Node.js heap before the build step:\n"
                "   export NODE_OPTIONS='--max-old-space-size=4096'\n"
                "2. Or add to your CI workflow env block:\n"
                "   env:\n"
                "     NODE_OPTIONS: '--max-old-space-size=4096'\n"
                "3. Reduce parallel workers: set --maxWorkers=2 in jest config.\n"
                "4. Split the bundle if webpack/vite memory is the culprit."
            )
            commands = ["export NODE_OPTIONS='--max-old-space-size=4096'", "npm run build"]
        elif java_ver:
            root_cause = (
                f"JVM process was killed by the OOM killer. "
                f"{'Approximate RSS at kill: ~' + str(mem_mb) + 'MB. ' if mem_mb else ''}"
                "Default JVM heap may exceed the CI runner's available RAM."
            )
            fix = (
                "1. Add JVM heap flags to Gradle/Maven:\n"
                "   JAVA_OPTS='-Xmx2g -Xms512m' or\n"
                "   org.gradle.jvmargs=-Xmx2048m in gradle.properties\n"
                "2. Enable Gradle daemon memory monitoring.\n"
                "3. Use --no-daemon on CI runners with limited RAM."
            )
            commands = ["export JAVA_OPTS='-Xmx2g'", "./gradlew build --no-daemon"]
        else:
            root_cause = (
                f"The process was killed by the OS OOM killer after exhausting available memory. "
                f"{'Approximate RSS at kill: ~' + str(mem_mb) + 'MB. ' if mem_mb else ''}"
                "CI runners typically have 2–8 GB RAM; heavy parallel builds can exceed this."
            )
            fix = (
                "1. Increase the runner's memory allocation in workflow configuration.\n"
                "2. Limit parallel workers for builds and tests.\n"
                "3. Inspect memory usage: add `free -h` or `cat /proc/meminfo` before the failing step.\n"
                "4. For Docker builds, set --memory=4g in docker run / docker build."
            )
            commands = ["docker build --memory=4g .", "free -h"]
        return root_cause, fix, commands

    if etype in ("DiskQuotaExceeded", "NoSpaceLeft"):
        root_cause = (
            "The CI runner's disk is full. "
            "Large Docker layer caches, build artifacts, or log files can fill ephemeral runner storage."
        )
        fix = (
            "1. Add a cleanup step before the failing step:\n"
            "   docker system prune -f\n"
            "2. Remove large artifacts from previous steps before writing new ones.\n"
            "3. Use shallow git clone: `git clone --depth=1`\n"
            "4. If using GitHub Actions, enable artifact retention limits."
        )
        commands = ["docker system prune -f", "df -h"]
        return root_cause, fix, commands

    # ── Infrastructure: Connections ────────────────────────────────────────
    if etype in ("ConnectionTimeout", "ConnectionRefused"):
        host_m = re.search(r'(?:connecting to|connect to|dial tcp)\s+([^\s:,]+)', emsg, re.IGNORECASE)
        host = host_m.group(1) if host_m else "the external service"
        root_cause = (
            f"Connection to `{host}` was refused or timed out. "
            "In CI, dependent services (databases, Redis, mock servers) must be declared as "
            "`services:` in the workflow and given a health-check startup delay."
        )
        fix = (
            f"1. Verify `{host}` service is declared and healthy in CI.\n"
            "   For GitHub Actions, add under `services:` in your workflow YAML.\n"
            "2. Add a startup wait:\n"
            "   uses: actions/wait-for-service or a sleep/poll loop.\n"
            "3. Verify host/port in the application config matches the CI service binding.\n"
            "4. Check runner firewall rules allow outbound to the target host."
        )
        commands = []
        return root_cause, fix, commands

    if etype == "DnsFailure":
        host_m = re.search(r'(?:resolve host:|Could not resolve host:)\s+(\S+)', emsg, re.IGNORECASE)
        host = host_m.group(1) if host_m else "the hostname"
        root_cause = (
            f"DNS resolution failed for `{host}`. "
            "Self-hosted runners may not have external DNS configured. "
            "Also check for typos in hostnames or hardcoded IPs that break in containerized CI."
        )
        fix = (
            f"1. Verify the hostname `{host}` is correct and resolves from your machine.\n"
            "2. If self-hosted runner: check /etc/resolv.conf and DNS configuration.\n"
            "3. If a private registry or internal service: add it to the runner's hosts file or DNS."
        )
        commands = [f"nslookup {host}", f"ping -c 1 {host}"]
        return root_cause, fix, commands

    # ── Docker ────────────────────────────────────────────────────────────
    if etype == "DockerPullDenied":
        image_m = re.search(r"pull access denied for ([^\s,]+)", emsg)
        image = image_m.group(1) if image_m else "the image"
        root_cause = (
            f"Docker image `{image}` could not be pulled — authentication failed or the image is private. "
            "CI runners do not inherit your local Docker credentials."
        )
        fix = (
            "1. Log in to the registry in your CI workflow:\n"
            "   echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin\n"
            f"2. If using GitHub Container Registry (ghcr.io):\n"
            "   echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin\n"
            "3. Ensure the secret is defined in repo Settings → Secrets."
        )
        commands = ["docker login", f"docker pull {image}"]
        return root_cause, fix, commands

    if etype == "DockerRateLimit":
        root_cause = (
            "Docker Hub rate limit exceeded. "
            "Anonymous pulls are limited to 100/6h per IP; authenticated pulls to 200/6h (free tier)."
        )
        fix = (
            "1. Authenticate to Docker Hub in CI:\n"
            "   echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin\n"
            "2. Use a Docker Hub Pro account for higher limits.\n"
            "3. Mirror frequently-used images to GitHub Container Registry (ghcr.io) or ECR."
        )
        commands = ["docker login -u $DOCKER_USERNAME"]
        return root_cause, fix, commands

    if etype == "DockerBuildFail":
        root_cause = (
            f"Docker build failed: {emsg}. "
            "This may be caused by a missing base image, failed RUN instruction, "
            "or a dependency installation step inside the Dockerfile that failed."
        )
        fix = (
            "1. Run the build locally with verbose output: `docker build --progress=plain .`\n"
            "2. Check the Dockerfile instruction that failed (the layer shown in the error).\n"
            "3. If a package install failed, try pinning to a known working version.\n"
            "4. Ensure the base image tag exists and has not been deprecated."
        )
        commands = ["docker build --progress=plain --no-cache ."]
        return root_cause, fix, commands

    # ── Permissions & Auth ────────────────────────────────────────────────
    if etype == "PermissionDenied":
        file_m = re.search(r"[Pp]ermission denied[:\s]*'?([^\s']+)'?", emsg)
        path = file_m.group(1) if file_m else "the script/file"
        root_cause = (
            f"The CI runner process cannot read/execute `{path}`. "
            "Shell scripts committed without execute permissions are a common cause. "
            "Also check if running as a restricted user inside a container."
        )
        fix = (
            f"1. Add execute permission to the script in git:\n"
            f"   git update-index --chmod=+x {path}\n"
            "2. Or add this step in CI before execution:\n"
            f"   chmod +x {path}\n"
            "3. Verify the CI user has access to the directory.\n"
            "4. If running in Docker, check USER directive in Dockerfile."
        )
        commands = [f"chmod +x {path}", f"git update-index --chmod=+x {path}"]
        return root_cause, fix, commands

    if etype in ("AuthFailed", "CredentialError", "InvalidToken", "SecretMissing"):
        secret_m = re.search(r"(?:secret|key|token)[:\s]+([A-Z_]+)", emsg, re.IGNORECASE)
        secret = secret_m.group(1) if secret_m else "the credential"
        root_cause = (
            f"Authentication failed — `{secret}` is missing, invalid, or expired. "
            "Secrets are not automatically available in fork PRs for security reasons."
        )
        fix = (
            f"1. Verify `{secret}` is defined in repo Settings → Secrets and variables → Actions.\n"
            "2. Reference it correctly in the workflow: `${{ secrets.SECRET_NAME }}`\n"
            "3. If a token, check it has not expired (GitHub PATs, API keys have expiry dates).\n"
            "4. For fork PRs, consider using `pull_request_target` with explicit secret access."
        )
        commands = []
        return root_cause, fix, commands

    if etype == "MissingEnvVar":
        var_m = re.search(r"Missing required environment variable: ([^\s]+)", emsg)
        var = var_m.group(1) if var_m else "the variable"
        root_cause = (
            f"Required environment variable `{var}` is not set in the CI environment. "
            "Applications that crash on missing env vars typically enforce this at startup."
        )
        fix = (
            f"1. Add `{var}` to your repository secrets (Settings → Secrets → Actions).\n"
            f"2. Reference it in the workflow step:\n"
            f"   env:\n"
            f"     {var}: ${{{{ secrets.{var} }}}}\n"
            f"3. For non-secret defaults, set a fallback: `{var}=${{{{var || 'default'}}}}`"
        )
        commands = []
        return root_cause, fix, commands

    # ── Git / Repository ──────────────────────────────────────────────────
    if etype in ("RepoNotFound", "GitAccessFailed"):
        url_m = re.search(r"'(https?://[^']+)'", emsg)
        url = url_m.group(1) if url_m else "the repository URL"
        root_cause = (
            f"Git cannot access `{url}`. "
            "Either the token used for checkout lacks `repo` scope, "
            "or the repository URL is wrong."
        )
        fix = (
            "1. If using GITHUB_TOKEN, verify it has `contents: read` permissions.\n"
            "2. For private repos, use a PAT with `repo` scope and store it as a secret.\n"
            "3. Verify the repository URL is correct and the repo is not renamed/archived."
        )
        commands = ["git remote -v", "git fetch --dry-run"]
        return root_cause, fix, commands

    # ── Java / JVM ────────────────────────────────────────────────────────
    if etype == "NullPointerException":
        # Try to extract the failing line from the stack trace
        line_m = re.search(r'at [\w\$\.]+\.(\w+)\((\S+):(\d+)\)', failure.stack_trace or "")
        location = f" in `{line_m.group(2)}:{line_m.group(3)}`" if line_m else ""
        root_cause = (
            f"Java NullPointerException{location}. "
            "A reference was dereferenced before being initialized or checked for null. "
            "This is often a test fixture issue (mocked object not configured) or "
            "an uninitialized field injected by a DI framework."
        )
        fix = (
            "1. Check the stack trace line for the null reference.\n"
            "2. Add null guard: `if (obj != null) { ... }` or use `Optional<T>`.\n"
            "3. Verify test mocks are properly configured with Mockito: `when(mock.method()).thenReturn(value)`.\n"
            "4. Check that Spring/DI beans are properly autowired in test context."
        )
        commands = ["mvn test -Dtest=<FailingTest>", "./gradlew test --tests *.FailingTest"]
        return root_cause, fix, commands

    # ── Generic / Unknown ─────────────────────────────────────────────────
    if etype == "GenericExit":
        exit_code_m = re.search(r'exit code[:\s]+(\d+)', emsg)
        code = exit_code_m.group(1) if exit_code_m else "non-zero"
        # Map common exit codes
        exit_code_hints = {
            "1":   "General error — check the step output immediately above for the actual error.",
            "2":   "Misuse of shell built-in or missing file.",
            "126": "Command found but not executable — check file permissions.",
            "127": "Command not found — the binary or script is not installed or not in PATH.",
            "128": "Invalid exit argument.",
            "130": "Script terminated by Ctrl+C (SIGINT).",
            "137": "Process killed (SIGKILL) — usually OOM. Check memory usage.",
            "139": "Segmentation fault (SIGSEGV).",
            "143": "Process terminated (SIGTERM).",
        }
        hint = exit_code_hints.get(code, "Review the full log output above this line.")
        root_cause = (
            f"Process exited with code {code}. {hint} "
            "No specific compiler or interpreter error was isolated — "
            "enable debug logging to find the underlying cause."
        )
        fix = (
            "1. Enable debug logging in CI:\n"
            "   ACTIONS_RUNNER_DEBUG=true or ACTIONS_STEP_DEBUG=true (GitHub Actions)\n"
            "2. Check the full log output above the exit code line.\n"
            "3. Run the failing command locally to reproduce.\n"
            "4. Add `set -x` to shell scripts to trace execution."
        )
        commands = []
        return root_cause, fix, commands

    # Fallback
    return (
        f"The build failed with error type `{etype}`: {emsg[:200]}. "
        "Review the full log and stack trace for context.",
        "1. Reproduce the failure locally.\n2. Enable verbose logging.\n3. Check environment differences between local and CI.",
        [],
    )


def _extract_quoted(text: str, context_pattern: str = "") -> Optional[str]:
    """Extract the first single- or double-quoted string in text."""
    m = re.search(r"['\"]([^'\"]+)['\"]", text)
    return m.group(1) if m else None


# ─── Confidence scoring ───────────────────────────────────────────────────────

def compute_confidence(
    failure: ParsedFailure,
    category: FailureCategory,
    similar: List[SimilarFailure],
    has_llm_enrichment: bool = False,
) -> Tuple[float, str]:
    """
    Evidence-based confidence scoring.
    Returns (score, explanation_string).

    Scoring factors:
      + Specific error type known          → 0.70 base
      + Has stack trace                    → +0.08
      + Has line number                    → +0.04
      + Context lines present              → +0.03
      + Env context embedded               → +0.03
      + Similar historical match ≥ 0.70   → +0.05
      + LLM enrichment available          → +0.03
      - GenericExit (no specific sig)      → 0.20 max
      - UNKNOWN category                  → 0.40 max
    """
    if failure.error_type == "GenericExit":
        return 0.20, "No specific error signature — confidence capped at 20%."

    score = 0.70
    evidence_parts = [f"Identified error type: `{failure.error_type}`"]

    if failure.stack_trace:
        score += 0.08
        evidence_parts.append("Stack trace available")
    if failure.line_number:
        score += 0.04
        evidence_parts.append(f"Error at line {failure.line_number}")
    real_ctx = [l for l in failure.context_lines if not l.startswith("[Cascading]")]
    if real_ctx:
        score += 0.03
        evidence_parts.append(f"{len(real_ctx)} context line(s)")
    if any("[ENV]" in l for l in failure.context_lines):
        score += 0.03
        evidence_parts.append("Runtime environment detected")
    if similar and similar[0].similarity_score >= 0.70:
        score += 0.05
        evidence_parts.append(f"Historical match (similarity={similar[0].similarity_score:.0%})")
    if has_llm_enrichment:
        score += 0.03
        evidence_parts.append("LLM-enriched analysis")
    if category == FailureCategory.UNKNOWN:
        score = min(score, 0.40)
        evidence_parts.append("Category unknown — capped at 40%")

    return round(min(score, 0.97), 2), "; ".join(evidence_parts)


# ─── LLM enrichment ──────────────────────────────────────────────────────────

def _query_external_llm(
    failure: ParsedFailure,
    env_ctx: Dict[str, str],
    category: str,
) -> Optional[dict]:
    """
    Call external LLM (Gemini or OpenAI) with a rich, expert-level prompt.
    Returns enriched root_cause, recommended_fix, commands or None.
    """
    env_str = ", ".join(f"{k}={v}" for k, v in env_ctx.items()) if env_ctx else "unknown"
    ctx_str = "\n".join(failure.context_lines[:15])
    stack_str = (failure.stack_trace or "")[:600]

    prompt = (
        "You are a senior CI/CD reliability engineer and DevOps expert with 15 years of experience.\n\n"
        f"CI Platform: {failure.platform or 'unknown'}\n"
        f"Environment: {env_str}\n"
        f"Error Type: {failure.error_type}\n"
        f"Error Category: {category}\n"
        f"Failed Step: {failure.step_name or 'unknown'}\n"
        f"Primary Error Message:\n{failure.error_message}\n\n"
        f"Stack Trace:\n{stack_str}\n\n"
        f"Context Lines:\n{ctx_str}\n\n"
        "Analyze this CI/CD failure and respond ONLY with valid JSON (no markdown) with these exact keys:\n"
        '{\n'
        '  "root_cause": "Single precise sentence explaining WHY this happened based on the evidence above",\n'
        '  "recommended_fix": "Step-by-step numbered fix with specific commands, not generic advice",\n'
        '  "commands": ["exact shell command 1", "exact shell command 2"]\n'
        '}'
    )

    if settings.ai_provider == "google" and settings.google_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.google_api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            with httpx.Client(timeout=12) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Gemini enrichment error: {e}")

    if settings.ai_provider == "openai" and settings.openai_api_key:
        try:
            headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 600,
            }
            with httpx.Client(timeout=12) as client:
                res = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"]
                    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"OpenAI enrichment error: {e}")

    return None


# ─── Main diagnosis pipeline ──────────────────────────────────────────────────

def run_ai_diagnosis(raw_log: str, filename: str = None) -> dict:
    """
    Expert CI/CD diagnosis pipeline.

    1. Parse logs → extract failures, environment context, platform.
    2. For each failure:
       a. Classify into category.
       b. Detect flaky-test signals.
       c. Search vector memory for historical similar failures.
       d. Generate specific root cause + fix using rule engine.
       e. Optionally enrich with external LLM (if API key configured).
       f. Compute evidence-based confidence score with explanation.
       g. Build structured evidence string from log context.
    3. Store non-generic failures in vector memory for future recall.
    4. Return structured diagnosis cards.
    """
    parsed_failures = parse_logs(raw_log)
    env_ctx = extract_environment_context(strip_ansi(raw_log))

    if not parsed_failures:
        # Check if the log is entirely success/warning — handle gracefully
        lower = raw_log.lower()
        if any(k in lower for k in ["passed", "succeeded", "build successful", "all checks passed"]):
            return {"platform": "generic", "failure_count": 0, "diagnoses": [], "note": "Log contains only success messages."}
        return {"platform": "generic", "failure_count": 0, "diagnoses": []}

    platform = parsed_failures[0].platform or "generic"
    diagnoses = []

    for failure in parsed_failures:
        # ── Classify ───────────────────────────────────────────────────────
        category = classify_failure(failure)

        # ── Flaky test detection ───────────────────────────────────────────
        is_flaky = is_flaky_indicator(failure.error_message or "")
        if not is_flaky:
            # Also check context lines for flakiness signals
            is_flaky = any(is_flaky_indicator(l) for l in failure.context_lines)
        if is_flaky:
            category = FailureCategory.FLAKY_TEST

        # ── Vector memory: similar historical failures ─────────────────────
        similar = search_similar(failure.error_message or "", n_results=3)

        # ── Root cause + fix (rule engine) ────────────────────────────────
        root_cause, fix_text, commands = generate_root_cause_and_fix(failure, category, raw_log)

        # ── LLM enrichment (optional, only if key configured) ─────────────
        llm_enriched = False
        if settings.ai_provider in ("google", "openai"):
            llm_result = _query_external_llm(failure, env_ctx, category.value)
            if llm_result:
                root_cause = llm_result.get("root_cause", root_cause)
                fix_text = llm_result.get("recommended_fix", fix_text)
                if llm_result.get("commands"):
                    commands = llm_result["commands"]
                llm_enriched = True

        # ── Evidence-based confidence ──────────────────────────────────────
        confidence, confidence_explanation = compute_confidence(failure, category, similar, llm_enriched)

        # ── Detailed reasoning ─────────────────────────────────────────────
        cascading_count = len([l for l in failure.context_lines if l.startswith("[Cascading]")])
        reasoning_parts = [
            f"Root cause identified: `{failure.error_type}` at line {failure.line_number or '?'}.",
        ]
        if env_ctx:
            env_summary = ", ".join(f"{k}={v}" for k, v in list(env_ctx.items())[:4])
            reasoning_parts.append(f"Runtime environment: {env_summary}.")
        if cascading_count > 0:
            reasoning_parts.append(
                f"{cascading_count} cascading message(s) (exit codes, lifecycle notices) grouped into this incident."
            )
        reasoning_parts.append(f"Confidence evidence: {confidence_explanation}.")
        if similar:
            reasoning_parts.append(
                f"Found {len(similar)} historical similar failure(s) in memory "
                f"(best match similarity: {similar[0].similarity_score:.0%})."
            )
        if is_flaky:
            reasoning_parts.append("Flakiness signals detected — rerun recommended before investigating further.")
        reasoning = " ".join(reasoning_parts)

        # ── Log evidence (concrete lines from the log) ────────────────────
        evidence_lines: List[str] = []
        # Include env line if present
        env_line = next((l for l in failure.context_lines if l.startswith("[ENV]")), None)
        if env_line:
            evidence_lines.append(env_line)
        # Include non-cascading, non-env context
        orig_ctx = [
            l for l in failure.context_lines
            if l.strip() and not l.startswith("[Cascading]") and not l.startswith("[ENV]")
        ]
        evidence_lines.extend(orig_ctx[-4:])
        # Primary error message
        evidence_lines.append(f"→ {failure.error_message or ''}")
        # Stack trace (truncated)
        if failure.stack_trace:
            st_lines = failure.stack_trace.strip().splitlines()
            evidence_lines.extend(st_lines[:6])
        log_evidence = "\n".join(evidence_lines)[:800]

        # ── Store in vector memory ─────────────────────────────────────────
        store_failure(
            error_text=failure.error_message or "",
            category=category.value,
            fix=fix_text,
            metadata={"platform": platform, "ecosystem": _infer_ecosystem_from_type(failure.error_type or "")},
        )

        diagnoses.append({
            "id": str(uuid.uuid4()),
            "pipeline_name": filename,
            "failed_step": failure.step_name,
            "failure_category": category.value,
            "error_message": failure.error_message,
            "root_cause": root_cause,
            "confidence_score": confidence,
            "recommended_fix": fix_text,
            "commands": commands,
            "reasoning": reasoning,
            "log_evidence": log_evidence,
            "similar_failures": [s.model_dump() for s in similar],
            "is_flaky": is_flaky,
            "rerun_recommended": is_flaky or category == FailureCategory.INFRASTRUCTURE,
            "resolution_status": "PENDING",
        })

    return {
        "platform": platform,
        "failure_count": len(diagnoses),
        "diagnoses": diagnoses,
    }


def _infer_ecosystem_from_type(error_type: str) -> str:
    node_types = {"CannotFindModule", "ModuleNotFound", "NpmEResolve", "NpmDependencyResolution",
                  "NpmError", "TypeScriptError", "JestFailure", "JestTestFail", "ReferenceError",
                  "JsTypeError", "JsSyntaxError", "NodeArgTypeError"}
    python_types = {"ModuleNotFoundError", "ImportError", "NoMatchingDistribution", "PackageNotFoundError",
                    "SyntaxError", "IndentationError", "AssertionError", "PytestFailure", "PytestError",
                    "AttributeError", "TypeError", "ValueError", "KeyError", "NameError", "RuntimeError"}
    java_types = {"NullPointerException", "ClassNotFoundException", "NoSuchMethodError",
                  "CompilationError", "JavaCompileError", "MavenArtifactNotFound", "SpringBeanError"}
    docker_types = {"DockerBuildFail", "DockerPullDenied", "DockerAuthFail", "DockerDaemonUnreachable",
                    "DockerDaemonError", "DockerRateLimit", "DockerManifestUnknown"}
    if error_type in node_types:
        return "node"
    if error_type in python_types:
        return "python"
    if error_type in java_types:
        return "java"
    if error_type in docker_types:
        return "docker"
    return "general"
