"""Projection framework contract failures."""


class ProjectionContractError(RuntimeError):
    """Report a violation of the fixed projector contract.

    Notes
    -----
    Raise this class directly for incompatible declared source,
    configuration, or output contracts. Malformed serialized evidence uses
    ``ProjectionPayloadError`` and identity disagreement uses
    ``ProjectionIdentityError``; both remain subclasses for broad catches.
    Neither error represents a transient materialization or storage failure.
    """
