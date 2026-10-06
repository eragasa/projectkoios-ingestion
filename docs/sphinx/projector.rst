Pure projector framework
========================

Terminology
-----------

A **projector** is a pure deterministic transformation from complete immutable
**source evidence** and complete immutable **configuration** to one rebuildable
**projection value**.

A projector never performs materialization, publication, inventory queries,
authority checks, retries, mutable lookups, clock reads, randomness, or workflow
orchestration. ``Projector.action`` is the fixed framework action;
implementations provide only ``project``. ``Projector`` is a constrained
``ConfigurableDataObjectActionizer`` specialization.

Failure taxonomy
----------------

``ProjectionContractError``
   The fixed declared source, configuration, or output contract was violated.

``ProjectionPayloadError``
   Serialized source evidence was malformed, noncanonical, incomplete, or
   structurally invalid.

``ProjectionIdentityError``
   Structurally valid values disagreed about identity, or projection output
   contained duplicate identities.

Payload and identity errors inherit from the contract error so callers can
catch the framework boundary broadly. Code that reports or assigns an operator
disposition should preserve the narrower error. Database and materialization
failures are not projector errors.

Framework API
-------------

.. automodule:: projectkoios.ingestion.base.projector.source
   :members:

.. automodule:: projectkoios.ingestion.base.projector.configuration
   :members:

.. automodule:: projectkoios.ingestion.base.projector.value
   :members:

.. automodule:: projectkoios.ingestion.base.projector.identity.model
   :members:

.. automodule:: projectkoios.ingestion.base.projector.request
   :members:

.. automodule:: projectkoios.ingestion.base.projector.result
   :members:

.. automodule:: projectkoios.ingestion.base.projector.projector
   :members:

.. automodule:: projectkoios.ingestion.base.projector.error
   :members:

.. automodule:: projectkoios.ingestion.base.projector.payload.error
   :members:

.. automodule:: projectkoios.ingestion.base.projector.identity.error
   :members:
