# `ingestion.tables` implementation

The package exports its existing table contracts and deterministic detector.
`TableRuleInspector` is the nominal inspection boundary, implemented by the
package-owned `PyMuPdfTableRuleInspector`. Renderer-facing modules depend on
the nominal `PageRegionRenderer`; they neither import nor instantiate
`PyMuPdfRegionRenderer`.
