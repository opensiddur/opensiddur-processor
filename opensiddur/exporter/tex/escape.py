""" Escaping literal text for LaTeX.

Shared by everything that puts user-supplied strings — running-head templates,
section separators, conditional markers — into the emitted document.
"""

import re

from opensiddur.common.bidi import strip_bidi_formatting

# Stands in for a literal backslash while the other specials are escaped, so
# that the braces of its own replacement text are not escaped in turn. U+0000
# cannot occur in a YAML scalar, so it can never collide with real input.
_BACKSLASH_SENTINEL = "\x00"


def escape_tex(s: str) -> str:
    """Escape characters that have special meaning in LaTeX.

    Covers the same characters, the same way, as ``f:escape-tex`` in ``tex/common.xsl``.
    Bidi formatting characters are dropped: ``\\textdir`` ignores them, and a font without
    a glyph for them prints a box (see ``opensiddur.common.bidi``).
    """
    t = strip_bidi_formatting(s).replace("\\", _BACKSLASH_SENTINEL)
    t = re.sub(r"([&%$#_{}])", r"\\\1", t)
    t = t.replace("~", r"\textasciitilde{}")
    t = t.replace("^", r"\textasciicircum{}")
    return t.replace(_BACKSLASH_SENTINEL, r"\textbackslash{}")
