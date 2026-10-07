# `pdf.batch.json` implementation

`PdfBatchPlanJsonContract` is a stateless concrete specialization of
`ingestion.json.contract.JsonContract[PdfBatchPlan]`.

## JSON shape

The document root contains exactly:

```text
schema_version
items
```

Each item object contains only:

```text
source_id
pdf_path
output_directory
sha256
byte_size
locator
```

Unknown or missing fields are rejected. `locator` may be `null`; all other
fields retain their established required scalar types. Raw path strings are
bounded and must round-trip exactly through `PurePosixPath.as_posix()` before an
item record is constructed.

## Formatting

Serialization preserves existing bytes:

- `ensure_ascii=False`;
- two-space indentation;
- domain insertion order rather than key sorting;
- one terminal newline; and
- item tuple order.

The concrete contract declares a PDF-plan byte limit before implementation.
That limit must accept all inventoried plans, reject limit-plus-one input before
parsing, and remain within generic hard ceilings.

## Reconstruction and serialization replay

Parsing uses the shared strict bounded `JsonParser`; it therefore rejects
malformed UTF-8, excessive depth/items/strings/numeric tokens, duplicate keys,
non-RFC constants, and non-finite numbers before reconstruction.

`from_json_value()` validates root and item shapes, creates `PdfBatchItem`
records, then creates `PdfBatchPlan`. Constructor validation remains
authoritative for record invariants.

The contract does not require arbitrary parsed input bytes to be canonical.
The existing parser accepts semantically valid whitespace and key-order
variations, so parse-time byte equality would be a separate compatibility
change. Instead, migration replay proves that the old and new serializers emit
identical bytes for the same plan and that parsing those bytes reconstructs the
same record.

Duplicate-key and non-RFC-constant rejection are deliberate parser hardening,
not consequences hidden in a path move. Their acceptance impact is tested and
documented before publication.

## Public operations

The inherited precise operations are:

- `serialize_text(plan)`;
- `serialize_bytes(plan)`;
- `parse_text(content)`; and
- `parse_bytes(content)`.

The contract also exposes `item_from_json_value(value)` for typed durable JSON
families, such as selective OCR plans, that embed the exact PDF source item
shape. This keeps item-object reconstruction with its JSON owner rather than
adding `from_dict()` to the record or importing a private helper across
modules.

The records expose no `to_json()`, `from_json()`, or `from_dict()` compatibility
methods. Consumers import and invoke this defining JSON owner directly.
