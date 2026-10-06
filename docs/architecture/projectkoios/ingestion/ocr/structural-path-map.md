# OCR and reconciliation structural path map

This is the reviewed source inventory for the OCR and native/OCR reconciliation
hierarchy migration. Paths are relative to
`src/python/projectkoios/ingestion`. Removed paths are not retained as aliases
or re-export facades.

## OCR

| Removed path | Direct owner path |
|---|---|
| `ocr/_geometry.py` | `ocr/geometry/mapping.py` |
| `ocr/_identity.py` | `ocr/identity/derivation.py` |
| `ocr/_limits.py` | `ocr/limit/definition.py` |
| `ocr/_primitives.py` | `ocr/validation/value.py` |
| `ocr/_validation.py` | `ocr/validation/reference.py`, `ocr/validation/request.py`, `ocr/validation/selection.py`, `ocr/validation/result.py` |
| `ocr/cache_key.py` | `ocr/cache/identity.py` |
| `ocr/failure_kind.py` | `ocr/kind/failure.py` |
| `ocr/language_resource_identity.py` | `ocr/identity/resource/language.py` |
| `ocr/limit_error.py` | `ocr/limit/error.py` |
| `ocr/native_text_block_reference.py` | `ocr/reference/native/text/block.py` |
| `ocr/output_mode.py` | `ocr/mode/output.py` |
| `ocr/page_image.py` | `ocr/image/page.py` |
| `ocr/processor_identity.py` | `ocr/identity/processor.py` |
| `ocr/resource_identity_kind.py` | `ocr/kind/resource/identity.py` |
| `ocr/result.py` | `ocr/result/ocr.py` |
| `ocr/result_status.py` | `ocr/status/result.py` |
| `ocr/selection_result.py` | `ocr/result/selection.py` |
| `ocr/selection_status.py` | `ocr/status/selection.py` |

## Native/OCR reconciliation

| Removed path | Direct owner path |
|---|---|
| `reconciliation/_candidate.py` | `reconciliation/candidate/model.py` |
| `reconciliation/_derivation.py` | `reconciliation/derivation/native.py`, `reconciliation/derivation/warning.py`, `reconciliation/derivation/match.py`, `reconciliation/derivation/stream.py` |
| `reconciliation/_geometry.py` | `reconciliation/geometry/analysis.py` |
| `reconciliation/_identity.py` | `reconciliation/identity/derivation.py` |
| `reconciliation/_limits.py` | `reconciliation/limit/definition.py` |
| `reconciliation/_primitives.py` | `reconciliation/validation/value.py` |
| `reconciliation/_validation.py` | `reconciliation/validation/request.py`, `reconciliation/validation/result.py` |
| `reconciliation/item_kind.py` | `reconciliation/kind/item.py` |
| `reconciliation/limit_error.py` | `reconciliation/limit/error.py` |
| `reconciliation/match_kind.py` | `reconciliation/kind/match.py` |
| `reconciliation/native_block_evidence.py` | `reconciliation/evidence/native/block.py` |
| `reconciliation/native_line_segment.py` | `reconciliation/segment/native/line.py` |
| `reconciliation/stream_choice.py` | `reconciliation/choice/stream.py` |

## Semantic review

- Qualified records are grouped role-first: `identity/resource/language.py`,
  `reference/native/text/block.py`, `result/selection.py`, and
  `evidence/native/block.py` state the record role before its qualifiers.
- Unqualified primary records such as `OCRRequest`, `OCRSelection`,
  `OCRProcessor`, `OCRReconciledItem`, and `OCRReconciliationMatch` remain in
  direct noun modules rather than acquiring redundant `model.py` wrappers.
- Geometry mapping in OCR converts pixel-space evidence, while reconciliation
  geometry analysis normalizes and compares retained source geometry.
- `validation/value.py` owns bounded scalar and container validation;
  cross-object validation is split by request, selection, result, and reference
  boundaries.
- Reconciliation derivation is split into native-stream, warning, match, and
  proposed-stream operations. These remain one deterministic synchronous
  action and do not own Workflow topology, retries, leases, approvals,
  checkpoints, concurrency, or stop propagation.
- OCR batch and reconciliation-batch contracts retain their existing ownership;
  this change moves their imports only.
- Stable contract payloads, field order, identity namespaces, and serialized
  bytes are unchanged.
