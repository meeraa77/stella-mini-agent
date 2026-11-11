from tools.creation import create_tool, parse_llm_output, register_handwritten
from tools.registry import ToolRegistry

FENCE = "`" * 3  # three backticks, built in code so nothing can break when copying


def make_reply(name, code):
    return "\n".join([
        "NAME: " + name,
        "DESCRIPTION: Extract identifier-like tokens from text.",
        'PARAMS: {"text": "string"}',
        'TEST_ARGS: {"text": "see P01308 and Q9"}',
        "CODE:",
        FENCE + "python",
        code,
        FENCE,
    ])


GOOD_CODE = (
    "import re\n"
    "def run(text):\n"
    '    m = re.findall(r"[A-Z]+\\d+", text)\n'
    "    if not m:\n"
    '        raise LookupError("none")\n'
    '    return {"ids": m}'
)
BAD_CODE = "import os\ndef run(text):\n    return {\"ids\": os.listdir('.')}"

GOOD = make_reply("find_ids", GOOD_CODE)
BAD = make_reply("find_ids", BAD_CODE)


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def generate(self, prompt, temperature=0.2, max_tokens=1500):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def setup(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("Tool needs: extract ids")
    return doc, ToolRegistry(generated_dir=str(tmp_path / "gen"))


def test_parse_output():
    p = parse_llm_output(GOOD)
    assert p["name"] == "find_ids" and p["params"] == {"text": "string"} and "def run" in p["code"]


def test_parse_rejects_malformed():
    try:
        parse_llm_output("NAME: x")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_retry_with_error_feedback_then_success(tmp_path):
    doc, reg = setup(tmp_path)
    llm = FakeLLM([BAD, GOOD])
    rep = create_tool("extract ids", str(doc), llm, registry=reg, generated_dir=str(tmp_path / "gen"))
    assert rep.passed and rep.attempts == 2 and rep.tool_name == "find_ids"
    assert "import not allowed: os" in llm.prompts[1]  # error fed back to the model
    assert reg.call("find_ids", text="P01308 X1").data == {"ids": ["P01308", "X1"]}


def test_gives_up_after_retries(tmp_path):
    doc, reg = setup(tmp_path)
    rep = create_tool("x", str(doc), FakeLLM([BAD, BAD, BAD]), registry=reg, generated_dir=str(tmp_path / "gen"))
    assert not rep.passed and rep.attempts == 3 and "static check failed" in rep.error
    assert "find_ids" not in reg.names()


def test_expect_keys_enforced(tmp_path):
    doc, reg = setup(tmp_path)
    rep = create_tool("x", str(doc), FakeLLM([GOOD] * 3), registry=reg,
                      expect_keys=["pathways"], generated_dir=str(tmp_path / "gen"))
    assert not rep.passed and "missing keys" in rep.error


def test_name_clash_with_builtin_rejected(tmp_path):
    doc, reg = setup(tmp_path)
    clash = GOOD.replace("NAME: find_ids", "NAME: uniprot_lookup")
    rep = create_tool("x", str(doc), FakeLLM([clash] * 3), registry=reg, generated_dir=str(tmp_path / "gen"))
    assert not rep.passed and "already exists" in rep.error


def test_register_handwritten_uses_same_checks(tmp_path):
    _, reg = setup(tmp_path)
    code = tmp_path / "hw.py"
    code.write_text("import re\ndef run(text):\n    return {'n': len(text)}\n")
    rep = register_handwritten(str(code), "hw_len", "count chars",
                               {"text": "string"}, {"text": "abc"}, registry=reg,
                               generated_dir=str(tmp_path / "gen"))
    assert rep.passed and rep.handwritten
    evil = tmp_path / "evil.py"
    evil.write_text("import os\ndef run(text):\n    return {'x': 1}\n")
    rep = register_handwritten(str(evil), "evil", "x", {"text": "string"}, {"text": "a"}, registry=reg,
                               generated_dir=str(tmp_path / "gen"))
    assert not rep.passed