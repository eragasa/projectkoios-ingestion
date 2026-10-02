# `projectkoios.ingestion` implementation

`projectkoios.ingestion.__init__` remains an explicit public export surface.
PDF renderer names remain importable from this package, but their definitions
stay in the canonical neutral renderer contract or concrete adapter module. The
initializer contains no backend implementation and no compatibility classes.

Transcript evidence selection remains owned by `transcript.evidence.selection`;
PDF rendering policy and backend execution remain owned by `pdf`. Neither slice
may absorb routing, storage, rights, citation, or product policy.
