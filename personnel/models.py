"""Domain models for facility personnel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


class PersonnelError(Exception):
    """Base error for the personnel module."""


class DuplicatePersonError(PersonnelError):
    """Raised when a person is registered twice."""


class CheckInError(PersonnelError):
    """Raised when check-in or check-out rules are violated."""


@dataclass(slots=True)
class Person:
    """Base class shared by all personnel types."""

    unique_id: str
    name: str
    contact_info: str
    on_site: bool = field(default=False, init=False)
    checked_in_at: datetime | None = field(default=None, init=False)
    location: str | None = field(default=None, init=False)

    @property
    def person_type(self) -> str:
        return self.__class__.__name__

    def _record_check_in(
        self, *, checked_in_at: datetime | None = None, location: str | None = None
    ) -> None:
        """Apply on-site state after ``PersonnelRegistry`` validated the transition."""
        self.on_site = True
        self.checked_in_at = checked_in_at or datetime.now()
        self.location = location

    def apply_restored_presence(
        self, *, checked_in_at: datetime | None = None, location: str | None = None
    ) -> None:
        """Reapply persisted on-site fields (integration persistence restore only)."""
        self._record_check_in(checked_in_at=checked_in_at, location=location)

    def _record_check_out(self) -> None:
        """Clear on-site state after ``PersonnelRegistry`` validated the transition."""
        self.on_site = False
        self.checked_in_at = None
        self.location = None

    def search_tokens(self) -> tuple[str, ...]:
        return (self.unique_id, self.name, self.contact_info, self.person_type)


@dataclass(slots=True)
class Employee(Person):
    department: str
    role_title: str
    hire_date: date
    assigned_keycard_id: str

    def __post_init__(self) -> None:
        self.validate_hire_date()

    def validate_hire_date(self, reference_date: date | None = None) -> None:
        reference_date = reference_date or date.today()
        if self.hire_date > reference_date:
            raise ValueError("Hire date cannot be in the future.")

    def search_tokens(self) -> tuple[str, ...]:
        return super().search_tokens() + (
            self.department,
            self.role_title,
            self.assigned_keycard_id,
        )


@dataclass(slots=True)
class Visitor(Person):
    host_employee_id: str
    visit_purpose: str
    expected_duration_minutes: int

    def __post_init__(self) -> None:
        if self.expected_duration_minutes <= 0:
            raise ValueError("Expected duration must be a positive number of minutes.")

    def is_overstaying(self, now: datetime | None = None) -> bool:
        if not self.on_site or self.checked_in_at is None:
            return False
        now = now or datetime.now()
        deadline = self.checked_in_at + timedelta(minutes=self.expected_duration_minutes)
        return now > deadline

    def search_tokens(self) -> tuple[str, ...]:
        return super().search_tokens() + (
            self.host_employee_id,
            self.visit_purpose,
        )


@dataclass(slots=True)
class Contractor(Person):
    company_name: str
    contract_start_date: date
    contract_end_date: date
    restricted_areas: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.contract_end_date < self.contract_start_date:
            raise ValueError("Contract end date cannot be earlier than the start date.")

    def is_contract_active(self, on_date: date | None = None) -> bool:
        on_date = on_date or date.today()
        return self.contract_start_date <= on_date <= self.contract_end_date

    def search_tokens(self) -> tuple[str, ...]:
        return super().search_tokens() + (
            self.company_name,
            *self.restricted_areas,
        )
