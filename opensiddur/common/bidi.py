""" Unicode's explicit bidirectional formatting characters.

Web text marks direction with invisible characters: a right-to-left mark after a Hebrew
title, an embedding around a quotation. They mean something only to a renderer that runs
the Unicode bidi algorithm. The TeX output does not: LuaTeX's ``\\textdir`` sets a direction
outright, and a mark set in a Latin font prints as a missing-glyph box. The importers drop
them from what they store, and the TeX escaping drops them from whatever still has them.

``f:escape-tex`` in ``exporter/tex/common.xsl`` strips the same characters. The zero-width
joiner and non-joiner are not bidi controls and are kept.
"""

import re

#: LRM, RLM, ALM, the embeddings and overrides (LRE RLE PDF LRO RLO) and the isolates
#: (LRI RLI FSI PDI).
BIDI_FORMATTING_CHARACTERS = "\u200e\u200f\u061c\u202a-\u202e\u2066-\u2069"

_BIDI_FORMATTING = re.compile(f"[{BIDI_FORMATTING_CHARACTERS}]")


def strip_bidi_formatting(s: str) -> str:
    """``s`` without its explicit bidirectional formatting characters."""
    return _BIDI_FORMATTING.sub("", s)
