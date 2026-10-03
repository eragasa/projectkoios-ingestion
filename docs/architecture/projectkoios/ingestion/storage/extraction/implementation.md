# Extraction storage implementation

`AbstractExtractionPublicationStore.publish()` accepts one
`ExtractionPublicationRequest` and returns one `ExtractionPublicationResult`.
An extraction manifest identity is create-once: replaying the exact request is
idempotent, while attempting to publish different decomposition bytes for that
manifest is a concrete `ExtractionPublicationError`. Multiple versioned
manifests may retain different decompositions of the same source document.

The disk adapter is authoritative. It writes canonical extraction JSON into a
private content-addressed object tree and then appends a bounded checksummed
journal record. Both object and journal writes are fsynced. Journal records form
a SHA-256 chain, retain exact payload size and identity, and tolerate only a
torn terminal record; the next exclusive writer truncates that incomplete tail.
Complete malformed records fail closed.

The MongoDB adapter is a rebuildable projection. It writes separate document,
page, block, warning, and manifest collections. Large PDF/media bytes are never
stored in MongoDB. The final document manifest is written last with
`publication_state=complete`; consumers must ignore incomplete publications.
Projection writes are create-once and idempotent by stable identity and exact
publication digest.
