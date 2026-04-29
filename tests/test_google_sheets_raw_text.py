from paster.google_sheets import raw_text_rows
from paster.models import AssignmentTicket, CompletionTicket, FieldActivityReport, ParseResult


def test_raw_text_rows_are_separate_from_structured_tabs():
    result = ParseResult(
        assignments=[
            AssignmentTicket(account="SFKL1", raw_text="assignment raw"),
        ],
        completions=[
            CompletionTicket(account="SFKL2", raw_text="completion raw"),
        ],
        field_activity_reports=[
            FieldActivityReport(location="kileleshwa", raw_text="field raw"),
        ],
    )

    rows = raw_text_rows(result)

    assert rows[0] == ["TYPE", "IDENTIFIER", "RAW TEXT"]
    assert rows[1] == ["Assignment", "SFKL1", "assignment raw"]
    assert rows[2] == ["Completion", "SFKL2", "completion raw"]
    assert rows[3] == ["Field Activity", "kileleshwa", "field raw"]
