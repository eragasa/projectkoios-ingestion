"""Private hard ceilings for OCR contracts."""

_MAX_SELECTIONS = 256
_MAX_IMAGES = 256
_MAX_PIXELS_PER_IMAGE = 25_000_000
_MAX_BYTES_PER_IMAGE = 100_000_000
_MAX_TOTAL_PIXELS = 25_000_000
_MAX_TOTAL_IMAGE_BYTES = 100_000_000
_MAX_LANGUAGES = 16
_MAX_LANGUAGE_CHARACTERS = 64
_MAX_NATIVE_PAGE_BLOCKS = 1_024
_MAX_NATIVE_PAGE_SOURCE_SPANS = 2_048
_MAX_NATIVE_TEXT_REFERENCES = 1_024
_MAX_IDENTITY_FIELD_CHARACTERS = 4_096
_MAX_TOTAL_IDENTITY_CHARACTERS = 1_000_000
_MAX_TOKENS_PER_SELECTION = 100_000
_MAX_LINES_PER_SELECTION = 25_000
_MAX_TEXT_CHARACTERS_PER_ITEM = 1_000_000
_MAX_TEXT_CHARACTERS_PER_SELECTION = 5_000_000
_MAX_WARNINGS_PER_SELECTION = 1_024
_MAX_WARNING_MESSAGE_CHARACTERS = 65_536
_MAX_WARNING_EVIDENCE_ENTRIES = 256
_MAX_WARNING_EVIDENCE_CHARACTERS = 1_000_000
_MAX_TOTAL_TOKENS = 100_000
_MAX_TOTAL_LINES = 25_000
_MAX_TOTAL_TEXT_CHARACTERS = 5_000_000
_MAX_TOTAL_WARNINGS = 4_096
_MAX_RESULT_BYTES = 64_000_000
_GRANDFATHERED_LANGUAGE_TAGS = frozenset(
    {
        "art-lojban",
        "cel-gaulish",
        "en-gb-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "no-bok",
        "no-nyn",
        "sgn-be-fr",
        "sgn-be-nl",
        "sgn-ch-de",
        "zh-guoyu",
        "zh-hakka",
        "zh-min",
        "zh-min-nan",
        "zh-xiang",
    }
)
