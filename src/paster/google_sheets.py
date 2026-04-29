from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from .capture_loader import APP_TIMEZONE, capture_records_to_text, filter_records_for_day, load_capture_jsonl
from .models import AssignmentTicket, CompletionTicket, ParseResult
from .parser import parse_whatsapp_text
from .ticket_dedupe import dedupe_assignments, dedupe_completions, with_deduped_parse_result

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CONNECTION_HEADERS = [
    "ACC",
    "NAME",
    "LOCATION",
    "CONTACT",
    "CLOSE DATE/TIME",
    "SN",
    "ONU",
    "INDOOR CABLE",
    "OUTDOOR CABLE",
    "ATB",
    "PATCH",
    "POWER LEVEL",
    "POWER FAT",
    "TECH",
    "REMARKS",
]
ASSIGNMENT_HEADERS = [
    "ACC",
    "NAME",
    "CONTACT",
    "ROUTE",
    "LOCATION",
    "TECH",
    "STATUS",
    "REMARKS",
]

SUMMARY_HEADERS = ["Item", "Count"]
RAW_TEXT_HEADERS = ["TYPE", "IDENTIFIER", "RAW TEXT"]


def open_spreadsheet(credentials_path: str | Path, spreadsheet_id: str):
    creds = Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


def sanitize_title(value: str) -> str:
    invalid = set("[]:*?/\\")
    cleaned = "".join("-" if char in invalid else char for char in value).strip()
    return cleaned[:100]


def build_connections_title(target_date: date) -> str:
    return sanitize_title(f"Connections {target_date.isoformat()}")


def build_summary_title(target_date: date) -> str:
    return sanitize_title(f"Summary {target_date.isoformat()}")


def build_assignments_title(target_date: date) -> str:
    return sanitize_title(f"Assignments {target_date.isoformat()}")


def build_raw_text_title(target_date: date) -> str:
    return sanitize_title(f"Raw Text {target_date.isoformat()}")


def get_or_create_worksheet(spreadsheet, worksheet_name: str, rows: int = 1000, cols: int = 26):
    try:
        return spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=worksheet_name, rows=rows, cols=cols)


def replace_worksheet_values(worksheet, rows: list[list[str | int | float | None]]) -> None:
    worksheet.clear()
    if rows:
        worksheet.update(values=rows, range_name="A1")


def completion_rows(records: list[CompletionTicket]) -> list[list[str | int | float | None]]:
    rows: list[list[str | int | float | None]] = [CONNECTION_HEADERS]
    for record in dedupe_completions(records):
        row = record.to_row()
        rows.append([row.get(header) for header in CONNECTION_HEADERS])
    return rows


def assignment_rows(records: list[AssignmentTicket]) -> list[list[str | None]]:
    rows: list[list[str | None]] = [ASSIGNMENT_HEADERS]
    for record in dedupe_assignments(records):
        rows.append(
            [
                record.account,
                record.client_name,
                record.contact,
                record.route_code,
                record.location,
                record.tech,
                record.status,
                record.remarks,
            ]
        )
    return rows


def with_deduped_completions(result: ParseResult) -> ParseResult:
    return with_deduped_parse_result(result)


def summary_rows(summary_counts: dict[str, int]) -> list[list[str | int]]:
    rows: list[list[str | int]] = [SUMMARY_HEADERS]
    for key, value in summary_counts.items():
        rows.append([key, value])
    return rows


def raw_text_rows(result: ParseResult) -> list[list[str | None]]:
    rows: list[list[str | None]] = [RAW_TEXT_HEADERS]
    for record in result.assignments:
        identifier = record.account or record.contact or record.client_name
        rows.append(["Assignment", identifier, record.raw_text])
    for record in result.completions:
        identifier = record.account or record.serial_number or record.client_name
        rows.append(["Completion", identifier, record.raw_text])
    for record in getattr(result, "field_activity_reports", []):
        identifier = record.location or record.contractor or record.scope
        rows.append(["Field Activity", identifier, record.raw_text])
    return rows


def sync_daily_parse_result(credentials_path: str | Path, spreadsheet_id: str, result: ParseResult, target_date: date) -> dict[str, str]:
    result = with_deduped_completions(result)
    spreadsheet = open_spreadsheet(credentials_path, spreadsheet_id)
    connections_title = build_connections_title(target_date)
    assignments_title = build_assignments_title(target_date)
    raw_text_title = build_raw_text_title(target_date)
    summary_title = build_summary_title(target_date)

    connections_sheet = get_or_create_worksheet(spreadsheet, connections_title, rows=max(1000, len(result.completions) + 20), cols=20)
    assignments_sheet = get_or_create_worksheet(spreadsheet, assignments_title, rows=max(1000, len(result.assignments) + 20), cols=10)
    raw_text_sheet = get_or_create_worksheet(
        spreadsheet,
        raw_text_title,
        rows=max(1000, len(result.assignments) + len(result.completions) + len(getattr(result, "field_activity_reports", [])) + 20),
        cols=5,
    )
    summary_sheet = get_or_create_worksheet(spreadsheet, summary_title, rows=100, cols=5)

    replace_worksheet_values(connections_sheet, completion_rows(result.completions))
    replace_worksheet_values(assignments_sheet, assignment_rows(result.assignments))
    replace_worksheet_values(raw_text_sheet, raw_text_rows(result))
    replace_worksheet_values(summary_sheet, summary_rows(result.summary_counts))

    timestamp = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    summary_sheet.update_acell("D1", "Last Sync")
    summary_sheet.update_acell("E1", timestamp)

    return {
        "spreadsheet_url": spreadsheet.url,
        "connections_sheet": connections_title,
        "assignments_sheet": assignments_title,
        "raw_text_sheet": raw_text_title,
        "summary_sheet": summary_title,
        "last_sync": timestamp,
    }


def sync_today_capture_to_google(credentials_path: str | Path, spreadsheet_id: str, capture_path: str | Path, target_date: date | None = None) -> dict[str, str]:
    today = target_date or datetime.now(APP_TIMEZONE).date()
    records = filter_records_for_day(load_capture_jsonl(capture_path), today)
    text = capture_records_to_text(records)
    result = parse_whatsapp_text(text)
    result.target_date = result.target_date or today
    return sync_daily_parse_result(credentials_path, spreadsheet_id, result, today)
