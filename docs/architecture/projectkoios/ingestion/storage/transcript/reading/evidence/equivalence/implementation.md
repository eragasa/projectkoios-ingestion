# Reading-evidence equivalence implementation

`ReadingEvidenceEquivalenceVerifier` compares two already-verified `ReadingEvidenceSourceResult` values. It compares complete canonical documents, independently observed inventories, and canonical projection-result identities.

Same-store replay additionally requires matching baseline/replay materialization scope and immutable replay evidence showing zero created members plus exact unchanged counts for every logical collection. Independent rebuild forbids materialization evidence so the two proof roles cannot be conflated.

The result is a technical equivalence finding only and implies no operator approval or lifecycle transition.
