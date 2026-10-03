# `scripts.equation_enrichment` implementation

The repository command is the CLI and composition boundary. It selects the
concrete `PyMuPdfRegionRenderer` and `Pix2TexCliEquationRecognizer`, then
injects the recognizer through the vendor-neutral
`AbstractEquationRecognizer` boundary into the authoritative
`workflow.equation_recognition` workflow.

The workflow plans an immutable `EquationRecognitionRequest`, invokes the
abstract recognizer action, and correlates the returned
`EquationRecognitionArtifact` to the exact request identity. The script catches
`EquationRecognitionError` explicitly and maps it to operator-facing CLI
failure. It does not execute the CPN shadow.

The separate `cpn.equation_recognition` module uses the pinned
`projectkoios-snakes` Python 3.14 baseline at revision
`72dbb1dbf0a91349faca21ceb660923cc442a8e9`. It models the completed
vendor-neutral workflow for shadow verification and imports the workflow's
request-planning function; the workflow never imports CPN or SNAKES.
