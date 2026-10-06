Synchronous pipeline framework
==============================

Terminology
-----------

A **pipeline** composes a fixed ordered set of typed actionizers behind one
configurable action. It presents that composition to Workflow as one prototask.
The ordered stage actionizer identities are part of the pipeline identity.

A pipeline owns synchronous domain composition only. It does not own queues,
leases, retries, durable checkpoints, scheduling, approvals, child batches, or
cross-request workflow state. Those remain external Workflow responsibilities.

Framework API
-------------

.. automodule:: projectkoios.ingestion.base.pipeline.identity
   :members:

.. automodule:: projectkoios.ingestion.base.pipeline.result
   :members:

.. automodule:: projectkoios.ingestion.base.pipeline.actionizer
   :members:

.. automodule:: projectkoios.ingestion.base.pipeline.error
   :members:
