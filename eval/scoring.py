def score(answer: str, expected: list[str]) -> bool:
    a = (answer or "").lower()
    return all(e.lower() in a for e in expected)