"""Which posts are prayers this importer takes, and which of those it can take unaided.

A post is **in scope** when it is filed under "Prayers & Praxes" (category 1132) or below,
and the site itself sets its prayer text: a ``toggleable-table`` with text in it, or liturgy
set in ``div[lang]`` blocks. Index posts, essays, and posts that only link to a file, embed a
scan or play audio are out of scope.

An in-scope post is **standard** when the converter can encode it without help, and
**irregular** otherwise, with the reasons. Irregular posts wait for a per-post override (see
``specs/OPENSIDDUR_ORG_IMPORT.md``, "A skill for irregular posts").
"""

from __future__ import annotations

import dataclasses
import html
from dataclasses import dataclass
from typing import Any

from opensiddur.importer.opensiddur_org.languages import NOT_TEXT_ROLES, UNKNOWN_LANGUAGE
from opensiddur.importer.opensiddur_org.parse_post import Cell, Column, Post
from opensiddur.importer.opensiddur_org.post_decisions import PostDecisions, default_post_decisions

PRAYERS_CATEGORY = 1132


def descendant_categories(categories: list[dict[str, Any]], roots: set[int]) -> set[int]:
    """``roots`` and every category below them."""
    children: dict[int, list[int]] = {}
    for category in categories:
        children.setdefault(int(category.get("parent_id") or 0), []).append(int(category["id"]))
    found: set[int] = set()
    pending = list(roots)
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(children.get(current, []))
    return found


def posts_in_categories(categories: list[dict[str, Any]], category_ids: set[int]) -> set[int]:
    """The IDs of posts filed in any of ``category_ids``."""
    post_ids: set[int] = set()
    for category in categories:
        if int(category["id"]) in category_ids:
            post_ids.update(int(p) for p in category.get("post_ids") or [])
    return post_ids


def category_names(categories: list[dict[str, Any]]) -> dict[int, str]:
    return {int(c["id"]): html.unescape(c.get("name", "")).strip() for c in categories}


def _cell_has_text(cell: Cell) -> bool:
    return not cell.is_empty


@dataclass(frozen=True)
class Scope:
    in_scope: bool
    reason: str


def content_scope(post: Post, decisions: PostDecisions | None = None) -> Scope:
    """Whether the post sets prayer text itself (the category test is separate). Art and
    essays that quote no prayer are out of scope by decision (``post_decisions.yaml``)."""
    if post.slug.startswith("list-of-"):
        return Scope(False, "index post")
    decided = (decisions or default_post_decisions()).out_of_scope.get(post.post_id)
    if decided:
        return Scope(False, decided)
    if post.columns and any(
        _cell_has_text(row.cells[i])
        for row in post.rows
        for i, column in enumerate(post.columns)
        if column.role != "contribute"
    ):
        return Scope(True, "table")
    if any(_cell_has_text(cell) for cell in post.loose_cells):
        return Scope(True, "prose")
    if post.file_links:
        return Scope(False, "file link only")
    if post.embeds:
        return Scope(False, "embed only")
    return Scope(False, "no prayer text")


def imported_columns(post: Post) -> list[tuple[int, Column]]:
    """The columns of the post's (first) table that become projects: every column with text,
    other than an empty "Contribute a translation" column (a source-only post is one project)
    and the columns that are not texts of their own (initials, commentary)."""
    return [
        (index, column)
        for index, column in enumerate(post.columns)
        if column.role not in NOT_TEXT_ROLES
        and any(_cell_has_text(row.cells[index]) for row in post.rows)
    ]


def table_view(post: Post, table_index: int) -> Post:
    """The post as if it had only its table ``table_index``: every per-table function reads
    ``post.columns`` and ``post.rows``."""
    table = post.tables[table_index]
    return dataclasses.replace(post, columns=table.columns, rows=table.rows, tables=[table])


def table_views(post: Post) -> list[Post]:
    return [table_view(post, i) for i in range(len(post.tables))] or [post]


def project_columns(post: Post) -> list[Column]:
    """One column for each project the post makes, across all its tables, in order."""
    found: dict[str, Column] = {}
    for view in table_views(post):
        for _, column in imported_columns(view):
            found.setdefault(column.key, column)
    return list(found.values())


def column_mode(post: Post, index: int) -> set[str]:
    """The kinds of block a column holds, ignoring headings."""
    return {
        block.kind
        for row in post.rows
        for block in row.cells[index].blocks
        if block.kind != "heading"
    }


def is_heading_row(post: Post, row_index: int) -> bool:
    """Whether every cell of a row with text holds just one heading."""
    cells = [cell for cell in post.rows[row_index].cells if not cell.is_empty]
    return bool(cells) and all(
        len(cell.blocks) == 1 and cell.blocks[0].kind == "heading" for cell in cells
    )


def irregularities(post: Post) -> list[str]:
    """Why the converter cannot encode this post unaided, from the post's own structure.

    Licence, contributor and URN problems are added by the caller, which knows the decisions
    and registries.
    """
    reasons: list[str] = []
    if not post.tables:
        reasons.append("prose blocks that do not alternate languages")
        return reasons
    if post.between_blocks:
        reasons.append("text between its blocks")
    if post.undecided_colours:
        reasons.append("colour-coded text: " + ", ".join(sorted(post.undecided_colours)))
    for view in table_views(post):
        for index, column in imported_columns(view):
            if not column.role:
                reasons.append(f"column {column.header!r}: unknown role")
            if column.lang == UNKNOWN_LANGUAGE:
                reasons.append(f"column {column.header!r}: unknown language")
    return reasons
