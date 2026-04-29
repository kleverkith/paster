from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Africa/Nairobi")


def load_capture_jsonl(path: str | Path) -> list[dict]:
    capture_path = Path(path)
    records: list[dict] = []
    if not capture_path.exists():
        return records
    with capture_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def parse_capture_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(APP_TIMEZONE)
    except ValueError:
        return None


def filter_records_for_day(records: list[dict], target_day: date | None = None) -> list[dict]:
    local_day = target_day or datetime.now(APP_TIMEZONE).date()
    filtered: list[dict] = []
    start_time = time(0, 0)
    for item in records:
        timestamp = parse_capture_timestamp(item.get("timestamp"))
        if timestamp and timestamp.date() == local_day and timestamp.time() >= start_time:
            filtered.append(item)
    return filtered


def capture_records_to_text(records: list[dict]) -> str:
    blocks: list[str] = []
    for item in records:
        lines: list[str] = []
        author = item.get("author") or item.get("from")
        timestamp = parse_capture_timestamp(item.get("timestamp"))
        body = (item.get("body") or "").strip()
        caption = (item.get("caption") or "").strip()

        if author or timestamp:
            formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else ""
            meta = " | ".join(part for part in [str(author or "").strip(), formatted_timestamp] if part)
            if meta:
                lines.append(meta)
        if body:
            lines.append(body)
        if caption:
            lines.append(caption)

        if lines:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
