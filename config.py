"""Central configuration for STELLA-mini."""
import os

# Tried in order; the first one your account supports is used.
MODEL_CANDIDATES = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Optional override, e.g. in PowerShell: $env:STELLA_MODEL = "llama-3.1-8b-instant"
if os.getenv("STELLA_MODEL"):
    MODEL_CANDIDATES = [os.getenv("STELLA_MODEL")]

CACHE_FILE = "data/llm_cache.json"
MAX_ITERATIONS = 8