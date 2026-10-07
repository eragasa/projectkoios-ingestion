# `projectkoios.ingestion.pdf.batch` implementation

## Purpose

The current root `batch.py` contains two PDF-specific records:
`PdfBatchItem` and `PdfBatchPlan`. Their root location hides PDF ownership and
encourages imports through the broad `projectkoios.ingestion` facade.

The target package makes that ownership explicit without absorbing command,
corpus, extraction, publication, or orchestration behavior:

```text
pdf/
  batch/
    __init__.py
    item.py
    plan.py
    json.py
    limits/
      __init__.py
      definition.py
      error.py
```

Both package initializers are docstring-only ownership markers. Consumers
import each record and JSON boundary from its defining leaf. Neither
`projectkoios.ingestion` nor `projectkoios.ingestion.pdf` re-exports the moved
records.

## Ownership

### `item.py`

`PdfBatchItem` owns one immutable portable source declaration:

- managed `source_id`;
- normalized relative PDF path;
- normalized relative output-directory path;
- lowercase SHA-256 digest;
- positive byte size; and
- optional bounded locator.

The item owns record invariants only. JSON object keys, raw-string path
normalization, and mapping reconstruction belong to
`PdfBatchPlanJsonContract`.

### `plan.py`

`PdfBatchPlan` owns one immutable ordered tuple of `PdfBatchItem` values. It
validates:

- schema version `1`;
- a non-empty tuple;
- the maximum item count;
- every item is a `PdfBatchItem` value;
- unique source IDs;
- unique PDF paths; and
- unique output directories.

Uniqueness validation remains private to the plan.

### `json.py`

`PdfBatchPlanJsonContract` specializes `ingestion.json.contract.JsonContract`
for the exact version-1 PDF batch schema. It owns item-object decoding,
plan-object decoding, record-to-value projection, pretty JSON formatting, and
terminal-newline replay. It composes shared bounded parsing and serialization
rather than calling `json.loads()` or `json.dumps()` directly.

### `limits`

`limits/definition.py` owns the two existing resource bounds:

- `MAX_PDF_BATCH_ITEMS = 256`; and
- `MAX_PDF_BATCH_TEXT_CHARACTERS = 4_096` for each bounded identity,
  path, or locator field.

`limits/error.py` owns `PdfBatchLimitError`, a `ValueError` subclass. It is used
only when one of those resource bounds is exceeded. Structural, type, path,
digest, uniqueness, and schema failures remain ordinary `ValueError` values.
Exact existing failure messages remain unchanged.

## Authority and lifecycle

A `PdfBatchPlan` is portable deterministic input, not a Workflow definition and
not execution authority. It does not own retries, leases, tokens, guards,
approvals, concurrency, checkpoints, stop propagation, or acceptance.

The plan does not read or hash a file. Its SHA-256 and byte-size fields bind an
external source declaration that an effectful consumer must verify before use.
The output directory is a portable relative target declaration, not permission
to overwrite or publish.

The ordered item tuple is significant and remains stable through JSON replay.
The plan introduces no new stable identity, timestamp, metadata bag, evidence
field, or compatibility version.

## Serialization compatibility

The migration preserves exact version-1 serialization:

- field order remains `schema_version`, then `items`;
- each item field order remains `source_id`, `pdf_path`, `output_directory`,
  `sha256`, `byte_size`, then `locator`;
- UTF-8 JSON remains indented by two spaces;
- the terminal newline remains present;
- item order remains unchanged; and
- parsing serialized plan bytes reconstructs the same plan record.

No legacy decoder, module alias, root re-export, or compatibility facade is
added. Stored plan bytes remain valid because the wire contract does not encode
Python module paths. The version-1 wire format is retained as stable; the
repository-internal Python import path is explicitly treated as unstable for
this hierarchy correction.

This hierarchy slice does not opportunistically strengthen duplicate-key or
JSON-constant parsing. Such parser hardening would be a separate wire-format
change with replay evidence.

## Consumer boundaries

Existing consumers are updated atomically:

- corpus preparation and validation;
- PDF batch command execution;
- equation batch command execution;
- transcript-batch planning and execution;
- selective OCR and OCR-reconciliation plans;
- repository scripts; and
- tests.

`batch_cli.py` remains at its current path for this slice. It is not a thin CLI:
it also owns resolution, filesystem safety, and summary behavior and imports an
extraction helper from `cli.py`. Moving it safely requires a later architectural
reduction. Its console-script target therefore remains unchanged while its
record imports move to direct leaves.

## Test ownership

The broad `tests/test__PdfBatchIngestion.py` currently mixes plan-record behavior with
command execution and filesystem safety. It is replaced by:

```text
tests/projectkoios/ingestion/pdf/batch/
  fixture.py
  test__PdfBatchItem.py
  test__PdfBatchPlan.py
  test__PdfBatchPlanJsonContract.py
  test__PdfBatchCommand.py
```

A frozen fixture builder owns the shared source payloads and plan construction.
Item value and path invariants belong in `test__PdfBatchItem.py`; ordered plan
and uniqueness invariants belong in `test__PdfBatchPlan.py`; exact JSON shape,
limits, parsing, formatting, and replay belong in
`test__PdfBatchPlanJsonContract.py`. Command dry-run, application,
source-integrity, symlink, no-overwrite, and preflight behavior belong in
`test__PdfBatchCommand.py`.

## Migration sequence

1. Review and accept this ownership design and exact structural path map.
2. Add the docstring-only package markers, limits, item, plan, and JSON leaves.
3. Specialize the reviewed `ingestion.json` boundary without changing
   constructor field order or serialized bytes.
4. Update every production, script, workflow, and test consumer to import the
   direct defining leaf.
5. Remove `PdfBatchItem` and `PdfBatchPlan` from the root facade.
6. Delete `projectkoios.ingestion.batch`; add no compatibility module.
7. Split the broad PDF-batch test by plan and command concerns.
8. Extend hierarchy-smell and clean-wheel checks to the new leaves.
9. Add explicit boundary tests for exactly 256 items, 257-item rejection,
   exactly 4,096 text characters, and 4,097-character rejection. Parameterized
   choices must explain each selected boundary case inline.
10. Run focused tests, Ruff, Mypy, the full test suite, Sphinx
    warnings-as-errors, lock verification, source/wheel builds, clean-wheel
    imports, command smoke, and `git diff --check`.
11. Compare representative plan bytes before and after the move.

## Non-goals

This slice does not:

- move or redesign `batch_cli.py`;
- change a console-script name or target;
- actionize batch execution;
- create a Pipeline or Workflow contract;
- alter PDF extraction, corpus, OCR, equation, or transcript behavior;
- change plan schema, IDs, paths, limits, messages, or JSON bytes; or
- reorganize the broader root/CLI surface.
