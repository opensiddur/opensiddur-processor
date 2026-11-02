"""Decisions about single posts, from ``post_decisions.yaml``.

The rules in ``specs/OPENSIDDUR_ORG_IMPORT.md`` settle most posts. A post they read wrongly, or
leave open, is decided once by a person and recorded here, so the question is not asked again.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DECISIONS_PATH = Path(__file__).parent / "post_decisions.yaml"


@dataclass(frozen=True)
class Layout:
    """Where a post that does not use the site's toggleable tables keeps its text. Each is an
    XPath over the post's content."""

    #: The elements holding the text, in order: a ``table`` (its columns are the text's
    #: languages) or a ``div[@lang]`` (a text in one language). Each is a table of the post.
    text: tuple[str, ...] = ()
    #: A table whose columns are the post's introduction, one language each. Each language's
    #: goes in the project of that language.
    introduction: str | None = None
    #: Column (from 1) of the text tables -> a header for each of its cell's parts in turn: the
    #: text before its first paragraph, then each ``p``. ``None`` drops a part.
    split: dict[int, tuple[str | None, ...]] = field(default_factory=dict)
    #: What follows the text credits where it was first published: a source, not notes.
    credit_after: bool = False
    #: An element of the post's own words quoting a text already in the collection -> that
    #: text's URN. It is transcluded where it stands rather than copied, so a book sets the
    #: edition it prefers.
    transclusions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PostDecisions:
    #: Post ID -> why it is out of scope.
    out_of_scope: dict[int, str] = field(default_factory=dict)
    #: Post ID -> column header -> the column's language (BCP 47).
    column_languages: dict[int, dict[str, str]] = field(default_factory=dict)
    #: Post ID -> colour (as its style writes it, lowercased) -> what it means.
    colours: dict[int, dict[str, str]] = field(default_factory=dict)
    #: Post ID -> what it is: an essay about the passages it quotes.
    essays: dict[int, str] = field(default_factory=dict)
    #: Post ID -> where its text is, for a post whose layout the rules cannot read.
    layouts: dict[int, Layout] = field(default_factory=dict)


NO_DECISIONS = PostDecisions()


def load_post_decisions(path: Path = DECISIONS_PATH) -> PostDecisions:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PostDecisions(
        out_of_scope={int(k): str(v) for k, v in (data.get("out_of_scope") or {}).items()},
        column_languages={
            int(post_id): {str(header): str(lang) for header, lang in headers.items()}
            for post_id, headers in (data.get("column_languages") or {}).items()
        },
        colours={
            int(post_id): {str(colour).lower(): str(meaning) for colour, meaning in colours.items()}
            for post_id, colours in (data.get("colours") or {}).items()
        },
        essays={int(k): str(v) for k, v in (data.get("essays") or {}).items()},
        layouts={int(k): _layout(v) for k, v in (data.get("layouts") or {}).items()},
    )


def _layout(data: dict) -> Layout:
    return Layout(
        text=tuple(str(x) for x in data.get("text") or ()),
        introduction=data.get("introduction"),
        split={int(column): tuple(None if h is None else str(h) for h in headers)
               for column, headers in (data.get("split") or {}).items()},
        credit_after=bool(data.get("credit_after")),
        transclusions={str(path): str(urn) for path, urn in (data.get("transclusions") or {}).items()},
    )


@functools.cache
def default_post_decisions() -> PostDecisions:
    return load_post_decisions()
