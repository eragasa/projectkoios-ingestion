# Structured transcription

Structured transcription composes exact extraction and typed evidence into a
destination-neutral ordered proposal.

Concrete request, result, item, omission, configuration, cache, inventory, and
validation owners live directly under `transcription/`. The related
source-specific item derivations live under `transcription/derivation/`.

One request validator checks the complete input boundary. One result validator
checks relational consistency, source coverage, warnings, ordering, and limits.
Validation does not recreate the composition pipeline or retain complete
subject graphs.

See [implementation](implementation.md) and [schematic](schematic.md).
