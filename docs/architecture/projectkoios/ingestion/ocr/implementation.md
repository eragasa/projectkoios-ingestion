# OCR implementation

The OCR domain uses semantic ownership packages and direct role leaves. Image,
selection, configuration, request, token, line, warning, failure, identity, and
result objects inherit the ingestion immutable-data or identity bases where
appropriate. Requests and results additionally implement the Project Koios
action-family bases. Stable constants, cache identity construction, strict
serialization, and bounded validation helpers remain class-free.

Every identity is recomputed from retained evidence and every collection and
payload is bounded. `serialization.py` strictly reconstructs canonical JSON
values into immutable classes. It validates exact object shapes, enum values,
byte content, geometry, ordered collections, cache keys, and derived identities
rather than trusting stored dictionaries.

Package initializers are namespace markers and re-export nothing. Consumers
import every definition from its owning leaf; no compatibility facade exists.
The reviewed hierarchy inventory is the
[structural path map](structural-path-map.md).
