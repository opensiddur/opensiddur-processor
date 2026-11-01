"""The registry of canonical URNs, and the checks that keep it honest.

`refdb` answers "where does this URN resolve?" by indexing what projects actually
contain. It is derived and disposable: delete it and a resync rebuilds it. This module
answers a different question — "what is the right name for this text, and what else has
been called the same thing?" — which cannot be derived from the corpus, because it is
precisely the judgement that keeps two projects from inventing two names for one prayer.

So the registry holds the three things refdb structurally cannot: a URN decomposed into
its parts, a human-readable label, and the canonical/alias edge. It is hand-maintained,
reviewed, and committed; refdb stays the single source of truth for where text lives.

See ``specs/SIDDUR_URN_SCHEME.md`` for the naming rules this enforces.

Run as::

    uv run python -m opensiddur.common.urn_registry --check
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from opensiddur.common.constants import REPO_ROOT

logger = logging.getLogger(__name__)

REGISTRY_DIRECTORY = REPO_ROOT / "specs" / "urn_registry"

SCHEME = "urn:x-opensiddur:"

# Namespaces whose names this registry governs. `bible:` is excluded because its names
# are fixed by the canon rather than chosen, and `haggadah:` because it names what is
# particular to the seder -- it appears here only in context records.
GOVERNED_NAMESPACES = frozenset({"prayer", "poem", "siddur", "mishnah", "talmud",
                                 "front"})

# `instruction` is a URN *type*, not a namespace, and the registry governs it too.
GOVERNED_TYPES = frozenset({"instruction"})

# A path component: lowercase, no `-` (which marks a range), no URN delimiters.
COMPONENT_RE = re.compile(r"^[a-z0-9_]+$")

# A contributor URN names a person rather than a text, so it is shaped differently from
# everything else here: `urn:x-opensiddur:contributor:<namespace>/<identifier>`, with the
# identifier chosen by whoever runs the namespace rather than by us. See "Contributors and
# contributor URNs" in `schema/JLPTEI-3.md`.
CONTRIBUTOR_TYPE = "contributor"

# Keep in sync with the `contributor-ref-constraints` Schematron rule in
# `schema/jlptei.odd.xml`, which enforces the same grammar at validation time.
CONTRIBUTOR_NAMESPACES = frozenset({"en.wikisource.org", "he.wikisource.org", "opensiddur.org"})

# Namespaces whose identifiers we choose ourselves, so an unregistered one is a typo rather
# than a contributor an importer has only just met. A wikisource username arrives from the
# wiki's revision history, and requiring a registry line for each would mean editing the
# registry on every import.
ROSTERED_CONTRIBUTOR_NAMESPACES = frozenset({"opensiddur.org"})

# Our own identifiers are lowercase kebab-case.
OPENSIDDUR_IDENTIFIER_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# A wikisource username is whatever the wiki allows, percent-encoded on the way in: mixed
# case, dots and bare IP addresses all occur. Only the URN delimiters are forbidden.
WIKI_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._~%!$&'()*+,;=@-]+$")

STATUS_CANONICAL = "canonical"
STATUS_ALIAS = "alias"
STATUS_CONTEXT = "context"
VALID_STATUSES = frozenset({STATUS_CANONICAL, STATUS_ALIAS, STATUS_CONTEXT})

ERROR, WARNING, INFO = "error", "warning", "info"


class RegistryError(RuntimeError):
    """The registry could not be read at all."""


@dataclass(frozen=True)
class Urn:
    """A parsed ``urn:x-opensiddur:`` name."""

    type: str
    namespace: str
    path: tuple[str, ...]
    project: str | None = None
    fragment: str | None = None

    def __str__(self) -> str:
        base = f"{SCHEME}{self.type}:{self.namespace}"
        if self.path:
            base += ":" + "/".join(self.path)
        if self.project:
            base += f"@{self.project}"
        if self.fragment:
            base += f"#{self.fragment}"
        return base

    @property
    def governed(self) -> bool:
        """Whether this registry is responsible for the name."""
        return self.namespace in GOVERNED_NAMESPACES or self.type in GOVERNED_TYPES

    @property
    def parent(self) -> "Urn | None":
        """The URN one component shallower, or None at the root of a namespace."""
        if len(self.path) <= 1:
            return None
        return Urn(self.type, self.namespace, self.path[:-1])

    def without_numeric_tail(self) -> "Urn":
        """Drop trailing numeric components.

        This is a fallback for edition-specific subdivisions. Check the exact URN
        first: canonical texts such as Mishnah chapter/mishnah references can also
        end in numbers. See "Sub-division numbering".
        """
        path = list(self.path)
        while len(path) > 1 and path[-1].isdigit():
            path.pop()
        return Urn(self.type, self.namespace, tuple(path), self.project, self.fragment)


def parse_urn(text: str) -> Urn:
    """Parse a URN, raising ``ValueError`` with a usable message if it will not."""
    if not text.startswith(SCHEME):
        raise ValueError(f"not an opensiddur URN: {text!r}")

    rest = text[len(SCHEME) :]
    rest, _, fragment = rest.partition("#")
    # The project is everything after the *last* `@`, as `opensiddur.exporter.urn.split_project`
    # reads it.
    rest, _, project = rest.rpartition("@") if "@" in rest else (rest, "", "")

    parts = rest.split(":")
    if len(parts) < 2:
        raise ValueError(f"URN has no namespace: {text!r}")
    urn_type, namespace = parts[0], parts[1]
    path = tuple(p for p in ":".join(parts[2:]).split("/") if p) if len(parts) > 2 else ()

    if not urn_type:
        raise ValueError(f"URN has an empty type: {text!r}")
    if not namespace:
        raise ValueError(f"URN has an empty namespace: {text!r}")

    return Urn(urn_type, namespace, path, project or None, fragment or None)


def split_contributor_urn(text: str) -> tuple[str, str]:
    """The ``(namespace, identifier)`` of a contributor URN.

    A contributor URN has one component fewer than a text URN -- ``contributor:<namespace>``
    rather than ``text:<namespace>:<path>`` -- so ``parse_urn`` reads ``namespace/identifier``
    as a single namespace and leaves the path empty. Splitting it is this function's job.

    Raises ``ValueError`` if the URN does not parse at all.
    """
    urn = parse_urn(text)
    namespace, separator, identifier = urn.namespace.partition("/")
    if not separator:
        identifier = ""
    if urn.path:
        identifier = "/".join((identifier,) + urn.path)
    return namespace, identifier


def check_contributor_urn(text: str) -> str | None:
    """Why ``text`` is not a well-formed contributor URN, or None if it is.

    Grammar only: whether the identifier names anyone we know is a question for the
    registry, and is asked separately, because only some namespaces are rostered.
    """
    # `urn:x-opensiddur:opensiddur.org/someone` -- the type segment was left out, so the
    # namespace slid into its place. Caught before parsing, both because that shape leaves
    # `parse_urn` no namespace to find and because it deserves its own message: it is what
    # the older importers emitted, and it is invisible in a rendered credits list.
    rest = text[len(SCHEME):] if text.startswith(SCHEME) else ""
    if rest.split("/", 1)[0].split(":", 1)[0] in CONTRIBUTOR_NAMESPACES:
        return (f"{text}: missing the {CONTRIBUTOR_TYPE!r} type segment; should be "
                f"{SCHEME}{CONTRIBUTOR_TYPE}:{rest}")

    try:
        urn = parse_urn(text)
        namespace, identifier = split_contributor_urn(text)
    except ValueError as exc:
        return str(exc)

    if urn.type != CONTRIBUTOR_TYPE:
        return f"{text}: not a contributor URN (type is {urn.type!r})"

    if namespace not in CONTRIBUTOR_NAMESPACES:
        return (f"{text}: unknown contributor namespace {namespace!r}; expected one of "
                f"{', '.join(sorted(CONTRIBUTOR_NAMESPACES))}")

    if urn.project or urn.fragment:
        return f"{text}: a contributor URN carries no @project or #fragment"

    if not identifier or "/" in identifier:
        return (f"{text}: expected exactly one identifier after {namespace}/, "
                f"found {identifier!r}")

    pattern = (OPENSIDDUR_IDENTIFIER_RE if namespace == "opensiddur.org"
               else WIKI_IDENTIFIER_RE)
    if not pattern.match(identifier):
        return f"{text}: identifier {identifier!r} is not valid for {namespace}"

    return None


@dataclass
class Record:
    """One line of the registry."""

    urn: str
    status: str
    canonical: str | None = None
    parent: str | None = None
    kind: str | None = None
    label_he: str | None = None
    label_en: str | None = None
    references: list[str] = field(default_factory=list)
    note: str | None = None
    context_urn: str | None = None
    source_file: str = ""
    line: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def where(self) -> str:
        return f"{self.source_file}:{self.line}"


@dataclass
class Problem:
    """Something wrong, or worth knowing, about the registry."""

    severity: str
    message: str
    where: str = ""

    def __str__(self) -> str:
        prefix = f"{self.where}: " if self.where else ""
        return f"{self.severity.upper()}: {prefix}{self.message}"


KNOWN_FIELDS = {
    "urn", "status", "canonical", "parent", "kind", "label_he", "label_en",
    "references", "note", "context_urn",
}


@dataclass
class Registry:
    """Every record, indexed by URN."""

    records: dict[str, Record] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.records)

    def of_status(self, status: str) -> list[Record]:
        return [r for r in self.records.values() if r.status == status]

    def resolve(self, urn: str) -> str:
        """The canonical URN for ``urn``, following one alias hop.

        A URN the registry does not know is returned unchanged: not every namespace is
        governed, and an unregistered governed URN is reported by :func:`validate`
        rather than silently rewritten here.
        """
        record = self.records.get(urn)
        if record is not None and record.status == STATUS_ALIAS and record.canonical:
            return record.canonical
        return urn


def _iter_records(path: Path) -> Iterator[Record]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except ValueError as exc:
            raise RegistryError(f"{path.name}:{number}: not valid JSON: {exc}") from exc
        if "urn" not in payload:
            raise RegistryError(f"{path.name}:{number}: record has no 'urn'")
        references = payload.get("references") or []
        if isinstance(references, str):
            references = [references]
        yield Record(
            urn=payload["urn"],
            status=payload.get("status", STATUS_CANONICAL),
            canonical=payload.get("canonical"),
            parent=payload.get("parent"),
            kind=payload.get("kind"),
            label_he=payload.get("label_he"),
            label_en=payload.get("label_en"),
            references=list(references),
            note=payload.get("note"),
            context_urn=payload.get("context_urn"),
            source_file=path.name,
            line=number,
            extra={k: v for k, v in payload.items() if k not in KNOWN_FIELDS},
        )


def load_registry(directory: Path | None = None) -> tuple[Registry, list[Problem]]:
    """Read every ``*.jsonl`` in the registry directory."""
    directory = directory or REGISTRY_DIRECTORY
    if not directory.is_dir():
        raise RegistryError(f"No registry directory at {directory}")

    registry, problems = Registry(), []
    for path in sorted(directory.glob("*.jsonl")):
        for record in _iter_records(path):
            existing = registry.records.get(record.urn)
            if existing is not None:
                problems.append(Problem(
                    ERROR,
                    f"{record.urn} is registered twice (also at {existing.where})",
                    record.where,
                ))
                continue
            registry.records[record.urn] = record
    return registry, problems


def _check_grammar(record: Record, registry: Registry) -> Iterator[Problem]:
    try:
        urn = parse_urn(record.urn)
    except ValueError as exc:
        yield Problem(ERROR, str(exc), record.where)
        return

    # The registry names texts, not their realisations in a project.
    if urn.project:
        yield Problem(ERROR, f"{record.urn} carries @{urn.project}; registry URNs name "
                             "texts, not realisations", record.where)
    if urn.fragment:
        yield Problem(ERROR, f"{record.urn} carries a #fragment", record.where)

    if urn.type == CONTRIBUTOR_TYPE:
        # A contributor identifier is not ours to lowercase: it is a wiki username, or a
        # kebab-case name we chose, so it has a grammar of its own.
        if (reason := check_contributor_urn(record.urn)) is not None:
            yield Problem(ERROR, reason, record.where)
    else:
        for component in urn.path:
            if not COMPONENT_RE.match(component):
                yield Problem(
                    ERROR,
                    f"{record.urn}: component {component!r} must be lowercase letters, "
                    "digits and underscore -- '-' marks a range",
                    record.where,
                )

    if record.status not in VALID_STATUSES:
        yield Problem(ERROR, f"{record.urn}: unknown status {record.status!r}",
                      record.where)

    if record.extra:
        yield Problem(INFO, f"{record.urn}: unrecognised field(s) "
                            f"{', '.join(sorted(record.extra))}", record.where)


def _check_edges(registry: Registry) -> Iterator[Problem]:
    canonical = {r.urn for r in registry.of_status(STATUS_CANONICAL)}

    for record in registry.records.values():
        if record.status == STATUS_ALIAS:
            if not record.canonical:
                yield Problem(ERROR, f"{record.urn} is an alias with no canonical",
                              record.where)
            elif record.canonical == record.urn:
                yield Problem(ERROR, f"{record.urn} is an alias of itself", record.where)
            elif record.urn in canonical:
                yield Problem(ERROR, f"{record.urn} is both canonical and an alias",
                              record.where)
            elif (target := registry.records.get(record.canonical)) is not None:
                if target.status == STATUS_ALIAS:
                    yield Problem(
                        ERROR,
                        f"{record.urn} aliases {record.canonical}, which is itself an "
                        "alias; point it at the canonical URN directly",
                        record.where,
                    )

        if record.status == STATUS_CONTEXT and not record.references and not record.note:
            yield Problem(
                WARNING,
                f"{record.urn} is a context URN referencing nothing and saying why not; "
                "a context that shares no text should explain that in its note",
                record.where,
            )

        if record.parent and record.parent not in registry.records:
            yield Problem(WARNING, f"{record.urn}: parent {record.parent} is not "
                                   "registered", record.where)

    # Cycles, over the parent edge.
    for record in registry.records.values():
        seen, cursor = {record.urn}, record.parent
        while cursor:
            if cursor in seen:
                yield Problem(ERROR, f"{record.urn}: parent chain is a cycle",
                              record.where)
                break
            seen.add(cursor)
            following = registry.records.get(cursor)
            cursor = following.parent if following else None


def _urns_in_projects(database) -> dict[str, set[str]]:
    """Every URN each project emits, with `@project` stripped and ranges expanded."""
    from opensiddur.exporter.urn import split_range

    found: dict[str, set[str]] = {}
    for project in database.list_projects():
        names: set[str] = set()
        for mapping in database.get_urns_by_project(project):
            urn = mapping.urn.rsplit("@", 1)[0]
            try:
                start, end = split_range(urn)
            except Exception:  # a malformed range is refdb's problem to report
                names.add(urn)
                continue
            names.update({start, end} if end else {start})
        found[project] = names
    return found


def check_against_refdb(registry: Registry, database=None) -> Iterator[Problem]:
    """Cross-check what projects actually emit against what is registered.

    Only checks that names **used** are registered. A registered name no project has
    realised yet is not a problem -- see "Partial witnesses are normal": the registry
    describes the vocabulary, not any book's coverage of it.
    """
    if database is None:
        from opensiddur.exporter.refdb import ReferenceDatabase

        database = ReferenceDatabase()

    aliases = {r.urn for r in registry.of_status(STATUS_ALIAS)}

    emitted = _urns_in_projects(database)
    if not emitted:
        # Nothing to compare is not agreement: a database built by other code is emptied on
        # open, and a check against it would pass without having looked at anything.
        yield Problem(
            ERROR,
            "the reference database holds no projects, so nothing was cross-checked; "
            "sync it first (python -m opensiddur.exporter.refdb) or pass --no-refdb",
        )
        return

    for project, urns in sorted(emitted.items()):
        unregistered, pending = set(), set()
        for text in sorted(urns):
            try:
                urn = parse_urn(text)
            except ValueError:
                continue
            if text in aliases:
                pending.add(text)
                continue
            if not urn.governed:
                continue
            if text in registry.records:
                continue
            if str(urn.without_numeric_tail()) not in registry.records:
                unregistered.add(text)

        for text in sorted(unregistered):
            yield Problem(ERROR, f"{project} emits {text}, which is not registered")
        if pending:
            yield Problem(
                INFO,
                f"{project} still emits {len(pending)} URN(s) recorded as aliases; "
                "pending migration",
            )


def check_contributors(registry: Registry, *, project_directory=None) -> Iterator[Problem]:
    """Cross-check the contributor URNs the corpus credits against the registry.

    `check_against_refdb` cannot do this: refdb indexes the `@corresp` URNs that say where
    text lives, and a contributor URN names a person, so it never appears there. The corpus
    has to be read directly.

    Grammar is checked everywhere. Registration is required only for the namespaces we name
    ourselves -- see :data:`ROSTERED_CONTRIBUTOR_NAMESPACES`. Elsewhere an unregistered
    contributor is reported at INFO, as a line worth adding rather than a mistake.
    """
    from lxml import etree

    from opensiddur.common.constants import PROJECT_DIRECTORY

    directory = Path(project_directory or PROJECT_DIRECTORY)
    if not directory.is_dir():
        raise RegistryError(f"No project directory at {directory}")

    # URN -> where it was first credited, so a message can point somewhere.
    seen: dict[str, str] = {}
    for xml_file in sorted(directory.glob("*/*.xml")):
        try:
            root = etree.parse(str(xml_file)).getroot()
        except etree.XMLSyntaxError:
            continue  # unparseable XML is the schema validator's to report
        for element in root.xpath("//*[@ref]"):
            value = element.get("ref")
            if value.startswith(SCHEME):
                seen.setdefault(value, f"{xml_file.parent.name}/{xml_file.name}")

    for text, where in sorted(seen.items()):
        if (reason := check_contributor_urn(text)) is not None:
            yield Problem(ERROR, reason, where)
            continue
        if text in registry.records:
            continue
        namespace, _ = split_contributor_urn(text)
        if namespace in ROSTERED_CONTRIBUTOR_NAMESPACES:
            yield Problem(
                ERROR,
                f"{text} is credited but not registered; a {namespace} identifier is one we "
                "chose, so an unregistered one is a typo rather than someone new",
                where,
            )
        else:
            yield Problem(
                INFO,
                f"{text} is credited but not registered; add a line to give it a label",
                where,
            )


def validate(
    registry: Registry,
    database=None,
    *,
    use_refdb: bool = True,
    use_projects: bool = True,
    project_directory=None,
) -> list[Problem]:
    """Every problem with the registry, worst first."""
    problems: list[Problem] = []
    for record in registry.records.values():
        problems.extend(_check_grammar(record, registry))
    problems.extend(_check_edges(registry))
    if use_refdb:
        try:
            problems.extend(check_against_refdb(registry, database))
        except Exception as exc:  # a missing or stale database must not mask real errors
            problems.append(Problem(WARNING, f"could not cross-check against refdb: {exc}"))
    if use_projects:
        try:
            problems.extend(check_contributors(registry, project_directory=project_directory))
        except Exception as exc:  # nor must a missing corpus
            problems.append(Problem(WARNING, f"could not check contributors: {exc}"))

    order = {ERROR: 0, WARNING: 1, INFO: 2}
    return sorted(problems, key=lambda p: (order[p.severity], p.where, p.message))


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the canonical URN registry: grammar, parentage, alias resolution, "
            "and agreement with what projects actually emit."
        )
    )
    parser.add_argument(
        "--registry", type=Path, default=None,
        help=f"Registry directory (default: {REGISTRY_DIRECTORY}).",
    )
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if anything is wrong. For CI.")
    parser.add_argument("--no-refdb", action="store_true",
                        help="Skip the cross-check against the reference database.")
    parser.add_argument("--no-projects", action="store_true",
                        help="Skip the contributor cross-check against the projects.")
    parser.add_argument(
        "--project-directory", type=Path, default=None,
        help="Base project directory (defaults to the repo's project/).",
    )
    parser.add_argument(
        "--reference-db", type=Path, default=None,
        help="Path to reference.db (defaults to the repo's database/reference.db).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_arg_parser().parse_args(argv)

    try:
        registry, problems = load_registry(args.registry)
    except RegistryError as exc:
        logger.error("%s", exc)
        return 1

    database = None
    if not args.no_refdb and args.reference_db is not None:
        from opensiddur.exporter.refdb import ReferenceDatabase

        database = ReferenceDatabase(args.reference_db)

    try:
        problems += validate(
            registry,
            database,
            use_refdb=not args.no_refdb,
            use_projects=not args.no_projects,
            project_directory=args.project_directory,
        )
    finally:
        if database is not None:
            database.close()
    for problem in problems:
        logger.info("%s", problem)

    counts = {severity: sum(1 for p in problems if p.severity == severity)
              for severity in (ERROR, WARNING, INFO)}
    logger.info(
        "%d record(s): %d canonical, %d alias, %d context. "
        "%d error(s), %d warning(s), %d note(s).",
        len(registry), len(registry.of_status(STATUS_CANONICAL)),
        len(registry.of_status(STATUS_ALIAS)), len(registry.of_status(STATUS_CONTEXT)),
        counts[ERROR], counts[WARNING], counts[INFO],
    )
    return 1 if (args.check and counts[ERROR]) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
