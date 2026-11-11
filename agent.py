"""STELLA-mini agent: retrieve templates -> plan -> call/create tool -> answer -> learn."""
import json
import re
import time
from pathlib import Path

import config
import llm
from tools.base import ToolSpec
from tools.creation import create_tool
from tools.registry import ToolRegistry

DOCS_DIR = Path("docs/api_snippets")
LOG_PATH = "results/logs/runs.jsonl"

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


def _build_prompt(task: str, history: list, examples: str = "") -> str:
    steps = "\n".join(history) if history else "(none yet)"
    docs = "\n".join(f"- {d}" for d in _doc_files()) or "(none)"
    ex = f"\nSimilar solved examples (use them as a guide, but verify with tools):\n{examples}\n" if examples else ""
    return f"""You are an agent that solves tasks using tools.
{ex}
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


def critic(steps: list, answer: str) -> bool:
    """Rule critic: a tool call succeeded and key numbers/IDs in the answer appear in tool output."""
    outputs = " ".join(s.get("output", "") for s in steps if s["action"] == "tool" and s["ok"])
    if not outputs:
        return False
    tokens = re.findall(r"[A-Za-z0-9\-\.]*\d[A-Za-z0-9\-\.]*", answer)
    tokens = [t.strip(".-") for t in tokens if t.strip(".-")]
    if not tokens:
        return True
    return any(t.lower() in outputs.lower() for t in tokens)


def _log(record: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# ---------- Agent loop ----------
def run_agent_traced(task, max_iterations=None, library=None, learn=False,
                     is_correct=None, meta=None, log_path=LOG_PATH) -> dict:
    """Run one task. library: TemplateLibrary or None. learn: save good solutions.
    is_correct: optional callable(answer)->bool used for admission (experience stage).
    meta: dict merged into the log record (condition, stage, task_id, seed...)."""
    max_iterations = max_iterations or config.MAX_ITERATIONS
    t0 = time.time()
    retrieved = library.retrieve(task, k=2, min_sim=0.2) if library is not None else []
    examples = library.describe_for_prompt(retrieved) if retrieved else ""

    history, steps, created = [], [], []
    answer, stopped = "", True

    for i in range(1, max_iterations + 1):
        reply = llm.ask(_build_prompt(task, history, examples), use_cache=False)
        try:
            decision = _parse_json(reply)
        except Exception as e:
            history.append(f"Step {i}: FAIL - invalid JSON ({e}). Reply with JSON only.")
            print(f"[{i}] FAIL: could not parse reply. Raw start: {reply[:200]!r}")
            continue

        action = decision.get("action")

        if action == "finish":
            print(f"[{i}] FINISH")
            answer, stopped = str(decision.get("answer", "")), False
            break

        if action == "create_tool":
            need, doc = decision.get("need", ""), decision.get("doc", "")
            if doc not in _doc_files():
                history.append(f"Step {i}: FAIL - doc '{doc}' not in the list.")
                print(f"[{i}] CREATE FAIL: unknown doc {doc}")
                steps.append({"action": "create_tool", "tool": None, "args": {}, "ok": False})
                continue
            before = set(registry.names())
            try:
                create_tool(need=need, doc_path=doc, llm=_LLMAdapter(), registry=registry)
            except Exception as e:
                history.append(f"Step {i}: create_tool FAIL - {type(e).__name__}: {e}")
                print(f"[{i}] CREATE FAIL: {type(e).__name__}: {e}")
                steps.append({"action": "create_tool", "tool": None, "args": {}, "ok": False})
                continue
            new = sorted(set(registry.names()) - before)
            if new:
                created += new
                print(f"[{i}] CREATED tool(s): {new}")
                history.append(f"Step {i}: created new tool(s) {new}. They can now be called.")
            else:
                print(f"[{i}] CREATE FAIL: no tool was registered")
                history.append(f"Step {i}: create_tool FAIL - no tool registered.")
            steps.append({"action": "create_tool", "tool": ",".join(new) or None, "args": {}, "ok": bool(new)})
            continue

        name = decision.get("tool")
        args = decision.get("args", {}) or {}
        result = registry.call(name, **args)
        status = "OK" if result.ok else "FAIL"
        detail = _short(result.data) if result.ok else result.error
        print(f"[{i}] {name}({args}) -> {status} ({result.latency_s:.2f}s): {detail[:200]}")
        history.append(f"Step {i}: called {name} with {args} -> {status}: {detail}")
        steps.append({"action": "tool", "tool": name, "args": args, "ok": result.ok, "output": detail})

    if stopped:
        answer = "Stopped: reached max iterations without a final answer."

    # ---- learning: admission rule ----
    admitted = None
    if learn and library is not None and not stopped:
        good = critic(steps, answer)
        if good and is_correct is not None:
            good = bool(is_correct(answer))
        if good:
            tool_steps = [s for s in steps if s["action"] == "tool" and s["ok"]]
            library.add(
                question=task,
                steps=[f"Call {s['tool']} with {sorted(s['args'])}" for s in tool_steps]
                      + ["Read the answer from the tool output"],
                tools_used=sorted({s["tool"] for s in tool_steps}),
            )
            admitted = True
        else:
            admitted = False

    record = {
        "run_id": time.strftime("%Y%m%d-%H%M%S"),
        "task": task,
        "templates_retrieved": [t.question for t in retrieved],
        "steps": [{k: v for k, v in s.items() if k != "output"} for s in steps],
        "tools_created": created,
        "final_answer": answer,
        "admitted": admitted,
        "steps_n": len(steps),
        "latency_s": round(time.time() - t0, 2),
        **(meta or {}),
    }
    _log(record, log_path)
    return {"answer": answer, "stopped": stopped, "steps": steps, "retrieved": retrieved,
            "created": created, "admitted": admitted, "record": record}


def run_agent(task: str, max_iterations: int = None, **kw) -> str:
    """Backward-compatible wrapper: returns just the answer string."""
    return run_agent_traced(task, max_iterations, **kw)["answer"]


if __name__ == "__main__":
    print("Tools loaded:", registry.names())
    print("\nFinal answer:", run_agent("Find basic information about the human gene TP53."))