# `ingestion.documents` implementation

`documents/base.py` defines `AbstractDocument`, `AbstractArticle`, and
`AbstractTextbook`. `documents/page/base.py` and `documents/block/base.py`
define the corresponding page and block roots. These are nominal ABCs rather
than serialized contract objects.

`documents/extracted.py` retains the existing extracted article and textbook
implementations. Each concrete representation exposes the stable identity of
its underlying extracted document through `document_identity`.

The package initializer preserves the established extracted-document import
surface during the module-to-package migration. New implementation code imports
the defining modules directly.
