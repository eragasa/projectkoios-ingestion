# Pix2Tex integration implementation

`Pix2TexCliEquationRecognizer` validates and retains exact executable and model
resource identities. It stages exact rendered PNG bytes in a private temporary
directory and invokes the executable without a shell. One invocation receives a
concrete `Pix2TexInvocationRequest` and either returns a concrete
`Pix2TexInvocationResult` or raises `Pix2TexInvocationError`.

Before invocation, processor version 5 applies a deterministic primary-evidence
gate. It retains all assemblies but invokes Pix2Tex only for proposed display
assemblies with 4–64 native-text characters, at most 14 native words, at most
three grouped candidates, and an opaque 8-bit RGB PNG containing at most two
foreground bands. Two-band regions touching a vertical edge remain retained but
are not requested. Ineligibility reasons are preserved as proposal warnings.
These bounds screen overbroad, context-contaminated, truncated, and weak visual
evidence; they do not establish mathematical correctness.

Processor version 5 also records high-precision output warnings for brace,
`\left`/`\right`, and environment mismatches; excessive spacing; implausible
output expansion; duplicated equation labels; and native equalities absent from
the proposal. Warnings never accept output or make it chunk-text-eligible.
Symbol substitutions can remain syntactically valid, so unattended execution
still requires separate evidence that the configured recognizer is suitable.

A nonzero exit invalidates the complete invocation. Diagnostic bytes remain
bounded, and stdout is discarded before UTF-8 decoding or LaTeX parsing. The
adapter translates successful outputs into vendor-neutral recognition proposals
and returns `EquationRecognitionArtifact`. Proposals remain automated,
unreviewed, unaccepted, and chunk-text-ineligible.
