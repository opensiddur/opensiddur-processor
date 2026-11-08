"""The typography settings an electronic book can honour, as CSS.

A settings file's `typography` describes the document, not a renderer (doc/typography.md), but
most of it is about paper: page size, margins, running heads, line numbers. A reflowing book
has none of those. What carries over is set here:

Fonts, text roles, paragraphs, lists, markers, notes, parallel columns and contents
are translated here or passed to the HTML renderer. Physical-page settings remain
print-only. See doc/typography.md for the setting-by-setting mapping.

The standalone exporter names fonts for the reader's device. The hosted Builder
embeds installed fonts into its HTML output.
"""

from __future__ import annotations

from opensiddur.exporter.typography import (
    HEBREW_FAMILY,
    LATIN_FAMILY,
    Alignment,
    ConditionalBlock,
    NamedSize,
    TypographyConfig,
    Visibility,
)


def css_length(length: str) -> str:
    """A settings length in CSS: TeX's big point, which CSS lacks, as points."""
    if length.endswith("bp"):
        return f"{float(length[:-2]) * 72.27 / 72:g}pt"
    return length


def css_string(text: str) -> str:
    """A CSS string literal."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\a ")
    return f'"{escaped}"'


def _stack(typography: TypographyConfig, family: str) -> str:
    # Always there: TypographyConfig fills in both chains a settings file leaves out.
    names = typography.fonts[family].names
    return ", ".join([*(css_string(name) for name in names), "serif"])


_ALIGN = {
    Alignment.JUSTIFY: "justify",
    Alignment.LEFT: "left",
    Alignment.RIGHT: "right",
    Alignment.CENTER: "center",
}

# Selectors for the text roles emitted by html.xslt and the book's colophon.
STYLE_SELECTORS = {
    "body": ".os-book",
    "heading1": '.head[data-heading-level="1"]:not(:where(.head-translation))',
    "heading2": '.head[data-heading-level="2"]:not(:where(.head-translation))',
    "heading3": '.head[data-heading-level="3"]:not(:where(.head-translation))',
    "heading4": '.head:is([data-heading-level="4"], [data-heading-level="5"], [data-heading-level="6"]):not(:where(.head-translation))',
    "heading_translation": ".head-translation",
    "title_main": ".titlePart.docTitle-main, .titlePart:not([class*='docTitle-'])",
    "title_sub": ".titlePart.docTitle-sub",
    "title_alt": ".titlePart.docTitle-alt, .titlePart.docTitle-alt-sub",
    "byline": ".byline",
    "edition": ".docEdition",
    "imprint": ".docImprint",
    "epigraph": ".epigraph",
    "imprimatur": ".imprimatur",
    "title_page_block": ".title-page-block",
    "distribution_notice": ".os-distribution",
    "back_notice": ".os-back-notice",
    "citation": ".citation",
    "parsha": ".parsha",
    "aliyah": ".aliyah",
    "verse_number": ".v",
    "chapter_number": ".ch",
    "instruction": ".rubric",
    "note": ".note",
    "note_mark": ".note-ref, .note-number",
    "section_separator": ".section-separator",
    "list_label": ".list > .label",
    # html.xslt gives a tei:hi a rend-* class per token; the superscript's raise is
    # reader.css's, fixed, and the role styles the raised text.
    "highlight_italic": ".rend-italic",
    "highlight_bold": ".rend-bold",
    "highlight_small_caps": ".rend-small-caps, .rend-smallcaps",
    "highlight_superscript": ".rend-sup, .rend-superscript, .rend-suspended, .rend-raised",
    "highlight_large": ".rend-large",
    "highlight_small": ".rend-small",
    "foreign": ".foreign",
    "reference": ".ref",
    "poetry_line": ".l",
    "list_item": ".list > .item",
    "abbreviation": ".abbr",
    "expansion": ".expan",
    "printed_error": ".sic",
    "correction": ".corr",
    "qere": ".read",
    # The words of the form, not the parentheses reader.css sets around it (html.xslt).
    "ketiv": ".written > .form",
    "alternative_reading": ".option-alt > .form",
}


def normal_size(typography: TypographyConfig, family: str) -> str:
    """A family's normal size, in TeX points, before a role scales it."""
    size = typography.fonts[family].entries[0].normal_size
    return f"{size:g}pt" if size is not None else typography.page.base_font_size.value


def size_properties(size: str) -> list[str]:
    """Inherited logical size survives nested changes of language and font."""
    sizes = list(NamedSize)
    if size in sizes:
        step = sizes.index(NamedSize(size)) - sizes.index(NamedSize.NORMAL)
        return [f"--os-size-scale: {1.2 ** step:.8g};", "--os-absolute-size: initial;"]
    return [f"--os-absolute-size: {css_length(size)};"]


