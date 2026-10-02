# `PdfRegionRenderLimitError` implementation

The class remains a marker subclass of `ValueError` with no policy or backend
behavior. Its canonical definition remains in `pdf.renderer`;
`pdf.__init__` and `projectkoios.ingestion.__init__` export that exact class
object under the existing public name.

Preflight policy raises it for configured bound violations. Concrete adapters
do not catch, translate, or redefine it. Existing limit field names remain in
messages so operators can identify the rejected bound.
