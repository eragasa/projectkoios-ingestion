# `pdf.preflight.plan` implementation

`plan.py` defines one frozen dataclass,
`PdfRegionRenderPreflightPlan`. Its fields are `selection`, `width_pixels`,
`height_pixels`, `channel_count`, `pixel_count`, and `raster_byte_count`.

Construction enforces positive integer dimensions/channel count and exact
consistency of the derived counts. Configuration-dependent ceilings remain
exclusively in policy, so the plan is an immutable statement that those
resource facts were approved,
not a second implementation of limit policy.
