"""Template Library: stores successful reasoning strategies and retrieves
similar ones for new questions (the 'evolving' memory of STELLA-mini)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_PATH = "data/templates.json"
DUPLICATE_THRESHOLD = 0.9


@dataclass
class Template:
    question: str                      # example question that this strategy solved
    steps: list[str]                   # the reasoning steps that worked
    tools_used: list[str] = field(default_factory=list)
    pitfalls: str = ""                 # things to avoid
    uses: int = 1                      # how many times this strategy was re-confirmed


class TemplateLibrary:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.templates: list[Template] = []
        self._load()

    # ---- persistence ----------------------------------------------------
    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.templates = [Template(**d) for d in json.load(f)]

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([asdict(t) for t in self.templates], f, indent=2)

    def clear(self) -> None:
        """Wipe the library (used to start a fresh experiment)."""
        self.templates = []
        self._save()

    def __len__(self) -> int:
        return len(self.templates)

    # ---- similarity ------------------------------------------------------
    def _similarities(self, text: str) -> list[float]:
        if not self.templates:
            return []
        corpus = [t.question for t in self.templates] + [text]
        matrix = TfidfVectorizer().fit_transform(corpus)
        return cosine_similarity(matrix[-1], matrix[:-1])[0].tolist()

    # ---- main API ---------------------------------------------------------
    def add(self, question: str, steps: list[str], tools_used: list[str] | None = None,
            pitfalls: str = "") -> bool:
        """Add a template. Returns True if new, False if merged into a duplicate."""
        tools_used = tools_used or []
        sims = self._similarities(question)
        if sims and max(sims) >= DUPLICATE_THRESHOLD:
            existing = self.templates[sims.index(max(sims))]
            existing.uses += 1
            for t in tools_used:
                if t not in existing.tools_used:
                    existing.tools_used.append(t)
            self._save()
            return False
        self.templates.append(Template(question, steps, tools_used, pitfalls))
        self._save()
        return True

    def retrieve(self, question: str, k: int = 2, min_sim: float = 0.1) -> list[Template]:
        """Return the top-k most similar templates (above min_sim)."""
        sims = self._similarities(question)
        ranked = sorted(zip(sims, self.templates), key=lambda p: -p[0])
        return [t for s, t in ranked[:k] if s >= min_sim]

    def describe_for_prompt(self, templates: list[Template]) -> str:
        """Format templates so they can be injected into the Manager prompt."""
        if not templates:
            return "(no similar past solutions)"
        blocks = []
        for i, t in enumerate(templates, 1):
            steps = "\n".join(f"   {n}. {s}" for n, s in enumerate(t.steps, 1))
            blocks.append(
                f"Past example {i}: {t.question}\n"
                f"  Steps that worked:\n{steps}\n"
                f"  Tools used: {', '.join(t.tools_used) or 'none'}\n"
                f"  Pitfalls: {t.pitfalls or 'none noted'}"
            )
        return "\n\n".join(blocks)


if __name__ == "__main__":
    lib = TemplateLibrary("data/templates_demo.json")
    lib.clear()
    print(lib.add("How many amino acids is human TP53?",
                  ["Look up TP53 in UniProt", "Read the sequence length"], ["uniprot"]))
    print(lib.add("How many amino acids is human TP53 protein?",
                  ["Look up TP53 in UniProt", "Read the sequence length"], ["uniprot"]))  # duplicate
    print(lib.add("What is the Entrez ID of BRCA1?",
                  ["Query the gene database", "Read the Entrez ID"], ["mygene"]))
    print("Library size:", len(lib))
    print(lib.describe_for_prompt(lib.retrieve("What is the length of human BRCA2 protein?")))