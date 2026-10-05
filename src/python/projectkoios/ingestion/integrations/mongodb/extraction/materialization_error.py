"""MongoDB extraction projection materialization failure."""


class MongoExtractionProjectionMaterializationError(RuntimeError):
    """Report an effectful MongoDB materialization failure.

    Parameters
    ----------
    code
        Stable machine-readable failure category.
    message
        Human-readable description without credentials or payload content.

    Notes
    -----
    This is intentionally not a projection contract error. Projection has
    already completed before materialization begins; failures here concern BSON
    encoding, document bounds, identity conflicts, or database writes.
    """

    def __init__(self, *, code: str, message: str) -> None:
        if type(code) is not str or not code:
            raise ValueError("materialization error code must be non-empty")
        super().__init__(message)
        self.code = code
