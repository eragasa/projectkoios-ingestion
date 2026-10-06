# Structured transcription

Structured transcription composes exact extraction and typed evidence into a
destination-neutral ordered proposal.

Concrete definitions live in direct noun modules or semantic ownership
packages. The related source-specific item derivations live under
`transcription/derivation/`.

One request validator checks the complete input boundary. One result validator
checks relational consistency, source coverage, warnings, ordering, and limits.
Validation does not recreate the composition pipeline or retain complete
subject graphs.

See [implementation](implementation.md), [schematic](schematic.md), and the
[structural path map](structural-path-map.md).
