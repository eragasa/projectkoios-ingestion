# Local Ollama multimodal region processing

`OllamaMultimodalRegionProcessor` is the concrete ingestion-owned adapter for
bounded, non-deterministic transcription of exact `RenderedRegion` PNG evidence.
Its implementation and public API live under
`projectkoios.ingestion.integrations.ollama`. It does not select pages, extract
PDFs, detect unresolved content,
accept model output, proofread text, or publish artifacts. Application policy must perform
those operations externally. A live invocation must be gated by the
application's explicit `--apply` mode and explicit Ollama configuration; there
is no hosted-provider, alternate-model, OCR, or other fallback.

Every proposal and result is permanently marked `automated_unreviewed` and
`nondeterministic`. Output is a text proposal, never an accepted transcription,
proofread result, source fact, or publication-ready artifact.

## Bounded operational canary

`workflows/029.run_bounded_ollama_multimodal_canary.py` is the maintained
operational entry point. Without `--apply` it only verifies and publishes the
exact one-selection plan and evidence. With `--apply` it permits one loopback
invocation bound to the configured Ollama version, model name, manifest digest,
rendered-region identity, request identity, and cache identity. Its result is
create-once: later runs validate and report the retained result without calling
the model again.

The canary stores private artifacts under
`/Users/eugene/projects/projectkoios/artifacts/reference-ollama-multimodal-canary-v1`.
The bounded run completed with one proposal and no adapter warning:

- plan `reference-ollama-multimodal-canary-plan:sha256:108176c48bce9e1850613e66c35f81ce229b600fb52af5339663b1fb9648f153`;
- result `ollama-multimodal-result:sha256:9bb2269177d5d67c5fa12d71dc633b27e5eefce0917f0aff6b84c95e2aac58e8`;
- summary `reference-ollama-multimodal-canary-summary:sha256:8abf47e2caa37f0c6c8cdff7e97d198a22fb29706c46266c89a224b473ed3a85`.

Completion and absence of adapter warnings do not establish transcription
quality. The workflow does not modify a reading transcript, accept proposed
text, make the text chunk-eligible, publish it, or trigger additional
selections. Expansion beyond the frozen selection requires separate
authorization.

## Composition

Render only the exact externally selected page or region. The renderer's public
signature is:

```python
PyMuPdfRegionRenderer(
    *,
    resolution_dpi: int = 144,
    color_mode: RegionColorMode = RegionColorMode.RGB,
    max_selections: int = 256,
    max_dimension_pixels: int = 16_384,
    max_pixels: int = 25_000_000,
    max_raster_bytes: int = 100_000_000,
    max_total_pixels: int = 25_000_000,
    max_total_raster_bytes: int = 100_000_000,
)

renderer.render(
    source: SourceDocument,
    content: BinaryIO,
    selections: Iterable[PageRegionSelection],
) -> tuple[RenderedRegion, ...]
```

`renderer.configuration` is the full immutable `RegionRenderConfiguration` and
`renderer.configuration_digest` is its stable identity. Convert each returned
region without changing its bytes or evidence:

```python
from projectkoios.ingestion.integrations.ollama.base import OllamaRequestOptions
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalConfiguration,
    OllamaMultimodalLimits,
    OllamaMultimodalSelection,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.base import (
    OllamaMultimodalRegionProcessor,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.request import (
    OllamaMultimodalRegionProcessingRequest,
)

selections = tuple(
    OllamaMultimodalSelection.from_rendered_region(region)
    for region in rendered_regions
)
request = OllamaMultimodalRegionProcessingRequest.create(selections)
processor = OllamaMultimodalRegionProcessor(
    configuration=OllamaMultimodalConfiguration(
        endpoint="http://127.0.0.1:11434",
        model_name="explicit-local-vision-model:tag",
        expected_model_digest="0123456789abcdef" * 4,
        expected_ollama_version="0.12.3",
        options=OllamaRequestOptions(
            temperature=0.0,
            seed=0,
            context_tokens=8192,
            output_tokens=2048,
        ),
        limits=OllamaMultimodalLimits(),
        connect_timeout_seconds=5.0,
        read_timeout_seconds=120.0,
    )
)
result = processor.action(request=request)
```

