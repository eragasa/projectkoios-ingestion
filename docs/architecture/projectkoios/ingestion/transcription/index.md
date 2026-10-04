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
- `evidence` and `order` own immutable warning and ordering derivations;
- `source/validation` owns item-to-source and complete-source coverage records;
- `omission/validation` owns omission and raw-block coverage records.

See [implementation](implementation.md) and [schematic](schematic.md).
