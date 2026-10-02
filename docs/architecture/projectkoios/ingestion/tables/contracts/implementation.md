# `tables.contracts` implementation

The module removes its private page-renderer protocol and concrete PyMuPDF
renderer import. It uses the canonical nominal `PageRegionRenderer` and requires
that dependency during detector construction. Table contracts, identities,
limits, and rule-inspector injection otherwise remain unchanged.
