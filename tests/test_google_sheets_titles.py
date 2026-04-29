from datetime import date

from paster.google_sheets import build_assignments_title, build_connections_title, build_raw_text_title, build_summary_title


def test_google_sheet_titles_are_daily():
    target = date(2026, 4, 28)

    assert build_connections_title(target) == "Connections 2026-04-28"
    assert build_assignments_title(target) == "Assignments 2026-04-28"
    assert build_raw_text_title(target) == "Raw Text 2026-04-28"
    assert build_summary_title(target) == "Summary 2026-04-28"
