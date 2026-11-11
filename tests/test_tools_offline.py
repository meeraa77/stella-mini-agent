"""Parsing tests with fake API payloads. They encode the response shapes we EXPECT;
the live tests (later) confirm the real APIs still match."""
from tools import base
from tools.builtin import ensembl, mygene, ncbi_gene, uniprot

def fake(payloads):
    calls = iter(payloads)
    return lambda *a, **k: next(calls)


def test_ncbi_gene(monkeypatch):
    monkeypatch.setattr(base, "get_json", fake([
        {"esearchresult": {"idlist": ["7157"]}},
        {"result": {"7157": {"name": "TP53", "description": "tumor protein p53",
                             "chromosome": "17", "maplocation": "17p13.1", "summary": "s"}}},
    ]))
    out = ncbi_gene.run("TP53")
    assert out["gene_id"] == "7157" and out["chromosome"] == "17"


def test_ncbi_gene_not_found(monkeypatch):
    monkeypatch.setattr(base, "get_json", fake([{"esearchresult": {"idlist": []}}]))
    try:
        ncbi_gene.run("ZZZ")
    except LookupError as e:
        assert "ZZZ" in str(e)
    else:
        raise AssertionError("expected LookupError")

def test_uniprot(monkeypatch):
    monkeypatch.setattr(base, "get_json", fake([{"results": [{
        "primaryAccession": "P01308", "uniProtkbId": "INS_HUMAN",
        "proteinDescription": {"recommendedName": {"fullName": {"value": "Insulin"}}},
        "sequence": {"length": 110}, "organism": {"scientificName": "Homo sapiens"},
        "comments": [{"commentType": "FUNCTION", "texts": [{"value": "Lowers glucose"}]}],
    }]}]))
    out = uniprot.run(gene_symbol="INS")
    assert out["accession"] == "P01308" and out["length"] == 110 and out["function"]


def test_uniprot_needs_an_identifier():
    try:
        uniprot.run()
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")   

def test_ensembl(monkeypatch):
    monkeypatch.setattr(base, "get_json", fake([{"id": "ENSG00000141510", "display_name": "TP53",
                                                 "seq_region_name": "17", "biotype": "protein_coding"}]))
    out = ensembl.run("TP53")
    assert out["ensembl_id"].startswith("ENSG") and out["chromosome"] == "17"   

def test_mygene(monkeypatch):
    monkeypatch.setattr(base, "get_json", fake([{"hits": [{"symbol": "TP53", "entrezgene": 7157, "alias": "p53"}]}]))
    out = mygene.run("TP53")
    assert out["entrez_id"] == "7157" and out["aliases"] == ["p53"]