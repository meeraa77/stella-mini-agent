"""Tool 4: MyGene.info quick annotation (free)."""
from __future__ import annotations

from tools import base
from tools.base import ToolSpec

URL = "https://mygene.info/v3/query"

SPEC = ToolSpec(
    name="mygene_query",
    description=(
        "Quick gene annotation from MyGene.info by symbol and species: Entrez ID, full "
        "name, aliases, gene type and a short summary."
    ),
    params_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "species": {"type": "string", "default": "human"},
        },
        "required": ["symbol"],
    },
)


def run(symbol: str, species: str = "human") -> dict:
    d = base.get_json(
        URL,
        params={
            "q": f"symbol:{symbol}",
            "species": species,
            "fields": "symbol,name,entrezgene,alias,summary,type_of_gene",
            "size": 1,
        },
    )
    hits = d.get("hits", [])
    if not hits:
        raise LookupError(f"no MyGene.info hit for {symbol} ({species})")
    h = hits[0]
    alias = h.get("alias") or []
    if isinstance(alias, str):
        alias = [alias]
    return {
        "entrez_id": str(h.get("entrezgene")) if h.get("entrezgene") is not None else None,
        "symbol": h.get("symbol"),
        "name": h.get("name"),
        "aliases": alias,
        "type_of_gene": h.get("type_of_gene"),
        "summary": (h.get("summary") or "")[:500],
        "source": "MyGene.info",
    }