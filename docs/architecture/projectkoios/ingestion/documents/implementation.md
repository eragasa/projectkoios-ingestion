# `ingestion.documents` implementation

`documents/base.py` defines `AbstractDocument`, `AbstractArticle`, and
`AbstractTextbook`. `documents/page/base.py` and `documents/block/base.py`
define the corresponding page and block roots. These are nominal ABCs rather
than serialized contract objects.

`documents/extracted.py` retains the existing extracted article and textbook
implementations. Each concrete representation exposes the stable identity of
its underlying extracted document through `document_identity`.

`documents/structure/analyzer.py` remains the nominal boundary used by the
pre-existing textbook structure contract. Article structure instead follows the
Ingestion Base `ArticleStructureRequest` →
`DeterministicArticleStructureActionizer` → `StructureAnalysis` operation and
does not inherit the analyzer hierarchy.

The package initializer preserves the established extracted-document import
surface during the module-to-package migration. New implementation code imports
the defining modules directly.

The parallel [`documents.page`](page/index.md) design assigns source page-item
identity, native order, persisted keyed lookup, and inventory identity to the
source Page owner. It freezes a later split in which generic
`AbstractDocumentPage` owns page identity/metadata and text-specific
`AbstractTextDocumentPage` owns ordered block identities and canonical text.
That split is not implemented by this design checkpoint; current nominal bases
and `ExtractedPage` remain authoritative.
