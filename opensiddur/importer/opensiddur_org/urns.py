"""Each post's URNs, decided once and recorded in ``specs/opensiddur_org/post_urns.jsonl``.

A post that is a version of a text already in the collection — a psalm, the Birkat
Hamazon, a prayer in Birnbaum — uses that text's URNs, so that it can be set in parallel with
the other versions. Only a post that matches nothing gets URNs of its own. Either way the
decision is recorded by post ID, so a later change of title, slug or category never changes a
post's URNs:

    {"post_id": 123, "kind": "existing", "urn": "urn:x-opensiddur:text:bible:psalms/29",
     "rows": {"1": "urn:x-opensiddur:text:bible:psalms/29/1", ...}}
    {"post_id": 456, "kind": "new", "urn": "urn:x-opensiddur:text:prayer:some_prayer"}

A ``new`` post's rows are ``<urn>/<n>``, numbered from 1 over the rows that are not
headings, except where ``rows`` names an existing URN: a post that strings together prayers
already in the collection (the Ḥanukkah blessings, say) is new as a whole but shares its
parts. An ``existing`` post names each row's URN, or null for a row that matches no part of
the existing text: a place where the version departs from the original. ``spans`` records
which part of the original each such row stands in for, which its milestone corresponds to.

A post with more than one table holds that many texts. Table ``k`` is the text
``<urn>/<k>``, unless ``tables`` records a decision of its own for it (an existing text, say):

    {"post_id": 4957, "kind": "new", "urn": "urn:x-opensiddur:text:prayer:scaling_the_walls",
     "tables": {"1": {"kind": "existing", "urn": "urn:x-opensiddur:text:bible:psalms/67", ...}}}
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from opensiddur.common.constants import REPO_ROOT

if TYPE_CHECKING:
    from opensiddur.importer.opensiddur_org.parse_post import Post

POST_URNS_PATH = REPO_ROOT / "specs" / "opensiddur_org" / "post_urns.jsonl"
TEXT_PREFIX = "urn:x-opensiddur:text:"

#: Tags that make a post a poem rather than a prayer.
POEM_TAGS = ("piyyut", "piyyuṭ", "פיוט", "poem", "poetry", "hymn", "zemer", "zemirot", "qinah", "ḳinah")


@dataclass
class PostUrns:
    post_id: int
    kind: str
    urn: str
    rows: dict[int, str | None] = field(default_factory=dict)
    #: Table number -> its own decision, for a post with more than one table.
    tables: dict[int, "PostUrns"] = field(default_factory=dict)
    #: For an ``existing`` post, each unmapped row -> the span of the original it stands in
    #: for, a range like ``…:bible:psalms/29/3-6``, or "" for material the version adds.
    spans: dict[int, str] = field(default_factory=dict)

    def table(self, number: int, count: int) -> "PostUrns":
        """The URNs of the post's table ``number`` (from 1) of ``count``."""
        if count == 1:
            return self
        return self.tables.get(number) or PostUrns(self.post_id, "new", f"{self.urn}/{number}")

    def quoted(self) -> "PostUrns":
        """For an essay, whose own URN is the essay's: the text of the passages it quotes."""
        return PostUrns(self.post_id, "new", f"{self.urn}/quoted")

    def row_urn(self, n: int) -> str | None:
        if self.kind == "new":
            return self.rows.get(n) or f"{self.urn}/{n}"
        return self.rows.get(n)

    def to_json(self) -> str:
        data: dict[str, object] = {"post_id": self.post_id, "kind": self.kind, "urn": self.urn}
        rows = {str(n): urn for n, urn in sorted(self.rows.items()) if urn or self.kind == "existing"}
        if rows:
            data["rows"] = rows
        if self.spans:
            data["spans"] = {str(n): span for n, span in sorted(self.spans.items())}
        if self.tables:
            data["tables"] = {str(n): json.loads(t.to_json()) for n, t in sorted(self.tables.items())}
            for table in data["tables"].values():
                del table["post_id"]
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "PostUrns":
        return cls.from_data(json.loads(line))

    @classmethod
    def from_data(cls, data: dict, post_id: int | None = None) -> "PostUrns":
        post_id = int(data["post_id"]) if post_id is None else post_id
        rows = {int(n): urn for n, urn in (data.get("rows") or {}).items()}
        tables = {int(n): cls.from_data(t, post_id) for n, t in (data.get("tables") or {}).items()}
        spans = {int(n): span for n, span in (data.get("spans") or {}).items()}
        return cls(post_id=post_id, kind=data["kind"], urn=data["urn"], rows=rows, tables=tables,
                   spans=spans)


def load_post_urns(path: Path = POST_URNS_PATH) -> dict[int, PostUrns]:
    if not path.exists():
        return {}
    records = [PostUrns.from_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {record.post_id: record for record in records}


def save_post_urns(records: dict[int, PostUrns], path: Path = POST_URNS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(records[k].to_json() + "\n" for k in sorted(records))
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def is_poem(tags: list[str]) -> bool:
    lowered = " ".join(tags).lower()
    return any(tag in lowered for tag in POEM_TAGS)


def mint(post: "Post", taken: set[str], variants: Mapping[str, str] | None = None) -> PostUrns:
    """A new URN for a post that matches nothing in the collection.

    The name is the post's title, by ``specs/NAMING_SCHEME.md``: its Latin part up to the
    attribution, folded to ASCII, each word respelled by the spelling list (``variants``,
    by default ``specs/naming/spellings.yaml``), then its original author's name. The site
    still finds the post by the bibliography's link to it, so the URN need not repeat its
    slug. If that name is already taken (by an unrelated text, since a related one would have
    matched), the post ID is appended.
    """
    from opensiddur.importer.opensiddur_org.naming import text_name

    if variants is None:
        from opensiddur.common.validate_names import load_spellings

        variants = load_spellings().variants
    namespace = "poem" if is_poem(post.tags) else "prayer"
    urn = f"{TEXT_PREFIX}{namespace}:{text_name(post, variants)}"
    if urn in taken:
        urn = f"{urn}_{post.post_id}"
    return PostUrns(post_id=post.post_id, kind="new", urn=urn)


def registry_lines(
    record: PostUrns, rows: Iterable[int], *, label_en: str, label_he: str = "",
    parent: str | None = None,
) -> list[dict[str, object]]:
    """The registry records a ``new`` post's URNs need: the post (under ``parent``, for one
    table of several) and each of ``rows`` (the row numbers that have text in some imported
    column)."""
    if record.kind != "new":
        return []
    label_en = label_en or record.urn.rsplit(":", 1)[-1]
    top: dict[str, object] = {"urn": record.urn, "status": "canonical", "label_en": label_en}
    if parent:
        top["parent"] = parent
    if label_he:
        top["label_he"] = label_he
    lines: list[dict[str, object]] = [top]
    for n in sorted(rows):
        if record.rows.get(n):
            continue  # an existing text's URN, registered already
        lines.append(
            {"urn": f"{record.urn}/{n}", "status": "canonical", "parent": record.urn,
             "label_en": f"{label_en} / {n}"}
        )
    return lines
