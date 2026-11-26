"""Check that the Tanakh projects agree about what each verse URN denotes.

A verse URN is the only join key between projects: the parallel compiler pairs text by exact
``@corresp`` equality and the reference database resolves transclusion ranges by it. Nothing
in the schema enforces that two projects mean the same thing by ``exodus/20/13``, and when
they disagree nothing fails -- the compiler simply pairs the wrong verses and a range stops
early. This validator is what notices.

Two checks:

* **Duplicates.** A URN naming two places within one project. The reference database keeps
  one of them and every other segment becomes unreachable.
* **Coverage.** The verse URNs each project exposes for a chapter they share. A project that
  is missing verses another has will silently drop text from a parallel compile or a range.

Verses genuinely absent from a witness are not errors, and are listed in
:data:`KNOWN_ABSENCES`. Chapters where a project's verse *count* is still under
investigation are listed in :data:`UNRESOLVED_CHAPTERS`, so they are reported separately
from new regressions rather than drowning them out.
"""

from __future__ import annotations

import argparse
import collections
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.versification import (
    NUMBERING_COMMON,
    NUMBERING_LENINGRAD,
    NUMBERING_MASORAH,
    NUMBERING_PROJECT,
)

VERSE_URN = re.compile(
    r"^urn:x-opensiddur:text:bible:(?P<book>[a-z_0-9]+)/(?P<chapter>\d+)/(?P<verse>\d+)$"
)

#: Projects whose verse URNs must agree, and the numbering each edition follows.
TANAKH_PROJECTS = tuple(NUMBERING_PROJECT[n] for n in
                        (NUMBERING_LENINGRAD, NUMBERING_MASORAH, NUMBERING_COMMON))
_MASORAH_PROJECT = NUMBERING_PROJECT[NUMBERING_MASORAH]
_COMMON_PROJECT = NUMBERING_PROJECT[NUMBERING_COMMON]

#: Verses a witness genuinely does not contain. Not a numbering difference: the text is
#: absent from the edition altogether, so it has no URN there and never should.
KNOWN_ABSENCES: dict[str, set[tuple[str, int, int]]] = {
    # Joshua 21:36-37 are absent from Miqra al pi ha-Masorah.
    _MASORAH_PROJECT: {("joshua", 21, 36), ("joshua", 21, 37)},
}

#: Chapters where a project's verse division is known to differ and has not yet been
#: reconciled with the canonical numbering. These predate the canonical URN space and are
#: reported as unresolved rather than as regressions. Each needs the edition's own text
#: aligned against the canonical division before it can be encoded or fixed.
UNRESOLVED_CHAPTERS: set[tuple[str, str, int]] = {
    (_COMMON_PROJECT, "ezra", 2),
    (_COMMON_PROJECT, "ezra", 4),
    (_COMMON_PROJECT, "isaiah", 9),
    (_COMMON_PROJECT, "kings_2", 18),
    (_COMMON_PROJECT, "leviticus", 14),
    (_COMMON_PROJECT, "nehemiah", 7),
    (_COMMON_PROJECT, "psalms", 30),
}


@dataclass(frozen=True)
class DuplicateVerseUrn:
    project: str
    urn: str
    occurrences: int

    def __str__(self) -> str:
        return f"{self.project}: {self.urn} appears {self.occurrences} times"


@dataclass(frozen=True)
class MissingVerseUrn:
    project: str
    book: str
    chapter: int
    verses: tuple[int, ...]
    present_in: tuple[str, ...]

    def __str__(self) -> str:
        listed = ", ".join(str(v) for v in self.verses)
        others = ", ".join(self.present_in)
        return (
            f"{self.project}: {self.book} {self.chapter} is missing verse(s) {listed}, "
            f"present in {others}"
        )


@dataclass(frozen=True)
class ExtraVerseUrn:
    """A verse no other project has. Almost always a verse attributed to the wrong chapter."""

    project: str
    book: str
    chapter: int
    verses: tuple[int, ...]

    def __str__(self) -> str:
        listed = ", ".join(str(v) for v in self.verses)
        return (
            f"{self.project}: {self.book} {self.chapter} has verse(s) {listed}, "
            "which no other project has"
        )


