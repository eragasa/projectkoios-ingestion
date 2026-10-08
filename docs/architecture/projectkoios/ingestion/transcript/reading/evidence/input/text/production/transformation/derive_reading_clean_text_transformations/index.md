# `derive_reading_clean_text_transformations`

Domain-owned derivation used by the current clean-text producer action. It reconstructs ordered, non-overlapping raw-coordinate edits for current dehyphenation decisions, control/soft-hyphen sanitation, and whitespace normalization, then requires exact replay to the retained clean text. Unsupported or stale current evidence fails closed rather than being approximated.
