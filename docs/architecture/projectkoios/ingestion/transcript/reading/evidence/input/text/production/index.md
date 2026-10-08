# Current clean-text production

This package owns the pure typed action that projects the current `CleanTranscript` contract into bounded replayable `ReadingCleanTextProducerEvidenceInventory` values. It binds each record to the explicitly selected page stream and derives exact raw-coordinate transformations for current dehyphenation, sanitation, and whitespace rules. It performs no I/O and is not a legacy decoder.
