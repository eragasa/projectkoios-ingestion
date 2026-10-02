# `projectkoios.ingestion.pdf.preflight` implementation

The package contains two cohesive modules: `plan.py` for the immutable plan
contract and `policy.py` for validation, deduplication, and allocation limits.
Its initializer exports the plan and policy classes without wrapping them; the
stable limit error remains owned by `pdf.renderer`.

The package has no optional-backend import, backend version lookup, document
open, page object, dynamically typed backend object, rectangle/matrix type,
pixmap operation, colorspace choice, or image encoding. A static boundary test
must reject such imports and references. Exact backend geometry is computed by
the adapter and supplied only as primitive dimensions to policy.
