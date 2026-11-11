"""Check: a solved question is saved, then retrieved for a similar one."""
import agent
from template_library import TemplateLibrary

lib = TemplateLibrary("data/templates_test.json")
lib.clear()

print("=== Run 1: learn from an experience question ===")
r1 = agent.run_agent_traced("What is the UniProt accession of human TP53?",
                            library=lib, learn=True,
                            meta={"condition": "B3", "stage": "S0", "task_id": "E1"})
print("Admitted:", r1["admitted"], "| library size:", len(lib))

print("\n=== Run 2: similar question, should retrieve the template ===")
r2 = agent.run_agent_traced("What is the UniProt accession of human BRCA1?",
                            library=lib, learn=False,
                            meta={"condition": "B3", "stage": "S2", "task_id": "H1"})
print("Retrieved:", [t.question for t in r2["retrieved"]])
print("Answer:", r2["answer"])