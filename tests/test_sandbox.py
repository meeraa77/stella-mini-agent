import pytest

from tools import sandbox

GOOD = "import re\n\ndef run(text):\n    return {'n': len(re.findall(r'\\d+', text))}\n"


def test_good_code_passes():
    assert sandbox.check_code(GOOD, expected_params=["text"]) == []


@pytest.mark.parametrize("code,fragment", [
    ("import os\ndef run(): return {}", "import not allowed"),
    ("from subprocess import run\ndef run(): return {}", "import not allowed"),
    ("def run():\n    return eval('1')", "eval"),
    ("def run():\n    return open('x').read()", "open"),
    ("def run(x):\n    return x.__class__", "dunder"),
    ("import requests\ndef run():\n    return requests.get('http://x').json()", "timeout"),
    ("def go(): return {}", "no top-level function named run"),
])
def test_bad_code_rejected(code, fragment):
    problems = sandbox.check_code(code)
    assert any(fragment in p for p in problems), problems


def test_missing_parameter_detected():
    assert any("missing parameters" in p for p in sandbox.check_code(GOOD, expected_params=["gene"]))

def test_run_file_ok(tmp_path):
    p = tmp_path / "t.py"
    p.write_text(GOOD)
    res = sandbox.run_file(str(p), {"text": "a1 b22 c333"})
    assert res == {"ok": True, "data": {"n": 3}, "error": None}


def test_run_file_reports_exceptions(tmp_path):
    p = tmp_path / "t.py"
    p.write_text("def run():\n    raise LookupError('nothing here')\n")
    res = sandbox.run_file(str(p), {})
    assert not res["ok"] and "nothing here" in res["error"]


def test_run_file_timeout(tmp_path):
    p = tmp_path / "t.py"
    p.write_text("def run():\n    while True:\n        pass\n")
    res = sandbox.run_file(str(p), {}, timeout=2)
    assert not res["ok"] and "timeout" in res["error"]