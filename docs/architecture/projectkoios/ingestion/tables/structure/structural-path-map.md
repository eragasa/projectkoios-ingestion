# Table-structure structural path map

This is the reviewed source inventory for the table-structure hierarchy
migration. Paths are relative to `src/python/projectkoios/ingestion`. Removed
paths are not retained as aliases or re-export facades.

| Removed path | Direct owner path |
|---|---|
| `tables/structure/bounds.py` | `tables/structure/limits/definition.py` |
| `tables/structure/limit_error.py` | `tables/structure/limits/error.py` |
| `tables/structure/cell_derivation.py` | `tables/structure/derivation/cell.py` |
| `tables/structure/column_derivation.py` | `tables/structure/derivation/column.py` |
| `tables/structure/continuation_derivation.py` | `tables/structure/derivation/continuation.py` |
| `tables/structure/region_derivation.py` | `tables/structure/derivation/region.py` |
| `tables/structure/derivation.py` | `tables/structure/derivation/structure.py` |
| `tables/structure/cell_validation.py` | `tables/structure/validation/cell.py` |
| `tables/structure/column_validation.py` | `tables/structure/validation/column.py` |
| `tables/structure/continuation_validation.py` | `tables/structure/validation/continuation.py` |
| `tables/structure/row_validation.py` | `tables/structure/validation/row.py` |
| `tables/structure/validation.py` | `tables/structure/validation/structure.py` |
| `tables/structure/cell_role.py` | `tables/structure/role/cell.py` |
| `tables/structure/evidence_status.py` | `tables/structure/status/evidence.py` |
| `tables/structure/source_record.py` | `tables/structure/record/source.py` |
| `tables/structure/warning_specification.py` | `tables/structure/specification/warning.py` |
| `tables/structure/reconstruction.py` | `tables/structure/reconstructor/base.py` |
| `tables/structure/reconstructor.py` | `tables/structure/reconstructor/deterministic.py` |
| `tables/structure/structure.py` | `tables/structure/model.py` |

## Semantic review

- Derivation and validation records are grouped by their primary roles; the
  specific cell, column, continuation, region, row, or whole-structure owner is
  the leaf name.
- Hard ceilings and their domain error share the plural `limits/` owner. The
  region header matcher moved with the region derivation rather than remaining
  in the limits definition.
- Qualified immutable records are grouped role-first under `role/`, `status/`,
  `record/`, and `specification/`.
- The nominal reconstruction boundary and deterministic implementation share
  the `reconstructor/` owner while remaining separate defining leaves.
- Unqualified primary records such as `TableCell`, `TableColumn`, `TableRow`,
  `TableStructureRequest`, and `TableStructureResult` remain in direct noun
  modules. `TableStructure` uses `model.py` because `structure/structure.py`
  would repeat its owning package name.
- Package initializers are docstring-only ownership markers. Consumers import
  definitions from their direct leaves; no compatibility facade is retained.
- Contract versions, stable identity inputs, field order, serialized bytes,
  processing bounds, warning semantics, and proposal-only status are unchanged.
