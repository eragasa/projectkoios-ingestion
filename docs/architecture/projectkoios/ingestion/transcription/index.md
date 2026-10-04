# Structured transcription

Structured transcription composes exact extraction and typed evidence into a
destination-neutral ordered proposal.

Ownership is divided among marker-only subpackages:

- `configuration` owns hard composition limits;
- `request` owns the complete action input and request validation;
- `derivation` owns immutable evidence-derived item drafts;
- `item` and `omission` own retained output records;
- `result` owns final identity and result validation;
- `composition` owns deterministic orchestration;
- `cache` owns derived cache identity;
- `evidence`, `order`, and `source` own their explicit classifications.

See [implementation](implementation.md) and [schematic](schematic.md).
