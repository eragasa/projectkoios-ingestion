# `ingestion.protocols` implementation

The prior `PageRegionRenderer` protocol definition and temporary renderer alias
are removed. Callers import the nominal `PageRegionRenderer` directly from
`pdf.renderer` or a neutral package export. Other existing ingestion protocols
retain their current ownership and behavior; this change does not refactor
unrelated protocol families.
