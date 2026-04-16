"""Test the personnel module."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from personnel import (
    CheckInError,
    Contractor,
    DuplicatePersonError,
    Employee,
    PersonnelRegistry,
    Visitor,
)


class PersonnelRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PersonnelRegistry()
        self.employee = Employee(
            unique_id="EMP-100",
            name="Dana Holt",
            contact_info="dana.holt@example.com",
            department="Operations",
            role_title="Facility Manager",
            hire_date=date(2024, 6, 1),
            assigned_keycard_id="KC-900",
        )
        self.registry.register(self.employee)

    def test_employee_hire_date_cannot_be_in_future(self) -> None:
        with self.assertRaises(ValueError):
            Employee(
                unique_id="EMP-101",
                name="Future Hire",
                contact_info="future@example.com",
                department="Ops",
                role_title="Analyst",
                hire_date=date.today() + timedelta(days=1),
                assigned_keycard_id="KC-901",
            )

    def test_visitor_requires_host_on_site(self) -> None:
        visitor = Visitor(
            unique_id="VIS-200",
            name="Nia Brooks",
            contact_info="nia@example.com",
            host_employee_id=self.employee.unique_id,
            visit_purpose="Vendor demo",
            expected_duration_minutes=45,
        )
        self.registry.register(visitor)

        with self.assertRaises(CheckInError):
            self.registry.check_in(visitor.unique_id)

    def test_visitor_requires_registered_employee_host_not_contractor(self) -> None:
        contractor = Contractor(
            unique_id="CON-900",
            name="Host-ish",
            contact_info="c@example.com",
            company_name="Co",
            contract_start_date=date(2026, 1, 1),
            contract_end_date=date(2026, 12, 31),
            restricted_areas=[],
        )
        self.registry.register(contractor)
        visitor = Visitor(
            unique_id="VIS-900",
            name="Wrong host ref",
            contact_info="v@example.com",
            host_employee_id=contractor.unique_id,
            visit_purpose="Tour",
            expected_duration_minutes=15,
        )
        self.registry.register(visitor)
        self.registry.check_in(contractor.unique_id)

        with self.assertRaises(CheckInError):
            self.registry.check_in(visitor.unique_id)

    def test_visitor_can_check_in_when_host_is_present(self) -> None:
        visitor = Visitor(
            unique_id="VIS-201",
            name="Marcus Lee",
            contact_info="marcus@example.com",
            host_employee_id=self.employee.unique_id,
            visit_purpose="Audit walkthrough",
            expected_duration_minutes=30,
        )
        self.registry.register(visitor)
        self.registry.check_in(self.employee.unique_id, location="Lobby")

        checked_in = self.registry.check_in(visitor.unique_id, location="Conference Room")

        self.assertTrue(checked_in.on_site)
        self.assertEqual("Conference Room", checked_in.location)

    def test_contractor_cannot_check_in_after_contract_expiry(self) -> None:
        contractor = Contractor(
            unique_id="CON-300",
            name="Avery Singh",
            contact_info="avery@buildco.example.com",
            company_name="BuildCo",
            contract_start_date=date(2026, 1, 1),
            contract_end_date=date(2026, 1, 31),
            restricted_areas=["Vault", "Server Room"],
        )
        self.registry.register(contractor)

        with self.assertRaises(CheckInError):
            self.registry.check_in(
                contractor.unique_id,
                checked_in_at=datetime(2026, 2, 1, 9, 0),
            )

    def test_overstay_report_includes_only_visitors_past_due(self) -> None:
        visitor = Visitor(
            unique_id="VIS-202",
            name="Eva Tran",
            contact_info="eva@example.com",
            host_employee_id=self.employee.unique_id,
            visit_purpose="Design review",
            expected_duration_minutes=20,
        )
        self.registry.register(visitor)
        self.registry.check_in(
            self.employee.unique_id,
            checked_in_at=datetime(2026, 4, 12, 9, 0),
        )
        self.registry.check_in(
            visitor.unique_id,
            checked_in_at=datetime(2026, 4, 12, 9, 0),
        )

        report = self.registry.overstay_report(now=datetime(2026, 4, 12, 9, 30))

        self.assertEqual([visitor], report)

    def test_employee_check_out_warns_about_hosted_visitors(self) -> None:
        visitor = Visitor(
            unique_id="VIS-203",
            name="Remy Patel",
            contact_info="remy@example.com",
            host_employee_id=self.employee.unique_id,
            visit_purpose="Partnership meeting",
            expected_duration_minutes=60,
        )
        self.registry.register(visitor)
        self.registry.check_in(self.employee.unique_id)
        self.registry.check_in(visitor.unique_id)

        warnings = self.registry.check_out(self.employee.unique_id)

        self.assertEqual(
            [
                "Visitor Remy Patel (VIS-203) is still on-site without host EMP-100.",
            ],
            warnings,
        )

    def test_emergency_headcount_groups_people_by_type(self) -> None:
        contractor = Contractor(
            unique_id="CON-301",
            name="Skylar Dean",
            contact_info="skylar@maint.example.com",
            company_name="MaintCorp",
            contract_start_date=date(2026, 4, 1),
            contract_end_date=date(2026, 4, 30),
            restricted_areas=[],
        )
        self.registry.register(contractor)
        self.registry.check_in(self.employee.unique_id, location="Front Desk")
        self.registry.check_in(
            contractor.unique_id,
            location="Mechanical Room",
            checked_in_at=datetime(2026, 4, 12, 8, 15),
        )

        report = self.registry.emergency_headcount()

        self.assertEqual(
            [{"name": "Skylar Dean", "id": "CON-301", "location": "Mechanical Room"}],
            report["Contractor"],
        )
        self.assertEqual(
            [{"name": "Dana Holt", "id": "EMP-100", "location": "Front Desk"}],
            report["Employee"],
        )

    def test_register_duplicate_id_raises(self) -> None:
        twin = Employee(
            unique_id="EMP-100",
            name="Other Dana",
            contact_info="other@example.com",
            department="Ops",
            role_title="Twin",
            hire_date=date(2024, 6, 1),
            assigned_keycard_id="KC-800",
        )
        with self.assertRaises(DuplicatePersonError):
            self.registry.register(twin)

    def test_check_in_when_already_on_site_raises(self) -> None:
        self.registry.check_in(self.employee.unique_id)
        with self.assertRaises(CheckInError):
            self.registry.check_in(self.employee.unique_id)

    def test_check_out_when_not_on_site_raises(self) -> None:
        with self.assertRaises(CheckInError):
            self.registry.check_out(self.employee.unique_id)

    def test_lookup_returns_none_or_person(self) -> None:
        self.assertIsNone(self.registry.lookup("NO-SUCH-ID"))
        self.assertIs(self.registry.lookup("EMP-100"), self.employee)

    def test_search_blank_returns_empty(self) -> None:
        self.assertEqual([], self.registry.search(""))
        self.assertEqual([], self.registry.search("   \t"))

    def test_search_matches_token_case_insensitive(self) -> None:
        self.registry.register(
            Employee(
                unique_id="EMP-777",
                name="Quinn",
                contact_info="q@example.com",
                department="Quantum Lab",
                role_title="Researcher",
                hire_date=date(2024, 1, 1),
                assigned_keycard_id="KC-7",
            )
        )
        hits = self.registry.search("quantum")
        self.assertEqual(1, len(hits))
        self.assertEqual("EMP-777", hits[0].unique_id)


if __name__ == "__main__":
    unittest.main()
