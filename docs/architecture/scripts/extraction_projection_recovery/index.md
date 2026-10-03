# `scripts.extraction_projection_recovery`

This repository command is the composition boundary for rebuilding an optional
MongoDB extraction projection from the authoritative disk publication journal.
It consumes private, non-secret connection metadata and retrieves the
application credential from macOS Keychain. It never prints or persists the
credential.

The command performs a non-mutating dry run by default. `--apply` is required
to connect to MongoDB and replay the bounded journal.
