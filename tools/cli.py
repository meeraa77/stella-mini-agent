"""Manual testing:  python -m tools.cli list | call <tool> key=value ... | search <words>"""
from __future__ import annotations

import json
import sys

from tools.registry import ToolRegistry


def _parse(v: str):
    try:
        return json.loads(v)
    except ValueError:
        return v


def main(argv: list[str]) -> int:
    reg = ToolRegistry()
    if not argv or argv[0] == "list":
        print(reg.describe_for_prompt())
    elif argv[0] == "search":
        print(reg.describe_for_prompt(reg.search(" ".join(argv[1:]))))
    elif argv[0] == "call" and len(argv) >= 2:
        kwargs = {k: _parse(v) for k, v in (a.split("=", 1) for a in argv[2:])}
        res = reg.call(argv[1], **kwargs)
        print(json.dumps({"ok": res.ok, "error": res.error, "data": res.data}, indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))