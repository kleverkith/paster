from __future__ import annotations

from .models import AssignmentTicket, CompletionTicket


ACTIONED_COLUMNS = [
    "ACC",
    "NAME",
    "CONTACT",
    "ROUTE",
    "LOCATION",
    "TECH",
    "ASSIGNMENT STATUS",
    "ASSIGNMENT REMARKS",
    "CLOSE DATE/TIME",
    "COMPLETION REMARKS",
]


def assignment_match_key(record: AssignmentTicket) -> str | None:
    if record.account:
        return f"ACC:{record.account.strip().upper()}"
    if record.contact:
        return f"CONTACT:{record.contact.strip()}"
    return None


def completion_match_key(record: CompletionTicket) -> str | None:
    if record.account:
        return f"ACC:{record.account.strip().upper()}"
    if record.contact:
        return f"CONTACT:{record.contact.strip()}"
    return None


def build_ticket_action_views(
    assignments: list[AssignmentTicket],
    completions: list[CompletionTicket],
) -> tuple[list[dict[str, str | None]], list[dict[str, str | None]]]:
    completion_by_key = {
        key: record
        for record in completions
        if (key := completion_match_key(record))
    }

    actioned: list[dict[str, str | None]] = []
    not_actioned: list[dict[str, str | None]] = []

    for assignment in assignments:
        key = assignment_match_key(assignment)
        completion = completion_by_key.get(key) if key else None
        row = {
            "ACC": assignment.account,
            "NAME": assignment.client_name or (completion.client_name if completion else None),
            "CONTACT": assignment.contact or (completion.contact if completion else None),
            "ROUTE": assignment.route_code,
            "LOCATION": assignment.location or (completion.location if completion else None),
            "TECH": assignment.tech or (completion.tech if completion else None),
            "ASSIGNMENT STATUS": assignment.status,
            "ASSIGNMENT REMARKS": assignment.remarks,
            "CLOSE DATE/TIME": completion.close_datetime if completion else None,
            "COMPLETION REMARKS": completion.remarks if completion else None,
        }
        if completion:
            actioned.append(row)
        else:
            not_actioned.append(row)

    return actioned, not_actioned
