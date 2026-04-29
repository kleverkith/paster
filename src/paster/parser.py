from __future__ import annotations

import re
from datetime import date, datetime

from .models import AssignmentTicket, CompletionTicket, FieldActivityReport, ParseResult
from .ticket_dedupe import with_deduped_parse_result

ACCOUNT_RE = re.compile(r"\bSFKL\s*\d+\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+?254|0)?(?:1\d{8}|7\d{8})\b")
ROUTE_RE = re.compile(r"\b\d{2}-S-[A-Z0-9-]+\b", re.IGNORECASE)
MAC_RE = re.compile(r"\bFHTTC[A-Z0-9]+\b", re.IGNORECASE)
DATE_PATTERNS = [
    (re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b"), ("%d/%m/%Y", "%d-%m-%Y")),
    (re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2})\b"), ("%d/%m/%y", "%d-%m-%y")),
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), ("%Y-%m-%d",)),
]
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

SUMMARY_KEYWORDS = {
    "Tickets Rescheduled by clients (Give dates)": ("rescheduled by client", "client rescheduled"),
    "Tickets Rescheduled due to weather": ("weather", "rain"),
    "Tickets with route  challenges": ("route challenge", "route issue", "no route", "access route"),
    "Tickets with Management Issues": ("management",),
    "Tickets not Fiber Ready": ("fiber not ready", "not fiber ready", "fibre not ready", "fiber ready: no"),
    "Tickets with client Offline/Unreachable": ("offline", "unreachable", "switched off"),
    "Tickets with client Not interested": ("not interested",),
    "Tickets Not done because of unfreindly clients": ("unfriendly", "hostile client"),
}
ASSIGNMENT_STATUS_PATTERNS = (
    ("not fiber ready", "Not fiber ready"),
    ("newactivation", "NewActivation"),
    ("assigned", "Assigned"),
    ("onhold", "Onhold"),
)
INVENTORY_MARKERS = (
    "assign inventory",
    "attach inventory",
    "inventory",
    "onu",
    "link is up",
    "pushing traffic",
)
NON_TICKET_MARKERS = (
    "bad power",
    "optimize",
    "optimization",
)


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 9 and digits.startswith("7"):
        return "0" + digits
    if len(digits) == 12 and digits.startswith("254"):
        return "0" + digits[3:]
    if len(digits) == 10 and digits.startswith("0"):
        return digits
    return value.strip()


def normalize_account(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", "", value).upper()
    return cleaned or None


def clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = re.sub(r"\s+", " ", line)
    return line.strip(" -:\t")


def normalize_label_line(line: str) -> str:
    cleaned = clean_line(line)
    cleaned = cleaned.replace("*", "").replace('"', "")
    return cleaned


def split_blocks(text: str) -> list[str]:
    blocks = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block.strip()]


def parse_date(text: str) -> date | None:
    for pattern, formats in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1)
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    return None


def extract_value(block: str, labels: tuple[str, ...]) -> str | None:
    lines = [normalize_label_line(line) for line in block.splitlines()]
    for line in lines:
        lowered = line.lower()
        for label in labels:
            prefix = label.lower()
            if lowered.startswith(prefix):
                value = line[len(label) :]
                value = value.lstrip(":;\"' ").strip()
                return value or None
    return None


def extract_number(value: str | None) -> float | None:
    if not value:
        return None
    match = NUMBER_RE.search(value)
    if not match:
        return None
    return float(match.group(0))


def normalize_length(value: str | None) -> str | int | None:
    if not value:
        return None
    match = NUMBER_RE.search(value)
    if not match:
        return value.strip()
    raw_number = match.group(0)
    try:
        number = int(float(raw_number))
    except ValueError:
        return value.strip()
    if "m" in value.lower():
        return f"{number}m"
    return number


def infer_summary_counts(text: str, assignments: list[AssignmentTicket], completions: list[CompletionTicket]) -> dict[str, int]:
    lowered = text.lower()
    counts = {
        "Assigned Tickets": len(assignments),
        "Tickets done": len(completions),
        "Teams Available": 0,
        "Challenges": 0,
    }
    for label, keywords in SUMMARY_KEYWORDS.items():
        counts[label] = sum(lowered.count(keyword) for keyword in keywords)
    counts["Challenges"] = sum(counts[label] for label in SUMMARY_KEYWORDS)
    return counts


def parse_field_activity_block(block: str) -> FieldActivityReport | None:
    contractor = extract_value(block, ("Contractor",))
    location = extract_value(block, ("Location",))
    scope = extract_value(block, ("Scope", "Scipe"))
    pob = extract_number(extract_value(block, ("POB",)))
    topic = extract_value(block, ("TOPIC", "Topic"))
    if not any([contractor, location, scope, pob is not None, topic]):
        return None
    return FieldActivityReport(
        contractor=contractor,
        location=location,
        scope=scope,
        pob=int(pob) if pob is not None else None,
        topic=topic,
        raw_text=block,
    )


