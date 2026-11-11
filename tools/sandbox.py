"""Static checks and subprocess execution for generated tools.

IMPORTANT: this reduces risk but is NOT a security boundary. Run the project only
in a throwaway environment (your laptop user account without secrets, Docker or
Colab) and never put credentials in the environment of the subprocess.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

ALLOWED_IMPORTS = {"requests", "json", "re"}
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "input",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
}
REQUESTS_METHODS = {"get", "post", "put", "delete", "head", "request"}
MARKER = "\n__STELLA_RESULT__"

HARNESS = r"""
import json, sys, runpy
path, kwargs = sys.argv[1], json.loads(sys.argv[2])
ns = runpy.run_path(path)
out = ns["run"](**kwargs)
sys.stdout.write("\n__STELLA_RESULT__" + json.dumps(out))
"""


def check_code(code: str, expected_params: list[str] | None = None) -> list[str]:
    """Return a list of problems; an empty list means the code passed."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"syntax error: {e}"]

    problems: list[str] = []
    run_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"import not allowed: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                problems.append(f"import not allowed: from {node.module}")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in FORBIDDEN_CALLS:
                problems.append(f"call not allowed: {f.id}()")
            if (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id == "requests"
                and f.attr in REQUESTS_METHODS
                and not any(k.arg == "timeout" for k in node.keywords)
            ):
                problems.append(f"requests.{f.attr}() must set timeout=")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append(f"dunder attribute not allowed: {node.attr}")
        elif isinstance(node, ast.Name) and node.id.startswith("__") and node.id != "__name__":
            problems.append(f"dunder name not allowed: {node.id}")

    for node in tree.body:  # top-level only
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            run_fn = node
    if run_fn is None:
        problems.append("no top-level function named run")
    elif expected_params is not None:
        args = {a.arg for a in run_fn.args.args + run_fn.args.kwonlyargs}
        missing = [p for p in expected_params if p not in args]
        if missing:
            problems.append(f"run() is missing parameters: {missing}")
    return problems

def _limits(timeout: int):
    def apply():  # POSIX only; skipped on Windows
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (timeout + 5, timeout + 5))
        resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))

    return apply if os.name == "posix" else None


def _clean_env() -> dict:
    keep = {"PATH", "HOME", "SYSTEMROOT", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "no_proxy", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"}
    return {k: v for k, v in os.environ.items() if k in keep}


def run_file(code_path: str, kwargs: dict, timeout: int = 20) -> dict:
    """Run run(**kwargs) from a Python file in a subprocess.

    Returns {'ok': bool, 'data': dict, 'error': str | None}.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", HARNESS, str(code_path), json.dumps(kwargs)],
            capture_output=True, text=True, timeout=timeout,
            env=_clean_env(), preexec_fn=_limits(timeout),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "data": {}, "error": f"timeout after {timeout}s"}
    if proc.returncode != 0:
        last = (proc.stderr.strip().splitlines() or ["unknown error"])[-1]
        return {"ok": False, "data": {}, "error": last}
    if MARKER not in proc.stdout:
        return {"ok": False, "data": {}, "error": "tool produced no result"}
    try:
        data = json.loads(proc.stdout.split(MARKER, 1)[1])
    except ValueError as e:
        return {"ok": False, "data": {}, "error": f"result was not valid JSON: {e}"}
    if not isinstance(data, dict):
        data = {"value": data}
    return {"ok": True, "data": data, "error": None}