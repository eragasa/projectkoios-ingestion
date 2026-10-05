"""Materializer framework contract failures."""


class MaterializationContractError(RuntimeError):
    """Report incompatible declared materialization contracts.

    Notes
    -----
    Backend write failures use adapter-owned errors. Identity disagreement uses
    the narrower ``MaterializationIdentityError``.
    """
