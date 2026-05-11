# Architecture Decision Record
## App 18 — Personnel
**Vault OS Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Vault OS roadmap needed a personnel registry subsystem that could model the people inside a secure facility: employees, visitors, and contractors. Earlier Vault OS apps focused on devices, access checks, and inventory custody. Personnel adds the human layer: who is registered, who is physically on-site, who is allowed to check in, which visitors depend on which employee hosts, and which contractors are valid only during a contract window.

The project is intentionally scoped as a class-based, in-memory simulator rather than a production HR or badge-management system. The README identifies the design focus as OOP: a shared `Person` base class, specialized subclasses, and a `PersonnelRegistry` responsible for both the full directory and live on-site roster. Runtime dependencies are standard-library only; `pytest` is used only for development and verification.

---

## Decisions

### Decision 1 — Shared `Person` base class with specialized subclasses

**Chosen:** Use a `Person` dataclass as the common base, then extend it with `Employee`, `Visitor`, and `Contractor`.

**Rejected:** A single dictionary-based record with optional fields for every personnel type.

**Reason:** All people share identity, contact, on-site state, check-in time, and location. Employees, visitors, and contractors then each add fields with different validation rules. Inheritance is appropriate here because the subclasses are true specializations of the same domain concept, not unrelated records forced into the same shape.

The base class owns the common state:
- `unique_id`
- `name`
- `contact_info`
- `on_site`
- `checked_in_at`
- `location`

The subclasses add type-specific data:
- `Employee`: department, role title, hire date, assigned keycard ID
- `Visitor`: host employee ID, visit purpose, expected duration
- `Contractor`: company, contract window, restricted areas

---

### Decision 2 — Registry controls check-in and check-out transitions

**Chosen:** `PersonnelRegistry` is the only public workflow layer for check-in and check-out.

**Rejected:** Letting callers directly set `person.on_site`, `person.checked_in_at`, or `person.location`.

**Reason:** On-site presence is not just a boolean. It has rules:
- A person must be registered before check-in.
- A person cannot check in twice.
- A person cannot check out unless currently on-site.
- A visitor cannot check in unless the host exists, is an `Employee`, and is already on-site.
- A contractor cannot check in outside the contract window.
- An employee checkout may produce warnings if hosted visitors remain on-site.

The model methods `_record_check_in()` and `_record_check_out()` exist, but the underscore makes their intent clear: they are internal state-transition helpers called after registry validation. This keeps the rules centralized.

---

### Decision 3 — Two indexes: full directory and live on-site roster

**Chosen:** Maintain both `_directory: dict[str, Person]` and `_on_site_roster: dict[str, Person]`.

**Rejected:** Store only one dictionary and compute the live roster by scanning every person for `on_site == True`.

**Reason:** The registry has two responsibilities: long-lived registration and active facility presence. Separating the full directory from the live roster makes `who_is_on_site()`, `emergency_headcount()`, and overstay checks direct and easy to reason about. The code also cross-checks both state sources when validating double check-in and checkout, which helps catch inconsistent state.

---

### Decision 4 — Visitor host validation at check-in time

**Chosen:** A visitor may be registered before the host is on-site, but the registry blocks visitor check-in unless the host is registered as an `Employee` and currently on-site.

**Rejected:** Require host presence at visitor registration time.

**Reason:** Registration and arrival are different events. A visitor can be pre-registered before the host arrives. The critical safety rule is not whether the host was present at registration, but whether the host is present at the moment the visitor enters the facility.

This also keeps the data model flexible: visitor records can exist in the directory before becoming physically present.

---

### Decision 5 — Contractor validity enforced by contract window

**Chosen:** Contractors have `contract_start_date`, `contract_end_date`, and `is_contract_active(on_date)`. The registry blocks contractor check-in when the attempted check-in date falls outside that window.

**Rejected:** Treat contractors like employees once registered.

**Reason:** Contractors are temporary personnel. Their eligibility is date-bound, not just identity-bound. The contract window is an important state rule that belongs in the model and must be enforced by the registry. The implementation allows inclusive start and end dates, which matches common contract semantics.

---

### Decision 6 — Search as token matching

**Chosen:** Each model exposes `search_tokens()`, and `PersonnelRegistry.search(query)` performs case-insensitive substring matching across those tokens.

**Rejected:** Hard-code search fields inside the registry or add a full query language.

**Reason:** Search needs to be simple and broad for a CLI simulator. The base `Person` contributes common tokens, while each subclass extends the searchable surface with relevant fields:
- Employee adds department, role, and keycard ID.
- Visitor adds host ID and purpose.
- Contractor adds company and restricted areas.

This keeps search extensible without requiring the registry to know every subclass-specific field.

---

### Decision 7 — Standard-library runtime with pytest-only dev dependency

**Chosen:** Runtime uses only Python standard library modules: `dataclasses`, `datetime`, and collections support. `pytest` is used for test execution.

**Rejected:** Use a database, a CLI framework such as Typer/Click, or persistence libraries.

**Reason:** The learning target is OOP and state management, not external tooling. A standard-library implementation keeps the app portable, simple to inspect, and small enough for a focused build while still supporting meaningful validation and behavior tests.

---

## Consequences

