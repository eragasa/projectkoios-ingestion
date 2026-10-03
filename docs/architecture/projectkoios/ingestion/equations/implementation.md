# `ingestion.equations` implementation

The module depends on the nominal `PageRegionRenderer` boundary. The
deterministic detector requires a renderer from its composition root and has no
concrete adapter default.

Detector behavior version 2 retains the fixed per-block inline ambiguity bound.
When a text block contains more inline-shaped matches than that bound, the
exact source block remains prose, no partial candidate subset is promoted, and
a deterministic `equation.inline_candidate_limit` warning records the observed
count and configured maximum. The detector does not raise the bound, split or
synthesize source geometry, or silently truncate candidate evidence.

Other equation selection, rendered-result validation, bounds, and identities
remain deterministic.