def is_completion_continuation_block(block: str) -> bool:
    labels = (
        "date",
        "account",
        "address",
        "house type",
        "client name",
        "client contact",
        "fiber home mac",
        "serial number",
        "signal at fat",
        "signal at atb",
        "materials",
        "indoor drop cable",
        "out door drop cable",
        "outdoor cable",
        "sleeves",
        "trunking",
        "atb",
        "patch cord",
        "patch",
        "username",
        "password",
        "client present",
    )
    for raw_line in block.splitlines():
        line = normalize_label_line(raw_line).lower()
        if any(line.startswith(label) for label in labels):
            return True
    return False


def normalize_assignment_segment(value: str) -> str | None:
    cleaned = clean_line(value)
    return cleaned or None


def strip_route_codes(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = ROUTE_RE.sub("", value)
    cleaned = clean_line(cleaned)
    return cleaned or None


def find_assignment_status(value: str) -> tuple[str | None, int | None, int | None]:
    lowered = value.lower()
    for raw_status, normalized_status in ASSIGNMENT_STATUS_PATTERNS:
        index = lowered.find(raw_status)
        if index >= 0:
            return normalized_status, index, index + len(raw_status)
    return None, None, None


def split_assignment_tail(value: str) -> tuple[str | None, str | None, str | None]:
    cleaned = clean_line(value)
    if not cleaned:
        return None, None, None

    status, status_start, status_end = find_assignment_status(cleaned)
    if status_start is None or status_end is None:
        return normalize_assignment_segment(cleaned), None, None

    before_status = cleaned[:status_start].strip(" -")
    after_status = cleaned[status_end:].strip(" -")

    location = normalize_assignment_segment(before_status)
    remarks = strip_route_codes(after_status)

    if before_status and "-" in before_status:
        left, right = before_status.rsplit("-", 1)
        left_clean = normalize_assignment_segment(left)
        right_clean = normalize_assignment_segment(right)
        if left_clean and right_clean:
            location = left_clean
            remarks = strip_route_codes(" - ".join(part for part in [right_clean, remarks] if part))

    return location, status, remarks


def split_assignment_status_segment(value: str | None) -> tuple[str | None, str | None]:
    cleaned = normalize_assignment_segment(value or "")
    if not cleaned:
        return None, None
    status, status_start, status_end = find_assignment_status(cleaned)
    if status_start is None or status_end is None:
        return None, strip_route_codes(cleaned)
    remainder = strip_route_codes(cleaned[status_end:].strip(" -"))
    return status, remainder


def infer_assignment_tech(block: str) -> str | None:
    mention_matches = re.findall(r"@(\d{6,})", block)
    if mention_matches:
        return f"@{mention_matches[-1]}"
    team_match = re.search(r"\bteam\s+([A-Za-z][A-Za-z .'-]+)", block, re.IGNORECASE)
    if team_match:
        return clean_line(team_match.group(1))
    return None


def parse_completion_remark_update(block: str) -> tuple[str, str] | None:
    lines = [clean_line(line) for line in block.splitlines() if clean_line(line)]
    if not lines:
        return None

    for line in reversed(lines):
        account_match = ACCOUNT_RE.search(line)
        if not account_match:
            continue
        lowered = normalize_label_line(line).lower()
        if "bad power" not in lowered or not any(marker in lowered for marker in NON_TICKET_MARKERS[1:]):
            continue

        account = normalize_account(account_match.group(0))
        remainder = line[account_match.end() :]
        remark = clean_line(remainder.replace("*", " ").replace("✅", " "))
        if account and remark:
            return account, remark
    return None


def parse_assignment_line(line: str, tech: str | None = None) -> AssignmentTicket | None:
    first_line = clean_line(line)
    account_match = ACCOUNT_RE.search(first_line)
    if not account_match:
        return None
    lowered = normalize_label_line(first_line).lower()
    if "account:" in lowered:
        return None
    if any(marker in lowered for marker in INVENTORY_MARKERS):
        return None
    if "bad power" in lowered and any(marker in lowered for marker in NON_TICKET_MARKERS[1:]):
        return None

    segments = [segment.strip() for segment in re.split(r"\t+", line) if segment.strip()]

    phone_match = PHONE_RE.search(first_line)
    route_matches = list(ROUTE_RE.finditer(first_line))
    route_match = None
    if phone_match:
        route_match = next((match for match in route_matches if match.start() > phone_match.end()), None)
    if not route_match and route_matches:
        route_match = route_matches[0]

    account = account_match.group(0).upper()
    account = normalize_account(account)
    client_name = None
    if phone_match:
        between = first_line[account_match.end() : phone_match.start()]
        client_name = clean_line(between)
    elif route_match:
        between = first_line[account_match.end() : route_match.start()]
        client_name = clean_line(between)
    else:
        between = first_line[account_match.end() :]
        client_name = clean_line(between)

    if not phone_match and not route_match and len(first_line.split()) <= 2:
        return None

    location = None
    status = None
    remarks = None
    if phone_match:
        contact_segment_tail = None
        if len(segments) >= 3:
            contact_segment = segments[2]
            contact_segment_match = PHONE_RE.search(contact_segment)
            if contact_segment_match:
                contact_segment_tail = clean_line(contact_segment[contact_segment_match.end() :])

        if len(segments) >= 4 or contact_segment_tail:
            tail_parts: list[str] = []
            if contact_segment_tail:
                tail_parts.append(contact_segment_tail)
            tail_parts.extend(segments[3:])
            route_from_segment = None
            for segment in [segments[2], *tail_parts]:
                route_segment_match = ROUTE_RE.search(segment)
                if route_segment_match:
                    route_from_segment = route_segment_match.group(0).upper()
                    break
            if route_from_segment and not route_match:
                route_match = re.search(re.escape(route_from_segment), first_line, re.IGNORECASE)

            if len(tail_parts) == 1:
                location, status, remarks = split_assignment_tail(tail_parts[0])
            elif len(tail_parts) >= 2:
                parsed_tail_parts = tail_parts[:]
                if ROUTE_RE.fullmatch(parsed_tail_parts[0]):
                    if not route_match:
                        route_match = re.search(re.escape(parsed_tail_parts[0]), first_line, re.IGNORECASE)
                    parsed_tail_parts = parsed_tail_parts[1:]
                if not parsed_tail_parts:
                    parsed_tail_parts = tail_parts[:1]

                location, status, inline_remarks = split_assignment_tail(parsed_tail_parts[0])
                trailing_parts = [normalize_assignment_segment(part) for part in parsed_tail_parts[1:]]
                trailing_parts = [part for part in trailing_parts if part]
                if status is None and trailing_parts:
                    extracted_status, remainder = split_assignment_status_segment(trailing_parts[0])
                    if extracted_status:
                        status = extracted_status
                        trailing_parts = ([remainder] if remainder else []) + trailing_parts[1:]
                remarks = strip_route_codes(
                    " ".join(part for part in [inline_remarks, *trailing_parts] if part)
                )
        elif route_match and route_match.start() > phone_match.end():
            before_route = clean_line(first_line[phone_match.end() : route_match.start()])
            after_route = clean_line(first_line[route_match.end() :])
            location, status, remarks = split_assignment_tail(before_route or after_route)
        elif route_match:
            location, status, remarks = split_assignment_tail(first_line[route_match.end() :])
        else:
            tail = first_line[phone_match.end() :].strip()
            location, status, remarks = split_assignment_tail(tail)
    elif route_match:
        location, status, remarks = split_assignment_tail(first_line[route_match.end() :])

    return AssignmentTicket(
        account=account,
        client_name=client_name or None,
        contact=normalize_phone(phone_match.group(0)) if phone_match else None,
        route_code=route_match.group(0).upper() if route_match else None,
        location=location,
        tech=tech,
        status=status,
        remarks=remarks,
        raw_text=first_line,
    )


def enrich_completions_from_assignments(
    completions: list[CompletionTicket],
    assignments: list[AssignmentTicket],
    remark_updates: dict[str, str] | None = None,
) -> list[CompletionTicket]:
    assignment_by_account = {
        assignment.account: assignment for assignment in assignments if assignment.account
    }
    remark_updates = remark_updates or {}
    enriched: list[CompletionTicket] = []
    for completion in completions:
        match = assignment_by_account.get(completion.account) if completion.account else None
        if not match:
            if completion.account and completion.account in remark_updates:
                completion.remarks = remark_updates[completion.account]
            enriched.append(completion)
            continue
        completion.client_name = completion.client_name or match.client_name
        completion.contact = completion.contact or match.contact
        completion.location = completion.location or match.remarks or match.location
        completion.tech = completion.tech or match.tech
        if completion.account and completion.account in remark_updates:
            completion.remarks = remark_updates[completion.account]
        enriched.append(completion)
    return enriched


def parse_assignment_block(block: str, fallback_tech: str | None = None) -> list[AssignmentTicket]:
    assignments: list[AssignmentTicket] = []
    block_tech = infer_assignment_tech(block) or fallback_tech
    for raw_line in block.splitlines():
        assignment = parse_assignment_line(raw_line, tech=block_tech)
        if assignment:
            assignments.append(assignment)
    return assignments


def parse_completion_block(block: str) -> CompletionTicket | None:
    lowered_block = block.lower()
    completion_signal_count = sum(
        1
        for marker in ("account", "address", "client name", "fiber home", "signal at fat", "signal at atb")
        if marker in lowered_block
    )
    if "gpon install" not in lowered_block and "account:" not in lowered_block and completion_signal_count < 3:
        return None

    account_match = ACCOUNT_RE.search(block)
    serial_match = MAC_RE.search(block)
    if not account_match and not serial_match and len(block.splitlines()) <= 2:
        return None
    if account_match and not serial_match and completion_signal_count < 3:
        return None

    raw_date = extract_value(block, ("Date",))
    target_date = parse_date(raw_date or block)
    client_name = extract_value(block, ("client name", "name"))
    location = extract_value(block, ("ADDRESS", "Address", "location"))
    contact = normalize_phone(extract_value(block, ("client contact", "contact")))
    signal_fat = extract_number(extract_value(block, ("Signal At FAT", "signal at fat")))
    signal_atb = extract_number(extract_value(block, ("Signal At ATB", "signal at atb")))
    indoor = normalize_length(extract_value(block, ("Materials indoor drop cable", "indoor drop cable")))
    outdoor = normalize_length(
        extract_value(
            block,
            (
                "Materials outdoor drop cable",
                "Materials out door drop cable",
                "out door drop cable",
                "outdoor cable",
            ),
        )
    )
    atb = extract_number(extract_value(block, ("ATB",)))
    patch = extract_number(extract_value(block, ("PATCH CORD", "PATCH")))

    tech = None
    mention_matches = re.findall(r"@~?([A-Za-z][A-Za-z ]+)", block)
    if mention_matches:
        tech = clean_line(mention_matches[-1])
    else:
        tail = clean_line(block.splitlines()[-1])
        if len(tail.split()) <= 4 and "@" not in tail and ":" not in tail:
            tech = tail

    remarks = "Connected"
    lowered = block.lower()
    for label, keywords in SUMMARY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            remarks = label
            break
    if "optimized" in lowered:
        remarks = "Connected - needs optimization"

    close_datetime = raw_date
    if target_date and not close_datetime:
        close_datetime = f"{target_date.day}/{target_date.month}/{target_date.year}"

    return CompletionTicket(
        account=normalize_account(account_match.group(0)) if account_match else None,
        client_name=client_name,
        location=location,
        contact=contact,
        close_datetime=close_datetime,
        serial_number=serial_match.group(0).upper() if serial_match else extract_value(block, ("fiber home mac", "serial number")),
        indoor_cable=indoor,
        outdoor_cable=outdoor,
        atb=int(atb) if atb is not None else None,
        patch=int(patch) if patch is not None else None,
        power_level=abs(signal_atb) if signal_atb is not None else None,
        power_fat=abs(signal_fat) if signal_fat is not None else None,
        tech=tech,
        remarks=remarks,
        raw_text=block,
    )


def parse_whatsapp_text(text: str) -> ParseResult:
    blocks = split_blocks(text)
    assignments: list[AssignmentTicket] = []
    completions: list[CompletionTicket] = []
    field_activity_reports: list[FieldActivityReport] = []
    completion_remark_updates: dict[str, str] = {}
    target_date = parse_date(text)
    current_assignment_tech: str | None = None

    index = 0
    while index < len(blocks):
        block = blocks[index]
        inferred_block_tech = infer_assignment_tech(block)
        if inferred_block_tech:
            current_assignment_tech = inferred_block_tech
        if "gpon install" in block.lower():
            while index + 1 < len(blocks) and is_completion_continuation_block(blocks[index + 1]):
                block = f"{block}\n{blocks[index + 1]}"
                index += 1

        completion = parse_completion_block(block)
        if completion:
            completions.append(completion)
            if not target_date:
                target_date = parse_date(block)
        block_assignments = parse_assignment_block(block, fallback_tech=current_assignment_tech)
        if block_assignments:
            assignments.extend(block_assignments)
            if not target_date:
                target_date = parse_date(block)
        field_activity_report = parse_field_activity_block(block)
        if field_activity_report:
            field_activity_reports.append(field_activity_report)
            if not target_date:
                target_date = parse_date(block)
        completion_remark_update = parse_completion_remark_update(block)
        if completion_remark_update:
            account, remark = completion_remark_update
            completion_remark_updates[account] = remark
            if not target_date:
                target_date = parse_date(block)
        index += 1

    result = ParseResult(
        assignments=assignments,
        completions=enrich_completions_from_assignments(completions, assignments, completion_remark_updates),
        field_activity_reports=field_activity_reports,
        summary_counts=infer_summary_counts(text, assignments, completions),
        target_date=target_date,
    )
    return with_deduped_parse_result(result)
