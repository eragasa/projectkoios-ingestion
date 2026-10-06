Extraction read-model projection
================================

Boundary
--------

``ExtractionProjectionProjector`` consumes exact
``ExtractionPublicationEvidence`` and an
``ExtractionProjectionConfiguration``. It returns an immutable
``ExtractionReadModel`` containing canonical documents for five logical
collections: documents, pages, blocks, warnings, and manifests.

The logical model is vendor-neutral. Physical MongoDB collection names,
connections, index preparation, authority, record selection, and write failures
belong outside the projector. ``ExtractionProjectionIndexReadinessActionizer``
owns index preparation as one runtime-neutral action; it does not infer Workflow
or Colored Petri Net topology.

Data flow
---------

#. An explicit readiness request ensures required physical indexes and records
   their exact observed definitions.
#. A journal reader obtains one checksummed record and its exact payload bytes.
#. ``ExtractionPublicationEvidence`` verifies byte count and SHA-256.
#. ``ExtractionProjectionMaterializationPipeline`` invokes the pure
   ``ExtractionProjectionProjector`` and receives a complete immutable read
   model.
#. The same actionizer passes that value, an explicit target identity, physical
   configuration, and authority identity to
   ``MongoExtractionProjectionMaterializer``.
#. The materializer writes create-once, with root completion documents last,
   and returns exact per-collection created/unchanged evidence.
#. A separate inventory reader observes materialized state.

Digest meanings
---------------

``publication_digest``
   SHA-256 of the authoritative extraction-result payload.

``projection_content_sha256``
   SHA-256 of every projected document field before inserting the digest
   marker. MongoDB create-once filters bind this value and ``_id``.

``ExtractionProjectionDocument.canonical_sha256``
   SHA-256 of the final canonical document, including the content marker.

``ExtractionProjectionCollectionInventory.content_sha256``
   SHA-256 over stable identities paired with SHA-256 digests of every complete
   observed canonical stored document. Any stored-field change alters the
   collection and aggregate inventory identities. Matching inventory evidence
   remains distinct from an explicit equivalence-verifier result.

Pure projection API
-------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection.collection
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.evidence
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.document
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.read.model
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.projector
   :members:

Extraction materialization API
------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.target
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.evidence.collection
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.evidence.model
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.materializer
   :members:

Extraction composition-action API
---------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection.pipeline.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.pipeline.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.pipeline.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.pipeline.actionizer
   :members:

Extraction projector-inventory API
----------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.collection
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.evidence
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.observer
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.reader.base
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.expected
   :members:

Extraction index-readiness API
------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.definition
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.evidence.index
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.evidence.model
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.backend.base
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.index.readiness.actionizer
   :members:

Inventory equivalence API
-------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.kind
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.mismatch
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.equivalence.verifier
   :members:

Extraction provider-action API
------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.artifact.validation.reader.base
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.artifact.validation.reader.error
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.artifact.validation.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.artifact.validation.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.artifact.validation.actionizer
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.freeze.bounded.source.model
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.freeze.bounded.source.reader
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.freeze.bounded.extraction.error
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.freeze.bounded.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.freeze.bounded.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.freeze.bounded.actionizer
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.journal.publication.backend.base
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.journal.publication.backend.error
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.journal.publication.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.journal.publication.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.journal.publication.actionizer
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.recovery.subset.backend.base
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.recovery.subset.backend.error
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.recovery.subset.evidence
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.recovery.subset.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.recovery.subset.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.recovery.subset.actionizer
   :members:

MongoDB materialization API
---------------------------

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.index.readiness.backend
   :members:

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.materializer
   :members:

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.materialization.error
   :members:
