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
#. ``ExtractionProjectionProjector`` validates canonical JSON and record/payload
   identities, then derives logical read-model documents.
#. ``MongoExtractionProjectionMaterializer`` writes the completed read model
   create-once, with root completion documents last.
#. A separate inventory reader observes materialized state.

Digest meanings
---------------

``publication_digest``
   SHA-256 of the authoritative extraction-result payload.

``projection_content_sha256``
   SHA-256 of every projected document field before inserting the digest
   marker. MongoDB create-once filters bind this value and ``_id``.

``ExtractionProjectionDocument.canonical_sha256``
   SHA-256 of the final canonical document, including the content marker. This
   supports future full-content inventory proof but is not itself a claim that
   the current inventory reader proves equivalence.

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

MongoDB materialization API
---------------------------

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.materializer
   :members:

.. automodule:: projectkoios.ingestion.integrations.mongodb.extraction.materialization_error
   :members:
