# OCR contract implementation

`contracts.py` owns exact OCR image, selection, configuration, request, token,
line, warning, failure, processor identity, and result contracts. Every identity
is recomputed from retained evidence and every collection and payload is
bounded.

`serialization.py` strictly reconstructs canonical JSON values into those
immutable classes. It validates exact object shapes, enum values, byte content,
geometry, ordered collections, cache keys, and all derived identities rather
than trusting stored dictionaries.

The package initializer is a namespace marker and re-exports nothing.
