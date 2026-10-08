# `projectkoios.ingestion.artifact.managed.verification` implementation

The hierarchy separates the byte-provider port from provider-neutral verification. Requests bind references, provider role, authority, and bounds. Providers supply transient chunks. The actionizer owns digest, length, media-signature, aggregate, and exact-coverage checks. Evidence and results represent success only; typed errors represent failures. No neutral value contains bytes, paths, URLs, credentials, or backend-native errors.
