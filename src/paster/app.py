from __future__ import annotations

import sys
from io import BytesIO
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from paster.action_tracker import build_ticket_action_views
from paster.capture_loader import APP_TIMEZONE, capture_records_to_text, filter_records_for_day, load_capture_jsonl
from paster.excel_writer import append_connections, create_parsed_report_workbook, update_summary, write_assignment_sheet
from paster.google_sheets import sync_daily_parse_result
from paster.local_config import load_local_config, save_local_config
from paster.ocr import extract_text_with_tesseract
from paster.parser import parse_whatsapp_text
from paster.watcher_status import load_status

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONNECTION_TEMPLATE = Path.home() / "Downloads" / "sample.xlsx"
DEFAULT_SUMMARY_TEMPLATE = Path.home() / "Downloads" / "Mon,,Wed,Friday Reports.xlsx"
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
SYNC_STATUS_FILE = DATA_DIR / "google-sync-status.json"
LOCAL_CONFIG_FILE = DATA_DIR / "app-config.json"


def uploaded_images_to_temp(files) -> list[Path]:
    temp_dir = OUTPUT_DIR / "_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for item in files:
        target = temp_dir / item.name
        target.write_bytes(item.getbuffer())
        paths.append(target)
    return paths


def suggest_output_name(prefix: str, extension: str, target_day: date) -> str:
    stamp = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}-{target_day.isoformat()}_{stamp}.{extension}"


def format_watcher_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        local_time = datetime.fromisoformat(normalized).astimezone(APP_TIMEZONE)
    except ValueError:
        return None
    return local_time.strftime("%Y-%m-%d %H:%M:%S")


def dataframe_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    export_df = df.copy()
    if isinstance(export_df.index, pd.RangeIndex):
        export_df.index = range(1, len(export_df) + 1)
        export_df.index.name = "No."
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name=sheet_name)
    return output.getvalue()


