from __future__ import annotations

import json
from pathlib import Path


def load_status(path: str | Path) -> dict:
    status_path = Path(path)
    if not status_path.exists():
        return {}
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
