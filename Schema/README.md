# Schema folder

This folder contains simple JSON Schema files for the `Personnel` repository domain models.

## Files

- `person.schema.json` — base shared person fields
- `employee.schema.json` — employee records
- `visitor.schema.json` — visitor records
- `contractor.schema.json` — contractor records
- `personnel.schema.json` — union schema for any supported personnel record

## Notes

- Schemas use JSON Schema Draft 2020-12.
- Dates use `format: date`.
- Timestamps use `format: date-time`.
- `on_site`, `checked_in_at`, and `location` are included as optional runtime state fields because the repository models expose them as tracked state.
