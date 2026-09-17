# Pix2tex equation-recognition adapter

`Pix2TexCliEquationRecognizer` treats pix2tex as an optional external native/ML boundary. The Project Koios package neither installs nor imports pix2tex, PyTorch, model weights, or their transitive dependencies. Provision them outside the repository and verify their applicable software, model, and redistribution terms independently.

A dedicated external environment may use a Python version supported by pix2tex without changing the Project Koios Python 3.14 package baseline. For example:

```bash
uv tool install --python 3.12 pix2tex
pix2tex_cli --no-cuda equation.png
```

The first invocation may download model resources into the external environment. Locate the exact configuration, tokenizer, model checkpoint, and image-resizer checkpoint used by that installation. Supply every one to `koios-enrich-pdf-equations-batch` through a distinct `--pix2tex-resource NAME=PATH` argument. The workflow records and rechecks each exact byte size and SHA-256 identity, the exact executable SHA-256, a location-normalized launcher semantic SHA-256, explicit backend version, and sampling temperature. Only the shebang is normalized for relocatable processor identity; the exact launcher bytes remain auditable and are rechecked before invocation.

Do not place external model weights in this repository. Do not assume that a package version uniquely identifies downloaded weights. Updating pix2tex, Python, PyTorch, configuration, tokenizer, or checkpoints creates a different processor identity and requires a new artifact location or explicit migration.

Pix2tex is an untrusted, stochastic recognition backend. The adapter uses no shell, stages only selected bounded PNG evidence in a private temporary directory, disables GPU selection, applies a bounded timeout, and limits retained output and diagnostics. It does not provide operating-system sandboxing or a memory limit. Deployments processing untrusted inputs or models must add an appropriate OS isolation boundary.

Pix2tex does not expose calibrated proposal or symbol confidence through this CLI. Every successful output is therefore explicitly unaccepted and confidence-unavailable. The optional `projectkoios-ingestion[mathml]` extra converts a retained LaTeX proposal to MathML; successful conversion does not validate the mathematics. Primary retrieval eligibility remains a conservative indexing decision rather than correctness or acceptance.
