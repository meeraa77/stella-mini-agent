"""Tool 2: UniProtKB lookup by gene symbol or accession (REST, free)."""
from __future__ import annotations

from tools import base
from tools.base import ToolSpec

SEARCH = "https://rest.uniprot.org/uniprotkb/search"

SPEC = ToolSpec(
    name="uniprot_lookup",
    description=(
        "Look up a reviewed UniProtKB protein by gene symbol (with organism taxonomy ID) "
        "or by accession. Returns accession, protein name, sequence length, organism "
        "and a short function note."
    ),
    params_schema={
        "type": "object",
        "properties": {
            "gene_symbol": {"type": "string"},
            "accession": {"type": "string"},
            "organism_id": {"type": "integer", "default": 9606},
        },
        "required": [],
    },
)


def run(gene_symbol: str | None = None, accession: str | None = None, organism_id: int = 9606) -> dict:
    if accession:
        query = f"accession:{accession}"
    elif gene_symbol:
        query = f"gene_exact:{gene_symbol} AND organism_id:{organism_id} AND reviewed:true"
    else:
        raise ValueError("give gene_symbol or accession")
    d = base.get_json(SEARCH, params={"query": query, "format": "json", "size": 1})
    results = d.get("results", [])
    if not results:
        raise LookupError(f"no UniProt entry for query: {query}")
    r = results[0]
    name = (
        r.get("proteinDescription", {})
        .get("recommendedName", {})
        .get("fullName", {})
        .get("value")
    )
    function = next(
        (
            c["texts"][0]["value"]
            for c in r.get("comments", [])
            if c.get("commentType") == "FUNCTION" and c.get("texts")
        ),
        None,
    )
    return {
        "accession": r.get("primaryAccession"),
        "entry_name": r.get("uniProtkbId"),
        "protein_name": name,
        "length": r.get("sequence", {}).get("length"),
        "organism": r.get("organism", {}).get("scientificName"),
        "function": function[:500] if function else None,
        "source": "UniProtKB",
    }