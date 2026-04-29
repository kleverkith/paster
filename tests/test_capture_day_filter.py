from datetime import date

from paster.capture_loader import filter_records_for_day


def test_filter_records_for_day_keeps_only_nairobi_day():
    records = [
        {"timestamp": "2026-04-27T21:00:00.000Z", "body": "midnight exactly should be ignored"},
        {"timestamp": "2026-04-27T21:30:00.000Z", "body": "same local day start"},
        {"timestamp": "2026-04-28T21:10:00.000Z", "body": "next local day"},
    ]

    filtered = filter_records_for_day(records, date(2026, 4, 28))

    assert len(filtered) == 2
    assert filtered[0]["body"] == "midnight exactly should be ignored"
    assert filtered[1]["body"] == "same local day start"
