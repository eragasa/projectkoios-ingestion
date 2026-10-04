# OCR implementation

The OCR domain owns one production class per named module. Image, selection,
configuration, request, token, line, warning, failure, identity, and result
objects inherit the ingestion immutable-data or identity bases where
appropriate. Requests and results additionally implement the Project Koios
action-family bases. Stable constants, cache-key construction, strict
serialization, and private bounded validation helpers remain class-free.

Every identity is recomputed from retained evidence and every collection and
payload is bounded. `serialization.py` strictly reconstructs canonical JSON
values into immutable classes. It validates exact object shapes, enum values,
byte content, geometry, ordered collections, cache keys, and derived identities
rather than trusting stored dictionaries.

The package initializer is a namespace marker and re-exports nothing. Consumers
import each class from its owning module; no compatibility facade or artificial
`contract` subpackage exists.
