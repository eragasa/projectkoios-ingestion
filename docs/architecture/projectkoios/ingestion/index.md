# `projectkoios.ingestion`

This package owns source ingestion and destination-independent document
processing. It exposes stable ingestion contracts while keeping format-neutral
policy separate from optional format/backend integrations. It does not own
cross-repository routing, product policy, persistence, or downstream authoring.
