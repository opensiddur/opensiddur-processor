"""Check project, settings, file and URN names against ``specs/NAMING_SCHEME.md``.

Four things are checked:

- a project's directory name is an identifier, ``<title>-<author>-<date>-<lang>``, whose last
  field is the language of its ``index.xml``;
- a settings file lives under the directory of the project it builds,
  ``settings/<book.project>/<variant>.yaml``, since that is what names the book;
- a project file's stem, and every path component of a URN a project or the registry carries,
  is lowercase ASCII words joined by ``_``;
- none of their words is a known misspelling, listed in ``specs/naming/spellings.yaml``.

Whether a word follows the transliteration table cannot be decided without its Hebrew, so the
last check finds only the misspellings already recorded. A project identifier is not spelled
by the table: its title may be the source's own romanization of its name, and its author is a
person's name.

Run as::

    uv run python -m opensiddur.common.validate_names --check
"""

from __future__ import annotations

import argparse
import collections
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import yaml
from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY, REPO_ROOT, SETTINGS_DIRECTORY
from opensiddur.common.urn_registry import (
    COMPONENT_RE, ERROR, REGISTRY_DIRECTORY, SCHEME, STATUS_ALIAS, WARNING, Problem,
    RegistryError, load_registry,
)

logger = logging.getLogger(__name__)

SPELLINGS_FILE = REPO_ROOT / "specs" / "naming" / "spellings.yaml"

#: Fields joined by `-`, the words of a field by `_`; at least two fields.
PROJECT_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*(?:-[a-z0-9]+(?:_[a-z0-9]+)*)+$")

FILE_STEM_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

# The URNs whose path components are names: a text, an instruction or a notes set. Read up to
# the end of the attribute value or to whitespace, so that a malformed component --
# `(mincha,_traditional)` -- is read whole and reported rather than cut short.
_URN_IN_TEXT = re.compile(re.escape(SCHEME) + r"(?P<type>text|instruction|notes):[^\s\"'<>]+")

# Punctuation that ends a sentence rather than a URN, when a URN is cited in prose.
_TRAILING_PUNCTUATION = ".,;:"

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


@dataclass(frozen=True)
class Spellings:
    """Common spellings that win over the table, and known misspellings of other words."""

    exceptions: frozenset[str]
    variants: dict[str, str]


def load_spellings(path: Path = SPELLINGS_FILE) -> Spellings:
    """Read the spellings list, raising ``ValueError`` if it contradicts itself."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    exceptions = frozenset(data.get("exceptions") or ())
    variants = dict(data.get("variants") or {})
    for variant, standard in variants.items():
        if variant in exceptions:
            raise ValueError(f"{path}: {variant!r} is both a common spelling and a variant")
        if standard in variants:
            raise ValueError(f"{path}: {variant!r} maps to {standard!r}, which is itself a "
                             "variant; map it to the standard spelling directly")
        if variant == standard:
            raise ValueError(f"{path}: {variant!r} is listed as a variant of itself")
    return Spellings(exceptions, variants)


def respell(name: str, spellings: Spellings | None = None) -> str:
    """``name`` with each of its words that is a known misspelling spelled the standard way,
    for an importer naming something from a source's own words."""
    variants = (spellings or load_spellings()).variants
    return re.sub(r"[a-z0-9]+", lambda m: variants.get(m.group(0), m.group(0)), name)


#: A text, instruction or notes URN's path: what respell_urns respells. The project and fragment
#: are not.
_URN_PATH = re.compile(re.escape(SCHEME) + r"((?:text:[a-z_]+:|instruction:|notes:))([^\s\"'<>@#]+)")


def respell_urns(text: str, spellings: Spellings | None = None) -> str:
    """``text`` with the path of every text, instruction or notes URN in it respelled."""
    spellings = spellings or load_spellings()
    return _URN_PATH.sub(lambda m: SCHEME + m.group(1) + respell(m.group(2), spellings), text)


def words(name: str) -> Iterator[str]:
    """The words of a project identifier, file stem or URN path, leaving out numbers."""
    for word in re.split(r"[-_/]", name):
        if word and not word.isdigit():
            yield word


def project_id_problem(name: str, language: str | None) -> str | None:
    """Why ``name`` is not a project identifier for a project in ``language``, or None."""
    if not PROJECT_ID_RE.match(name):
        return ("not a project identifier: lowercase <title>-<author>-<date>-<lang>, fields "
                "joined by '-' and words by '_'")
    if language is None:
        return "has no language to end with: its index.xml has no xml:lang"
    suffix = language.lower()
    if not (name.endswith("-" + suffix) and len(name) > len(suffix) + 1):
        return f"does not end with its language, -{suffix} (the xml:lang of index.xml)"
    return None


