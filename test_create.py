"""Test: ask the agent's tool creator to build a Reactome tool."""
import llm
from tools.creation import create_tool
from tools.registry import ToolRegistry


class LLMAdapter:
    """Matches what creation.py expects: llm.generate(prompt, ...) -> str."""
    def generate(self, prompt, temperature=None, max_tokens=None, **kw):
        return llm.ask(prompt, use_cache=False)

    # extra aliases in case other code paths call these
    def ask(self, prompt, *a, **kw):
        return llm.ask(prompt, use_cache=False)

    def __call__(self, prompt, *a, **kw):
        return llm.ask(prompt, use_cache=False)


registry = ToolRegistry()
print("Before:", registry.names())

report = create_tool(
    need="Search Reactome for pathways matching a text query and return the top results.",
    doc_path="docs/api_snippets/reactome.md",
    llm=LLMAdapter(),
    registry=registry,
)

print("\nReport:", report)
print("After:", registry.names())