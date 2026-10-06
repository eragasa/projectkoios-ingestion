# `projectkoios.ingestion.textbooks`

This package owns textbook ingestion and the nominal textbook-structure analyzer
boundary. The boundary refines `DocumentStructureAnalyzer`; no production
textbook analyzer is currently implemented.

Definitions are imported from direct leaves. The package initializer is an
ownership marker and exports nothing.
