from tools import base
from tools.base import ToolSpec
from tools.registry import ToolRegistry


def reg(tmp_path):
    return ToolRegistry(generated_dir=str(tmp_path / "gen"))


def test_builtin_tools_loaded(tmp_path):
    r = reg(tmp_path)
    assert {"ncbi_gene_search", "uniprot_lookup", "ensembl_gene", "mygene_query"} <= set(r.names())


def test_unknown_tool_rejected_cleanly(tmp_path):
    res = reg(tmp_path).call("no_such_tool", x=1)
    assert not res.ok and "unknown tool" in res.error


def test_argument_validation(tmp_path):
    r = reg(tmp_path)
    assert "missing" in r.call("ncbi_gene_search").error
    assert "unexpected" in r.call("ncbi_gene_search", symbol="TP53", bogus=1).error


def test_search_finds_relevant_tool(tmp_path):
    names = [s.name for s in reg(tmp_path).search("protein sequence length accession")]
    assert names[0] == "uniprot_lookup"


def test_tool_exception_becomes_error_result(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise base.ToolError("HTTP 503")
    monkeypatch.setattr(base, "get_json", boom)
    res = reg(tmp_path).call("ncbi_gene_search", symbol="TP53")
    assert not res.ok and "HTTP 503" in res.error


def test_register_and_call_generated_tool(tmp_path):
    r = reg(tmp_path)
    code = tmp_path / "echo_len.py"
    code.write_text("def run(text):\n    return {'length': len(text)}\n")
    r.register(ToolSpec("echo_len", "count characters", {"type": "object",
               "properties": {"text": {"type": "string"}}, "required": ["text"]}), str(code))
    assert r.call("echo_len", text="abcd").data == {"length": 4}
    # a new registry instance reloads it from disk
    assert "echo_len" in reg(tmp_path).names()