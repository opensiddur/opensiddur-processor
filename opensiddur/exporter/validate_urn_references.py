"""Validation for the URN references a project carries.

Two checks, with different prerequisites. The reference check -- ``@target``/``@targetEnd``
-- is post-conversion: it is meant to run after an entire project/source has been converted
and the reference DB has been populated. The contributor check -- ``@ref`` -- needs neither,
since a contributor URN names a person rather than a stretch of text and so resolves against
the registry rather than against the corpus.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.urn_registry import (
    ROSTERED_CONTRIBUTOR_NAMESPACES,
    check_contributor_urn,
    load_registry,
    split_contributor_urn,
)
from opensiddur.exporter.refdb import INDEX_DB_FILE, ReferenceDatabase
from opensiddur.exporter.urn import ResolvedUrnRange, UrnResolver, coarsen
from opensiddur.exporter.xml_id_ref import parse_file_fragment_ref, resolve_file_fragment_ref


@dataclass(frozen=True)
class UnresolvableUrnReference:
    project: str
    file_name: str
    element_path: str
    attribute_name: str
    urn: str
    reason: Optional[str] = None


def _iter_project_xml_files(project_path: Path) -> Iterable[Path]:
    yield from sorted(project_path.glob("*.xml"))


def _resolvable(
    value: str,
    *,
    check_urns: bool,
    resolver: Optional[UrnResolver],
    project_directory: Path,
) -> bool:
    """A single, non-range target/targetEnd value: True if it resolves or is out of scope.

    Out of scope: ``http(s)://`` URLs, a same-file ``#id`` (e.g. ``j:endConditional/@target``,
    a standoff note's anchor), and any ``urn:`` value when ``check_urns`` is false.
    """
    if value.startswith("urn:x-opensiddur:"):
        if not check_urns:
            return True
        try:
            return bool(resolver.resolve_range(value))
        except ValueError:
            return False  # a malformed range does not resolve
    if value.startswith("http://") or value.startswith("https://"):
        return True
    file_ref = parse_file_fragment_ref(value)
    if file_ref is None:
        return True
    return resolve_file_fragment_ref(project_directory, file_ref)


def _optional_page_reference(element: etree._Element) -> bool:
    """A missing destination removes this navigation clause at export time."""
    tei = "{http://www.tei-c.org/ns/1.0}"
    return (element.tag == tei + "ref" and element.get("type") == "page"
            and "@" in element.get("target", "")
            and any(parent.tag == tei + "seg"
                    and parent.get("type") == "optional-page-reference"
                    for parent in element.iterancestors()))


def validate_project_urn_references(
    project: str,
    *,
    project_directory: Path = PROJECT_DIRECTORY,
    reference_db_path: Path = INDEX_DB_FILE,
    index_before_validate: bool = False,
    check_urns: bool = True,
) -> list[UnresolvableUrnReference]:
    """Validate that compilation-relevant references are resolvable.

    Checks ``@target`` and ``@targetEnd`` on every element that carries either — not just
    ``tei:ptr``/``tei:ref``/``j:transclude``, so a pointer on some other element is never missed
    — dispatching by value kind:

    - ``urn:x-opensiddur:...`` — resolved via refdb (``@corresp``-based range addressing).
      Skipped entirely when ``check_urns`` is false: unlike the file/fragment check below,
      this one is only meaningful once every project a URN might resolve into has been
      indexed into refdb, which is a separate, explicit step
      (``python -m opensiddur.exporter.refdb``) — not something one project's conversion can
      itself guarantee.
    - ``/{project}/{file}#{fragment}`` — resolved by looking up that ``xml:id`` directly in
      the named file (see ``opensiddur.exporter.xml_id_ref``). Self-contained: no refdb or
      cross-project state required, so this check always runs.
    - ``http://``/``https://`` and a same-file ``#id`` (e.g. ``j:endConditional/@target``, a
      standoff note's anchor) are out of scope.

    A missing edition-qualified destination on ``tei:ref[@type="page"]`` inside
    ``tei:seg[@type="optional-page-reference"]`` is allowed: the exporters suppress
    that optional navigation clause. Malformed ranges, required page references and
    transclusions still fail.

    When both ``@target`` and ``@targetEnd`` are URNs, they're treated as a range: ``@targetEnd``
    must resolve within the project ``@target`` did (this is how ``j:transclude`` uses the pair,
    but the check applies to any element using them the same way).
    """

    project_path = Path(project_directory) / project
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(f"Project directory does not exist: {project_path}")

    refdb = ReferenceDatabase(reference_db_path) if check_urns else None
    try:
        if check_urns and index_before_validate:
            refdb.index_project(project, project_directory=project_directory)

        resolver = UrnResolver(refdb) if check_urns else None

        failures: list[UnresolvableUrnReference] = []
        for xml_file in _iter_project_xml_files(project_path):
            tree = etree.parse(str(xml_file))
            root = tree.getroot()

            for el in root.xpath("//*[@target or @targetEnd]"):
                target = el.get("target")
                target_end = el.get("targetEnd")
                start_project: Optional[str] = None

                if target:
                    if check_urns and target.startswith("urn:x-opensiddur:"):
                        try:
                            start_candidates, reason = resolver.resolve_range(target), None
                        except ValueError as malformed:
                            # A malformed range, or one whose ends are in different files.
                            start_candidates, reason = [], str(malformed)
                        if not start_candidates and not (
                                reason is None and _optional_page_reference(el)):
                            failures.append(
                                UnresolvableUrnReference(
                                    project=project,
                                    file_name=xml_file.name,
                                    element_path=tree.getpath(el),
                                    attribute_name="target",
                                    urn=target,
                                    reason=reason,
                                )
                            )
                        elif start_candidates:
                            # Prefer resolving within the current project when possible, since
                            # that's the common compilation expectation.
                            start = (
                                UrnResolver.prioritize_range(start_candidates, [project])
                                or start_candidates[0]
                            )
                            start_project = start.project
                    elif not _resolvable(
                        target,
                        check_urns=check_urns,
                        resolver=resolver,
                        project_directory=project_directory,
                    ):
                        failures.append(
                            UnresolvableUrnReference(
                                project=project,
                                file_name=xml_file.name,
                                element_path=tree.getpath(el),
                                attribute_name="target",
                                urn=target,
                            )
                        )

                if target_end:
                    if start_project is not None and target_end.startswith("urn:x-opensiddur:"):
                        try:
                            end_candidates = resolver.resolve_range(target_end)
                        except ValueError:
                            end_candidates = []
                        prioritized_end = end_candidates and UrnResolver.prioritize_range(
                            end_candidates, [start_project]
                        )
                        # targetEnd names a single point, not a range: a ResolvedUrnRange here
                        # means the data violates the schema constraint that forbids a ranged
                        # targetEnd (it should have been split into two transclude elements).
                        if not prioritized_end or isinstance(prioritized_end, ResolvedUrnRange):
                            failures.append(
                                UnresolvableUrnReference(
                                    project=project,
                                    file_name=xml_file.name,
                                    element_path=tree.getpath(el),
                                    attribute_name="targetEnd",
                                    urn=target_end,
                                )
                            )
                    elif start_project is None and not _resolvable(
                        target_end,
                        check_urns=check_urns,
                        resolver=resolver,
                        project_directory=project_directory,
                    ):
                        failures.append(
                            UnresolvableUrnReference(
                                project=project,
                                file_name=xml_file.name,
                                element_path=tree.getpath(el),
                                attribute_name="targetEnd",
                                urn=target_end,
                            )
                        )
    finally:
        if refdb is not None:
            refdb.close()

    return failures


@dataclass(frozen=True)
class InvalidContributorReference:
    """A contributor credit that names nobody we can identify."""

    project: str
    file_name: str
    element_path: str
    ref: str
    reason: str


def validate_project_contributor_references(
    project: str,
    *,
    project_directory: Path = PROJECT_DIRECTORY,
    registry_directory: Optional[Path] = None,
) -> list[InvalidContributorReference]:
    """Validate the contributor URNs a project credits.

    Checks ``@ref`` on every element that carries one -- not just ``tei:respStmt/tei:name``,
    for the same reason the target check above is not limited to ``tei:ptr`` -- against the
    grammar in ``opensiddur.common.urn_registry`` and, for the namespaces we name ourselves,
    against the registry roster. A misspelt identifier is otherwise indistinguishable from a
    second person, and silently becomes one in the credits.

    Independent of refdb and of the resolver: a contributor URN names a person, not a stretch
    of text, so there is nothing to resolve and nothing to index first.
    """
    project_path = Path(project_directory) / project
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(f"Project directory does not exist: {project_path}")

    registry, _ = load_registry(registry_directory)

    failures: list[InvalidContributorReference] = []
    for xml_file in _iter_project_xml_files(project_path):
        tree = etree.parse(str(xml_file))
        for el in tree.getroot().xpath("//*[@ref]"):
            ref = el.get("ref")
            if not ref.startswith("urn:x-opensiddur:"):
                continue

            reason = check_contributor_urn(ref)
            if reason is None and ref not in registry.records:
                namespace, _ = split_contributor_urn(ref)
                if namespace in ROSTERED_CONTRIBUTOR_NAMESPACES:
                    reason = (
                        f"{ref} is not registered in specs/urn_registry/; a {namespace} "
                        "identifier is one we chose, so an unregistered one is a typo"
                    )
            if reason is not None:
                failures.append(
                    InvalidContributorReference(
                        project=project,
                        file_name=xml_file.name,
                        element_path=tree.getpath(el),
                        ref=ref,
                        reason=reason,
                    )
                )

    return failures


@dataclass(frozen=True)
class CoarsenedUrnReference:
    """A reference that resolves only once a division is dropped from the end of it."""

    project: str
    file_name: str
    element_path: str
    attribute_name: str
    urn: str
    resolves_as: str


def find_coarsened_urn_references(
    project: str,
    *,
    project_directory: Path = PROJECT_DIRECTORY,
    reference_db_path: Path = INDEX_DB_FILE,
) -> list[CoarsenedUrnReference]:
    """References that no project carries as written, but whose containing division exists.

    A reference to a point inside a verse — a half-verse, a named part of one — resolves to
    the whole verse in any project that does not divide the text that finely, so the
    compiled text covers more than the reference asks for. That is deliberate: a translation
    has no accents and can place no half-verses, and dropping its column entirely would be
    worse. But it is exactly the silent over-reading that sub-verse URNs exist to end, so it
    is reported here, before a build, rather than only in the compiler's log during one.
    """
    project_path = Path(project_directory) / project
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(f"Project directory does not exist: {project_path}")

    refdb = ReferenceDatabase(reference_db_path)
    try:
        resolver = UrnResolver(refdb)
        coarsened: list[CoarsenedUrnReference] = []

        for xml_file in _iter_project_xml_files(project_path):
            tree = etree.parse(str(xml_file))
            root = tree.getroot()
            references = [
                (el, attribute)
                for el in root.xpath("//*[@target or @targetEnd]")
                for attribute in ("target", "targetEnd")
                if el.get(attribute)
            ]

            for el, attribute in references:
                urn = el.get(attribute)
                if not urn or not urn.startswith("urn:x-opensiddur:"):
                    continue
                try:
                    if resolver.resolve_range(urn):
                        continue
                except ValueError:
                    continue  # malformed, which the resolvability check already reports
                # The same fallback the compiler takes: an end that resolves is kept.
                def resolves(one: str) -> bool:
                    try:
                        return bool(resolver.resolve_range(one))
                    except ValueError:
                        return False

                coarser = coarsen(urn, resolves=resolves)
                if not coarser:
                    continue
                try:
                    if not resolver.resolve_range(coarser):
                        continue
                except ValueError:
                    continue
                coarsened.append(
                    CoarsenedUrnReference(
                        project=project,
                        file_name=xml_file.name,
                        element_path=tree.getpath(el),
                        attribute_name=attribute,
                        urn=urn,
                        resolves_as=coarser,
                    )
                )
    finally:
        refdb.close()

    return coarsened


def _format_failure(f: UnresolvableUrnReference) -> str:
    message = f"{f.project}/{f.file_name}: {f.element_path} @{f.attribute_name}={f.urn}"
    return f"{message} ({f.reason})" if f.reason else message


def _format_contributor(c: InvalidContributorReference) -> str:
    return f"{c.project}/{c.file_name}: {c.element_path} @ref: {c.reason}"


def _format_coarsened(c: CoarsenedUrnReference) -> str:
    return (
        f"{c.project}/{c.file_name}: {c.element_path} @{c.attribute_name}={c.urn} "
        f"resolves only as {c.resolves_as}, which covers more text"
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate that compilation-relevant URN references are resolvable using refdb (post-conversion)."
    )
    parser.add_argument(
        "projects", nargs="+", metavar="project",
        help="Project name under project/ (e.g., tanakh-wlc-he, tanakh-jps-1917-en); one or more",
    )
    parser.add_argument(
        "--project-directory",
        default=str(PROJECT_DIRECTORY),
        help="Base project directory (defaults to repo project/)",
    )
    parser.add_argument(
        "--reference-db",
        default=str(INDEX_DB_FILE),
        help="Path to reference.db (defaults to opensiddur database/reference.db)",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="(Optional) index the project into refdb before validating",
    )

    args = parser.parse_args(argv)
    project_directory = Path(args.project_directory)
    reference_db_path = Path(args.reference_db)

    status = 0
    for project in args.projects:
        failures = validate_project_urn_references(
            project,
            project_directory=project_directory,
            reference_db_path=reference_db_path,
            index_before_validate=args.index,
        )
        # Reported but not fatal: a reference that coarsens still compiles, and for a project
        # that cannot carry the finer division there is nothing to fix in the reference itself.
        for c in find_coarsened_urn_references(
            project,
            project_directory=project_directory,
            reference_db_path=reference_db_path,
        ):
            print(_format_coarsened(c))

        contributor_failures = validate_project_contributor_references(
            project,
            project_directory=project_directory,
        )

        if failures or contributor_failures:
            for f in failures:
                print(_format_failure(f))
            for c in contributor_failures:
                print(_format_contributor(c))
            status = 2
    return status


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

