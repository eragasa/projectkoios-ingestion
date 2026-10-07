# `json.limits` implementation

`JsonLimits` is an immutable definition supplied explicitly to each parser,
projector, serializer, and concrete `JsonContract`. It bounds UTF-8 bytes,
container depth, aggregate nodes, individual string bytes, aggregate string
bytes, and numeric-token characters.

Repository-wide hard ceilings prevent a domain contract from configuring an
unbounded parser. Each concrete contract may select lower limits required by
its own wire format. Existing domain maxima remain with those domains and are
passed into `JsonLimits`; they are not silently replaced by generic defaults.

The package initializer exports nothing.
