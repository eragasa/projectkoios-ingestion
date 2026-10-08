# `reference.page.location.anchor`

`anchor.py` owns the immutable `ReferenceTopicAnchor` value. Each anchor owns
its bounded NFKC/case-fold tokenization, identity, and whole-token phrase match.
It does not provide static helper methods or retain payloads in results.