def project_language(project_path: Path) -> str | None:
    """The ``xml:lang`` of a project's ``index.xml``, or None if it has none to read."""
    try:
        root = etree.parse(str(project_path / "index.xml")).getroot()
    except (OSError, etree.XMLSyntaxError):
        return None
    return root.get(_XML_LANG) or None


def _strip_prose_punctuation(urn: str) -> str:
    """``urn`` without the punctuation of the prose it is cited in: a full stop or comma after
    it, or the closing parenthesis of a parenthesis it ends."""
    while True:
        stripped = urn.rstrip(_TRAILING_PUNCTUATION)
        if stripped.endswith(")") and stripped.count(")") > stripped.count("("):
            stripped = stripped[:-1]
        if stripped == urn:
            return urn
        urn = stripped


def urn_paths(text: str) -> Iterator[str]:
    """The path of each text, instruction and notes URN in ``text``.

    The path leaves out the type, a text URN's namespace, the project and the fragment. A
    range contributes both of its ends.
    """
    from opensiddur.exporter.urn import split_project, split_range

    for match in _URN_IN_TEXT.finditer(text):
        urn = match.group(0)
        if text[match.end():match.end() + 1].isspace() or match.end() == len(text):
            urn = _strip_prose_punctuation(urn)
        urn, _ = split_project(urn.split("#", 1)[0])
        try:
            ends = split_range(urn)
        except ValueError:  # a malformed range is validate_urn_references's to report
            ends = None
        start, end = ends or (urn, None)
        # text:<namespace>:<path>, but instruction:<path>
        skip = 2 if match.group("type") == "text" else 1
        for one in (start, end) if end else (start,):
            parts = one[len(SCHEME):].split(":", skip)
            if len(parts) == skip + 1:
                yield parts[skip]


class _Findings:
    """Misspellings and malformed names found in one place, gathered to report once each."""

    def __init__(self, spellings: Spellings):
        self.spellings = spellings
        self.variants: dict[str, list[str]] = collections.defaultdict(list)
        self.malformed: dict[str, list[str]] = collections.defaultdict(list)

    def stem(self, stem: str, where: str) -> None:
        if not FILE_STEM_RE.match(stem):
            self.malformed[stem].append(where)
        self.spelling(stem, where)

    def urn_path(self, path: str, where: str) -> None:
        for component in path.split("/"):
            if component and not COMPONENT_RE.match(component):
                self.malformed[component].append(where)
        self.spelling(path, where)

    def spelling(self, name: str, where: str) -> None:
        for word in words(name):
            if word in self.spellings.variants:
                self.variants[word].append(where)

    def problems(self, where: str, what: str) -> Iterator[Problem]:
        for component, places in sorted(self.malformed.items()):
            yield Problem(ERROR, f"{what} {component!r} is not lowercase ASCII words joined by "
                                 f"'_' ({_places(places)})", where)
        for word, places in sorted(self.variants.items()):
            yield Problem(ERROR, f"{word!r} should be spelled "
                                 f"{self.spellings.variants[word]!r} ({_places(places)})", where)


def _places(places: list[str]) -> str:
    distinct = sorted(set(places))
    shown = ", ".join(distinct[:3])
    more = f" and {len(distinct) - 3} more" if len(distinct) > 3 else ""
    return f"{len(places)} use(s): {shown}{more}"


def check_project(project_path: Path, spellings: Spellings, *,
                  names_only: bool = False) -> Iterator[Problem]:
    """Every naming problem in one project directory; with ``names_only``, only its name's."""
    project = project_path.name
    if (reason := project_id_problem(project, project_language(project_path))) is not None:
        yield Problem(ERROR, f"project {project!r} {reason}", project)
    if names_only:
        return

    stems = _Findings(spellings)
    urns = _Findings(spellings)
    for xml_file in sorted(project_path.glob("*.xml")):
        stems.stem(xml_file.stem, xml_file.name)
        for path in urn_paths(xml_file.read_text(encoding="utf-8")):
            urns.urn_path(path, xml_file.name)
    yield from stems.problems(project, "file name")
    yield from urns.problems(project, "URN component")


