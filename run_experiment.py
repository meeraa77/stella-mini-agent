"""Run B1/B2/B3 at stages S0 and S2 on held-out tasks (resumable)."""
import argparse
import json
import time
from pathlib import Path

import agent
from template_library import TemplateLibrary
from eval.scoring import score

TASKS = "tasks/tasks.jsonl"
OUT = "results/raw/results.jsonl"

SEED_TEMPLATES = [
    ("What is the UniProt accession of a human gene?",
     ["Call the UniProt tool with the gene symbol and organism human",
      "Read the accession from the tool output"], []),
    ("What is the Ensembl gene ID of a human gene?",
     ["Call the Ensembl tool with the gene symbol and species human",
      "Read the gene ID from the tool output"], []),
]


def load_tasks():
    with open(TASKS, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return ([r for r in rows if r["split"] == "experience"],
            [r for r in rows if r["split"] == "heldout"])


def write(row):
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def load_done():
    if not Path(OUT).exists():
        return set()
    with open(OUT, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return {(r["condition"], r["stage"], r["repeat"], r["task_id"]) for r in rows}


DONE = load_done()


def run_one(task, cond, stage, rep, lib, learn, sleep):
    if (cond, stage, rep, task["task_id"]) in DONE:
        return
    meta = {"condition": cond, "stage": stage, "task_id": task["task_id"], "repeat": rep}
    try:
        res = agent.run_agent_traced(
            task["question"], library=lib, learn=learn,
            is_correct=(lambda a: score(a, task["expected"])) if learn else None,
            meta=meta)
        correct = score(res["answer"], task["expected"])
        row = {**meta, "split": task["split"], "correct": correct,
               "steps_n": res["record"]["steps_n"],
               "latency_s": res["record"]["latency_s"],
               "tools_created": len(res["created"]),
               "templates_retrieved": len(res["retrieved"]),
               "admitted": res["admitted"], "answer": res["answer"][:300]}
    except Exception as e:
        row = {**meta, "split": task["split"], "correct": False, "steps_n": 0,
               "latency_s": 0, "tools_created": 0, "templates_retrieved": 0,
               "admitted": None, "answer": f"ERROR: {e}"}
    write(row)
    print(f"  {cond} {stage} r{rep} {task['task_id']}: correct={row['correct']}")
    time.sleep(sleep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", nargs="+", default=["B1", "B2", "B3"])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None, help="tasks per split (smoke test)")
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    exp, held = load_tasks()
    if args.limit:
        exp, held = exp[:args.limit], held[:args.limit]

    for rep in range(1, args.repeats + 1):
        for cond in args.conditions:
            print(f"\n=== {cond} repeat {rep} ===")
            lib = None
            if cond in ("B2", "B3"):
                lib = TemplateLibrary(f"data/lib_{cond}_{rep}.json")
                started = any(k[0] == cond and k[2] == rep for k in DONE)
                if not started:
                    lib.clear()
                    if cond == "B2":
                        for q, steps, tools in SEED_TEMPLATES:
                            lib.add(question=q, steps=steps, tools_used=tools)

            for t in held:                      # S0: before experience
                run_one(t, cond, "S0", rep, lib, False, args.sleep)

            if cond == "B3":                    # experience phase: learn
                for t in exp:
                    run_one(t, cond, "EXP", rep, lib, True, args.sleep)
                print(f"  library size after learning: {len(lib)}")

            for t in held:                      # S2: after experience
                run_one(t, cond, "S2", rep, lib, False, args.sleep)


if __name__ == "__main__":
    main()