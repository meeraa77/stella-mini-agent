"""Thin wrapper around the Groq API with a disk cache and model fallback."""
import os
import json
import hashlib
import time
from dotenv import load_dotenv
from groq import Groq
import config

load_dotenv()
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
_active_model = None  # remembers the first model that works

EFFORTS = ["low", "medium", "high"]       # raised on each retry
TOKENS = [4096, 8192, 8192]


def _load_cache() -> dict:
    if os.path.exists(config.CACHE_FILE):
        try:
            with open(config.CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except ValueError:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(config.CACHE_FILE), exist_ok=True)
    with open(config.CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def _call(model: str, prompt: str, attempt: int = 0) -> str:
    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_completion_tokens=TOKENS[min(attempt, 2)],
    )
    if "gpt-oss" in model:
        kwargs["reasoning_effort"] = EFFORTS[min(attempt, 2)]
    resp = _client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        print(f"  (empty content; finish_reason={choice.finish_reason}, "
              f"completion_tokens={getattr(resp.usage, 'completion_tokens', '?')})")
    return text


def ask(prompt: str, use_cache: bool = True, retries: int = 3) -> str:
    """Send a prompt to the LLM and return a non-empty text response."""
    global _active_model
    key = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    cache = _load_cache()
    if use_cache and cache.get(key):
        return cache[key]

    candidates = [_active_model] if _active_model else config.MODEL_CANDIDATES
    for model in candidates:
        for attempt in range(retries):
            try:
                text = _call(model, prompt, attempt)
                if not text:
                    print(f"Empty reply from {model} (attempt {attempt + 1}), retrying...")
                    time.sleep(3)
                    continue
                _active_model = model
                cache[key] = text
                _save_cache(cache)
                return text
            except Exception as e:
                msg = str(e)
                if "model_not_found" in msg or "does not exist" in msg or "decommissioned" in msg:
                    print(f"Model {model} unavailable, trying next...")
                    break
                print(f"LLM error (attempt {attempt + 1}): {msg[:200]}")
                time.sleep(5 * (attempt + 1))
    return ""  # callers treat an empty reply as a failed step


if __name__ == "__main__":
    print(ask("In one sentence, what is the TP53 gene?", use_cache=False))
    print("Model used:", _active_model)