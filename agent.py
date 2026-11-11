"""STELLA-mini agent: plan -> call a tool (or create one) -> observe -> repeat."""
import json
import re
from pathlib import Path

import config
import llm
from tools.base import ToolSpec
from tools.creation import create_tool
from tools.registry import ToolRegistry

DOCS_DIR = Path("docs/api_snippets")

# ---------- Build the registry ----------
try:
    registry = ToolRegistry()
except ModuleNotFoundError as e:
    print(f"WARNING: built-in tools not found ({e}). Using demo tool only.")
    registry = ToolRegistry(load_builtin=False)


def _word_count(text: str = "") -> dict:
    return {"words": len(text.split())}


if "word_count" not in registry.names():
    registry.register_callable(
        ToolSpec(
            name="word_count",
            description="Count the words in a text.",
            params_schema={"properties": {"text": {"type": "string"}}, "required": ["text"]},
        ),
        _word_count,
    )


class _LLMAdapter:
    """What creation.py expects: llm.generate(prompt, ...) -> str."""
    def generate(self, prompt, temperature=None, max_tokens=None, **kw):
        return llm.ask(prompt, use_cache=False)


# ---------- Helpers ----------
def _doc_files() -> list[str]:
    if not DOCS_DIR.exists():
        return []
    return sorted(str(p).replace("\\", "/") for p in DOCS_DIR.glob("*.md"))


def _parse_json(text: str) -> dict:
    """Extract the first valid JSON object from the model's reply."""
    text = text.replace("```json", "").replace("```", "")
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
            if isinstance(obj, dict) and "action" in obj:
                return obj
        except ValueError:
            continue
    raise ValueError("no valid JSON with an 'action' key found")


def _build_prompt(task: str, history: list) -> str:
    steps = "\n".join(history) if history else "(none yet)"
    docs = "\n".join(f"- {d}" for d in _doc_files()) or "(none)"
    return f"""You are an agent that solves tasks using tools.

Task: {task}

Available tools:
{registry.describe_for_prompt()}

API documentation files you can use to create a NEW tool:
{docs}

Previous steps:
{steps}

Rules:
- Use tools to get facts; do not answer from memory when a tool can look it up.
- Only create a new tool if NO existing tool fits the task and a documentation file above covers the API.
- A created tool appears in the tool list on the next step; then call it.
- Some tools need IDs from other tools (e.g. a UniProt accession); call those first.

Reply with ONLY one JSON object, no extra text, in one of these forms:
{{"action": "tool", "tool": "<tool name>", "args": {{...}}}}
{{"action": "create_tool", "need": "<what the tool must do>", "doc": "<one documentation file path from the list>"}}
{{"action": "finish", "answer": "<final answer>"}}
"""


def _short(obj, limit: int = 1500) -> str:
    s = json.dumps(obj, default=str)
    return s if len(s) <= limit else s[:limit] + "...[truncated]"


# ---------- Agent loop ----------
def run_agent(task: str, max_iterations: int = None) -> str:
    max_iterations = max_iterations or config.MAX_ITERATIONS
    history = []

    for i in range(1, max_iterations + 1):
        reply = llm.ask(_build_prompt(task, history), use_cache=False)
        try:
            decision = _parse_json(reply)
        except Exception as e:
            history.append(f"Step {i}: FAIL - invalid JSON ({e}). Reply with JSON only.")
            print(f"[{i}] FAIL: could not parse reply. Raw start: {reply[:200]!r}")
            continue

        action = decision.get("action")

        if action == "finish":
            print(f"[{i}] FINISH")
            return str(decision.get("answer", ""))

        if action == "create_tool":
            need = decision.get("need", "")
            doc = decision.get("doc", "")
            if doc not in _doc_files():
                history.append(f"Step {i}: FAIL - doc '{doc}' not in the list.")
                print(f"[{i}] CREATE FAIL: unknown doc {doc}")
                continue
            before = set(registry.names())
            try:
                create_tool(need=need, doc_path=doc, llm=_LLMAdapter(), registry=registry)
            except Exception as e:
                history.append(f"Step {i}: create_tool FAIL - {type(e).__name__}: {e}")
                print(f"[{i}] CREATE FAIL: {type(e).__name__}: {e}")
                continue
            new = sorted(set(registry.names()) - before)
            if new:
                print(f"[{i}] CREATED tool(s): {new}")
                history.append(f"Step {i}: created new tool(s) {new}. They can now be called.")
            else:
                print(f"[{i}] CREATE FAIL: no tool was registered")
                history.append(f"Step {i}: create_tool FAIL - no tool registered.")
            continue

        name = decision.get("tool")
        args = decision.get("args", {}) or {}
        result = registry.call(name, **args)  # never raises; returns ToolResult

        status = "OK" if result.ok else "FAIL"
        detail = _short(result.data) if result.ok else result.error
        print(f"[{i}] {name}({args}) -> {status} ({result.latency_s:.2f}s): {detail[:200]}")
        history.append(f"Step {i}: called {name} with {args} -> {status}: {detail}")

    return "Stopped: reached max iterations without a final answer."


if __name__ == "__main__":
    print("Tools loaded:", registry.names())
    answer = run_agent("Find Reactome pathways related to apoptosis and name the top results.")
    print("\nFinal answer:", answer)