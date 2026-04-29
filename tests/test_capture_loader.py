from paster.capture_loader import capture_records_to_text


def test_capture_records_to_text_combines_body_and_caption():
    records = [
        {
            "author": "Coach",
            "timestamp": "2026-04-28T05:29:00",
            "body": "SFKL4421 Nyok Mawir 789022235 02-S-FKLN-06",
            "caption": "",
        },
        {
            "author": "Field Tech",
            "timestamp": "2026-04-28T16:11:00",
            "body": "GPON INSTALL\nAccount:SFKL7233",
            "caption": "client name: Tamara Sikipa",
        },
    ]

    text = capture_records_to_text(records)

    assert "Coach | 2026-04-28 05:29:00" in text
    assert "GPON INSTALL" in text
    assert "client name: Tamara Sikipa" in text
