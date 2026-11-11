"""Tool 1: NCBI Gene lookup by official symbol (E-utilities, free)."""
from __future__ import annotations

import os

from tools import base
from tools.base import ToolSpec

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

SPEC = ToolSpec(
    name="ncbi_gene_search",
    description=(
        "Look up a gene in NCBI Gene by official symbol and organism. Returns the "
        "NCBI Gene ID, official name, chromosome, map location and a short summary."
    ),
    params_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "organism": {"type": "string", "default": "Homo sapiens"},
        },
        "required": ["symbol"],
    },
)


def _key() -> dict:
    k = os.getenv("NCBI_API_KEY")  # optional; raises the rate limit
    return {"api_key": k} if k else {}


def run(symbol: str, organism: str = "Homo sapiens") -> dict:
    term = f"{symbol}[Gene Name] AND {organism}[Organism]"
    s = base.get_json(
        ESEARCH,
        params={"db": "gene", "term": term, "retmode": "json", "retmax": 1, **_key()},
        min_interval=0.35,
    )
    ids = s.get("esearchresult", {}).get("idlist", [])
    if not ids:
        raise LookupError(f"no NCBI Gene record for {symbol} ({organism})")
    gid = ids[0]
    d = base.get_json(
        ESUMMARY,
        params={"db": "gene", "id": gid, "retmode": "json", **_key()},
        min_interval=0.35,
    )
    rec = d.get("result", {}).get(gid)
    if not rec:
        raise LookupError(f"NCBI returned no summary for Gene ID {gid}")
    return {
        "gene_id": gid,
        "symbol": rec.get("name"),
        "description": rec.get("description"),
        "chromosome": rec.get("chromosome"),
        "map_location": rec.get("maplocation"),
        "summary": (rec.get("summary") or "")[:500],
        "source": "NCBI Gene",
    }