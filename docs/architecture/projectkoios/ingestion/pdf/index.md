# `projectkoios.ingestion.pdf`

This package owns PDF-specific ingestion contracts, extraction, artifacts, and
bounded region rendering. For region rendering it is the public composition
boundary between backend-neutral preflight policy and an optional concrete
backend adapter; it does not own downstream interpretation of rendered bytes.