def main() -> None:
    st.set_page_config(page_title="Paster", layout="wide")
    st.title("Paster")
    st.caption("Parse WhatsApp work updates into Excel and optional Google Sheets.")
    st.session_state.setdefault("whatsapp_text", "")
    today_nairobi = datetime.now(APP_TIMEZONE).date()
    app_config = load_local_config(LOCAL_CONFIG_FILE)

    with st.sidebar:
        st.subheader("Templates")
        connection_template = st.text_input("Connections template", str(DEFAULT_CONNECTION_TEMPLATE))
        summary_template = st.text_input("Summary template", str(DEFAULT_SUMMARY_TEMPLATE))
        output_dir = Path(st.text_input("Output folder", str(OUTPUT_DIR)))
        target_sheet_name = st.text_input("Connections sheet name", "April Connections")
        summary_sheet_name = st.text_input("Summary sheet name", "Sheet1")
        assignment_sheet_name = st.text_input("Assignment sheet name", "Assignments")

        st.subheader("OCR")
        use_ocr = st.checkbox("OCR uploaded images with Tesseract")

        st.subheader("Watcher")
        capture_file = st.text_input("Capture JSONL", str(DATA_DIR / "messages.jsonl"))
        status_file = st.text_input("Watcher status file", str(DATA_DIR / "status.json"))
        watcher_status = load_status(status_file)
        st.caption("Daily capture window: 00:00 to 23:59 Africa/Nairobi")
        if watcher_status:
            st.json(watcher_status)
            last_captured = format_watcher_timestamp(watcher_status.get("lastMessageAt"))
            if last_captured:
                st.caption(f"Latest captured message: {last_captured} Africa/Nairobi")
        if not st.session_state.get("whatsapp_text"):
            records = filter_records_for_day(load_capture_jsonl(capture_file), today_nairobi)
            if records:
                st.session_state["whatsapp_text"] = capture_records_to_text(records)

        st.subheader("Google Sheets")
        push_to_google = st.checkbox("Also sync today's parsed data to Google Sheets")
        gs_creds = st.text_input("Credentials JSON path", app_config.get("google_credentials_path", ""))
        gs_spreadsheet_id = st.text_input("Spreadsheet ID", app_config.get("google_spreadsheet_id", ""))
        sync_status = load_status(SYNC_STATUS_FILE)
        if sync_status:
            st.json(sync_status)
        if gs_creds and gs_spreadsheet_id:
            save_local_config(
                LOCAL_CONFIG_FILE,
                {
                    "google_credentials_path": gs_creds,
                    "google_spreadsheet_id": gs_spreadsheet_id,
                },
            )

    left, right = st.columns([3, 2])
    with left:
        if st.button("Reload Latest Scraped Group Messages"):
            records = filter_records_for_day(load_capture_jsonl(capture_file), today_nairobi)
            combined_capture = capture_records_to_text(records)
            st.session_state["whatsapp_text"] = combined_capture
        st.caption("The text box keeps its current contents. Click reload to pull the newest watcher capture.")
        whatsapp_text = st.text_area(
            "WhatsApp text",
            key="whatsapp_text",
            height=420,
            placeholder="Paste copied WhatsApp messages or exported chat text here.",
        )
        images = st.file_uploader(
            "Optional screenshots",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )
    with right:
        override_date = st.date_input("Report date", value=today_nairobi)

    if st.button("Parse Messages", type="primary"):
        combined_text = whatsapp_text
        if use_ocr and images:
            try:
                image_paths = uploaded_images_to_temp(images)
                combined_text = f"{combined_text}\n\n{extract_text_with_tesseract(image_paths)}".strip()
            except Exception as exc:
                st.error(str(exc))
                st.stop()

        result = parse_whatsapp_text(combined_text)
        target_date = result.target_date or override_date
        st.session_state["parse_text"] = combined_text
        st.session_state["result"] = result
        st.session_state["target_date"] = target_date

    result = st.session_state.get("result")
    if result:
        assignments = getattr(result, "assignments", [])
        field_activity_reports = getattr(result, "field_activity_reports", [])
        completions = getattr(result, "completions", [])
        summary_counts = getattr(result, "summary_counts", {})
        actioned_tickets, not_actioned_tickets = build_ticket_action_views(assignments, completions)

        st.subheader("Parsed Assignments")
        assignments_df = pd.DataFrame([item.to_dict() for item in assignments])
        st.dataframe(assignments_df, use_container_width=True)
        st.download_button(
            "Download Parsed Assignments (.xlsx)",
            data=dataframe_to_xlsx_bytes(assignments_df, "Parsed Assignments"),
            file_name=suggest_output_name("parsed-assignments", "xlsx", st.session_state["target_date"]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if field_activity_reports:
            st.subheader("Parsed Field Activity")
            field_activity_df = pd.DataFrame([item.to_dict() for item in field_activity_reports])
            st.dataframe(field_activity_df, use_container_width=True)
            st.download_button(
                "Download Parsed Field Activity (.xlsx)",
                data=dataframe_to_xlsx_bytes(field_activity_df, "Parsed Field Activity"),
                file_name=suggest_output_name("parsed-field-activity", "xlsx", st.session_state["target_date"]),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.subheader("Parsed Completions")
        completions_df = pd.DataFrame([item.to_dict() for item in completions])
        st.dataframe(completions_df, use_container_width=True)
        st.download_button(
            "Download Parsed Completions (.xlsx)",
            data=dataframe_to_xlsx_bytes(completions_df, "Parsed Completions"),
            file_name=suggest_output_name("parsed-completions", "xlsx", st.session_state["target_date"]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.subheader("Actioned Tickets")
        actioned_df = pd.DataFrame(actioned_tickets)
        st.dataframe(actioned_df, use_container_width=True)
        st.download_button(
            "Download Actioned Tickets (.xlsx)",
            data=dataframe_to_xlsx_bytes(actioned_df, "Actioned Tickets"),
            file_name=suggest_output_name("actioned-tickets", "xlsx", st.session_state["target_date"]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.subheader("Not Actioned Tickets")
        not_actioned_df = pd.DataFrame(not_actioned_tickets)
        st.dataframe(not_actioned_df, use_container_width=True)
        st.download_button(
            "Download Not Actioned Tickets (.xlsx)",
            data=dataframe_to_xlsx_bytes(not_actioned_df, "Not Actioned Tickets"),
            file_name=suggest_output_name("not-actioned-tickets", "xlsx", st.session_state["target_date"]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.subheader("Summary Counts")
        summary_df = pd.DataFrame(
            [
                {"Item": key, "Count": value}
                for key, value in {
                    **summary_counts,
                    "Actioned Tickets": len(actioned_tickets),
                    "Not Actioned Tickets": len(not_actioned_tickets),
                }.items()
            ]
        )
        st.dataframe(summary_df, use_container_width=True)
        st.download_button(
            "Download Summary Counts (.xlsx)",
            data=dataframe_to_xlsx_bytes(summary_df, "Summary Counts"),
            file_name=suggest_output_name("summary-counts", "xlsx", st.session_state["target_date"]),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        connections_output = output_dir / suggest_output_name("connections-output", "xlsx", st.session_state["target_date"])
        summary_output = output_dir / suggest_output_name("summary-output", "xlsx", st.session_state["target_date"])
        parsed_report_output = output_dir / suggest_output_name("parsed-report", "xlsx", st.session_state["target_date"])

        if st.button("Generate Excel Files"):
            try:
                append_connections(
                    template_path=connection_template,
                    output_path=connections_output,
                    records=completions,
                    sheet_name=target_sheet_name,
                )
                write_assignment_sheet(
                    workbook_path=connections_output,
                    records=assignments,
                    sheet_name=assignment_sheet_name,
                )
                update_summary(
                    template_path=summary_template,
                    output_path=summary_output,
                    summary_counts=summary_counts,
                    target_date=st.session_state["target_date"],
                    sheet_name=summary_sheet_name,
                )
                create_parsed_report_workbook(
                    output_path=parsed_report_output,
                    assignments=assignments,
                    field_activity_reports=field_activity_reports,
                    completions=completions,
                    summary_counts=summary_counts,
                )
            except Exception as exc:
                st.error(f"Excel generation failed: {exc}")
                st.stop()

            st.success("Excel files generated.")
            st.write(f"Connections workbook: `{connections_output}`")
            st.write(f"Assignments sheet: `{assignment_sheet_name}`")
            st.write(f"Summary workbook: `{summary_output}`")
            st.write(f"Parsed report workbook: `{parsed_report_output}`")

            if push_to_google and gs_creds and gs_spreadsheet_id:
                try:
                    sync_info = sync_daily_parse_result(
                        gs_creds,
                        gs_spreadsheet_id,
                        result,
                        st.session_state["target_date"],
                    )
                    st.success("Google Sheets updated.")
                    st.write(f"Spreadsheet: {sync_info['spreadsheet_url']}")
                    st.write(f"Connections tab: `{sync_info['connections_sheet']}`")
                    st.write(f"Assignments tab: `{sync_info['assignments_sheet']}`")
                    st.write(f"Raw text tab: `{sync_info['raw_text_sheet']}`")
                    st.write(f"Summary tab: `{sync_info['summary_sheet']}`")
                except Exception as exc:
                    st.warning(f"Google Sheets update failed: {exc}")

        if gs_creds and gs_spreadsheet_id and st.button("Sync Today's Data To Google Sheets Now"):
            try:
                sync_info = sync_daily_parse_result(
                    gs_creds,
                    gs_spreadsheet_id,
                    result,
                    st.session_state["target_date"],
                )
                st.success("Today's data synced to Google Sheets.")
                st.write(f"Spreadsheet: {sync_info['spreadsheet_url']}")
                st.write(f"Connections tab: `{sync_info['connections_sheet']}`")
                st.write(f"Assignments tab: `{sync_info['assignments_sheet']}`")
                st.write(f"Raw text tab: `{sync_info['raw_text_sheet']}`")
                st.write(f"Summary tab: `{sync_info['summary_sheet']}`")
                realtime_command = (
                    f'python -m paster.realtime_sync --credentials "{gs_creds}" '
                    f'--spreadsheet-id "{gs_spreadsheet_id}" '
                    f'--capture "{capture_file}" '
                    f'--interval-seconds 60 '
                    f'--status-file "{SYNC_STATUS_FILE}"'
                )
                st.code(realtime_command, language="powershell")
            except Exception as exc:
                st.warning(f"Google Sheets sync failed: {exc}")

        with st.expander("Combined text used for parsing"):
            st.text(st.session_state.get("parse_text", ""))


if __name__ == "__main__":
    main()
