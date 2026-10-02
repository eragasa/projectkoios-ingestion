# `PageRegionRenderer` implementation

An `ABC` declares `name` and `version` identity attributes and one
`@abstractmethod`, `render`. The action accepts a `SourceDocument`, `BinaryIO`,
and iterable of `PageRegionSelection`; it returns a tuple of `RenderedRegion`.
It declares no configuration or configuration-digest requirement.

The base supplies no default backend, factory, registry, forwarding behavior,
preflight delegation, or identity implementation. PDF-specific bases and
concrete adapters inherit it nominally. Broad consumers use this established
public base instead of private duck-typed renderer protocols.
