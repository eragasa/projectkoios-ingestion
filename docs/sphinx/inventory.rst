Read-only inventory framework
=============================

Terminology
-----------

An **inventory** observes one explicit external target under one explicit query
authority and complete immutable observation configuration. It returns compact
immutable evidence and never mutates the target.

A **projector inventory** specializes that pattern for stored output bound to a
projector schema. Matching inventory identities prove matching observed
content only when the concrete inventory hashes complete canonical stored
documents. Inventory does not repair state and does not itself claim expected
versus observed equivalence.

Framework API
-------------

.. automodule:: projectkoios.ingestion.base.inventory.target
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.configuration
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.evidence
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.identity
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.request
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.result
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.inventory
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.error
   :members:

.. automodule:: projectkoios.ingestion.base.inventory.identity_error
   :members:

Projector-inventory API
-----------------------

.. automodule:: projectkoios.ingestion.base.projector.inventory.target
   :members:

.. automodule:: projectkoios.ingestion.base.projector.inventory.configuration
   :members:

.. automodule:: projectkoios.ingestion.base.projector.inventory.evidence
   :members:

.. automodule:: projectkoios.ingestion.base.projector.inventory.inventory
   :members:
