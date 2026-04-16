"""Interactive CLI for the Personnel registry app."""

from __future__ import annotations

from datetime import date

from .models import CheckInError, Contractor, DuplicatePersonError, Employee, Person, Visitor
from .registry import PersonnelRegistry


def run_cli() -> None:
    registry = PersonnelRegistry()
    print("Vault OS Personnel Registry")
    print("Manage employees, visitors, and contractors for the facility.\n")

    actions = {
        "1": ("Register a person", lambda: register_person(registry)),
        "2": ("Check someone in", lambda: check_in_person(registry)),
        "3": ("Check someone out", lambda: check_out_person(registry)),
        "4": ("View who is on-site", lambda: show_on_site(registry)),
        "5": ("Run emergency headcount", lambda: show_headcount(registry)),
        "6": ("View overstay report", lambda: show_overstay_report(registry)),
        "7": ("Search directory", lambda: search_directory(registry)),
        "8": ("Lookup person by ID", lambda: lookup_person(registry)),
        "0": ("Exit", None),
    }

    while True:
        print_menu(actions)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye.")
            return

        action = actions.get(choice)
        if action is None:
            print("Invalid option. Try again.\n")
            continue

        try:
            action[1]()
        except (CheckInError, DuplicatePersonError, ValueError) as error:
            print(f"Error: {error}\n")
        except KeyboardInterrupt:
            print("\nAction canceled.\n")


def print_menu(actions: dict[str, tuple[str, object]]) -> None:
    print("Menu")
    for key, (label, _) in actions.items():
        print(f"  {key}. {label}")


def register_person(registry: PersonnelRegistry) -> None:
    person_type = input("Register employee, visitor, or contractor? ").strip().lower()
    unique_id = prompt_non_empty("Unique ID: ")
    name = prompt_non_empty("Name: ")
    contact_info = prompt_non_empty("Contact info: ")

    if person_type == "employee":
        person = Employee(
            unique_id=unique_id,
            name=name,
            contact_info=contact_info,
            department=prompt_non_empty("Department: "),
            role_title=prompt_non_empty("Role title: "),
            hire_date=prompt_date("Hire date (YYYY-MM-DD): "),
            assigned_keycard_id=prompt_non_empty("Assigned keycard ID: "),
        )
    elif person_type == "visitor":
        person = Visitor(
            unique_id=unique_id,
            name=name,
            contact_info=contact_info,
            host_employee_id=prompt_non_empty("Host employee ID: "),
            visit_purpose=prompt_non_empty("Visit purpose: "),
            expected_duration_minutes=prompt_int("Expected duration in minutes: "),
        )
    elif person_type == "contractor":
        restricted_areas = input(
            "Restricted areas (comma-separated, leave blank for none): "
        ).strip()
        person = Contractor(
            unique_id=unique_id,
            name=name,
            contact_info=contact_info,
            company_name=prompt_non_empty("Company name: "),
            contract_start_date=prompt_date("Contract start date (YYYY-MM-DD): "),
            contract_end_date=prompt_date("Contract end date (YYYY-MM-DD): "),
            restricted_areas=parse_csv(restricted_areas),
        )
    else:
        raise ValueError("Person type must be employee, visitor, or contractor.")

    registry.register(person)
    print(f"Registered {person.person_type} {person.name} ({person.unique_id}).\n")


def check_in_person(registry: PersonnelRegistry) -> None:
    unique_id = prompt_non_empty("Unique ID to check in: ")
    location = input("Current location (optional): ").strip() or None
    person = registry.check_in(unique_id, location=location)
    print(f"{person.name} is now on-site.\n")


def check_out_person(registry: PersonnelRegistry) -> None:
    unique_id = prompt_non_empty("Unique ID to check out: ")
    warnings = registry.check_out(unique_id)
    print(f"{unique_id} checked out.")
    if warnings:
        for warning in warnings:
            print(f"Warning: {warning}")
    print()


def show_on_site(registry: PersonnelRegistry) -> None:
    people = registry.who_is_on_site()
    if not people:
        print("No one is currently on-site.\n")
        return

    print("On-site roster")
    for person in people:
        location = person.location or "Unknown"
        print(f"- {person.person_type}: {person.name} ({person.unique_id}) at {location}")
    print()


def show_headcount(registry: PersonnelRegistry) -> None:
    grouped = registry.emergency_headcount()
    if not grouped:
        print("Emergency headcount is empty.\n")
        return

    print("Emergency headcount")
    for person_type, records in grouped.items():
        print(f"{person_type}s")
        for record in records:
            print(f"- {record['name']} ({record['id']}) at {record['location']}")
    print()


def show_overstay_report(registry: PersonnelRegistry) -> None:
    visitors = registry.overstay_report()
    if not visitors:
        print("No visitors are currently overstaying.\n")
        return

    print("Overstay report")
    for visitor in visitors:
        print(
            f"- {visitor.name} ({visitor.unique_id}), host {visitor.host_employee_id}, "
            f"checked in at {visitor.checked_in_at:%Y-%m-%d %H:%M}"
        )
    print()


def search_directory(registry: PersonnelRegistry) -> None:
    query = prompt_non_empty("Search term: ")
    results = registry.search(query)
    if not results:
        print("No matches found.\n")
        return

    print("Search results")
    for person in results:
        print(format_person_line(person))
    print()


def lookup_person(registry: PersonnelRegistry) -> None:
    unique_id = prompt_non_empty("Lookup ID: ")
    person = registry.lookup(unique_id)
    if person is None:
        print("No matching person found.\n")
        return

    print("Person record")
    print(format_person_details(person))
    print()


def format_person_line(person: Person) -> str:
    return f"- {person.person_type}: {person.name} ({person.unique_id})"


def format_person_details(person: Person) -> str:
    lines = [
        f"Type: {person.person_type}",
        f"ID: {person.unique_id}",
        f"Name: {person.name}",
        f"Contact: {person.contact_info}",
        f"On-site: {'Yes' if person.on_site else 'No'}",
    ]
    if person.location:
        lines.append(f"Location: {person.location}")

    if isinstance(person, Employee):
        lines.extend(
            [
                f"Department: {person.department}",
                f"Role title: {person.role_title}",
                f"Hire date: {person.hire_date.isoformat()}",
                f"Keycard ID: {person.assigned_keycard_id}",
            ]
        )
    elif isinstance(person, Visitor):
        lines.extend(
            [
                f"Host employee ID: {person.host_employee_id}",
                f"Visit purpose: {person.visit_purpose}",
                f"Expected duration: {person.expected_duration_minutes} minutes",
            ]
        )
    elif isinstance(person, Contractor):
        restricted = ", ".join(person.restricted_areas) if person.restricted_areas else "None"
        lines.extend(
            [
                f"Company name: {person.company_name}",
                f"Contract window: {person.contract_start_date.isoformat()} to {person.contract_end_date.isoformat()}",
                f"Restricted areas: {restricted}",
            ]
        )

    return "\n".join(lines)


def prompt_non_empty(label: str) -> str:
    value = input(label).strip()
    if not value:
        raise ValueError("This field cannot be blank.")
    return value


def prompt_date(label: str) -> date:
    value = prompt_non_empty(label)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Dates must use YYYY-MM-DD format.") from error


def prompt_int(label: str) -> int:
    value = prompt_non_empty(label)
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("Enter a whole number.") from error


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]
