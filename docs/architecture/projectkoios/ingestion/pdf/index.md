# `projectkoios.ingestion.pdf`

This package owns PDF-specific ingestion contracts, extraction, artifacts,
nominal renderer bases, and bounded region-render policy. Its neutral public
boundary stops at the renderer bases and results; concrete backend selection
belongs to explicit composition roots, and downstream interpretation of
rendered bytes remains outside the package.
