# SHA-256 implementation

`SHA256Hash` is the canonical lowercase 64-character hexadecimal value. It is a
string subtype so persisted JSON contracts retain their existing representation.
Construction rejects malformed hashes, and `is_canonical()` supports validation
at existing immutable contract boundaries.

`SHA256Fingerprinter` calculates a `SHA256Hash` from exact bytes. Its chunked
operation preserves bounded streaming callers without exposing a mutable hash
implementation. Direct `hashlib.sha256` use is confined to this class.

`SHA256Verifier` fingerprints exact bytes and compares the result with an
expected `SHA256Hash` using `hmac.compare_digest`. Callers use it when their
purpose is verification rather than calculation. A malformed expected value
returns `False`; malformed source content types still fail the byte contract.

Existing serialized fields remain JSON strings. This change centralizes their
construction and checking without changing retained payload bytes, stable-ID
namespaces, journal records, or publication schemas.

The fake Tesseract executable embedded in its adapter test remains an isolated
external-program fixture and uses the Python standard library independently. It
does not exercise Ingestion's internal hashing boundary.
