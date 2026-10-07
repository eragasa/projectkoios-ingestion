# PDF batch structural path map

This is the exact reviewed map for the bounded PDF-batch record migration.
Paths are relative to the repository root. Removed source paths are not retained
as aliases or re-export facades.

## Production source

| Removed path or responsibility | Direct owner path | Ownership |
|---|---|---|
| `src/python/projectkoios/ingestion/batch.py` — `PdfBatchItem` invariants | `src/python/projectkoios/ingestion/pdf/batch/item.py` | One immutable checksummed PDF source declaration record |
| `src/python/projectkoios/ingestion/batch.py` — `PdfBatchPlan` invariants and uniqueness | `src/python/projectkoios/ingestion/pdf/batch/plan.py` | Ordered bounded plan record |
| `src/python/projectkoios/ingestion/batch.py` — item mapping decode, plan parse, and plan serialization | `src/python/projectkoios/ingestion/pdf/batch/json.py` | `PdfBatchPlanJsonContract` specialization and exact version-1 JSON bytes |
| `src/python/projectkoios/ingestion/batch.py` — `_MAX_BATCH_ITEMS` and `_MAX_IDENTITY_LENGTH` | `src/python/projectkoios/ingestion/pdf/batch/limits/definition.py` | PDF-batch item-count and text-length bounds |
| `src/python/projectkoios/ingestion/batch.py` — limit rejection through generic `ValueError` | `src/python/projectkoios/ingestion/pdf/batch/limits/error.py` | Typed `PdfBatchLimitError` compatible with `ValueError` |
| no package marker | `src/python/projectkoios/ingestion/pdf/batch/__init__.py` | Docstring-only PDF-batch namespace |
| no limits package marker | `src/python/projectkoios/ingestion/pdf/batch/limits/__init__.py` | Docstring-only limits namespace |
| root exports for `PdfBatchItem` and `PdfBatchPlan` in `src/python/projectkoios/ingestion/__init__.py` | direct imports from `pdf/batch/item.py` and `pdf/batch/plan.py` | No compatibility facade |

`src/python/projectkoios/ingestion/batch_cli.py` is retained in this slice. Its
imports change, but its path, console entry point, command behavior, and output
remain unchanged.

## Tests

| Removed path | Direct owner path | Ownership |
|---|---|---|
| `tests/test__PdfBatchIngestion.py` — shared payload and plan setup | `tests/projectkoios/ingestion/pdf/batch/fixture.py` | Frozen OOP PDF-batch fixture builder |
| `tests/test__PdfBatchIngestion.py` — item value/path cases | `tests/projectkoios/ingestion/pdf/batch/test__PdfBatchItem.py` | Source declaration record invariants |
| `tests/test__PdfBatchIngestion.py` — order, count, and uniqueness cases | `tests/projectkoios/ingestion/pdf/batch/test__PdfBatchPlan.py` | Plan record invariants |
| `tests/test__PdfBatchIngestion.py` — JSON parsing, serialization, and replay cases | `tests/projectkoios/ingestion/pdf/batch/test__PdfBatchPlanJsonContract.py` | Typed JSON boundary |
| `tests/test__PdfBatchIngestion.py` — command planning, execution, integrity, symlink, and preflight cases | `tests/projectkoios/ingestion/pdf/batch/test__PdfBatchCommand.py` | Effectful command boundary |

All other tests update imports in place unless their primary tested owner is
already part of another separately reviewed hierarchy slice.

## Documentation

| New path | Ownership |
|---|---|
| `docs/architecture/projectkoios/ingestion/pdf/batch/index.md` | Package scope and contents |
| `docs/architecture/projectkoios/ingestion/pdf/batch/implementation.md` | Invariants, boundaries, migration, and validation |
| `docs/architecture/projectkoios/ingestion/pdf/batch/schematic.md` | Dependency direction |
| `docs/architecture/projectkoios/ingestion/pdf/batch/structural-path-map.md` | Exact source and test map |

## Prohibited compatibility paths

The migration does not create any of the following:

```text
src/python/projectkoios/ingestion/batch.py
src/python/projectkoios/ingestion/pdf/batch/batch.py
src/python/projectkoios/ingestion/pdf/batch/pdf_batch.py
```

Package initializers remain docstring-only and export no moved names.
