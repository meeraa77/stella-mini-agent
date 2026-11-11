"""Tool registry: the single interface the agent uses.

Interface contract with Meera (frozen on Day 1):
    registry.list_tools()            -> list[ToolSpec]
    registry.search(query, k=5)      -> list[ToolSpec]
    registry.call(name, **kwargs)    -> ToolResult
    registry.register(spec, code)    -> None
    registry.describe_for_prompt()   -> str
"""
from __future__ import annotations

import importlib
import json
import re
import time
from pathlib import Path
from typing import Callable

from tools import sandbox
from tools.base import ToolResult, ToolSpec

BUILTIN_MODULES = [
    "tools.builtin.ncbi_gene",
    "tools.builtin.uniprot",
    "tools.builtin.ensembl",
    "tools.builtin.mygene",
]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class ToolRegistry:
    def __init__(self, generated_dir: str = "tools/generated", load_builtin: bool = True):
        self.generated_dir = Path(generated_dir)
        self._specs: dict[str, ToolSpec] = {}
        self._fns: dict[str, Callable] = {}      # builtin tools run in-process
        self._paths: dict[str, str] = {}         # generated tools run in a subprocess
        if load_builtin:
            for mod_name in BUILTIN_MODULES:
                mod = importlib.import_module(mod_name)
                self.register_callable(mod.SPEC, mod.run)
        self._load_generated()

    # ---- registration -------------------------------------------------
    def register_callable(self, spec: ToolSpec, fn: Callable) -> None:
        self._specs[spec.name] = spec
        self._fns[spec.name] = fn

    def register(self, spec: ToolSpec, code_path: str, persist: bool = True) -> None:
        spec.source = "generated"
        self._specs[spec.name] = spec
        self._paths[spec.name] = str(code_path)
        if persist:
            self.generated_dir.mkdir(parents=True, exist_ok=True)
            payload = {**spec.to_dict(), "code_path": str(code_path)}
            (self.generated_dir / f"{spec.name}.json").write_text(json.dumps(payload, indent=2))

    def _load_generated(self) -> None:
        if not self.generated_dir.exists():
            return
        for p in sorted(self.generated_dir.glob("*.json")):
            d = json.loads(p.read_text())
            code = d.get("code_path")
            if code and Path(code).exists():
                self._specs[d["name"]] = ToolSpec.from_dict(d)
                self._paths[d["name"]] = code

    # ---- discovery ----------------------------------------------------
    def list_tools(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def names(self) -> list[str]:
        return list(self._specs)

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def search(self, query: str, k: int = 5) -> list[ToolSpec]:
        q = _tokens(query)
        scored = []
        for spec in self._specs.values():
            score = len(q & _tokens(spec.description)) + 2 * len(q & _tokens(spec.name))
            if score > 0:
                scored.append((score, spec))
        scored.sort(key=lambda t: -t[0])
        return [s for _, s in scored[:k]]

    def describe_for_prompt(self, specs: list[ToolSpec] | None = None) -> str:
        lines = []
        for s in specs or self.list_tools():
            props = s.params_schema.get("properties", {})
            req = set(s.params_schema.get("required", []))
            args = ", ".join(
                f"{n}: {p.get('type', 'any')}{'' if n in req else ' (optional)'}" for n, p in props.items()
            )
            lines.append(f"- {s.name}({args}): {s.description}")
        return "\n".join(lines)

    # ---- execution ----------------------------------------------------
    def call(self, name: str, timeout: int = 20, **kwargs) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None:
            return ToolResult(False, {}, f"unknown tool: {name}")
        props = spec.params_schema.get("properties", {})
        missing = [r for r in spec.params_schema.get("required", []) if r not in kwargs]
        unexpected = [k for k in kwargs if k not in props]
        if missing or unexpected:
            return ToolResult(False, {}, f"bad arguments: missing={missing} unexpected={unexpected}")

        t0 = time.time()
        if name in self._paths:  # generated: isolated subprocess
            res = sandbox.run_file(self._paths[name], kwargs, timeout=timeout)
            return ToolResult(res["ok"], res["data"], res["error"], time.time() - t0)
        try:
            out = self._fns[name](**kwargs)
            if not isinstance(out, dict):
                out = {"value": out}
            return ToolResult(True, out, None, time.time() - t0)
        except Exception as e:  # tools must never crash the agent loop
            return ToolResult(False, {}, f"{type(e).__name__}: {e}", time.time() - t0)