# `DeterministicEquationCandidateDetector` implementation

Construction requires a `PageRegionRenderer` supplied by the caller; there is
no optional renderer argument and no concrete fallback. Detection continues to
create exact `PageRegionSelection` values, invoke the neutral render action, and
validate returned region identity, order, and aggregate evidence under existing
bounds.
