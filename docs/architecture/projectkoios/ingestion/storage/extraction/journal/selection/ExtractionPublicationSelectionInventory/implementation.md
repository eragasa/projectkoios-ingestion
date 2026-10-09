# `ExtractionPublicationSelectionInventory` implementation

The inventory receives the complete authoritative record stream and the ordered publication-request identities selected by the plan. It independently reconstructs the complete journal inventory, selects only matching records in journal order, and binds that source-journal identity into its own identity. Request and record identities are streamed independently so the completion manifest can reject a valid selection constructed from any other journal.
