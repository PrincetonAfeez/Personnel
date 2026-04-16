"""Test the CLI for the personnel module."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest

from personnel import CheckInError, Contractor, Employee, PersonnelRegistry, Visitor
from personnel.cli import (
    check_in_person,
    check_out_person,
    format_person_details,
    format_person_line,
    lookup_person,
    parse_csv,
    print_menu,
    prompt_date,
    prompt_int,
    prompt_non_empty,
    register_person,
    run_cli,
    search_directory,
    show_headcount,
    show_on_site,
    show_overstay_report,
)


def test_parse_csv_empty_and_tokens() -> None:
    assert parse_csv("") == []
    assert parse_csv("  ") == []
    assert parse_csv("Vault") == ["Vault"]
    assert parse_csv(" a , b , ") == ["a", "b"]


def test_format_person_line() -> None:
    emp = Employee(
        unique_id="E1",
        name="Alex",
        contact_info="a@b.co",
        department="Ops",
        role_title="Lead",
        hire_date=date(2024, 1, 2),
        assigned_keycard_id="K1",
    )
    assert format_person_line(emp) == "- Employee: Alex (E1)"


def test_format_person_details_visitor_includes_host() -> None:
    v = Visitor(
        unique_id="V1",
        name="Guest",
        contact_info="g@x.co",
        host_employee_id="E1",
        visit_purpose="Meet",
        expected_duration_minutes=30,
    )
    text = format_person_details(v)
    assert "Visitor" in text
    assert "Host employee ID: E1" in text
    assert "On-site: No" in text


def test_format_person_details_contractor_restricted_areas_none() -> None:
    c = Contractor(
        unique_id="C1",
        name="Pat",
        contact_info="p@co",
        company_name="Co",
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 1, 31),
        restricted_areas=[],
    )
    text = format_person_details(c)
    assert "Restricted areas: None" in text


def test_prompt_non_empty_accepts_value() -> None:
    with patch("personnel.cli.input", return_value="  hello  "):
        assert prompt_non_empty("Label: ") == "hello"


def test_prompt_non_empty_rejects_blank() -> None:
    with patch("personnel.cli.input", return_value="   "):
        with pytest.raises(ValueError, match="cannot be blank"):
            prompt_non_empty("Label: ")


def test_prompt_date_iso() -> None:
    with patch("personnel.cli.input", return_value="2024-06-01"):
        assert prompt_date("D: ") == date(2024, 6, 1)


def test_prompt_date_invalid_format() -> None:
    with patch("personnel.cli.input", return_value="06/01/2024"):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            prompt_date("D: ")


def test_prompt_int_valid() -> None:
    with patch("personnel.cli.input", return_value="42"):
        assert prompt_int("N: ") == 42


def test_prompt_int_invalid() -> None:
    with patch("personnel.cli.input", return_value="x"):
        with pytest.raises(ValueError, match="whole number"):
            prompt_int("N: ")


def test_register_person_employee(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    replies = iter(
        [
            "employee",
            "EMP-9",
            "Sam Row",
            "sam@example.com",
            "IT",
            "Engineer",
            "2024-03-01",
            "KC-99",
        ]
    )

    with patch("personnel.cli.input", lambda _label: next(replies)):
        register_person(registry)

    person = registry.lookup("EMP-9")
    assert person is not None
    assert isinstance(person, Employee)
    assert person.department == "IT"
    captured = capsys.readouterr().out
    assert "Registered Employee" in captured
    assert "EMP-9" in captured


def test_register_person_visitor(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="HOST-CLI",
            name="Host",
            contact_info="h@e",
            department="D",
            role_title="R",
            hire_date=date(2020, 1, 1),
            assigned_keycard_id="K",
        )
    )
    replies = iter(
        [
            "visitor",
            "VIS-CLI-1",
            "Visitor Name",
            "vis@example.com",
            "HOST-CLI",
            "Delivery",
            "45",
        ]
    )
    with patch("personnel.cli.input", lambda _label: next(replies)):
        register_person(registry)
    v = registry.lookup("VIS-CLI-1")
    assert isinstance(v, Visitor)
    assert v.host_employee_id == "HOST-CLI"
    assert "Registered Visitor" in capsys.readouterr().out


def test_register_person_contractor_with_restricted_areas(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    replies = iter(
        [
            "contractor",
            "CON-CLI-1",
            "Contractor Name",
            "con@example.com",
            " Vault , Server Room ",
            "Acme Inc",
            "2026-01-01",
            "2026-06-30",
        ]
    )

    with patch("personnel.cli.input", lambda _label: next(replies)):
        register_person(registry)

    c = registry.lookup("CON-CLI-1")
    assert isinstance(c, Contractor)
    assert c.restricted_areas == ["Vault", "Server Room"]
    assert "Registered Contractor" in capsys.readouterr().out


def test_format_person_details_employee_on_site_shows_location() -> None:
    emp = Employee(
        unique_id="ELOC",
        name="Loc",
        contact_info="l@e",
        department="D",
        role_title="R",
        hire_date=date(2020, 1, 1),
        assigned_keycard_id="K",
    )
    emp._record_check_in(checked_in_at=datetime(2026, 1, 1, 9, 0), location="Lobby")
    text = format_person_details(emp)
    assert "On-site: Yes" in text
    assert "Location: Lobby" in text


def test_search_directory_no_matches(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    with patch("personnel.cli.input", return_value="zzzznomatch"):
        search_directory(registry)
    assert "No matches found" in capsys.readouterr().out


def test_show_overstay_report_lists_overstaying_visitors(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    visitor = Visitor(
        unique_id="VO",
        name="Over",
        contact_info="o@e",
        host_employee_id="EH",
        visit_purpose="Short",
        expected_duration_minutes=5,
    )
    visitor._record_check_in(checked_in_at=datetime(2026, 4, 12, 10, 0), location="Desk")
    with patch.object(registry, "overstay_report", return_value=[visitor]):
        show_overstay_report(registry)

    out = capsys.readouterr().out
    assert "Overstay report" in out
    assert "Over" in out
    assert "VO" in out
    assert "EH" in out


def test_register_person_invalid_type() -> None:
    registry = PersonnelRegistry()
    replies = iter(["intern", "I1", "n", "c"])

    with patch("personnel.cli.input", lambda _label: next(replies)):
        with pytest.raises(ValueError, match="employee, visitor, or contractor"):
            register_person(registry)


def test_check_in_person_success(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="E10",
            name="Bo",
            contact_info="b@e",
            department="X",
            role_title="Y",
            hire_date=date(2023, 1, 1),
            assigned_keycard_id="K",
        )
    )
    with patch("personnel.cli.input", side_effect=["E10", "Lobby"]):
        check_in_person(registry)
    out = capsys.readouterr().out
    assert "on-site" in out.lower()
    assert registry.lookup("E10") is not None
    assert registry.lookup("E10").on_site is True


def test_check_in_person_propagates_when_already_on_site() -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="E10",
            name="Bo",
            contact_info="b@e",
            department="X",
            role_title="Y",
            hire_date=date(2023, 1, 1),
            assigned_keycard_id="K",
        )
    )
    registry.check_in("E10")
    with (
        patch("personnel.cli.input", side_effect=["E10", "Lobby"]),
        pytest.raises(CheckInError, match="already on-site"),
    ):
        check_in_person(registry)


def test_check_out_person(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="E11",
            name="Bo",
            contact_info="b@e",
            department="X",
            role_title="Y",
            hire_date=date(2023, 1, 1),
            assigned_keycard_id="K",
        )
    )
    registry.check_in("E11")
    with patch("personnel.cli.input", return_value="E11"):
        check_out_person(registry)
    assert "checked out" in capsys.readouterr().out.lower()


def test_check_out_person_prints_warnings_when_host_leaves_visitor_on_site(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="E-HOST",
            name="Host",
            contact_info="h@e",
            department="D",
            role_title="R",
            hire_date=date(2020, 1, 1),
            assigned_keycard_id="K",
        )
    )
    registry.register(
        Visitor(
            unique_id="V-STAY",
            name="Guest",
            contact_info="g@e",
            host_employee_id="E-HOST",
            visit_purpose="Meet",
            expected_duration_minutes=60,
        )
    )
    registry.check_in("E-HOST")
    registry.check_in("V-STAY")
    with patch("personnel.cli.input", return_value="E-HOST"):
        check_out_person(registry)
    out = capsys.readouterr().out
    assert "Warning:" in out
    assert "V-STAY" in out


def test_lookup_person_found_and_missing(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="E2",
            name="Bo",
            contact_info="b@e",
            department="X",
            role_title="Y",
            hire_date=date(2023, 1, 1),
            assigned_keycard_id="K",
        )
    )

    with patch("personnel.cli.input", return_value="E2"):
        lookup_person(registry)
    assert "Person record" in capsys.readouterr().out

    with patch("personnel.cli.input", return_value="NOPE"):
        lookup_person(registry)
    assert "No matching" in capsys.readouterr().out


def test_search_directory(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    registry.register(
        Employee(
            unique_id="E3",
            name="UniqueNameX",
            contact_info="b@e",
            department="X",
            role_title="Y",
            hire_date=date(2023, 1, 1),
            assigned_keycard_id="K",
        )
    )

    with patch("personnel.cli.input", return_value="UniqueNameX"):
        search_directory(registry)
    out = capsys.readouterr().out
    assert "Search results" in out
    assert "UniqueNameX" in out


def test_show_on_site_empty_and_populated(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    show_on_site(registry)
    assert "No one is currently on-site" in capsys.readouterr().out

    registry.register(
        Employee(
            unique_id="E4",
            name="OnSite",
            contact_info="o@e",
            department="D",
            role_title="R",
            hire_date=date(2022, 1, 1),
            assigned_keycard_id="K",
        )
    )
    registry.check_in("E4", location="Desk")
    show_on_site(registry)
    out = capsys.readouterr().out
    assert "On-site roster" in out
    assert "Desk" in out


def test_show_headcount_empty_and_grouped(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    show_headcount(registry)
    assert "empty" in capsys.readouterr().out.lower()

    registry.register(
        Employee(
            unique_id="E5",
            name="A",
            contact_info="a@e",
            department="D",
            role_title="R",
            hire_date=date(2022, 1, 1),
            assigned_keycard_id="K",
        )
    )
    registry.check_in("E5", location="L1")
    show_headcount(registry)
    out = capsys.readouterr().out
    assert "Emergency headcount" in out
    assert "Employees" in out


def test_show_overstay_report(capsys: pytest.CaptureFixture[str]) -> None:
    registry = PersonnelRegistry()
    emp = Employee(
        unique_id="E6",
        name="Host",
        contact_info="h@e",
        department="D",
        role_title="R",
        hire_date=date(2022, 1, 1),
        assigned_keycard_id="K",
    )
    registry.register(emp)
    vis = Visitor(
        unique_id="V9",
        name="Late",
        contact_info="v@e",
        host_employee_id="E6",
        visit_purpose="p",
        expected_duration_minutes=1,
    )
    registry.register(vis)
    registry.check_in("E6")
    registry.check_in("V9")
    show_overstay_report(registry)
    assert "No visitors are currently overstaying" in capsys.readouterr().out


def test_print_menu_lists_keys(capsys: pytest.CaptureFixture[str]) -> None:
    actions = {
        "1": ("One", None),
        "0": ("Exit", None),
    }
    print_menu(actions)
    out = capsys.readouterr().out
    assert "1. One" in out
    assert "0. Exit" in out


def test_run_cli_exits_on_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("personnel.cli.input", return_value="0"):
        run_cli()
    assert "Goodbye" in capsys.readouterr().out


def test_run_cli_invalid_then_exit(capsys: pytest.CaptureFixture[str]) -> None:
    replies = iter(["99", "0"])

    with patch("personnel.cli.input", lambda _p: next(replies)):
        run_cli()

    out = capsys.readouterr().out
    assert "Invalid option" in out
    assert "Goodbye" in out


def test_run_cli_check_in_error_shown_for_unregistered_id(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("personnel.cli.input", side_effect=["2", "NOT-THERE", "", "0"]):
        run_cli()
    out = capsys.readouterr().out
    assert "Error:" in out
    assert "not registered" in out
    assert "Goodbye" in out


def test_run_cli_keyboard_interrupt_during_action(capsys: pytest.CaptureFixture[str]) -> None:
    """Menu choice runs an action; interrupt inside that action is caught."""
    with patch("personnel.cli.input", side_effect=["1", KeyboardInterrupt(), "0"]):
        run_cli()

    out = capsys.readouterr().out
    assert "Action canceled" in out
    assert "Goodbye" in out