def check_projects(project_directory: Path, spellings: Spellings,
                   projects: Iterable[str] | None = None, *,
                   names_only: bool = False) -> Iterator[Problem]:
    directory = Path(project_directory)
    names = list(projects) if projects else sorted(
        p.name for p in directory.iterdir() if p.is_dir())
    for name in names:
        project_path = directory / name
        if not project_path.is_dir():
            yield Problem(ERROR, "no such project directory", name)
            continue
        yield from check_project(project_path, spellings, names_only=names_only)


def check_settings(settings_directory: Path) -> Iterator[Problem]:
    """Every settings file lives under the directory of the project it builds."""
    directory = Path(settings_directory)
    # One level only: a file anywhere else is misplaced, which books --check reports.
    for path in sorted(directory.glob("*/*.yaml")):
        where = str(path.relative_to(directory))
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            yield Problem(ERROR, f"not readable YAML: {exc}", where)
            continue
        book = data.get("book") if isinstance(data, dict) else None
        project = book.get("project") if isinstance(book, dict) else None
        if not project:
            continue  # a settings file with no book is books --check's to report
        if path.parent.name != project:
            yield Problem(ERROR, f"builds {project!r}, so it belongs in {project}/{path.name}",
                          where)


def check_registry(registry_directory: Path | None, spellings: Spellings) -> Iterator[Problem]:
    """Every URN the registry records, alias or not, is spelled by the table.

    An alias is a name being retired, so its misspellings are expected; it is the canonical
    and context records that must be right.
    """
    registry, _ = load_registry(registry_directory)
    findings = _Findings(spellings)
    for record in registry.records.values():
        if record.status == STATUS_ALIAS:
            continue
        for path in urn_paths(record.urn):
            findings.urn_path(path, record.where)
    yield from findings.problems("registry", "URN component")


def validate(
    project_directory: Path = PROJECT_DIRECTORY,
    settings_directory: Path | None = SETTINGS_DIRECTORY,
    registry_directory: Path | None = REGISTRY_DIRECTORY,
    *,
    projects: Iterable[str] | None = None,
    spellings: Spellings | None = None,
    names_only: bool = False,
) -> list[Problem]:
    """Every naming problem found, by place. ``None`` for a directory skips its check.

    ``names_only`` checks the projects' names and the settings' places, and not the files,
    the URNs or the registry.
    """
    spellings = spellings or load_spellings()
    problems = list(check_projects(project_directory, spellings, projects, names_only=names_only))
    if settings_directory is not None:
        if Path(settings_directory).is_dir():
            problems.extend(check_settings(settings_directory))
        else:
            problems.append(Problem(WARNING, f"no settings directory at {settings_directory}"))
    if registry_directory is not None and not names_only:
        try:
            problems.extend(check_registry(registry_directory, spellings))
        except RegistryError as exc:
            problems.append(Problem(ERROR, str(exc), "registry"))
    return sorted(problems, key=lambda p: (p.where, p.severity, p.message))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("projects", nargs="*", help="Check only these projects. Default: all.")
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY,
                        help="Base directory containing project subdirectories.")
    parser.add_argument("--settings-directory", type=Path, default=SETTINGS_DIRECTORY,
                        help="Directory of book settings files (<project>/<variant>.yaml).")
    parser.add_argument("--registry", type=Path, default=REGISTRY_DIRECTORY,
                        help="URN registry directory.")
    parser.add_argument("--spellings", type=Path, default=SPELLINGS_FILE,
                        help="Common spellings and known variants.")
    parser.add_argument("--no-settings", action="store_true", help="Skip the settings check.")
    parser.add_argument("--no-registry", action="store_true", help="Skip the registry check.")
    parser.add_argument("--names-only", action="store_true",
                        help="Check only project names and where settings files are, not file "
                             "names, URNs or the registry.")
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if anything is wrong. For CI.")
    args = parser.parse_args(argv)

    try:
        spellings = load_spellings(args.spellings)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        logger.error("%s", exc)
        return 1
    problems = validate(
        args.project_directory,
        None if args.no_settings else args.settings_directory,
        None if args.no_registry else args.registry,
        projects=args.projects,
        spellings=spellings,
        names_only=args.names_only,
    )
    for problem in problems:
        logger.info("%s", problem)
    errors = sum(1 for p in problems if p.severity == ERROR)
    logger.info("%d naming error(s); see specs/NAMING_SCHEME.md", errors)
    return 1 if (args.check and errors) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
