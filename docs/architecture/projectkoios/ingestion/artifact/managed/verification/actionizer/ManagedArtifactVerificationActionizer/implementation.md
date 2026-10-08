# `ManagedArtifactVerificationActionizer` implementation

The actionizer verifies that the requested provider implementation matches its configured `ManagedArtifactByteProvider`. For every ordered reference it consumes bounded nonempty chunks, computes SHA-256 incrementally, measures exact bytes, retains only a bounded signature prefix, detects the closed media type, and enforces aggregate bounds. It constructs evidence only after all observations equal the reference and returns an exact-coverage successful result. Provider failures remain typed; payload bytes are never retained.