**Positive:**
- The object model clearly demonstrates inheritance: `Employee`, `Visitor`, and `Contractor` are specialized `Person` objects.
- Check-in and check-out rules live in one place: `PersonnelRegistry`.
- Visitor host validation and contractor contract validation give the app real domain behavior beyond CRUD.
- Emergency headcount and overstay reporting reuse the on-site roster instead of duplicating state.
- Search remains small but useful through subclass-provided search tokens.
- The package exposes a clean public surface through `personnel.__all__`.

**Negative / Trade-offs:**
- The registry is in-memory only. Data disappears when the process exits.
- IDs are caller-provided strings rather than generated by the system, so the app depends on the operator to use a consistent ID scheme.
- The CLI does not have command-line subcommands or non-interactive flags; all workflows are menu-driven.
- `Person._record_check_in()` and `_record_check_out()` are not technically private in Python. They rely on convention rather than enforcement.
- Visitor host warnings happen at employee checkout, but the system does not automatically force hosted visitors to leave.

---

## Alternatives Not Explored

- **Database persistence:** Out of scope for Day 18. A JSON or SQLite persistence layer would be a reasonable next step, but the project’s focus is object state and registry rules.
- **Role/permission engine integration with App 16 Access:** This app stores an employee’s keycard ID as data, but it does not call the Access app. Keeping the modules separate avoids coupling during the OOP phase.
- **Formal event log:** The registry tracks current state, but not a historical check-in/out audit log. That would be valuable in a later integration layer.
- **CLI framework:** `input()` loops are sufficient for this educational app and avoid third-party runtime dependencies.

---

*Constitution reference: Article 1 (Python fundamentals and appropriate architecture), Article 3 (scope discipline), Article 4 (engineering quality), and Article 6 (verification behavior). No amendments triggered.*

-e 

---


# Technical Design Document
## App 18 — Personnel
**Vault OS Group | Document 2 of 5**

---

## Overview

Personnel is a standard-library Python package that models facility personnel and an on-site roster. It provides:

- Domain models in `personnel/models.py`
- Registry and reporting logic in `personnel/registry.py`
- Interactive CLI workflows in `personnel/cli.py`
- Public package exports in `personnel/__init__.py`
- Module entry point in `personnel/__main__.py`
- Convenience root launcher in `main.py`

The package name is `personnel`. The application runs with:

```bash
python -m personnel
python main.py
```

Tests are run with:

```bash
python -m pytest personnel tests
```

Runtime dependencies: Python standard library only. Development dependency: `pytest>=8.0`.

---

## System Context

Personnel sits in the Vault OS group as the human roster subsystem. It does not manage doors, access levels, physical devices, or inventory items. Instead, it answers questions such as:

- Who is registered in the facility directory?
- Who is currently on-site?
- Is this visitor allowed to enter yet?
- Is this contractor currently inside the contract window?
- Which visitors have overstayed?
- Which hosted visitors remain after an employee checks out?
- What is the emergency headcount grouped by person type?

The implementation is an in-memory simulator, not a persistent HR system.

---

## Component Breakdown

### `personnel.models`

Defines the domain model and exceptions.

**Errors:**
- `PersonnelError`
- `DuplicatePersonError`
- `CheckInError`

**Models:**
- `Person`
- `Employee`
- `Visitor`
- `Contractor`

### `personnel.registry`

Defines `PersonnelRegistry`, the service layer responsible for:

- registration
- lookup
- search
- check-in
- check-out
- on-site roster listing
- emergency headcount
- visitor overstay reports
- persisted roster restoration hooks for future integration

### `personnel.cli`

Defines the interactive menu and command handlers:

- `run_cli()`
- `register_person()`
- `check_in_person()`
- `check_out_person()`
- `show_on_site()`
- `show_headcount()`
- `show_overstay_report()`
- `search_directory()`
- `lookup_person()`
- prompt and formatting helpers

### `personnel.__main__`

Allows:

```bash
python -m personnel
```

### `main.py`

Convenience wrapper:

```bash
python main.py
```

### `personnel.__init__`

Exports the public package surface:

```python
CheckInError
Contractor
DuplicatePersonError
Employee
Person
PersonnelError
PersonnelRegistry
Visitor
```

---

## Module Dependency Graph

```text
main.py
  └── personnel.cli.run_cli

personnel.__main__
  └── personnel.cli.run_cli

personnel.__init__
  ├── personnel.models
  └── personnel.registry

personnel.cli
  ├── datetime.date
  ├── personnel.models
  │   ├── CheckInError
  │   ├── Contractor
  │   ├── DuplicatePersonError
  │   ├── Employee
  │   ├── Person
  │   └── Visitor
  └── personnel.registry.PersonnelRegistry

personnel.registry
  ├── collections.defaultdict
  ├── collections.abc.Iterable
  ├── datetime.datetime
  └── personnel.models
      ├── CheckInError
      ├── Contractor
      ├── DuplicatePersonError
      ├── Employee
      ├── Person
      └── Visitor

personnel.models
  ├── dataclasses
  └── datetime
```

---

## Core Data Structures

### `Person`

```python
@dataclass(slots=True)
class Person:
    unique_id: str
    name: str
    contact_info: str
    on_site: bool = field(default=False, init=False)
    checked_in_at: datetime | None = field(default=None, init=False)
    location: str | None = field(default=None, init=False)
```

