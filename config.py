"""Central configuration for STELLA-mini."""
# Tried in order; the first one your account supports is used.
MODEL_CANDIDATES = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
CACHE_FILE = "data/llm_cache.json"
MAX_ITERATIONS = 8