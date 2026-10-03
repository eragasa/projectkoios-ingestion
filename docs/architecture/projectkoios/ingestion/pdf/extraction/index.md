# `projectkoios.ingestion.pdf.extraction`

This package owns backend-neutral, immutable data-object actions used while
constructing PDF extraction evidence. It does not load or expose an optional PDF
backend.

## Contents

- `contracts.py` — neutral extraction configuration and limit failures.
- [`geometry`](geometry/index.md) — deterministic block-geometry validation.
- [`text`](text/index.md) — deterministic block-text composition.
- [`implementation.md`](implementation.md) — package boundary and constraints.
- [`schematic.md`](schematic.md) — action relationships.