`Person` is the shared base object. `on_site`, `checked_in_at`, and `location` are initialized internally and not accepted through the constructor.

### `Employee`

```python
@dataclass(slots=True)
class Employee(Person):
    department: str
    role_title: str
    hire_date: date
    assigned_keycard_id: str
```

Validation:
- `hire_date` cannot be later than the reference date.
- Constructor uses `date.today()` as the default reference.

### `Visitor`

```python
@dataclass(slots=True)
class Visitor(Person):
    host_employee_id: str
    visit_purpose: str
    expected_duration_minutes: int
```

Validation:
- `expected_duration_minutes` must be positive.

Behavior:
- `is_overstaying(now)` returns `True` only if the visitor is on-site, has a check-in time, and `now` is later than the expected departure deadline.

### `Contractor`

```python
@dataclass(slots=True)
class Contractor(Person):
    company_name: str
    contract_start_date: date
    contract_end_date: date
    restricted_areas: list[str] = field(default_factory=list)
```

Validation:
- `contract_end_date` cannot be earlier than `contract_start_date`.

Behavior:
- `is_contract_active(on_date)` checks whether the date is inside the inclusive contract window.

### `PersonnelRegistry`

```python
class PersonnelRegistry:
    self._directory: dict[str, Person]
    self._on_site_roster: dict[str, Person]
```

The directory tracks everyone registered. The roster tracks only current on-site people.

---

## Core Algorithms & Logic

### Registration

```text
register(person)
  if unique_id already exists:
      raise DuplicatePersonError
  store person in _directory
  return person
```

Registration does not automatically check a person in.

---

### Lookup

```text
lookup(unique_id)
  return _directory.get(unique_id)
```

Lookup returns `None` instead of raising.

---

### Search

```text
search(query)
  trim and lowercase query
  if query is blank:
      return []
  for each person in directory:
      ask person for search_tokens()
      if query is substring of any lowercased token:
          include person
  return sorted matches
```

Sorting is by:
1. person type
2. lowercase name
3. unique ID

---

### Check-in

```text
check_in(unique_id, location=None, checked_in_at=None)
  require person is registered
  reject if person already on-site or already in roster
  validate person-specific check-in rules
  record check-in on person
  add person to _on_site_roster
  return person
```

Person-specific validation:
- `Visitor`: host must exist, host must be an `Employee`, host must be on-site.
- `Contractor`: check-in date must fall inside contract window.
- `Employee`: no extra validation beyond being registered and not already on-site.

---

### Check-out

```text
check_out(unique_id)
  require person is registered
  reject if person is not on-site or not in roster
  if person is Employee:
      collect hosted visitor warnings
  clear person's on-site state
  remove person from _on_site_roster
  return warnings
```

This intentionally warns rather than blocks when an employee leaves while visitors remain.

---

### Emergency headcount

```text
emergency_headcount()
  create defaultdict(list)
  for person in who_is_on_site():
      grouped[person.person_type].append({
          "name": person.name,
          "id": person.unique_id,
          "location": person.location or "Unknown",
      })
  return dict(grouped)
```

The result is grouped by type name, not by subclass object.

---

### Overstay report

```text
overstay_report(now=None)
  current_time = now or datetime.now()
  collect on-site Visitor objects where visitor.is_overstaying(current_time)
  return sorted visitors by lowercased name and unique_id
```

Overstay is calculated only for visitors currently on-site.

---

## State Management

### Directory state

`_directory` is the full set of registered people. It is append-only through `register()` in the public API. There is no delete or update workflow in this app.

### On-site state

`_on_site_roster` stores people currently inside the facility. The registry keeps it in sync with each `Person` object’s `on_site`, `checked_in_at`, and `location` fields.

### Restore hooks

Two restore helpers exist for future integration/persistence work:

- `Person.apply_restored_presence()`
- `PersonnelRegistry.restore_onsite_snapshot()`

These are deliberately not normal CLI workflows. They support rehydrating persisted state when a later Vault OS integration layer exists.

---

## Error Handling Strategy

### Domain errors

`PersonnelError` is the base exception. Specific errors are:

| Error | Raised when |
|---|---|
| `DuplicatePersonError` | A duplicate `unique_id` is registered |
| `CheckInError` | A check-in/check-out rule is violated |

### Model validation errors

`ValueError` is used for invalid model construction or prompt parsing:

- blank required CLI field
- invalid date format
- invalid integer format
- future employee hire date
- non-positive visitor expected duration
- contractor end date before start date
- invalid registration person type

### CLI behavior

The CLI catches:
- `CheckInError`
- `DuplicatePersonError`
- `ValueError`
- `KeyboardInterrupt` during an action

It prints user-facing messages and returns to the menu.

---

## External Dependencies

### Runtime

None beyond Python standard library.

### Development

| Dependency | Version | Used for |
|---|---:|---|
| `pytest` | `>=8.0` | test execution |

---

## Concurrency Model

None. The app is single-process and interactive. State is stored in memory inside one `PersonnelRegistry` object.

Concurrency would matter only if multiple CLI sessions or processes shared a backing store. That is outside this app’s scope.

---

## Known Limitations

