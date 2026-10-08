# `ingestion.page_projection` prototype inventory

The flat module demonstrated feasibility for:

- explicit document metadata and source-digest binding;
- physical/printed page order and citation locations;
- paragraph, heading, and unique figure-caption output;
- omission of equation/media payloads from text projection;
- caption-duplication detection;
- bounded page windows; and
- separation of projection from Search admission.

Its path-taking APIs, baseline/summary/report readers, JSON shapes, validation thresholds, identities, report bytes, and filesystem policy are prototype implementation details. They are not retained, decoded, replayed, or exposed by the clean [`page.projection`](../page/projection/implementation.md) rewrite.
