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
class PostDecisions:
    #: Post ID -> why it is out of scope.
    out_of_scope: dict[int, str] = field(default_factory=dict)
    #: Post ID -> column header -> the column's language (BCP 47).
    column_languages: dict[int, dict[str, str]] = field(default_factory=dict)
    #: Post ID -> colour (as its style writes it, lowercased) -> what it means.
    colours: dict[int, dict[str, str]] = field(default_factory=dict)
    #: Post ID -> what it is: an essay about the passages it quotes.
    essays: dict[int, str] = field(default_factory=dict)


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
    )


@functools.cache
def default_post_decisions() -> PostDecisions:
    return load_post_decisions()
