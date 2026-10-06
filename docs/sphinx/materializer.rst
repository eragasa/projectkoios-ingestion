Effectful materializer framework
================================

Terminology
-----------

A **materializer** applies one complete immutable projection value to one
explicit external target under one explicit authority. It returns immutable
outcome evidence.

A materializer does not project source evidence, select work, read inventories,
grant authority, retry failures, or orchestrate workflow state. Its fixed
``Materializer.action`` validates contracts and provenance before delegating
only the target effect to ``materialize``.

Identity and replay
-------------------

``MaterializationRequest.request_id`` binds the projection, target,
configuration, and presented authority. ``idempotency_key`` binds the same
operation without the authority identity, so a renewed grant does not change
the logical replay operation. The target identity is distinct from both the
physical write configuration and authority.

Framework API
-------------

.. automodule:: projectkoios.ingestion.base.materializer.target
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.configuration
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.evidence
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.identity.model
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.request
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.result
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.actionizer
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.error
   :members:

.. automodule:: projectkoios.ingestion.base.materializer.identity.error
   :members:
