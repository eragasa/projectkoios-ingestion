from projectkoios.ingestion.integrations.pix2tex.output_policy import (
    pix2tex_output_quality_warning_codes,
)


def test__output_quality__retains_clean_equation_without_warning() -> None:
    assert not pix2tex_output_quality_warning_codes(
        r"E=m c^{2}\qquad(1)",
        "E = m c2 (1)",
    )


def test__output_quality__does_not_treat_arrow_commands_as_delimiters() -> None:
    assert not pix2tex_output_quality_warning_codes(
        r"x\leftarrow y\rightarrow z",
        "x y z",
    )


def test__output_quality__does_not_treat_escaped_braces_as_groups() -> None:
    assert not pix2tex_output_quality_warning_codes(
        r"S=\left\{x\right\}",
        "S = {x}",
    )


def test__output_quality__reports_structural_mismatches() -> None:
    warnings = pix2tex_output_quality_warning_codes(
        r"\begin{array}{c}\left(x\end{matrix}",
        "x",
    )

    assert warnings == (
        "latex_left_right_delimiter_mismatch",
        "latex_environment_mismatch",
    )


def test__output_quality__reports_excessive_spacing_and_expansion() -> None:
    latex = r"x=1" + (r"\;" * 400)

    warnings = pix2tex_output_quality_warning_codes(latex, "x = 1")

    assert warnings == (
        "latex_excessive_spacing_commands",
        "latex_output_expansion_suspect",
    )


def test__output_quality__reports_duplicate_equation_label() -> None:
    warnings = pix2tex_output_quality_warning_codes(
        r"\begin{array}{c}x\\y\end{array}(4.5\mathrm{c})(4.5\mathrm{c})",
        "x y (4.5c)",
        ("(4.5c)",),
    )

    assert warnings == ("latex_duplicate_equation_label",)


def test__output_quality__does_not_infer_labels_from_numeric_groups() -> None:
    assert not pix2tex_output_quality_warning_codes(
        r"x=(1)(1)",
        "x = (1)(1)",
    )


def test__output_quality__reports_missing_native_equality() -> None:
    warnings = pix2tex_output_quality_warning_codes(
        r"\lvert J_1\rvert\sim\lvert J_2\rvert",
        "|J1| = |J2|",
    )

    assert warnings == ("latex_native_equality_missing",)
