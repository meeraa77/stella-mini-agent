"""Keyword scorer: an answer is correct if it contains any expected string."""


def score(answer: str, expected: list[str]) -> bool:
    a = (answer or "").lower()
    return any(e.lower() in a for e in expected)