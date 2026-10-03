# `pdf.extraction` implementation

`contracts.py` owns neutral extraction configuration and page-limit failures.
`geometry.py` and `text.py` define typed immutable requests, typed immutable
results, fixed request bounds, and `DataObjectActionizer` implementations.
Their identities and contract versions participate in deterministic replay. The
package initializer is a namespace marker only and re-exports nothing.

The package accepts normalized bounded values rather than backend dictionaries
or backend objects. It therefore contains no `Any`-typed PyMuPDF boundary, lazy
dependency import, document lifecycle, page access, asset extraction, warning
publication, or adapter selection.

The concrete extractor remains responsible for converting raw backend values
into requests and for translating action results into `SourceSpan`,
`ExtractedBlock`, and `IngestionWarning` contracts. The actions do not mutate
input, repair evidence, or decide whether a block is retained.
