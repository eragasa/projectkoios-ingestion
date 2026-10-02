# `DeterministicFigureCandidateDetector` implementation

Construction requires a `PageRegionRenderer`; there is no optional renderer or
concrete fallback. Existing layout and inspector defaults are unaffected. The
detector retains its figure-specific rendered-pixel aggregate bound by requiring
the composition root to provide an appropriately configured PDF renderer.
