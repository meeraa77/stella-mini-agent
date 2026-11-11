"""Evaluate the agent on a small task set. Usage: python run_eval.py [--fresh]
--fresh removes the saved Reactome tool first, so the agent must create it."""
import csv
import glob
import os
import shutil
import sys
import time

if "--fresh" in sys.argv:
    os.makedirs("backup_generated", exist_ok=True)
    for f in glob.glob("tools/generated/*reactome*"): 
        shutil.move(f, os.path.join("backup_generated", os.path.basename(f)))
    print("Removed saved Reactome tool (backup in backup_generated/).")

import agent  # noqa: E402  (imported after the optional cleanup)

if not hasattr(agent, "create_tool"):
    print("WARNING: agent.py has no create_tool; creation tasks will fail.")

# (id, task, keywords: pass if the answer contains ANY of them, needs creation?)
TASKS = [
    ("T1", "What is the UniProt accession of human TP53?", ["P04637"], False),
    ("T2", "What is the Ensembl gene ID of human TP53?", ["ENSG00000141510"], False),
    ("T3", "On which chromosome is human BRCA1 located?", ["17"], False),
    ("T4", "Find basic information about the human gene EGFR.", ["7p11", "1956", "chromosome 7"], False),
    ("T5", "Find Reactome pathways related to human TP53 and name the top results.", ["R-HSA", "pathway"], True),
]

# count LLM calls (= steps) and tool calls by wrapping them
counts = {"llm": 0, "tool": 0, "tool_fail": 0}
_orig_ask = agent.llm.ask
_orig_call = agent.registry.call


def _ask(*a, **kw):
    counts["llm"] += 1
    return _orig_ask(*a, **kw)


def _call(name, *a, **kw):
    r = _orig_call(name, *a, **kw)
    counts["tool"] += 1
    if not r.ok:
        counts["tool_fail"] += 1
    return r


agent.llm.ask = _ask
agent.registry.call = _call

rows = []
for tid, task, keys, creation in TASKS:
    for k in counts:
        counts[k] = 0
    before = set(agent.registry.names())
    t0 = time.time()
    try:
        answer = agent.run_agent(task)
    except Exception as e:
        answer = f"Stopped: {type(e).__name__}: {e}"
    secs = time.time() - t0
    created = sorted(set(agent.registry.names()) - before)
    passed = (not answer.startswith("Stopped")) and any(k.lower() in answer.lower() for k in keys)
    rows.append({
        "id": tid, "creation_task": creation, "passed": passed,
        "steps": counts["llm"], "tool_calls": counts["tool"],
        "tool_failures": counts["tool_fail"], "tools_created": len(created),
        "seconds": round(secs, 1),
    })
    print(f"--> {tid}: {'PASS' if passed else 'FAIL'} in {secs:.1f}s\n")
    time.sleep(3)  # be gentle with the free-tier rate limit

# results table
print("\n" + "=" * 78)
print(f"{'ID':<4}{'Creation':<10}{'Result':<8}{'Steps':<7}{'Tools':<7}{'ToolFail':<10}{'Created':<9}{'Sec':<6}")
for r in rows:
    print(f"{r['id']:<4}{str(r['creation_task']):<10}{'PASS' if r['passed'] else 'FAIL':<8}"
          f"{r['steps']:<7}{r['tool_calls']:<7}{r['tool_failures']:<10}{r['tools_created']:<9}{r['seconds']:<6}")
n_pass = sum(r["passed"] for r in rows)
print(f"\nPass rate: {n_pass}/{len(rows)} ({100 * n_pass / len(rows):.0f}%)")

os.makedirs("eval", exist_ok=True)
with open("eval/results.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print("Saved eval/results.csv")