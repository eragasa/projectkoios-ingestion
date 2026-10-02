# `figures.contracts` implementation

The module removes its private page-renderer protocol and concrete PyMuPDF
renderer import. It uses the canonical nominal `PageRegionRenderer` and requires
that dependency during detector construction. Figure contracts, identities,
limits, and inspector injection otherwise remain unchanged.
