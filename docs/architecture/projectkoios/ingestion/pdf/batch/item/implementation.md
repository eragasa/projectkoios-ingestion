# `pdf.batch.item` implementation

## Public record

`item.py` defines one frozen dataclass, `PdfBatchItem`, with this field order:

1. `source_id: str`
2. `pdf_path: PurePosixPath`
3. `output_directory: PurePosixPath`
4. `sha256: str`
5. `byte_size: int`
6. `locator: str | None = None`

The order is retained because the plan serializer emits these values in the
same established order.

## Invariants

Construction requires:

- `source_id` to be non-empty and no longer than
  `MAX_PDF_BATCH_TEXT_CHARACTERS`;
- both paths to be `PurePosixPath` values;
- both paths to be relative, non-empty, normalized, and free of `..`, empty,
  and `.` components;
- `pdf_path` to have a case-insensitive `.pdf` suffix;
- `sha256` to satisfy `SHA256Hash.is_canonical()`;
- `byte_size` to be a positive integer with `bool` rejected; and
- `locator`, when present, to be a non-empty bounded string.

Direct construction also bounds each path's `as_posix()` text. Raw JSON path
strings receive the additional lexical round-trip check in
`PdfBatchPlanJsonContract` before `PurePosixPath` construction.

Resource-bound failures raise `PdfBatchLimitError`. Type, emptiness, path,
suffix, digest, and value-shape failures remain `ValueError` with their
established messages.

## Authority boundary

The item records claimed SHA-256 and byte-size evidence; it does not produce or
verify that evidence. Effectful consumers must read the source safely and check
both values before extraction. Likewise, `output_directory` names a portable
relative target but grants no overwrite or publication authority.

The record carries no timestamp, metadata bag, workflow token, acceptance
state, or inferred lifecycle. It has no independent stable ID because the
version-1 wire format has never defined one.

## Dependencies

The module may depend only on:

- standard-library dataclass and portable-path types;
- `projectkoios.ingestion.sha256.hash.SHA256Hash`;
- `pdf.batch.limits.definition`; and
- `pdf.batch.limits.error`.

It must not import `ingestion.json`, command, corpus, extraction, adapter,
publication, or Workflow modules.
