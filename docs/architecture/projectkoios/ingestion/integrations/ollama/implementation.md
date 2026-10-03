# Ollama integration implementation

The integration is split by responsibility:

```text
integrations/ollama/base.py
integrations/ollama/transport/http.py
integrations/ollama/multimodal/base.py
integrations/ollama/multimodal/selection/identity.py
integrations/ollama/multimodal/cache/identity.py
integrations/ollama/multimodal/processor/region/base.py
integrations/ollama/multimodal/processor/region/identity.py
integrations/ollama/multimodal/processor/region/request.py
integrations/ollama/multimodal/processor/region/result.py
integrations/ollama/multimodal/processor/region/preflight/result.py
integrations/ollama/multimodal/processor/region/model_list/model.py
integrations/ollama/multimodal/processor/region/model_list/result.py
```

`base.py` has no socket, HTTP-client, IP-address, or URL-parser dependency. It
owns only shared types used to configure and inject an Ollama transport.

`transport/http.py` owns the privacy-sensitive loopback HTTP implementation and
endpoint normalization. It rejects credentials, non-loopback hosts, unsupported
paths and methods, redirects by omission, oversized responses, and unsafe URL
components.

`multimodal/base.py` owns shared bounded multimodal values. Selection and cache
identities live with their own subdomains. The
`multimodal/processor/region` package owns the region processor, bounded
response parsing, processor identity, action pair, and named preflight and
model-list results.

Each concrete owner declares its contract name and version as class members and
validates its own invariants. No aggregate contract class can be called as an
alternate construction or validation path. Further decomposition can proceed
without moving transport policy back into either base layer.