- No persistence; all data is lost on exit.
- No generated IDs; operators provide IDs manually.
- No edit/update workflow after registration.
- No deletion/deactivation workflow.
- No check-in/out audit log.
- No real authentication or authorization.
- Visitor warnings do not enforce policy; they only inform the operator.
- Search is simple substring matching, not structured filtering.
- CLI is menu-driven and not scriptable via command-line arguments.

---

## Design Patterns Used

| Pattern | Location | Purpose |
|---|---|---|
| Inheritance | `Person` → `Employee`, `Visitor`, `Contractor` | Model shared identity with specialized personnel types |
| Encapsulation | `PersonnelRegistry` | Centralize roster mutation and validation |
| Template-like extension | `search_tokens()` overrides | Let subclasses extend searchable fields |
| Service object | `PersonnelRegistry` | Coordinate models and enforce workflows |
| Defensive validation | model `__post_init__`, registry checks | Prevent invalid state transitions |
| DTO-like reporting | `emergency_headcount()` dictionaries | Return simple structured records to CLI |

-e 

---


# Interface Design Specification
## App 18 — Personnel
**Vault OS Group | Document 3 of 5**

---

## Invocation Syntax

### Module entry point

```bash
python -m personnel
```

### Convenience wrapper

```bash
python main.py
```

### Tests

```bash
python -m pytest personnel tests
```

---

## Command-Line Arguments

The application has no command-line flags or positional arguments. It launches directly into an interactive menu.

| Name | Type | Required | Default | Accepted values | Description |
|---|---|---:|---|---|---|
| N/A | N/A | N/A | N/A | N/A | No CLI arguments are parsed |

---

## Interactive Menu

When launched, the CLI prints a menu:

```text
Vault OS Personnel Registry
Manage employees, visitors, and contractors for the facility.

Menu
  1. Register a person
  2. Check someone in
  3. Check someone out
  4. View who is on-site
  5. Run emergency headcount
  6. View overstay report
  7. Search directory
  8. Lookup person by ID
  0. Exit
```

---

## Menu Command Reference

### `1` — Register a person

Prompts:

| Prompt | Type | Required | Accepted values | Description |
|---|---|---:|---|---|
| `Register employee, visitor, or contractor?` | string | Yes | `employee`, `visitor`, `contractor` | Selects subclass |
| `Unique ID` | string | Yes | Any non-empty string | Facility identifier |
| `Name` | string | Yes | Any non-empty string | Person name |
| `Contact info` | string | Yes | Any non-empty string | Contact field |

Employee-specific prompts:

| Prompt | Type | Required | Accepted values | Description |
|---|---|---:|---|---|
| `Department` | string | Yes | non-empty | Employee department |
| `Role title` | string | Yes | non-empty | Employee role |
| `Hire date` | date | Yes | `YYYY-MM-DD` | Cannot be future date |
| `Assigned keycard ID` | string | Yes | non-empty | Keycard reference |

Visitor-specific prompts:

| Prompt | Type | Required | Accepted values | Description |
|---|---|---:|---|---|
| `Host employee ID` | string | Yes | registered employee ID recommended | Host reference |
| `Visit purpose` | string | Yes | non-empty | Visit reason |
| `Expected duration in minutes` | int | Yes | positive integer | Used for overstay detection |

Contractor-specific prompts:

| Prompt | Type | Required | Accepted values | Description |
|---|---|---:|---|---|
| `Restricted areas` | CSV string | No | comma-separated text | Parsed into list |
| `Company name` | string | Yes | non-empty | Contractor company |
| `Contract start date` | date | Yes | `YYYY-MM-DD` | First active day |
| `Contract end date` | date | Yes | `YYYY-MM-DD` | Must be on/after start |

Output:

```text
Registered Employee Dana Holt (EMP-100).
Registered Visitor Nia Brooks (VIS-200).
Registered Contractor Avery Singh (CON-300).
```

---

### `2` — Check someone in

Prompts:

| Prompt | Type | Required | Default | Description |
|---|---|---:|---|---|
| `Unique ID to check in` | string | Yes | N/A | Registered person ID |
| `Current location (optional)` | string | No | `None` | Location attached to roster record |

Output:

```text
Dana Holt is now on-site.
```

Failure examples:
- unregistered person
- already on-site
- visitor host not registered
- visitor host not an employee
- visitor host not on-site
- contractor contract inactive

---

### `3` — Check someone out

Prompts:

| Prompt | Type | Required | Description |
|---|---|---:|---|
| `Unique ID to check out` | string | Yes | Registered person ID |

Output:

```text
EMP-100 checked out.
```

If an employee checks out while hosted visitors remain on-site:

```text
Warning: Visitor Remy Patel (VIS-203) is still on-site without host EMP-100.
```

---

### `4` — View who is on-site

No prompts.

Empty output:

```text
No one is currently on-site.
```

Populated output:

```text
On-site roster
- Employee: Dana Holt (EMP-100) at Lobby
- Visitor: Remy Patel (VIS-203) at Conference Room
```

---

### `5` — Run emergency headcount

No prompts.

Empty output:

```text
Emergency headcount is empty.
```

Populated output:

```text
Emergency headcount
Employees
- Dana Holt (EMP-100) at Front Desk
Contractors
- Skylar Dean (CON-301) at Mechanical Room
```

---

### `6` — View overstay report

No prompts.

Empty output:

```text
No visitors are currently overstaying.
```

Populated output:

