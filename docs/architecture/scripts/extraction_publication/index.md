# `scripts.extraction_publication`

This repository command composes exact PDF extraction with the authoritative
disk publication store and optional MongoDB read projection. It requires the
planned source SHA-256 and byte size, validates private non-secret connection
metadata, and obtains the database credential from macOS Keychain.

The command is non-mutating unless `--apply` is supplied.
