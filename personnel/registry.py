"""Registry and reporting logic for the personnel app."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from .models import CheckInError, Contractor, DuplicatePersonError, Employee, Person, Visitor


class PersonnelRegistry:
    """Tracks all registered people and the live on-site roster."""

    def __init__(self) -> None:
        self._directory: dict[str, Person] = {}
        self._on_site_roster: dict[str, Person] = {}

    def register(self, person: Person) -> Person:
        if person.unique_id in self._directory:
            raise DuplicatePersonError(f"{person.unique_id} is already registered.")
        self._directory[person.unique_id] = person
        return person

    def lookup(self, unique_id: str) -> Person | None:
        return self._directory.get(unique_id)

    def search(self, query: str) -> list[Person]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches = []
        for person in self._directory.values():
            if any(needle in token.lower() for token in person.search_tokens()):
                matches.append(person)
        return self._sort_people(matches)

    def check_in(
        self,
        unique_id: str,
        *,
        location: str | None = None,
        checked_in_at: datetime | None = None,
    ) -> Person:
        person = self._require_registered_person(unique_id)
        if person.on_site or unique_id in self._on_site_roster:
            raise CheckInError(f"{unique_id} is already on-site.")

        self._validate_check_in(person, checked_in_at=checked_in_at)

        person._record_check_in(checked_in_at=checked_in_at, location=location)
        self._on_site_roster[unique_id] = person
        return person

    def check_out(self, unique_id: str) -> list[str]:
        person = self._require_registered_person(unique_id)
        if not person.on_site or unique_id not in self._on_site_roster:
            raise CheckInError(f"{unique_id} is not currently on-site.")

        warnings: list[str] = []
        if isinstance(person, Employee):
            warnings = self._host_departure_warnings(person.unique_id)

        person._record_check_out()
        del self._on_site_roster[unique_id]
        return warnings

    def who_is_on_site(self) -> list[Person]:
        return self._sort_people(self._on_site_roster.values())

    def iter_people_sorted_by_id(self) -> list[Person]:
        """All registered people sorted by ``unique_id`` (stable export order)."""
        return sorted(self._directory.values(), key=lambda person: person.unique_id)

    def restore_onsite_snapshot(
        self,
        unique_id: str,
        *,
        checked_in_at: datetime,
        location: str | None = None,
    ) -> None:
        """Reapply persisted on-site roster (integration persistence restore only)."""
        person = self.lookup(unique_id)
        if person is None:
            raise CheckInError(f"{unique_id} is not registered.")
        person.apply_restored_presence(checked_in_at=checked_in_at, location=location)
        self._on_site_roster[unique_id] = person

    def emergency_headcount(self) -> dict[str, list[dict[str, str]]]:
        grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        for person in self.who_is_on_site():
            grouped[person.person_type].append(
                {
                    "name": person.name,
                    "id": person.unique_id,
                    "location": person.location or "Unknown",
                }
            )
        return dict(grouped)

    def overstay_report(self, *, now: datetime | None = None) -> list[Visitor]:
        current_time = now or datetime.now()
        visitors = [
            person
            for person in self._on_site_roster.values()
            if isinstance(person, Visitor) and person.is_overstaying(current_time)
        ]
        return sorted(visitors, key=lambda visitor: (visitor.name.lower(), visitor.unique_id))

    def _validate_check_in(self, person: Person, *, checked_in_at: datetime | None = None) -> None:
        if isinstance(person, Visitor):
            host = self.lookup(person.host_employee_id)
            if not isinstance(host, Employee):
                raise CheckInError(
                    f"Visitor {person.unique_id} requires a registered employee host."
                )
            if not host.on_site:
                raise CheckInError(
                    f"Visitor {person.unique_id} cannot check in until host {host.unique_id} is on-site."
                )
            return

        if isinstance(person, Contractor):
            visit_date = (checked_in_at or datetime.now()).date()
            if not person.is_contract_active(visit_date):
                raise CheckInError(
                    f"Contractor {person.unique_id} cannot check in because the contract is inactive."
                )

    def _host_departure_warnings(self, employee_id: str) -> list[str]:
        warnings = []
        for person in self._on_site_roster.values():
            if isinstance(person, Visitor) and person.host_employee_id == employee_id:
                warnings.append(
                    f"Visitor {person.name} ({person.unique_id}) is still on-site without host {employee_id}."
                )
        return warnings

    def _require_registered_person(self, unique_id: str) -> Person:
        person = self.lookup(unique_id)
        if person is None:
            raise CheckInError(f"{unique_id} is not registered.")
        return person

    @staticmethod
    def _sort_people(people: Iterable[Person]) -> list[Person]:
        return sorted(people, key=lambda person: (person.person_type, person.name.lower(), person.unique_id))