def style_css(typography: TypographyConfig) -> list[str]:
    rules = []
    for role, selector in STYLE_SELECTORS.items():
        style = getattr(typography.styles, role)
        declarations = []
        if style.font is not None:
            declarations += [
                f"--os-role-family: {_stack(typography, style.font)};",
                f"--os-role-normal: var(--normal-{style.font});",
            ]
        if style.size is not None:
            declarations += size_properties(style.size)
            if role == "highlight_superscript":
                # A size the role names is the raised text's size, as in the PDF, rather
                # than the size reader.css then reduces.
                declarations.append("--os-rend-scale: 1;")
        for field, property_name in (
            ("weight", "font-weight"), ("style", "font-style"),
            ("variant", "font-variant"), ("align", "--os-role-align"),
        ):
            value = getattr(style, field)
            if value is not None:
                declarations.append(f"{property_name}: {value.value};")
        for field, property_name in (("space_before", "margin-block-start"),
                                     ("space_after", "margin-block-end")):
            value = getattr(style, field)
            if value is not None:
                declarations.append(f"{property_name}: {css_length(value)};")
        if declarations:
            scoped = selector if role == "body" else f":is(.os-book, .os-about) :is({selector})"
            rules.append(f"{scoped} {{ {' '.join(declarations)} }}")
    return rules


def xslt_parameters(typography: TypographyConfig) -> dict[str, str | bool]:
    """The settings html.xslt reads: the characters that bracket a conditional run."""
    conditional = typography.markers.conditional
    return {
        "inline-open": conditional.inline_open,
        "inline-close": conditional.inline_close,
        "block": conditional.block.value,
        "notes-mark": typography.notes.mark.value,
        "notes-visible": typography.notes.placement.value != "none",
    }


def typography_css(typography: TypographyConfig) -> str:
    """The book's own styles, layered over reader.css.

    Every typography variable reader.css uses is written here, for every book: reader.css
    gives them no value of its own, so there is no fallback to disagree with the settings.
    """
    markers = typography.markers
    conditional = markers.conditional
    rules = [
        ":root {",
        f"  --font-latin: {_stack(typography, LATIN_FAMILY)};",
        f"  --font-hebrew: {_stack(typography, HEBREW_FAMILY)};",
        *(f"  --normal-{family}: {normal_size(typography, family)};" for family in typography.fonts),
        f"  --paragraph-indent: {css_length(typography.paragraphs.indent)};",
        f"  --list-indent: {css_length(typography.lists.item_indent)};",
        f"  --line-spacing: {typography.paragraphs.line_spacing * 1.35:.8g};",
        f"  --text-align: {_ALIGN[typography.paragraphs.alignment]};",
        f"  --paragraph-spacing: {css_length(typography.paragraphs.spacing)};",
        f"  --cond-rule-width: {conditional.rule_width};",
        f"  --cond-rule-thickness: {css_length(conditional.rule_thickness)};",
        "}",
        f".section-separator::before {{ content: {css_string(markers.section_separator)}; }}",
    ]
    rules += style_css(typography)
    if typography.notes.placement.value == "none":
        rules.append(".note-anchor { display: none; }")
    if typography.notes.anchor.value == "inline":
        rules.append(".note-ref { vertical-align: baseline; }")
    elif typography.notes.anchor.value == "interlinear":
        rules.append(".note-ref { position: absolute; transform: translateY(-0.6em); }")
    if typography.parallel.layout.value == "interleaved":
        rules += [
            ".par { grid-template-columns: 1fr; "
            f"row-gap: {css_length(typography.parallel.interleaved.spacing)}; }}",
            ".col-parallel { "
            f"margin-inline: {css_length(typography.parallel.interleaved.translation_indent)}; "
            + " ".join(size_properties(typography.parallel.interleaved.translation_size)) + " }",
        ]
    elif typography.parallel.layout.value == "pairs":
        width = typography.parallel.column_width
        rules.append(
            "@media (min-width: 40.001rem) { .par { "
            f"grid-template-columns: repeat(2, {width}); "
            f"column-gap: min(2rem, calc(100% - 2 * {width})); "
            f"justify-content: {typography.parallel.column_position.value}; }} }}"
        )
    if markers.verse_numbers == Visibility.HIDDEN:
        rules.append(".v { display: none; }")
    if markers.chapter_numbers == Visibility.HIDDEN:
        rules.append(".ch { display: none; }")
    if conditional.block != ConditionalBlock.RULE:
        rules.append(".cm-block .cm-br { border: 0; width: auto; }")
    return "\n".join(rules) + "\n"