The application owns the unresolved-selection threshold and must retain it in
its plan. The adapter accepts only the ordered regions given to it. A selection
and every corresponding result retain source ID, source blob ID and hash,
physical page index, rendered-region ID, PNG SHA-256 and byte length, and pixel
dimensions. The request retains the exact fixed/versioned rendered prompt,
prompt-template and rendered-prompt hashes, ordered evidence manifest, task,
and stable request ID. The result repeats ordered complete selection coverage
and includes output text/hash/length, warnings or failure, processor identity,
metadata and chat response identities, and a content-addressed result ID.

`serialize_contract(result)` produces canonical JSON suitable for application
publication. Raw extraction contracts use the same `serialize_contract(...)`
API. `contract_dict(...)` returns the corresponding JSON-compatible mapping.
The result does not contain PNG bytes. Requests do contain their exact
`RenderedRegion` evidence and should not be treated as compact publication
records.

A pre-call lookup key is available as
`build_ollama_multimodal_cache_key(request, processor.identity())`. Store only a
result whose `cacheable` is true; every failed, partial, stale, malformed, or
postflight-mismatched invocation is explicitly non-cacheable.

## Contract ownership and versions

There is no aggregate `OllamaMultimodalContract`. The request builds and
validates its prompt and identity; the result constructs and validates complete
or failed coverage; identity classes own their identity rules; and the region
processor owns HTTP/chat parsing and response bounds. Compound operation
outcomes such as preflight and model-list verification are immutable named
result objects, not positional result tuples.

Contract names and versions are class members of their owning objects. They
participate in stable identities, and the publication result records its
contract version. Existing identity namespaces remain unchanged. A durable
shape change requires a new owner version and explicit migration rather than
silently replacing the meaning of an older artifact.

## Local transport and model verification

`LoopbackOllamaHttpTransport` uses direct `http.client` connections. Endpoints
are restricted to normalized loopback HTTP hosts, credentials and endpoint
paths are rejected, the connected peer is rechecked as loopback, environment
proxies are not consulted, and redirects are returned rather than followed.
Connect/read timeouts and request, metadata-response, chat-response, image,
pixel, prompt, output, warning, and selection counts all have configured and
implementation hard bounds. Every metadata and chat JSON response also has
hard nesting, item-count, integer, and string bounds. Parsing rejects duplicate
keys, non-RFC constants, non-finite values, invalid Unicode, and forbidden
control characters; malformed untrusted data becomes complete non-cacheable
failure coverage rather than escaping the adapter boundary.

Before chat, the processor performs bounded requests in this order:

1. `GET /api/version`, exactly matching `expected_ollama_version`;
2. `GET /api/tags`, finding one exact model name with the expected bare 64-hex
   manifest digest;
3. `POST /api/show` for that exact name, requiring advertised `vision`;
4. non-streaming `POST /api/chat`, with exact base64 PNGs, no tools,
   `think:false`, fixed options and JSON Schema `format`;
5. `GET /api/tags` again, requiring the same exact name and digest.

The result binds SHA-256/length identities for all metadata response bodies and
the chat body/content. `OllamaModelVerification` records the observed Ollama
version, expected digest, explicit equal preflight/postflight observed digests,
capabilities, and status `expected_digest_verified_before_and_after`.

Ollama chat accepts a mutable model name/tag and does not report the served
manifest digest. The two tag checks are therefore not an atomic proof of which
manifest served the intervening chat. Every successful verification explicitly
retains limitation `non_atomic_tag_to_chat_binding`; no stronger claim is made.
A postflight change discards otherwise valid output and makes the result failed
and non-cacheable.

## Untrusted content and output

PDF raster content is untrusted prompt-injection input. Text or graphics in a
page that tell the model or application to ignore policy, call a tool, reveal
secrets, or execute an action have no authority. The adapter exposes no model
tools and omits `tools` from the chat request. It accepts only an assistant text
message and rejects `tool_calls`, thinking fields, or any extra message or
structured-output fields.

Model output is inert data only. Applications must never execute it, interpret
it as policy or instructions, or use it to authorize additional selections,
network access, tool calls, publication, or acceptance. Human/application
review remains outside this adapter.

## Test seam

Tests inject the structural `OllamaTransport` request seam:

```python
class MockTransport:
    def request(
        self,
        *,
        endpoint: str,
        method: str,
        path: str,
        body: bytes | None,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_response_bytes: int,
    ) -> OllamaHttpResponse: ...
```

Unit tests must not use a live daemon, live model, or external network. An
in-process loopback server is appropriate only for the concrete HTTP transport.
