""" Escaping literal text for LaTeX.

Shared by everything that puts user-supplied strings — running-head templates,
section separators, conditional markers — into the emitted document.
"""

import re

# Stands in for a literal backslash while the other specials are escaped, so
# that the braces of its own replacement text are not escaped in turn. U+0000
# cannot occur in a YAML scalar, so it can never collide with real input.
_BACKSLASH_SENTINEL = "\x00"


def escape_tex(s: str) -> str:
    """Escape characters that have special meaning in LaTeX.

    Covers the same characters, the same way, as ``f:escape-tex`` in ``tex/common.xsl``.
    """
    t = s.replace("\\", _BACKSLASH_SENTINEL)
    t = re.sub(r"([&%$#_{}])", r"\\\1", t)
    t = t.replace("~", r"\textasciitilde{}")
    t = t.replace("^", r"\textasciicircum{}")
    return t.replace(_BACKSLASH_SENTINEL, r"\textbackslash{}")
