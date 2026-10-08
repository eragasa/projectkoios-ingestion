# `ReadingEvidenceStorageJsonContract` implementation

Implements `JsonContract` for the explicit current registry of canonical reading values. Encoding emits stable semantic type and enum tags. Decoding validates exact fields, reconstructs values through public constructors, and compares every persisted `init=False` identity/digest/count with the reconstructed field.
