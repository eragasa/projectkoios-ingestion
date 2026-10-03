# `projectkoios.ingestion.integrations.pix2tex`

This package owns the concrete Pix2Tex CLI equation-recognition adapter and its
subprocess invocation request, output, result, and failure classes. The adapter
implements the vendor-neutral `AbstractEquationRecognizer` boundary. Workflow
and CPN code import no Pix2Tex-owned type.

Namespace initializers are markers and do not re-export implementation classes.
