# `figures.detection` implementation

The internal detector-context annotation uses `PageRegionRenderer` directly
rather than importing a private protocol from `figures.contracts`. Planning,
materialization, duplicate-result checks, and aggregate evidence validation are
otherwise unchanged.