```text
Overstay report
- Eva Tran (VIS-202), host EMP-100, checked in at 2026-04-12 09:00
```

---

### `7` — Search directory

Prompts:

| Prompt | Type | Required | Description |
|---|---|---:|---|
| `Search term` | string | Yes | Case-insensitive substring across search tokens |

Output:

```text
Search results
- Employee: Quinn (EMP-777)
```

Empty output:

```text
No matches found.
```

---

### `8` — Lookup person by ID

Prompts:

| Prompt | Type | Required | Description |
|---|---|---:|---|
| `Lookup ID` | string | Yes | Exact registered ID |

Output:

```text
Person record
Type: Employee
ID: EMP-100
Name: Dana Holt
Contact: dana.holt@example.com
On-site: Yes
Location: Lobby
Department: Operations
Role title: Facility Manager
Hire date: 2024-06-01
Keycard ID: KC-900
```

Missing output:

```text
No matching person found.
```

---

### `0` — Exit

Output:

```text
Goodbye.
```

---

## Public Python API

### Models

```python
from personnel import Employee, Visitor, Contractor, Person
from personnel import PersonnelRegistry
from personnel import CheckInError, DuplicatePersonError, PersonnelError
```

### `PersonnelRegistry.register(person) -> Person`

Registers a person in the directory.

Raises:
- `DuplicatePersonError` if `unique_id` already exists.

---

### `PersonnelRegistry.lookup(unique_id) -> Person | None`

Returns the registered person or `None`.

---

### `PersonnelRegistry.search(query) -> list[Person]`

Case-insensitive substring search across person-specific tokens. Blank queries return an empty list.

---

### `PersonnelRegistry.check_in(unique_id, location=None, checked_in_at=None) -> Person`

Checks a registered person into the live roster.

Raises:
- `CheckInError` for unknown ID
- `CheckInError` for double check-in
- `CheckInError` when visitor host rules are not satisfied
- `CheckInError` when contractor contract is inactive

---

### `PersonnelRegistry.check_out(unique_id) -> list[str]`

Checks a person out. Returns warnings. Employee checkout may warn about hosted visitors still on-site.

Raises:
- `CheckInError` for unknown ID
- `CheckInError` if the person is not currently on-site

---

### `PersonnelRegistry.who_is_on_site() -> list[Person]`

Returns current on-site personnel sorted by type, name, and ID.

---

### `PersonnelRegistry.emergency_headcount() -> dict[str, list[dict[str, str]]]`

Returns grouped emergency headcount records.

Example:

```python
{
    "Employee": [
        {"name": "Dana Holt", "id": "EMP-100", "location": "Front Desk"}
    ],
    "Contractor": [
        {"name": "Skylar Dean", "id": "CON-301", "location": "Mechanical Room"}
    ],
}
```

---

### `PersonnelRegistry.overstay_report(now=None) -> list[Visitor]`

Returns on-site visitors whose expected duration has been exceeded.

---

## Input Contract

- Dates must use ISO format: `YYYY-MM-DD`.
- Visitor expected duration must be a whole number and positive.
- Contractor end date must be on or after start date.
- Employee hire date cannot be in the future at construction time.
- Unique IDs must be unique within the registry.
- Visitor hosts must refer to registered employees for check-in.
- Contractor check-in date must fall inside the inclusive contract window.

---

## Output Contract

The CLI prints human-readable text. There is no JSON or file output.

Python methods return live model objects or simple data structures:
- `Person` subclasses
- `list[Person]`
- `list[str]`
- `dict[str, list[dict[str, str]]]`

---

## Exit Code Reference

The CLI does not explicitly call `sys.exit()` or return an integer. Normal completion through menu option `0` exits with Python’s default success behavior.

| Scenario | Process result |
|---|---|
| Option `0` selected | normal termination |
| Handled validation error | menu continues |
| KeyboardInterrupt inside action | action canceled; menu continues |
| Unhandled top-level interruption outside action | not explicitly handled by `run_cli()` |

---

## Error Output Behavior

Handled errors are printed as:

```text
Error: <message>
```

Action cancellation is printed as:

```text
Action canceled.
```

Invalid menu options are printed as:

```text
Invalid option. Try again.
```

---

## Environment Variables

None.

---

## Configuration Files

None.

---

## Side Effects

- Mutates in-memory registry state.
- Mutates `Person` objects during check-in/check-out.
- Prints to stdout.
- Reads from stdin.
- Does not write files.
- Does not persist state across process exits.

---

## Usage Examples

### Basic — register and check in an employee

```text
$ python -m personnel
Choose an option: 1
Register employee, visitor, or contractor? employee
Unique ID: EMP-100
Name: Dana Holt
Contact info: dana@example.com
Department: Operations
Role title: Facility Manager
Hire date (YYYY-MM-DD): 2024-06-01
Assigned keycard ID: KC-900
Registered Employee Dana Holt (EMP-100).

Choose an option: 2
Unique ID to check in: EMP-100
Current location (optional): Lobby
Dana Holt is now on-site.
```

---

### Advanced — visitor check-in with host present

```text
Choose an option: 2
Unique ID to check in: EMP-100
Current location (optional): Lobby
Dana Holt is now on-site.

Choose an option: 2
Unique ID to check in: VIS-200
Current location (optional): Conference Room
Nia Brooks is now on-site.
```

