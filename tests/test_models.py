"""Tests for ``personnel.models`` (imported explicitly as its own module)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from personnel.models import (
    CheckInError,
    Contractor,
    DuplicatePersonError,
    Employee,
    Person,
    PersonnelError,
    Visitor,
)


def test_person_base_class_for_instances() -> None:
    emp = Employee(
        unique_id="PB",
        name="N",
        contact_info="c",
        department="D",
        role_title="R",
        hire_date=date(2019, 1, 1),
        assigned_keycard_id="K",
    )
    assert isinstance(emp, Person)


def test_exception_hierarchy() -> None:
    assert issubclass(CheckInError, PersonnelError)
    assert issubclass(DuplicatePersonError, PersonnelError)


def test_employee_person_type_and_search_tokens() -> None:
    emp = Employee(
        unique_id="E1",
        name="N",
        contact_info="c",
        department="DeptA",
        role_title="RoleB",
        hire_date=date(2020, 1, 1),
        assigned_keycard_id="K99",
    )
    assert emp.person_type == "Employee"
    tokens = emp.search_tokens()
    assert "E1" in tokens
    assert "DeptA" in tokens
    assert "RoleB" in tokens
    assert "K99" in tokens


def test_employee_validate_hire_date_with_reference() -> None:
    emp = Employee(
        unique_id="E2",
        name="N",
        contact_info="c",
        department="D",
        role_title="R",
        hire_date=date(2025, 6, 15),
        assigned_keycard_id="K",
    )
    emp.validate_hire_date(reference_date=date(2025, 6, 20))
    with pytest.raises(ValueError, match="future"):
        emp.validate_hire_date(reference_date=date(2025, 6, 10))


def test_record_check_in_and_out_on_employee() -> None:
    emp = Employee(
        unique_id="E3",
        name="N",
        contact_info="c",
        department="D",
        role_title="R",
        hire_date=date(2020, 1, 1),
        assigned_keycard_id="K",
    )
    at = datetime(2026, 1, 1, 10, 0)
    emp._record_check_in(checked_in_at=at, location="Gate")
    assert emp.on_site is True
    assert emp.checked_in_at == at
    assert emp.location == "Gate"
    emp._record_check_out()
    assert emp.on_site is False
    assert emp.checked_in_at is None
    assert emp.location is None


def test_visitor_expected_duration_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        Visitor(
            unique_id="V",
            name="N",
            contact_info="c",
            host_employee_id="H",
            visit_purpose="p",
            expected_duration_minutes=0,
        )


def test_visitor_is_overstaying_false_when_not_on_site() -> None:
    v = Visitor(
        unique_id="V1",
        name="N",
        contact_info="c",
        host_employee_id="H",
        visit_purpose="p",
        expected_duration_minutes=30,
    )
    assert v.is_overstaying(now=datetime(2099, 1, 1)) is False


def test_visitor_is_overstaying_true_when_past_deadline() -> None:
    v = Visitor(
        unique_id="V2",
        name="N",
        contact_info="c",
        host_employee_id="H",
        visit_purpose="p",
        expected_duration_minutes=30,
    )
    v._record_check_in(checked_in_at=datetime(2026, 6, 1, 12, 0), location="L")
    assert v.is_overstaying(now=datetime(2026, 6, 1, 12, 31)) is True
    assert v.is_overstaying(now=datetime(2026, 6, 1, 12, 30)) is False


def test_visitor_search_tokens() -> None:
    v = Visitor(
        unique_id="V3",
        name="N",
        contact_info="c",
        host_employee_id="HOST-1",
        visit_purpose="Audit",
        expected_duration_minutes=10,
    )
    t = v.search_tokens()
    assert "HOST-1" in t
    assert "Audit" in t


def test_contractor_invalid_date_range() -> None:
    with pytest.raises(ValueError, match="end date"):
        Contractor(
            unique_id="C",
            name="N",
            contact_info="c",
            company_name="Co",
            contract_start_date=date(2026, 3, 1),
            contract_end_date=date(2026, 2, 1),
            restricted_areas=[],
        )


def test_contractor_is_contract_active_boundaries() -> None:
    c = Contractor(
        unique_id="C1",
        name="N",
        contact_info="c",
        company_name="Co",
        contract_start_date=date(2026, 2, 1),
        contract_end_date=date(2026, 2, 28),
        restricted_areas=[],
    )
    assert c.is_contract_active(date(2026, 1, 31)) is False
    assert c.is_contract_active(date(2026, 2, 1)) is True
    assert c.is_contract_active(date(2026, 2, 28)) is True
    assert c.is_contract_active(date(2026, 3, 1)) is False


def test_contractor_search_tokens_includes_restricted_areas() -> None:
    c = Contractor(
        unique_id="C2",
        name="N",
        contact_info="c",
        company_name="BuildCo",
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 12, 31),
        restricted_areas=["Vault", "Lab"],
    )
    t = c.search_tokens()
    assert "BuildCo" in t
    assert "Vault" in t
    assert "Lab" in t
