from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class AssignmentTicket:
    account: str | None = None
    client_name: str | None = None
    contact: str | None = None
    route_code: str | None = None
    location: str | None = None
    tech: str | None = None
    status: str | None = None
    remarks: str | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompletionTicket:
    account: str | None = None
    client_name: str | None = None
    location: str | None = None
    contact: str | None = None
    close_datetime: str | None = None
    serial_number: str | None = None
    onu: int = 1
    indoor_cable: str | int | None = None
    outdoor_cable: str | int | None = None
    atb: int | None = None
    patch: int | None = None
    power_level: float | None = None
    power_fat: float | None = None
    tech: str | None = None
    remarks: str = "Connected"
    raw_text: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "ACC": self.account,
            "NAME": self.client_name,
            "LOCATION": self.location,
            "CONTACT": self.contact,
            "CLOSE DATE/TIME": self.close_datetime,
            "SN": self.serial_number,
            "ONU": self.onu,
            "INDOOR CABLE": self.indoor_cable,
            "OUTDOOR CABLE": self.outdoor_cable,
            "ATB": self.atb,
            "PATCH": self.patch,
            "POWER LEVEL": self.power_level,
            "POWER FAT": self.power_fat,
            "TECH": self.tech,
            "REMARKS": self.remarks,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FieldActivityReport:
    contractor: str | None = None
    location: str | None = None
    scope: str | None = None
    pob: int | None = None
    topic: str | None = None
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    assignments: list[AssignmentTicket] = field(default_factory=list)
    completions: list[CompletionTicket] = field(default_factory=list)
    field_activity_reports: list[FieldActivityReport] = field(default_factory=list)
    summary_counts: dict[str, int] = field(default_factory=dict)
    target_date: date | None = None
