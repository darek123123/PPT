from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .schemas import Session


def write_session(path: str | Path, session: Session) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)


def read_session(path: str | Path) -> Session:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    return Session.from_dict(data)
