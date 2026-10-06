# SHA-256 schematic

```text
exact bytes
    │
    ▼
SHA256Fingerprinter.fingerprint()
    │
    ▼
SHA256Hash ───────────────────────────────┐
                                         │ expected
exact bytes ──► SHA256Verifier.verify() ◄─┘
                         │
                         ▼
                       bool
```

For bounded streams:

```text
ordered byte chunks
    → SHA256Fingerprinter.fingerprint_chunks()
    → SHA256Hash
```
