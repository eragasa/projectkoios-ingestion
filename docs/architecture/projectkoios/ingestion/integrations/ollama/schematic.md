# Ollama integration schematic

```text
OllamaMultimodalRegionProcessor
├── shared transport values → integrations/ollama/base.py
├── transport abstract base → integrations/ollama/base.py
├── loopback HTTP transport → integrations/ollama/transport/http.py
├── shared multimodal values → integrations/ollama/multimodal/base.py
├── selection identity → integrations/ollama/multimodal/selection/identity.py
├── cache identity → integrations/ollama/multimodal/cache/identity.py
└── region processing → integrations/ollama/multimodal/processor/region/
    ├── processor and parsing → base.py
    ├── processor identity → identity.py
    ├── action request → request.py
    ├── action result → result.py
    ├── preflight result → preflight/result.py
    ├── model descriptor → model_list/model.py
    └── model-list verification result → model_list/result.py
```
