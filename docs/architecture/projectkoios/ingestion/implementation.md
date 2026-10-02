# `projectkoios.ingestion` implementation

`projectkoios.ingestion.__init__` remains an explicit public export surface.
The neutral `PageRegionRenderer`, `PdfRegionRenderer`, and render-limit error
remain importable from this package, but concrete renderer adapters do not. The
initializer contains no backend implementation, compatibility alias, or
compatibility class.

Transcript evidence selection remains owned by `transcript.evidence.selection`;
PDF rendering policy and backend execution remain owned by `pdf`. Neither slice
may absorb routing, storage, rights, citation, or product policy.
