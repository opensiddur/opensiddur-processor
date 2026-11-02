"""Which licence each imported column is under, from ``licence_decisions.yaml``.

The decision is made per column, not per post, because a post that claims fair use may set a
public-domain original beside a translation that is still in copyright: the original can be
imported and the translation cannot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from opensiddur.importer.opensiddur_org.parse_post import Column, Post

DECISIONS_PATH = Path(__file__).parent / "licence_decisions.yaml"


@dataclass(frozen=True)
class Licence:
    id: str
    url: str
    name: str


#: The licences JLPTEI allows (``schema/JLPTEI-3.md``). CC URLs are written in the
#: ``https://creativecommons.org/...`` form the other importers use.
LICENCES: dict[str, Licence] = {
    licence.id: licence
    for licence in (
        Licence("cc0-1.0", "https://creativecommons.org/publicdomain/zero/1.0/",
                "Creative Commons Zero 1.0 Universal"),
        Licence("pd-mark-1.0", "https://creativecommons.org/publicdomain/mark/1.0/",
                "Public Domain Mark 1.0"),
        Licence("cc-by-3.0", "https://creativecommons.org/licenses/by/3.0/",
                "Creative Commons Attribution 3.0 Unported"),
        Licence("cc-by-4.0", "https://creativecommons.org/licenses/by/4.0/",
                "Creative Commons Attribution 4.0 International"),
        Licence("cc-by-sa-3.0", "https://creativecommons.org/licenses/by-sa/3.0/",
                "Creative Commons Attribution-ShareAlike 3.0 Unported"),
        Licence("cc-by-sa-4.0", "https://creativecommons.org/licenses/by-sa/4.0/",
                "Creative Commons Attribution-ShareAlike 4.0 International"),
    )
}


@dataclass(frozen=True)
class LicenceDecision:
    status: Literal["allow", "reject", "undecided"]
    licence: Licence | None = None
    #: Why the column is under ``licence`` when the post's own licence says otherwise, or
    #: why it was rejected or is undecided.
    basis: str = ""


@dataclass
class LicenceDecisions:
    licences: dict[str, dict[str, Any]]
    posts: dict[int, dict[str, Any]]

    def for_column(self, post: Post, column: Column) -> LicenceDecision:
        post_entry = self.posts.get(post.post_id)
        if post_entry is not None and lapsed(post_entry, post):
            post_entry = None
        if post_entry is not None and "hold" in post_entry:
            held = post_entry.get("columns")
            if held is None or column.lang in held:
                return LicenceDecision("undecided", basis=f"held: {post_entry['hold']}")
            post_entry = None
        if post_entry is not None:
            if "reject" in post_entry:
                return LicenceDecision("reject", basis=str(post_entry["reject"]))
            if "allow" not in post_entry:
                raise ValueError(f"licence decision for post {post.post_id} neither allows, rejects nor holds: {post_entry}")
            columns = post_entry.get("columns")
            if columns is None or column.lang in columns:
                return LicenceDecision(
                    "allow", self._licence(post_entry["allow"]), str(post_entry.get("reason", ""))
                )

        entry = self.licences.get(normalize_licence_url(post.licence_url))
        if entry is None:
            reason = f"licence {post.licence_url!r} is undecided" if post.licence_url else "no licence"
            return LicenceDecision("undecided", basis=reason)
        if "reject" in entry:
            return LicenceDecision("reject", basis=str(entry["reject"]))
        if "allow" in entry:
            return LicenceDecision("allow", self._licence(entry["allow"]), str(entry.get("basis", "")))
        before = entry.get("public_domain_sources_before")
        if before is not None:
            year = original_year(post)
            if column.role == "source" and year is not None and year < int(before):
                return LicenceDecision(
                    "allow", LICENCES["pd-mark-1.0"],
                    f"The original was published in {year} and is in the public domain.",
                )
            return LicenceDecision(
                "undecided", basis=f"licence {post.licence_url!r} needs a decision for this column"
            )
        raise ValueError(f"licence decision for {post.licence_url!r} names no action: {entry}")

    @staticmethod
    def _licence(licence_id: str) -> Licence:
        try:
            return LICENCES[licence_id]
        except KeyError as exc:
            raise ValueError(f"unknown licence id {licence_id!r} in licence decisions") from exc


def lapsed(entry: dict[str, Any], post: Post) -> bool:
    """Whether a decision about one post no longer holds: it was made against the post as last
    updated on ``as_of`` under the licence ``licence``, and the post has since been updated or
    relicensed. The post is then decided again, so a rejection is never permanent."""
    if "as_of" in entry and str(entry["as_of"]) != post.last_updated:
        return True
    if "licence" in entry and normalize_licence_url(str(entry["licence"])) != normalize_licence_url(post.licence_url):
        return True
    return False


def normalize_licence_url(url: str) -> str:
    """The form decisions are keyed by: https, and a trailing slash on Creative Commons URLs."""
    url = url.strip().rstrip("'\"")
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    url = url.replace("https://www.creativecommons.org/", "https://creativecommons.org/")
    if url.startswith("https://creativecommons.org/") and not url.endswith("/"):
        url += "/"
    return url


def original_year(post: Post) -> int | None:
    """The year the original was finished, from ``date_src_end`` (or the start)."""
    for value in (post.date_src_end, post.date_src_start):
        if value[:4].isdigit():
            return int(value[:4])
    return None


def load_decisions(path: Path = DECISIONS_PATH) -> LicenceDecisions:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    licences = {normalize_licence_url(url): entry or {} for url, entry in (data.get("licences") or {}).items()}
    posts = {int(post_id): entry or {} for post_id, entry in (data.get("posts") or {}).items()}
    return LicenceDecisions(licences=licences, posts=posts)
