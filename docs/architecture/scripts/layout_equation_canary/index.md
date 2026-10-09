# Layout-equation canary semantics

[`scripts.layout_equation_canary`](implementation.md) defines fail-closed stage,
coverage, and verification semantics for private Heron-to-equation capability
runs.

The module does not identify private sources, invoke a detector by itself,
grant detector admission, establish transcription correctness, or authorize
publication. Private run artifacts remain discovery evidence rather than a
compatibility contract.

See the [schematic](schematic.md).