---

### Edge case — employee leaves hosted visitor on-site

```text
Choose an option: 3
Unique ID to check out: EMP-100
EMP-100 checked out.
Warning: Visitor Remy Patel (VIS-203) is still on-site without host EMP-100.
```

---

### Intentional failure — visitor host is absent

```text
Choose an option: 2
Unique ID to check in: VIS-200
Current location (optional): Conference Room
Error: Visitor VIS-200 cannot check in until host EMP-100 is on-site.
```

-e 

---


# Runbook
## App 18 — Personnel
**Vault OS Group | Document 4 of 5**

---

## Prerequisites

- Python 3.10 or newer
- `pip`
- Terminal capable of interactive stdin/stdout
- No runtime third-party packages

Development/testing:
- `pytest>=8.0`

---

## Installation Procedure

### Editable install with dev dependencies

```bash
git clone https://github.com/PrincetonAfeez/Personnel
cd Personnel
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install:

```bash
pip install -e ".[dev]"
```

### Install test dependencies only

```bash
pip install -r requirements.txt
```

---

## Configuration Steps

No configuration files or environment variables are required.

The app starts with an empty in-memory registry every time it launches.

---

## Standard Operating Procedures

### Start the app

```bash
python -m personnel
```

Alternative:

```bash
python main.py
```

---

### Register an employee

1. Choose menu option `1`.
2. Enter `employee`.
3. Provide ID, name, contact, department, role title, hire date, and keycard ID.
4. Confirm registration message.

---

### Register a visitor

1. Choose menu option `1`.
2. Enter `visitor`.
3. Provide ID, name, contact, host employee ID, purpose, and expected duration.
4. Confirm registration message.

Important: the visitor can be registered before the host is on-site, but cannot check in until the host is present.

---

### Register a contractor

1. Choose menu option `1`.
2. Enter `contractor`.
3. Provide ID, name, contact, restricted areas, company name, contract start date, and contract end date.
4. Confirm registration message.

Important: contractor check-in is allowed only inside the contract window.

---

### Check someone in

1. Choose menu option `2`.
2. Enter the registered unique ID.
3. Optionally provide a current location.
4. Confirm the “now on-site” message.

---

### Check someone out

1. Choose menu option `3`.
2. Enter the registered unique ID.
3. Review any warnings, especially hosted visitor warnings.

---

### View on-site roster

```text
Menu option 4
```

Use this for routine operational awareness.

---

### Run emergency headcount

```text
Menu option 5
```

Use this during drills or simulated incident response.

---

### View overstay report

```text
Menu option 6
```

Use this to detect visitors who have exceeded their expected duration.

---

### Search directory

```text
Menu option 7
```

Useful search terms:
- person ID
- name
- contact
- department
- role
- keycard ID
- host employee ID
- visit purpose
- company
- restricted area

---

### Lookup a person by ID

```text
Menu option 8
```

Use when the exact ID is known.

---

## Health Checks

### Package import check

```bash
python -c "import personnel; print(personnel.__all__)"
```

Expected: public exports include `Employee`, `Visitor`, `Contractor`, and `PersonnelRegistry`.

---

### Module entry check

```bash
python -m personnel
```

Expected: menu appears. Select `0` to exit.

---

### Root wrapper check

```bash
python main.py
```

Expected: same menu appears. Select `0` to exit.

---

### Test suite check

```bash
python -m pytest personnel tests
```

Expected: tests pass.

---

## Expected Output Samples

### Startup

```text
Vault OS Personnel Registry
Manage employees, visitors, and contractors for the facility.

Menu
  1. Register a person
  2. Check someone in
  3. Check someone out
  4. View who is on-site
  5. Run emergency headcount
  6. View overstay report
  7. Search directory
  8. Lookup person by ID
  0. Exit
```

---

### Empty roster

```text
No one is currently on-site.
```

---

### On-site roster

```text
On-site roster
- Employee: Dana Holt (EMP-100) at Lobby
- Visitor: Marcus Lee (VIS-201) at Conference Room
```

---

### Emergency headcount

```text
Emergency headcount
Employees
- Dana Holt (EMP-100) at Front Desk
Contractors
- Skylar Dean (CON-301) at Mechanical Room
```

---

### Overstay report

```text
Overstay report
- Eva Tran (VIS-202), host EMP-100, checked in at 2026-04-12 09:00
```

---

## Known Failure Modes

### Duplicate registration

Cause: registering a person whose ID already exists.

Output:

```text
Error: EMP-100 is already registered.
```

Recovery: choose a unique ID or lookup the existing record.

---

### Visitor host not registered

Cause: visitor’s `host_employee_id` does not refer to a registered employee.

Output:

```text
Error: Visitor VIS-200 requires a registered employee host.
```

Recovery: register the employee host first.

---

### Visitor host not on-site

Cause: visitor tries to check in before the host employee has checked in.

Output:

```text
Error: Visitor VIS-200 cannot check in until host EMP-100 is on-site.
```

Recovery: check in the host employee, then check in the visitor.

---

### Host reference points to contractor

Cause: visitor references a registered contractor ID as host.

Output:

```text
Error: Visitor VIS-900 requires a registered employee host.
```

Recovery: update the visitor record is not supported in this app; register a corrected visitor record with an employee host.

---

### Contractor contract inactive

Cause: contractor check-in attempted before start date or after end date.

Output:

```text
Error: Contractor CON-300 cannot check in because the contract is inactive.
```

Recovery: verify contract dates. The current app has no edit workflow; re-registering with a new ID is the practical demo workaround.

---

### Double check-in

Cause: person is already on-site.

Output:

```text
Error: EMP-100 is already on-site.
```

Recovery: check the person out before checking in again.

---

### Check-out when absent

Cause: person is registered but not currently on-site.

Output:

```text
Error: EMP-100 is not currently on-site.
```

Recovery: verify roster with menu option `4`.

---

### Invalid date format

Cause: entering date in a format other than `YYYY-MM-DD`.

Output:

```text
Error: Dates must use YYYY-MM-DD format.
```

Recovery: retry using ISO date format.

---

## Troubleshooting Decision Tree

```text
Problem: CLI will not start
├─ Is Python 3.10+ installed?
│  ├─ No → install/activate a compatible Python
│  └─ Yes
├─ Are you in the repo root?
│  ├─ No → cd into Personnel/
│  └─ Yes
├─ Does "python -m personnel" work?
│  ├─ Yes → use module entry
│  └─ No → run "pip install -e .[dev]" and retry

