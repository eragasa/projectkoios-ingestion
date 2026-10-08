# `reference.evidence.limits.definition`

## Owner

This leaf owns the immutable `ReferenceEvidenceLimits` value and its canonical
`REFERENCE_EVIDENCE_LIMITS` instance. The value encapsulates the retained
262,144-byte wire limit, the equal pre-hash identity-input limit, the
128,000,000-byte bound-artifact limit, the 4,096-character record-text limit,
the 4,096 lineage-identity limit, the 512 layout-identity limit, the 32
layer-count limit, and the 32 reason/limitation limit. Consumers read named
fields from this owner rather than importing disconnected scalar constants.

The owner also encapsulates explicit shared-parser settings:

- maximum container depth: `64`;
- maximum parsed/projected items: `8,192`;
- maximum individual string bytes: `16,384`;
- maximum aggregate string bytes: `262,144`; and
- maximum numeric-token characters: `4,096`.

The `8,192` item ceiling exceeds the calculated `4,953` projected items for a
maximum-cardinality schema-generation-1 record while remaining independently
bounded. The string-byte ceiling permits the retained 4,096-character field
limit at four-byte UTF-8 width. The identity-input ceiling bounds canonical
identity material before its owning derivation fingerprints those bytes; the
document ceiling remains the exact wire limit. No identity, parser, or
serializer limit is implicit or unlimited.
