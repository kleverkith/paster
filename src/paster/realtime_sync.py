from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from paster.capture_loader import APP_TIMEZONE
from paster.google_sheets import sync_today_capture_to_google


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync today's scraped WhatsApp data to Google Sheets.")
    parser.add_argument("--credentials", required=True, help="Path to Google service account JSON credentials.")
    parser.add_argument("--spreadsheet-id", required=True, help="Target Google Spreadsheet ID.")
    parser.add_argument("--capture", required=True, help="Path to messages.jsonl capture file.")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Polling interval for realtime sync.")
    parser.add_argument("--once", action="store_true", help="Run one sync and exit.")
    parser.add_argument("--status-file", default="", help="Optional status JSON file path.")
    return parser.parse_args()


def write_status(path: str, payload: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    while True:
        status: dict[str, str | int] = {
            "updatedAt": datetime.now(APP_TIMEZONE).isoformat(),
            "state": "syncing",
            "capture": args.capture,
            "spreadsheetId": args.spreadsheet_id,
            "intervalSeconds": args.interval_seconds,
        }
        try:
            result = sync_today_capture_to_google(args.credentials, args.spreadsheet_id, args.capture)
            status.update({"state": "ok", **result})
            print(json.dumps(status))
        except Exception as exc:
            status.update({"state": "error", "error": str(exc)})
            print(json.dumps(status))
        write_status(args.status_file, status)
        if args.once:
            break
        time.sleep(max(15, args.interval_seconds))


if __name__ == "__main__":
    main()
