"""
Where meeting notes come from.

LEARN: Here it's a folder per client (data\\meetings\\<client_id>\\*.md).
In a real firm this would be the CRM's notes API or a call-recording
transcript service. Only this file would change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class Meeting:
    source: str
    date: str | None
    type: str | None
    attendees: str | None
    text: str


def _front_matter(raw: str) -> tuple[dict[str, str], str]:
    raw = raw.lstrip("﻿")  # files saved by some Windows editors start with a BOM
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, parts[2].strip()


class NotesStore:
    def __init__(self, notes_dir: Path):
        self.notes_dir = notes_dir

    def meetings(self, client_id: str, last_n: int) -> list[Meeting]:
        """Most recent first. Unknown client -> empty list."""
        if not CLIENT_ID.match(client_id):
            raise ValueError("invalid client_id")
        folder = self.notes_dir / client_id
        if not folder.is_dir():
            return []
        out = []
        for path in sorted(folder.glob("*.md"), reverse=True)[:last_n]:  # file names start with the date
            meta, body = _front_matter(path.read_text(encoding="utf-8"))
            out.append(Meeting(source=path.name, date=meta.get("date"), type=meta.get("type"),
                               attendees=meta.get("attendees"), text=body))
        return out

    def clients(self) -> list[str]:
        if not self.notes_dir.is_dir():
            return []
        return sorted(p.name for p in self.notes_dir.iterdir() if p.is_dir())
