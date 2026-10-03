# `PyMuPdfExtractor` implementation

The adapter lazily imports PyMuPDF, validates exact source bytes, enforces the
configured page bound before page loading, and records backend identity in the
extractor/cache version.

For each page it retains PyMuPDF's native block order. Supported text blocks are
normalized into immutable line/span tuples and processed by
`BlockTextActionizer`. Supported image blocks retain exact image/mask hashes and
media evidence. Both block kinds normalize at most five coordinate values plus
the backend coordinate count and invoke `BlockGeometryActionizer`.

A valid geometry result is copied unchanged into `SourceSpan` only when it is
also contained by the page's unrotated cropbox coordinate space. Invalid or
out-of-page geometry produces `bounding_box=None` and one linked bounded
warning containing the page-local source object ID, block kind, invalidity
reason, and bounded raw coordinate evidence. The block content or asset and
exact source object ID are still retained. No endpoint sorting, coordinate
clamping, epsilon expansion, or synthetic rectangle is permitted.

Changing this behavior requires an extractor behavior/cache-version bump.
Focused tests cover valid geometry, Simon's reversed-Y image geometry,
malformed/non-finite/negative/unordered/non-positive-area/out-of-page cases,
deterministic replay, warning linkage, and prior-version cache separation.
