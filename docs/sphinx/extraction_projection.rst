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
belong outside the projector.

Data flow
---------

#. A journal reader obtains one checksummed record and its exact payload bytes.
#. ``ExtractionPublicationEvidence`` verifies byte count and SHA-256.
#. ``ExtractionProjectionMaterializationPipeline`` invokes the pure
   ``ExtractionProjectionProjector`` and receives a complete immutable read
   model.
#. The pipeline passes that value, an explicit target identity, physical
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

.. automodule:: projectkoios.ingestion.storage.extraction.projection.read_model
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.projector
   :members:

Extraction materialization API
------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.target
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.collection_evidence
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.evidence
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.materialization.materializer
   :members:

Extraction pipeline API
-----------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection_pipeline.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection_pipeline.request
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection_pipeline.result
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection_pipeline.pipeline
   :members:

Extraction projector-inventory API
----------------------------------

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.configuration
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.collection
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.evidence
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.inventory
   :members:

.. automodule:: projectkoios.ingestion.storage.extraction.projection.inventory.reader
   :members:

MongoDB materialization API
---------------------------

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.materializer
   :members:

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.materialization_error
   :members:
