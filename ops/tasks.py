"""Programmatic access to tasks.md — the shared ground truth of the PWJ loop."""

from __future__ import annotations

import re
from pathlib import Path

TASKS_PATH = Path("tasks.md")
SECTIONS = ("## Queue", "## In progress", "## Awaiting judge", "## Done / Rejected (with reason)")
_ID = re.compile(r"\bT-(\d{3,})\b")


def next_task_id(path: Path | str = TASKS_PATH) -> str:
    text = Path(path).read_text() if Path(path).exists() else ""
    ids = [int(m) for m in _ID.findall(text)]
    return f"T-{(max(ids) + 1 if ids else 1):03d}"


def append_to_section(entry: str, section: str = "## Queue", path: Path | str = TASKS_PATH) -> None:
    """Insert ``entry`` (one or more lines) at the end of ``section``."""
    p = Path(path)
    text = p.read_text()
    if section not in text:
        raise ValueError(f"section {section!r} not found in {p}")
    start = text.index(section) + len(section)
    nexts = [text.index(s, start) for s in SECTIONS if s != section and s in text[start:]]
    end = min(nexts) if nexts else len(text)
    block = text[start:end].rstrip("\n")
    new_block = f"{block}\n{entry.rstrip()}\n\n"
    p.write_text(text[:start] + new_block + text[end:])


def hypothesis_entry(task_id: str, claim: str, test: str, decision_rule: str, owner: str = "quant-researcher") -> str:
    return (
        f"- [ ] {task_id} | owner: {owner} | H: {claim}. Test: {test}. Decision rule: {decision_rule}. Owner: {owner}.\n"
        f"      DONE: tearsheet in research/reports/ meeting the decision rule; `python -m eval.gate` run; Judge verdict recorded."
    )
