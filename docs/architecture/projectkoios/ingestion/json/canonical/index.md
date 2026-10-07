# `projectkoios.ingestion.json.canonical`

This module defines `CanonicalJsonSerializer`, the concrete shared formatter
used for deterministic immutable-value serialization and stable-ID material.

It is intentionally not a `JsonContract`: arbitrary projected values cannot be
reconstructed as their original Python types.

## Contents

- [`implementation.md`](implementation.md)
- [`schematic.md`](schematic.md)
