"""Deterministic quality warnings for retained Pix2Tex output."""

from __future__ import annotations

import re

_ENVIRONMENT_TOKEN = re.compile(r"\\(begin|end)\{([^{}]+)\}")
_LABEL = re.compile(r"\(([^()]*(?:\\mathrm\{[^{}]*\})?[^()]*)\)")
_LABEL_COMMAND = re.compile(r"\\(?:mathrm|text)\{([^{}]*)\}")
_LABEL_NOISE = re.compile(r"\\[A-Za-z]+|[{}\\\s]")
_LABEL_VALUE = re.compile(r"[A-Za-z]?\d+(?:\.\d+)*(?:[A-Za-z])?")
_SPACING_COMMAND = re.compile(r"\\(?:qquad|quad|;|,)")


def pix2tex_output_quality_warning_codes(
    latex: str,
    native_text: str,
    source_labels: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return high-precision warnings without accepting or replacing output."""

    warnings: list[str] = []
    brace_depth = 0
    braces_valid = True
    preceding_slashes = 0
    for character in latex:
        escaped = preceding_slashes % 2 == 1
        if character == "{" and not escaped:
            brace_depth += 1
        elif character == "}" and not escaped:
            brace_depth -= 1
            if brace_depth < 0:
                braces_valid = False
                break
        if character == "\\":
            preceding_slashes += 1
        else:
            preceding_slashes = 0
    if brace_depth != 0 or not braces_valid:
        warnings.append("latex_brace_mismatch")

    delimiter_depth = 0
    delimiters_valid = True
    for match in re.finditer(r"\\(?:left|right)(?![A-Za-z])", latex):
        if match.group() == r"\left":
            delimiter_depth += 1
        else:
            delimiter_depth -= 1
            if delimiter_depth < 0:
                delimiters_valid = False
                break
    if delimiter_depth != 0 or not delimiters_valid:
        warnings.append("latex_left_right_delimiter_mismatch")

    environments: list[str] = []
    environments_valid = True
    for match in _ENVIRONMENT_TOKEN.finditer(latex):
        operation, name = match.groups()
        if operation == "begin":
            environments.append(name)
        elif not environments or environments.pop() != name:
            environments_valid = False
            break
    if environments or not environments_valid:
        warnings.append("latex_environment_mismatch")

    spacing_count = len(_SPACING_COMMAND.findall(latex))
    if spacing_count > 64:
        warnings.append("latex_excessive_spacing_commands")
    if len(latex) > 800:
        warnings.append("latex_output_expansion_suspect")

    labels: list[str] = []
    for match in _LABEL.finditer(latex):
        value = _LABEL_COMMAND.sub(r"\1", match.group(1))
        value = _LABEL_NOISE.sub("", value)
        if _LABEL_VALUE.fullmatch(value) is not None:
            labels.append(value)
    expected_labels: set[str] = set()
    for source_label in source_labels:
        value = source_label.strip()
        if value.startswith("(") and value.endswith(")"):
            value = value[1:-1]
        value = _LABEL_COMMAND.sub(r"\1", value)
        value = _LABEL_NOISE.sub("", value)
        if _LABEL_VALUE.fullmatch(value) is not None:
            expected_labels.add(value)
    if any(labels.count(value) > 1 for value in expected_labels):
        warnings.append("latex_duplicate_equation_label")

    if native_text.count("=") > latex.count("="):
        warnings.append("latex_native_equality_missing")
    return tuple(warnings)
