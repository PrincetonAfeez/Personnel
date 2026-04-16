# Vault OS — Personnel

**Secure facility management simulator — employee, visitor, and contractor registry.**

Language: **Python** (standard library only at runtime).

## Overview

Vault OS is a class-based simulation of a secure facility (museum, data center, bank vault, and so on). 

The design focus is **OOP**: a shared `Person` base, specialized subclasses, and a **`PersonnelRegistry`** that keeps both the full directory and the live on-site roster.

## Features

- **Person** base: unique ID, name, contact info, on-site state (updated through the registry).
- **Employee**: department, role, hire date, keycard ID; hire date cannot be in the future at creation.
- **Visitor**: host employee ID, visit purpose, expected duration; `is_overstaying()` vs check-in time.
- **Contractor**: company, contract window, restricted areas; `is_contract_active()` for a given date.
- **PersonnelRegistry**: `register`, `check_in`, `check_out`, `who_is_on_site`, `lookup`, `search`, `emergency_headcount`, `overstay_report`; check-in rules vary by type (visitor needs on-site employee host; contractor must be inside the contract window).
- Duplicate registration and double check-in are rejected; employee checkout can warn if hosted visitors remain on-site.
- **CLI**: register, check in/out, roster, headcount, overstay report, search, lookup.

## Requirements

- Python **3.10+**

## Install (editable)

From this directory:

```bash
pip install -e ".[dev]"
```

Or install test dependencies only:

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m personnel
```

Alternate entry point:

```bash
python main.py
```

## Tests

```bash
python -m pytest personnel tests
```

Test layout:

| File | Focus |
|------|--------|
| `tests/test_personnel.py` | Registry integration (unittest) |
| `tests/test_models.py` | `personnel.models` |
| `tests/test_registry.py` | `personnel.registry` |
| `tests/test_cli.py` | `personnel.cli` |
| `tests/test_init_and_main.py` | Package exports and `personnel.__main__` |

## Project layout

```
Personnel/
├── personnel/
│   ├── __init__.py      # Public exports
│   ├── __main__.py      # `python -m personnel`
│   ├── models.py        # Person, Employee, Visitor, Contractor, errors
│   ├── registry.py      # PersonnelRegistry
│   └── cli.py           # Interactive CLI
├── tests/
├── main.py              # CLI wrapper
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Specification context

Each Day app is scoped for a focused build: real use of **classes, inheritance, and encapsulation**, deliberate design choices, and explainable tradeoffs—not a full production access-control product.
