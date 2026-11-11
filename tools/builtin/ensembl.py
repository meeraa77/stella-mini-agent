"""Tool 3: Ensembl gene lookup by symbol (REST, free)."""
from __future__ import annotations

from urllib.parse import quote

from tools import base
from tools.base import ToolSpec

URL = "https://rest.ensembl.org/lookup/symbol/{species}/{symbol}"

SPEC = ToolSpec(
    name="ensembl_gene",
    description=(
        "Look up a gene in Ensembl by symbol and species. Returns the Ensembl gene ID, "
        "biotype, chromosome, start/end coordinates, strand and assembly."
    ),
    params_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "species": {"type": "string", "default": "homo_sapiens"},
        },
        "required": ["symbol"],
    },
)


def run(symbol: str, species: str = "homo_sapiens") -> dict:
    d = base.get_json(
        URL.format(species=quote(species), symbol=quote(symbol)),
        params={"content-type": "application/json"},
        headers={"Content-Type": "application/json"},
    )
    if not d or "id" not in d:
        raise LookupError(f"no Ensembl gene for {symbol} ({species})")
    return {
        "ensembl_id": d["id"],
        "symbol": d.get("display_name"),
        "description": d.get("description"),
        "biotype": d.get("biotype"),
        "chromosome": d.get("seq_region_name"),
        "start": d.get("start"),
        "end": d.get("end"),
        "strand": d.get("strand"),
        "assembly": d.get("assembly_name"),
        "source": "Ensembl",
    }