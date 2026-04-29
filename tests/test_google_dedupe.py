from paster.google_sheets import dedupe_completions
from paster.models import CompletionTicket


def test_dedupe_completions_prefers_serial_number_identifier():
    records = [
        CompletionTicket(account="SFKL17369", serial_number="FHTTc1bd0fef", client_name="Old"),
        CompletionTicket(account="SFKL17369", serial_number="FHTTc1bd0fef", client_name="New"),
    ]

    deduped = dedupe_completions(records)

    assert len(deduped) == 1
    assert deduped[0].client_name == "New"


def test_dedupe_completions_falls_back_to_account_identifier():
    records = [
        CompletionTicket(account="SFKL17369", serial_number=None, client_name="First"),
        CompletionTicket(account="sfkl17369", serial_number=None, client_name="Second"),
    ]

    deduped = dedupe_completions(records)

    assert len(deduped) == 1
    assert deduped[0].client_name == "Second"
