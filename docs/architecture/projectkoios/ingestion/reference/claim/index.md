# `projectkoios.ingestion.reference.claim`

This package owns bounded, payload-free claim candidates derived from exact
reference evidence and positive page-location results.

- [`candidate`](candidate/index.md) owns the immutable candidate action result.
- [`definition`](definition/index.md) owns stable contract identifiers.
- [`identity`](identity/index.md) owns bounded candidate-ID derivation.
- [`limitation`](limitation/index.md) owns its closed limitations.
- [`status`](status/index.md) owns its closed non-acceptance status.
- [`error`](error/index.md) owns domain failures.
- [`projection`](projection/index.md) owns deterministic candidate projection.
- [`structural-path-map`](structural-path-map.md) records the clean path break.

The package does not decide claim support, citation acceptance, quotation,
publication, or scientific validity.
