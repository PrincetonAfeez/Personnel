"""Tests for ``personnel.registry`` (imported explicitly as its own module)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from personnel.models import CheckInError, Contractor, Employee, Visitor
from personnel.registry import PersonnelRegistry


def test_check_in_unknown_person_raises() -> None:
    reg = PersonnelRegistry()
    with pytest.raises(CheckInError, match="not registered"):
        reg.check_in("NOBODY")


def test_check_out_unknown_person_raises() -> None:
    reg = PersonnelRegistry()
    with pytest.raises(CheckInError, match="not registered"):
        reg.check_out("NOBODY")


def test_visitor_rejects_missing_host_registration() -> None:
    reg = PersonnelRegistry()
    v = Visitor(
        unique_id="V1",
        name="Guest",
        contact_info="g@e",
        host_employee_id="NOT-REGISTERED",
        visit_purpose="Meet",
        expected_duration_minutes=20,
    )
    reg.register(v)
    with pytest.raises(CheckInError, match="registered employee host"):
        reg.check_in("V1")


def test_who_is_on_site_sorted_by_type_then_name() -> None:
    reg = PersonnelRegistry()
    alice = Employee(
        unique_id="E-A",
        name="Alice",
        contact_info="a@e",
        department="D",
        role_title="R",
        hire_date=date(2020, 1, 1),
        assigned_keycard_id="K",
    )
    zed = Employee(
        unique_id="E-Z",
        name="Zed",
        contact_info="z@e",
        department="D",
        role_title="R",
        hire_date=date(2020, 1, 1),
        assigned_keycard_id="K2",
    )
    reg.register(alice)
    reg.register(zed)
    reg.check_in("E-Z")
    reg.check_in("E-A")
    roster = reg.who_is_on_site()
    assert [p.unique_id for p in roster] == ["E-A", "E-Z"]


def test_overstay_report_empty_when_no_visitors() -> None:
    reg = PersonnelRegistry()
    e = Employee(
        unique_id="E1",
        name="Only",
        contact_info="o@e",
        department="D",
        role_title="R",
        hire_date=date(2020, 1, 1),
        assigned_keycard_id="K",
    )
    reg.register(e)
    reg.check_in("E1")
    assert reg.overstay_report(now=datetime(2026, 1, 1, 15, 0)) == []


def test_contractor_check_in_allowed_during_active_contract() -> None:
    reg = PersonnelRegistry()
    c = Contractor(
        unique_id="C1",
        name="Pat",
        contact_info="p@c",
        company_name="Co",
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 1, 31),
        restricted_areas=[],
    )
    reg.register(c)
    reg.check_in("C1", checked_in_at=datetime(2026, 1, 15, 8, 0))
    assert reg.lookup("C1") is not None
    assert reg.lookup("C1").on_site is True
