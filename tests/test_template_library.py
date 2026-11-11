from template_library import TemplateLibrary


def test_add_and_retrieve(tmp_path):
    lib = TemplateLibrary(str(tmp_path / "t.json"))
    lib.add("How many amino acids is human TP53?", ["lookup uniprot"], ["uniprot"])
    lib.add("What is the Entrez ID of BRCA1?", ["query gene db"], ["mygene"])
    result = lib.retrieve("length of human TP53 protein amino acids", k=1)
    assert result and "TP53" in result[0].question


def test_duplicate_is_merged(tmp_path):
    lib = TemplateLibrary(str(tmp_path / "t.json"))
    assert lib.add("How many amino acids is human TP53?", ["a"], ["uniprot"]) is True
    assert lib.add("How many amino acids is human TP53?", ["a"], ["uniprot"]) is False
    assert len(lib) == 1 and lib.templates[0].uses == 2


def test_persistence(tmp_path):
    path = str(tmp_path / "t.json")
    TemplateLibrary(path).add("question one here", ["step"], [])
    assert len(TemplateLibrary(path)) == 1