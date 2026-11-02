"""Credits: who made each imported text, and under which contributor URN.

opensiddur.org gives one person a WordPress user per role: "Isaac Gantwerk Mayer",
"Isaac Gantwerk Mayer (translation)", "Isaac Gantwerk Mayer (transcription & naqdanut)".
The export's ``contributors_by_id.json`` ties them together with ``sibling_ids`` and names
each user's role in ``role_label``. A person gets one URN, from the slug of their user with
no role: ``urn:x-opensiddur:contributor:opensiddur.org/isaac-gantwerk-mayer``.

A coauthor with a role whose account is active made the digital text (a translation, a
transcription) and is credited with a ``tei:respStmt``. The site also keeps inactive profiles
for people who never used it: the translators of the printed books it transcribes (Helena
Frank, Solomon Solis-Cohen). Their work is credited in the source ``tei:bibl``, under no
contributor URN, because an ``opensiddur.org`` URN claims that the person contributed to
the Open Siddur. A coauthor without a role, or with a death date, is an author of the
original and goes in the ``tei:bibl`` too. ``schema/JLPTEI-3.md`` ("Contributors and
contributor URNs") draws the same line.

Every ``opensiddur.org`` contributor URN must be registered in
``specs/urn_registry/contributor.jsonl``. This module never registers anyone; it reports the
people who are missing so that the lines can be reviewed before they are added.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opensiddur.common.urn_registry import REGISTRY_DIRECTORY
from opensiddur.importer.opensiddur_org.parse_post import Post

CONTRIBUTOR_PREFIX = "urn:x-opensiddur:contributor:opensiddur.org/"

#: Words in a role qualifier -> the JLPTEI ``resp/@key`` and its display text. Checked in
#: order; the first match wins.
ROLE_KEYS: tuple[tuple[str, str, str], ...] = (
    ("translat", "trl", "Translated by"),
    ("transcri", "trc", "Transcribed by"),
    ("naqdan", "trc", "Transcribed by"),
    ("emend", "edt", "Edited by"),
    ("amend", "edt", "Edited by"),
    ("imaging", "fac", "Facsimile by"),
)

#: Which kinds of column each responsibility is credited on. A transcriber made the source
#: text; a translator made the translation. Anything else is credited everywhere.
RESP_COLUMN_ROLES: dict[str, frozenset[str]] = {
    "trl": frozenset({"translation", "adaptation"}),
    "trc": frozenset({"source", "transliteration", "hebraization", "reconstruction", ""}),
}


@dataclass(frozen=True)
class Credit:
    key: str
    resp: str
    name: str
    slug: str

    @property
    def urn(self) -> str:
        return CONTRIBUTOR_PREFIX + self.slug


#: Names the site gives to a coauthor it cannot name. They are credited with nothing.
PLACEHOLDER_SLUGS = frozenset({"unknown", "anonymous"})


@dataclass(frozen=True)
class Credits:
    """A post's credits: who made the digital text, the original's authors, and the people
    whose work on the printed source (a translation) is credited in the source bibl."""

    responsibilities: tuple[Credit, ...]
    authors: tuple[str, ...]
    source_responsibilities: tuple[Credit, ...] = ()

    def for_column_role(self, role: str) -> tuple[Credit, ...]:
        return tuple(
            credit
            for credit in self.responsibilities
            if credit.key not in RESP_COLUMN_ROLES or role in RESP_COLUMN_ROLES[credit.key]
        )


class Contributors:
    """The export's ``contributors_by_id.json``, indexed by slug."""

    def __init__(self, by_id: dict[str, dict[str, Any]]):
        self.by_id = by_id
        self.by_slug = {entry.get("author_slug", ""): entry for entry in by_id.values()}

    @classmethod
    def load(cls, path: Path) -> "Contributors":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def person_slug(self, profile_slug: str) -> str:
        """The slug of the person behind a role-specific user: their user with no role."""
        entry = self.by_slug.get(profile_slug)
        if entry is None:
            return profile_slug
        if not entry.get("role_label"):
            return entry.get("author_slug") or profile_slug
        for sibling_id in _sibling_ids(entry):
            sibling = self.by_id.get(str(sibling_id))
            if sibling and not sibling.get("role_label"):
                return sibling.get("author_slug") or profile_slug
        return entry.get("author_slug") or profile_slug

    def display_name(self, profile_slug: str, fallback: str) -> str:
        entry = self.by_slug.get(self.person_slug(profile_slug))
        name = (entry or {}).get("display_name") or fallback
        return re.sub(r"\s*\([^()]*\)\s*$", "", name).strip()

    def death_date(self, profile_slug: str) -> str:
        return str((self.by_slug.get(profile_slug) or {}).get("death_date") or "")

    def is_active(self, profile_slug: str) -> bool:
        """Whether any of the person's accounts is active, i.e. they use the site."""
        entry = self.by_slug.get(profile_slug)
        if entry is None:
            return False
        accounts = [entry] + [self.by_id.get(str(i)) or {} for i in _sibling_ids(entry)]
        return any(account.get("status") == "active" for account in accounts)


def _sibling_ids(entry: dict[str, Any]) -> list[int]:
    value = entry.get("sibling_ids") or []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return [int(v) for v in value if str(v).isdigit()]


def role_key(qualifier: str) -> tuple[str, str] | None:
    """The responsibility a role qualifier names, or None when it names no role (some
    qualifiers only tell two people apart: "(Charleston, South Carolina)")."""
    lowered = qualifier.lower()
    for word, key, resp in ROLE_KEYS:
        if word in lowered:
            return key, resp
    return None


def post_credits(post: Post, contributors: Contributors) -> Credits:
    responsibilities: list[Credit] = []
    source_responsibilities: list[Credit] = []
    authors: list[str] = []
    for coauthor in post.coauthors:
        role = role_key(coauthor.qualifier)
        name = contributors.display_name(coauthor.profile_slug, coauthor.name)
        slug = contributors.person_slug(coauthor.profile_slug)
        if slug in PLACEHOLDER_SLUGS:
            continue
        if role is None or contributors.death_date(coauthor.profile_slug):
            if name not in authors:
                authors.append(name)
            continue
        key, resp = role
        credit = Credit(key=key, resp=resp, name=name, slug=slug)
        target = responsibilities if contributors.is_active(coauthor.profile_slug) else source_responsibilities
        if credit not in target:
            target.append(credit)
    return Credits(tuple(responsibilities), tuple(authors), tuple(source_responsibilities))


def registered_contributors(registry_directory: Path = REGISTRY_DIRECTORY) -> set[str]:
    path = registry_directory / "contributor.jsonl"
    urns: set[str] = set()
    if not path.exists():
        return urns
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            urns.add(json.loads(line)["urn"])
    return urns


def candidate_line(credit: Credit) -> str:
    """A ``contributor.jsonl`` line for a person not yet registered, for review. Directional
    marks the site leaves after a name in another script are dropped from the label."""
    label = re.sub("[\u200e\u200f\u202a-\u202e]", "", credit.name).strip()
    return json.dumps({"urn": credit.urn, "status": "canonical", "label_en": label}, ensure_ascii=False)


def unregistered(credits: Credits, registered: set[str]) -> list[Credit]:
    """The people credited with a URN that is not registered, each once."""
    missing: dict[str, Credit] = {}
    for credit in credits.responsibilities:
        if credit.urn not in registered:
            missing.setdefault(credit.urn, credit)
    return list(missing.values())
