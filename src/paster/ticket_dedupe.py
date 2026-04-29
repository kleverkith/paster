from __future__ import annotations

from .models import AssignmentTicket, CompletionTicket, FieldActivityReport, ParseResult


def normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip().upper()
    return cleaned or None


def assignment_identifier(record: AssignmentTicket) -> str:
    account = normalize_identifier(record.account)
    if account:
        return f"ACC:{account}"
    contact = normalize_identifier(record.contact)
    if contact:
        return f"CONTACT:{contact}"
    name = normalize_identifier(record.client_name)
    location = normalize_identifier(record.location)
    route = normalize_identifier(record.route_code)
    fallback = "|".join(part for part in [name, contact, route, location] if part)
    return f"FALLBACK:{fallback or record.raw_text.strip().upper()}"


def completion_identifier(record: CompletionTicket) -> str:
    serial = normalize_identifier(record.serial_number)
    if serial:
        return f"SN:{serial}"
    account = normalize_identifier(record.account)
    if account:
        return f"ACC:{account}"
    contact = normalize_identifier(record.contact)
    name = normalize_identifier(record.client_name)
    location = normalize_identifier(record.location)
    fallback = "|".join(part for part in [name, contact, location] if part)
    return f"FALLBACK:{fallback or record.raw_text.strip().upper()}"


def dedupe_assignments(records: list[AssignmentTicket]) -> list[AssignmentTicket]:
    deduped: dict[str, AssignmentTicket] = {}
    for record in records:
        deduped[assignment_identifier(record)] = record
    return list(deduped.values())


def dedupe_completions(records: list[CompletionTicket]) -> list[CompletionTicket]:
    deduped: dict[str, CompletionTicket] = {}
    for record in records:
        deduped[completion_identifier(record)] = record
    return list(deduped.values())


def field_activity_identifier(record: FieldActivityReport) -> str:
    contractor = normalize_identifier(record.contractor)
    location = normalize_identifier(record.location)
    scope = normalize_identifier(record.scope)
    pob = normalize_identifier(str(record.pob) if record.pob is not None else None)
    topic = normalize_identifier(record.topic)
    fallback = "|".join(part for part in [contractor, location, scope, pob, topic] if part)
    return f"FIELD:{fallback or record.raw_text.strip().upper()}"


def dedupe_field_activity_reports(records: list[FieldActivityReport]) -> list[FieldActivityReport]:
    deduped: dict[str, FieldActivityReport] = {}
    for record in records:
        deduped[field_activity_identifier(record)] = record
    return list(deduped.values())


def with_deduped_parse_result(result: ParseResult) -> ParseResult:
    assignments = dedupe_assignments(result.assignments)
    completions = dedupe_completions(result.completions)
    field_activity_reports = dedupe_field_activity_reports(result.field_activity_reports)
    summary_counts = dict(result.summary_counts)
    summary_counts["Assigned Tickets"] = len(assignments)
    summary_counts["Tickets done"] = len(completions)
    summary_counts["Teams Available"] = len(field_activity_reports)
    return ParseResult(
        assignments=assignments,
        completions=completions,
        field_activity_reports=field_activity_reports,
        summary_counts=summary_counts,
        target_date=result.target_date,
    )
