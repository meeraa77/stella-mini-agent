"""Shared types and the HTTP helper used by every tool."""
from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

try:  # caching keeps reruns fast and results repeatable
    import requests_cache

    _CACHE_DIR = Path(os.getenv("STELLA_CACHE_DIR", "data"))
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _SESSION = requests_cache.CachedSession(
        str(_CACHE_DIR / "http_cache"),
        expire_after=int(os.getenv("STELLA_CACHE_SECONDS", 7 * 24 * 3600)),
        allowable_methods=("GET",),
    )
except ImportError:  # works without the cache, just slower
    _SESSION = requests.Session()


class ToolError(Exception):
    """Raised by tools when a request fails or nothing is found."""


@dataclass
class ToolSpec:
    name: str
    description: str
    params_schema: dict
    source: str = "builtin"  # 'builtin' or 'generated'

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ToolSpec":
        return cls(d["name"], d["description"], d["params_schema"], d.get("source", "generated"))


@dataclass
class ToolResult:
    ok: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    latency_s: float = 0.0


def get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
    min_interval: float = 0.0,
    retries: int = 2,
) -> Any:
    """GET a URL and return parsed JSON. Retries on 429/5xx, fails fast on 4xx."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = _SESSION.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            last = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            last = ToolError(f"HTTP {r.status_code} from {url}")
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise ToolError(f"HTTP {r.status_code} from {url}")
        if min_interval and not getattr(r, "from_cache", False):
            time.sleep(min_interval)  # be polite to the API
        try:
            return r.json()
        except ValueError as e:
            raise ToolError(f"response was not JSON: {e}") from e
    raise ToolError(f"request failed: {last}")