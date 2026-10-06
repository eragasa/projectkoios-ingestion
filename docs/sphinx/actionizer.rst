Configurable actionizer framework
=================================

Hierarchy
---------

The nominal action hierarchy is:

.. code-block:: text

   DataObjectActionizer
   └── ConfigurableDataObjectActionizer
       ├── Projector
       ├── Materializer
       ├── Inventory
       │   └── ProjectorInventory
       └── Pipeline

``ConfigurableDataObjectActionizer`` adds one complete immutable configuration
contract to the general Core action boundary. It does not add projection,
materialization, or pipeline semantics. Each specialized action owns those
additional invariants.

Framework API
-------------

.. automodule:: projectkoios.ingestion.base.actionizer.configuration
   :members:

.. automodule:: projectkoios.ingestion.base.actionizer.request
   :members:

.. automodule:: projectkoios.ingestion.base.actionizer.result
   :members:

.. automodule:: projectkoios.ingestion.base.actionizer.configurable
   :members:
