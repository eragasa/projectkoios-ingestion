# Pix2Tex integration implementation

`Pix2TexCliEquationRecognizer` validates and retains exact executable and model
resource identities. It stages exact rendered PNG bytes in a private temporary
directory and invokes the executable without a shell. One invocation receives a
concrete `Pix2TexInvocationRequest` and either returns a concrete
`Pix2TexInvocationResult` or raises `Pix2TexInvocationError`.

A nonzero exit invalidates the complete invocation. Diagnostic bytes remain
bounded, and stdout is discarded before UTF-8 decoding or LaTeX parsing. The
adapter translates successful outputs into vendor-neutral recognition proposals
and returns `EquationRecognitionArtifact`. Proposals remain automated,
unreviewed, unaccepted, and chunk-text-ineligible.
