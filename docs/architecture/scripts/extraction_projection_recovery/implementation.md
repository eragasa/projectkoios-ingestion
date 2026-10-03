# Extraction projection recovery implementation

The command validates that connection metadata is a private regular file,
requires a loopback MongoDB address, validates bounded names and ports, and
constructs `ExtractionProjectionRecoveryRequest`. Connection validation and
Keychain-backed client creation are shared with the extraction publication
command through `scripts.mongodb_extraction_connection`; no URI or password is
accepted from command-line arguments or repository files.

On `--apply`, it authenticates through PyMongo, verifies the server, opens the
private `DiskExtractionPublicationStore`, and invokes
`MongoExtractionPublicationStore.recover()`. The MongoDB adapter validates every
journal record and payload before idempotently rebuilding document, page, block,
warning, and manifest collections. The final report contains only identities,
counts, and journal position.

Notebook provisioning belongs to the private laptop deployment overlay. This
command owns only the ingestion recovery operation and does not install,
configure, start, or stop MongoDB.