@dataclass
class VersificationReport:
    duplicates: list[DuplicateVerseUrn] = field(default_factory=list)
    missing: list[MissingVerseUrn] = field(default_factory=list)
    extra: list[ExtraVerseUrn] = field(default_factory=list)
    unresolved: list[MissingVerseUrn | ExtraVerseUrn] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing beyond the known, documented divergences was found."""
        return not self.duplicates and not self.missing and not self.extra


def _verse_urns(path: Path) -> list[tuple[str, int, int]]:
    """Every verse URN in one file, in document order, duplicates included."""
    tree = etree.parse(str(path))
    found = []
    for element in tree.getroot().xpath("//*[@corresp]"):
        match = VERSE_URN.match(element.get("corresp", ""))
        if match:
            found.append(
                (match["book"], int(match["chapter"]), int(match["verse"]))
            )
    return found


def collect_verse_urns(
    project: str, *, project_directory: Path = PROJECT_DIRECTORY
) -> collections.Counter:
    """Count every verse URN a project exposes."""
    project_path = Path(project_directory) / project
    if not project_path.is_dir():
        raise ValueError(f"Project directory does not exist: {project_path}")
    counts: collections.Counter = collections.Counter()
    for xml_file in sorted(project_path.glob("*.xml")):
        counts.update(_verse_urns(xml_file))
    return counts


def validate_versification(
    projects: Iterable[str] = TANAKH_PROJECTS,
    *,
    project_directory: Path = PROJECT_DIRECTORY,
) -> VersificationReport:
    """Compare the verse URNs the given projects expose."""
    projects = tuple(projects)
    report = VersificationReport()
    per_project = {}

    for project in projects:
        counts = collect_verse_urns(project, project_directory=project_directory)
        per_project[project] = set(counts)
        for ref, occurrences in sorted(counts.items()):
            if occurrences > 1:
                book, chapter, verse = ref
                report.duplicates.append(
                    DuplicateVerseUrn(
                        project=project,
                        urn=f"urn:x-opensiddur:text:bible:{book}/{chapter}/{verse}",
                        occurrences=occurrences,
                    )
                )

    # Compare only chapters a project actually covers: a project that has not imported a
    # book at all is incomplete, which is a different thing from disagreeing about it.
    chapters_of = {
        project: {(book, chapter) for book, chapter, _ in refs}
        for project, refs in per_project.items()
    }

    verses_of: dict[str, dict[tuple[str, int], set[int]]] = {}
    for project, refs in per_project.items():
        by_chapter: dict[tuple[str, int], set[int]] = collections.defaultdict(set)
        for book, chapter, verse in refs:
            by_chapter[(book, chapter)].add(verse)
        verses_of[project] = by_chapter

    for project in projects:
        absences = KNOWN_ABSENCES.get(project, set())
        for book, chapter in sorted(chapters_of[project]):
            others = [
                other
                for other in projects
                if other != project and (book, chapter) in chapters_of[other]
            ]
            if not others:
                continue
            mine = verses_of[project][(book, chapter)]
            elsewhere = [verses_of[other][(book, chapter)] for other in others]

            # A verse only this project has is its own invention — in practice a verse
            # attributed to the wrong chapter — not something the others are missing.
            # Reporting it against them would blame two projects for one project's defect.
            extra = sorted(v for v in mine if not any(v in other for other in elsewhere))
            missing = sorted(
                v
                for v in set().union(*elsewhere) - mine
                if (book, chapter, v) not in absences
                and all(v in other for other in elsewhere)
            )

            unresolved = (project, book, chapter) in UNRESOLVED_CHAPTERS
            if extra:
                finding = ExtraVerseUrn(project, book, chapter, tuple(extra))
                (report.unresolved if unresolved else report.extra).append(finding)
            if missing:
                finding = MissingVerseUrn(
                    project, book, chapter, tuple(missing), tuple(others)
                )
                (report.unresolved if unresolved else report.missing).append(finding)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--project-directory", type=Path, default=PROJECT_DIRECTORY,
        help="Directory holding the projects.",
    )
    parser.add_argument(
        "--project", action="append", dest="projects",
        help="Project to check; repeatable. Defaults to the Tanakh projects.",
    )
    args = parser.parse_args(argv)

    report = validate_versification(
        args.projects or TANAKH_PROJECTS, project_directory=args.project_directory
    )

    for duplicate in report.duplicates:
        print(f"DUPLICATE  {duplicate}")
    for missing in report.missing:
        print(f"MISSING    {missing}")
    for extra in report.extra:
        print(f"EXTRA      {extra}")
    for unresolved in report.unresolved:
        print(f"unresolved {unresolved}")

    if report.ok:
        print(
            f"OK: verse URNs agree across projects "
            f"({len(report.unresolved)} known unresolved chapter(s))"
        )
        return 0
    print(
        f"FAILED: {len(report.duplicates)} duplicate, {len(report.missing)} missing and "
        f"{len(report.extra)} extra verse(s)"
    )
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