Problem: person cannot check in
├─ Is the ID registered?
│  ├─ No → register person first
│  └─ Yes
├─ Is the person already on-site?
│  ├─ Yes → check out first
│  └─ No
├─ Is the person a Visitor?
│  ├─ Yes → verify host exists, is Employee, and is on-site
│  └─ No
├─ Is the person a Contractor?
│  ├─ Yes → verify date is inside contract window
│  └─ No → inspect error message

Problem: emergency headcount looks wrong
├─ Did everyone check in through registry.check_in / menu option 2?
│  ├─ No → direct object mutation can desync state
│  └─ Yes
├─ Did people check out?
│  ├─ Yes → they should not appear
│  └─ No → inspect on-site roster
```

---

## Dependency Failure Handling

Runtime has no third-party dependency failure path.

For test failures related to pytest:

```bash
pip install -r requirements.txt
python -m pytest personnel tests
```

If `pytest` is unavailable, install the dev extra:

```bash
pip install -e ".[dev]"
```

---

## Recovery Procedures

### Reset app state

Because the app is in-memory, exiting and restarting clears the registry:

```text
0. Exit
python -m personnel
```

---

### Recover from incorrect data entry

The current app does not support editing or deleting records. For demo use:

1. Register a corrected person with a new ID.
2. Avoid using the incorrect record.
3. Restart the app to clear all state if needed.

---

### Recover from roster inconsistency during future integration

Use the restore hook only in integration/persistence code:

```python
registry.restore_onsite_snapshot(
    unique_id="EMP-100",
    checked_in_at=stored_datetime,
    location="Lobby",
)
```

This is not part of normal CLI operation.

---

## Logging Reference

The app does not maintain a persistent event log.

Observable state is available through:
- current on-site roster
- emergency headcount
- overstay report
- lookup details

Warnings are printed directly during checkout when hosted visitors remain on-site.

---

## Maintenance Notes

- Keep model validation in `models.py`.
- Keep workflow validation in `registry.py`.
- Keep presentation and prompting in `cli.py`.
- Do not add direct CLI mutations of `Person.on_site`; route all presence changes through `PersonnelRegistry`.
- If persistence is added later, store both directory records and roster presence state.
- If integration with the Access app is added later, treat `assigned_keycard_id` as a link, not as a replacement for personnel identity.

-e 

---


# Lessons Learned
## App 18 — Personnel
**Vault OS Group | Document 5 of 5**

---

## Project Summary

Personnel is the Vault OS human-roster subsystem. It models employees, visitors, and contractors with a shared base class and type-specific validation, then uses `PersonnelRegistry` to enforce registration, check-in, check-out, host, contractor, roster, overstay, and headcount behavior.

The project’s main architectural value is that it separates object identity from facility presence. A person can be registered without being on-site. A person can be on-site only after the registry validates the transition. This is the key modeling improvement over a simple list of names.

---

## Original Goals vs. Actual Outcome

**Original goal:** Build a facility personnel registry with employees, visitors, contractors, check-in/check-out, search, overstay reporting, and emergency headcount.

**Actual outcome:** The app meets that goal with a clean package layout and meaningful tests. It includes:
- `Person` base class
- `Employee`, `Visitor`, `Contractor`
- `PersonnelRegistry`
- interactive CLI
- public package exports
- module entry point
- pytest suite covering models, registry behavior, CLI helpers, package exports, and integration flows

The implementation stays inside the intended Day 18 scope. It does not add persistence, network services, authentication, or a database.

---

## Technical Decisions That Paid Off

### Registry-mediated state changes

The most important decision was routing check-in and check-out through `PersonnelRegistry`. This made it possible to enforce visitor host rules and contractor date rules without scattering those checks across the CLI.

### Separate directory and on-site roster

Keeping `_directory` and `_on_site_roster` separate made the mental model clearer. The directory answers “Who is known to the facility?” The roster answers “Who is physically inside right now?”

### `search_tokens()` extension point

Letting each subclass extend its own searchable fields avoided a brittle registry search function. The registry can simply ask every person for tokens.

### Package structure

Compared with a single-file script, the `personnel/` package layout is stronger:
- `models.py` for data and validation
- `registry.py` for workflows
- `cli.py` for presentation
- `__main__.py` for module execution
- `__init__.py` for public exports

This is a clear step toward maintainable app design.

---

## Technical Decisions That Created Debt

### In-memory-only state

The app is easy to understand, but every session starts from scratch. That is acceptable for the learning scope, but it limits realism.

### No audit trail

Check-in and check-out mutate current state, but historical movement is not recorded. A real facility would need an immutable event log.

### No edit/delete workflows

Incorrectly entered personnel cannot be fixed through the CLI. Restarting clears state, but that is not a realistic operational workflow.

### ID ownership left to operator

The app validates duplicate IDs but does not generate IDs or enforce ID formats. This keeps the implementation simple, but shifts consistency to the user.

### Underscore methods still callable

`_record_check_in()` and `_record_check_out()` are intended for registry use, but Python does not enforce private methods. The design relies on convention.

---

## What Was Harder Than Expected

### Visitor host rules

The visitor rule has more nuance than it first appears. It is not enough for the host ID to exist. The host must:
1. exist in the registry,
2. be an `Employee`, and
3. currently be on-site.

The test for a contractor being used as a host confirms why type checking matters.

### Presence state synchronization

The app stores on-site state both on the `Person` object and in the registry roster. That gives fast roster access but means transitions must update both consistently.

### Time-dependent visitor overstay logic

The visitor overstay check depends on check-in time and current time. Tests need explicit `datetime` values to avoid flaky behavior.

---

## What Was Easier Than Expected

### Emergency headcount

Once the on-site roster existed, emergency headcount was straightforward. It simply groups current people by `person_type` and returns name, ID, and location.

### Search

Search became simple after each class exposed `search_tokens()`. There was no need for a query parser.

### CLI formatting

Because the domain objects expose enough structured data, CLI formatting functions could stay small and mostly presentation-focused.

---

## Python-Specific Learnings

- `dataclass(slots=True)` is useful for lightweight domain models with fixed fields.
- `field(default=False, init=False)` is a clean way to create internal state that is not constructor input.
- `date.fromisoformat()` is enough for strict `YYYY-MM-DD` parsing.
- `isinstance()` is appropriate when workflow rules differ by subclass.
- Returning tuples/lists from controlled methods is safer than exposing internal dictionaries directly.
- `pytest` and `unittest` can coexist, though consistency would be cleaner long-term.

---

## Architecture Insights

This project demonstrates a useful boundary:

- Models know what they are.
- Registry knows what is allowed.
- CLI knows how to ask and print.

That separation is the main architectural win. The `Person` classes do not decide whether they may enter the facility. The registry makes that decision because it can inspect the broader system state: who is registered, who is on-site, and whether a host is present.

The app also shows that inheritance works best when the subclasses truly share identity and lifecycle. Employees, visitors, and contractors are all people; their differences are rules and fields, not separate systems.

---

## Testing Gaps

The existing tests cover many important behaviors:
- model validation
- exception hierarchy
- host validation
- contractor active windows
- duplicate registration
- double check-in
- checkout warnings
- overstay reports
- headcount grouping
- CLI prompt helpers and menu behavior
- package exports and module entry point

Remaining useful tests:
1. Check that `restore_onsite_snapshot()` restores both the person state and roster membership.
2. Check emergency headcount ordering in mixed-type rosters.
3. Add a CLI test for a full visitor-host happy path.
4. Add tests for blank search tokens and unusual casing across all subclasses.
5. Add tests for multiple hosted visitors warning on employee checkout.
6. Add tests around exact overstay boundary behavior from the registry level, not just the model level.

---

## Reusable Patterns Identified

- **Registry as workflow boundary:** Use a service object to mutate models only after validation.
- **Subclass search tokens:** Let models describe their searchable fields.
- **On-site roster as index:** Keep a dedicated live index for operational queries.
- **Warning return values:** Return warnings from operations that should proceed but require operator attention.
- **Package export list:** Use `__all__` to define the supported public API.
- **Module entry point:** Use `__main__.py` so users can run the package directly.

---

## If I Built This Again

1. **Add an event log** for registration, check-in, checkout, warnings, and failed attempts.
2. **Generate IDs** for employees, visitors, and contractors with type prefixes.
3. **Add persistence** using JSON first, then SQLite if the integration layer needs queries.
4. **Add update workflows** for contact info, contractor dates, visitor purpose, and restricted areas.
5. **Add explicit visitor release policy** when a host leaves.
6. **Integrate with Access** by validating `assigned_keycard_id` against the keycard registry.
7. **Add non-interactive CLI subcommands** for testability and scripting.
8. **Separate restore methods into a persistence adapter** so normal domain classes do not expose integration hooks.

---

## Open Questions

- Should a visitor be automatically checked out if the host checks out?
- Should contractors be allowed to remain on-site after a contract expires if they checked in before expiry?
- Should employees have departments modeled as enums or free text?
- Should visitors be allowed to change hosts mid-visit?
- Should overstay create an alert record rather than only appearing in a report?
- Should search return current on-site status alongside each result?
- Should the personnel registry own ID generation?

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation) and Article 6 (verification behavior) for App 18.*
