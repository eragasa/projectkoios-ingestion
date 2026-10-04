# Table structure

[Implementation](implementation.md) · [Schematic](schematic.md)

This package owns deterministic, bounded table-structure proposals derived from
exact table-detection evidence. Production classes live in individually named
modules. Derivation and validation are represented as immutable ingestion base
objects rather than module-level helper functions. Final warning links are
owned by the `TableStructureResult` factory.
