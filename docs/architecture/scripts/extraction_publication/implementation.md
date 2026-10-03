# Extraction publication implementation

Dry-run validation confirms the source is a safe regular file with the planned
byte size, validates a lowercase SHA-256 identity, and reports the intended disk
and MongoDB destinations without creating either.

On `--apply`, the command calls the ingestion-owned PDF extraction boundary with
both planned identity fields. It creates an immutable
`ExtractionPublicationRequest`, commits canonical extraction JSON and its
checksummed journal record through `DiskExtractionPublicationStore`, and then
projects the committed record through `MongoExtractionPublicationStore`.

Disk commit precedes MongoDB projection. If projection fails after disk commit,
the command reports an exception and the separate recovery command can replay
the authoritative journal. It never stores PDF bytes or credentials in MongoDB.
