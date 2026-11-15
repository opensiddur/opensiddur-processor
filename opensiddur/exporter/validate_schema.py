"""Schema-validate the XML of one or more projects, as a CI gate.

``opensiddur.importer.util.validation`` validates a single file and its ``main`` returns a
bool without ever exiting non-zero -- fine for a one-off check, unusable as a required
status check. This module runs RelaxNG + Schematron (well-formedness comes with the
RelaxNG pass) over every ``*.xml`` in a set of projects, prints a per-file report, and
exits non-zero if anything failed.

It is deliberately a sibling of :mod:`opensiddur.exporter.validate_urn_references` and
:mod:`opensiddur.exporter.validate_versification`: same ``--project-directory`` default,
same "raise SystemExit(code)" shape. Exit ``1`` on any invalid or malformed file, ``0``
otherwise (``validate_urn_references`` uses ``2``, ``validate_versification`` uses ``1``).

Typical CI use, validating every file in the projects a PR touched::

    python -m opensiddur.exporter.validate_schema \\
        --project-directory "$GITHUB_WORKSPACE/projects/project" \\
        --repo-root "$GITHUB_WORKSPACE" --github-annotations \\
        --cache "$RUNNER_TEMP/schema-validation.json" \\
        --project chumash-opensiddur-he --project tanakh-wlc-he

With no ``--project`` and no ``--files-from`` every project under ``--project-directory``
is validated.

``--cache PATH`` skips files that already passed: it names a JSON file of the content hashes of
files that validated cleanly, stamped with a :func:`schema_fingerprint`. A file whose hash is
recorded there is reported valid without running the validators; a stamp that does not match the
current schema and validator code discards every recorded hash. Only passing files are recorded,
so a failing file is revalidated -- and its errors reported -- on every run. Validity here is a
property of one file's content alone (the Schematron reads no other document), so this cache
cannot mask a cross-file problem; referential integrity across files is the business of
:mod:`opensiddur.exporter.validate_urn_references` and ``urn_registry --check``, which are not
cached.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from opensiddur.exporter.refdb import file_hash

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.progress import progress
from opensiddur.importer.util import validation as _validation
from opensiddur.importer.util.constants import SCHEMA_RNG_PATH, SCHEMA_SCH_XSLT_PATH
from opensiddur.importer.util.validation import relaxng_validate, schematron_validate

logger = logging.getLogger(__name__)

#: A cleaned Jing line: ``XML:<line>:<col>: <level>: <message>`` (the temp path is replaced
#: with the literal ``XML`` by ``relaxng_validate``).
_JING_LINE = re.compile(r"^XML:(?P<line>\d+):(?P<col>\d+):\s*(?P<message>.*)$")
#: The lxml well-formedness message shape produced below.
_SYNTAX_LINE = re.compile(r"at line (?P<line>\d+), column (?P<col>\d+)$")


@dataclass(frozen=True)
class FileResult:
    """The outcome for one file. ``ok`` is true only when there are no errors."""

    path: Path
    errors: tuple[str, ...] = ()
    #: True when the result came from ``--cache`` instead of running the validators.
    cached: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class SchemaReport:
    results: list[FileResult] = field(default_factory=list)
    #: Project names passed via ``--project`` whose directory does not exist. Not an error:
    #: a PR may delete a project.
    skipped_projects: list[str] = field(default_factory=list)

    @property
    def failures(self) -> list[FileResult]:
        return [r for r in self.results if not r.ok]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def cached(self) -> int:
        return sum(1 for r in self.results if r.cached)


#: The sha256 of a file's contents -- what decides whether it must be revalidated, as it
#: decides whether it must be re-indexed. Not the mtime: a fresh checkout gives every file an
#: mtime of "now".
_file_hash = file_hash


def _canonical_xml(path: Path) -> bytes:
    """``path`` in canonical form with comments removed.

    The built RelaxNG carries a "Schema generated from ODD source <timestamp>" comment, so a
    raw hash would change on every schema build even when the schema did not.
    """
    tree = etree.parse(str(path), etree.XMLParser(remove_comments=True))
    return etree.tostring(tree, method="c14n")


def schema_fingerprint(
    rng: Path = SCHEMA_RNG_PATH, sch_xslt: Path = SCHEMA_SCH_XSLT_PATH
) -> str:
    """A hash of everything besides a file's own content that decides whether it is valid.

    That is the two built schemas (canonicalised, see :func:`_canonical_xml`) and the source
    of this module and of the validation module, so that a change in how validation runs or
    reports cannot reuse results recorded under the old code.
    """
    digest = hashlib.sha256()
    for part in (
        _canonical_xml(Path(rng)),
        _canonical_xml(Path(sch_xslt)),
        Path(__file__).read_bytes(),
        Path(_validation.__file__).read_bytes(),
    ):
        digest.update(hashlib.sha256(part).digest())
    return digest.hexdigest()


class ValidationCache:
    """The content hashes of files that passed validation under one schema fingerprint.

    Stored as JSON: ``{"fingerprint": "...", "valid": ["<sha256>", ...]}``.
    """

    def __init__(self, fingerprint: str, valid: Optional[set[str]] = None):
        self.fingerprint = fingerprint
        self.valid: set[str] = set(valid or ())

    @classmethod
    def load(cls, path: Path, fingerprint: str) -> "ValidationCache":
        """The cache at ``path``, or an empty one.

        A missing or unreadable file, or one recorded under a different fingerprint, gives an
        empty cache (so everything is validated) rather than an error.
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if data.get("fingerprint") == fingerprint:
                return cls(fingerprint, {str(h) for h in data.get("valid", [])})
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        return cls(fingerprint)

    def is_valid(self, file_hash: str) -> bool:
        return file_hash in self.valid

    def add(self, file_hash: str) -> None:
        self.valid.add(file_hash)

    def save(self, path: Path, keep: set[str]) -> None:
        """Write the cache, keeping only the hashes in ``keep``.

        ``keep`` is the hashes of the files that exist now, so hashes of edited or deleted
        files drop out instead of accumulating from one restored cache to the next.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"fingerprint": self.fingerprint, "valid": sorted(self.valid & keep)}
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as out:
            json.dump(data, out, indent=0)
        os.replace(out.name, path)


def iter_target_files(
    *,
    project_directory: Path = PROJECT_DIRECTORY,
    projects: Optional[list[str]] = None,
    files_from: Optional[list[Path]] = None,
) -> tuple[list[Path], list[str]]:
    """Resolve what to validate.

    Returns ``(files, skipped_projects)``. ``files_from`` (explicit paths, absolute or
    relative to ``project_directory``) and ``projects`` (every top-level ``*.xml`` in each,
    matching every other project iterator in this package) are unioned. With neither, every
    project directory under ``project_directory`` is used.
    """
    project_directory = Path(project_directory)
    files: list[Path] = []
    seen: set[Path] = set()
    skipped: list[str] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(path)

    for raw in files_from or []:
        path = Path(raw)
        if not path.is_absolute():
            path = project_directory / path
        add(path)

    names = projects
    if names is None and not files_from:
        names = sorted(p.name for p in project_directory.iterdir() if p.is_dir())
    for name in names or []:
        project_path = project_directory / name
        if not project_path.is_dir():
            skipped.append(name)
            continue
        for xml_file in sorted(project_path.glob("*.xml")):
            add(xml_file)

    return files, skipped


def validate_file(path: Path) -> FileResult:
    """RelaxNG + Schematron for one file, well-formedness first.

    The raw file text is handed to the validators (not a re-serialised tree) so Jing's line
    numbers point at the source.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return FileResult(Path(path), (f"cannot read file: {exc}",))

    try:
        etree.fromstring(text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return FileResult(
            Path(path),
            (f"XML syntax error: {exc.msg} at line {exc.lineno}, column {exc.position[0]}",),
        )

    ok_rng, errors_rng = relaxng_validate(text)
    ok_sch, errors_sch = schematron_validate(text)
    if ok_rng and ok_sch:
        return FileResult(Path(path))
    return FileResult(Path(path), tuple(errors_rng) + tuple(errors_sch))


def validate_files(
    paths: list[Path], cache: Optional[ValidationCache] = None
) -> list[FileResult]:
    """Validate each of ``paths``, skipping any whose content ``cache`` records as valid."""
    tracked = progress(paths, "Schema validation", logger=logger)
    if cache is None:
        return [validate_file(path) for path in tracked]
    results = []
    for path in tracked:
        try:
            file_hash = _file_hash(path)
        except OSError:
            results.append(validate_file(path))  # reports the read error
            continue
        if cache.is_valid(file_hash):
            results.append(FileResult(Path(path), cached=True))
            continue
        result = validate_file(path)
        if result.ok:
            cache.add(file_hash)
        results.append(result)
    return results


def format_annotation(file_path: str, error: str) -> str:
    """A GitHub ``::error`` workflow command for one error line.

    Jing and lxml errors carry ``line``/``col``; Schematron errors carry only an XPath
    location, which goes in the message.
    """
    jing = _JING_LINE.match(error)
    if jing:
        return (
            f"::error file={file_path},line={jing['line']},col={jing['col']}::"
            f"{jing['message']}"
        )
    syntax = _SYNTAX_LINE.search(error)
    if syntax:
        return (
            f"::error file={file_path},line={syntax['line']},col={syntax['col']}::{error}"
        )
    return f"::error file={file_path}::{error}"


def validate_schema(
    *,
    project_directory: Path = PROJECT_DIRECTORY,
    projects: Optional[list[str]] = None,
    files_from: Optional[list[Path]] = None,
    cache_path: Optional[Path] = None,
) -> SchemaReport:
    files, skipped = iter_target_files(
        project_directory=project_directory, projects=projects, files_from=files_from
    )
    if cache_path is None:
        return SchemaReport(results=validate_files(files), skipped_projects=skipped)

    cache = ValidationCache.load(cache_path, schema_fingerprint())
    results = validate_files(files, cache)
    # Keep the hashes of every file that exists now, not only the ones validated in this run:
    # a PR run validates only the projects it touched and must not drop the rest.
    logger.info("Updating the schema-validation cache: %s", cache_path)
    current = {_file_hash(path) for path in Path(project_directory).glob("*/*.xml")}
    current |= {_file_hash(r.path) for r in results if r.ok and Path(r.path).is_file()}
    cache.save(cache_path, keep=current)
    return SchemaReport(results=results, skipped_projects=skipped)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--project-directory",
        type=Path,
        default=PROJECT_DIRECTORY,
        help="Base project directory (defaults to repo project/).",
    )
    parser.add_argument(
        "--project",
        action="append",
        dest="projects",
        help="Project to validate; repeatable. Every *.xml in it is checked. "
        "Defaults to every project under --project-directory.",
    )
    parser.add_argument(
        "--files-from",
        type=Path,
        help="File of newline-delimited XML paths to validate (absolute, or relative to "
        "--project-directory). Unioned with --project.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root that --github-annotations file paths are made relative to.",
    )
    parser.add_argument(
        "--github-annotations",
        action="store_true",
        help="Also emit ::error file=...,line=...:: workflow commands.",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        help="JSON file of files already known to be valid (created if missing). A file whose "
        "content and schema are unchanged since it last passed is not revalidated.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Also list files that passed.")
    args = parser.parse_args(argv)

    files_from: Optional[list[Path]] = None
    if args.files_from:
        files_from = [
            Path(line.strip())
            for line in Path(args.files_from).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    report = validate_schema(
        project_directory=args.project_directory,
        projects=args.projects,
        files_from=files_from,
        cache_path=args.cache,
    )

    def rel(path: Path) -> str:
        try:
            return os.path.relpath(Path(path).resolve(), Path(args.repo_root).resolve())
        except ValueError:  # different drive on Windows
            return str(path)

    for name in report.skipped_projects:
        print(f"SKIP  {name} (no such project directory)")

    for result in report.results:
        if result.ok:
            if args.verbose:
                print(f"OK    {rel(result.path)}{' (cached)' if result.cached else ''}")
            continue
        print(f"FAIL  {rel(result.path)}")
        for error in result.errors:
            print(f"      {error}")
            if args.github_annotations:
                print(format_annotation(rel(result.path), error))

    checked = len(report.results)
    if report.ok:
        from_cache = f" ({report.cached} from cache)" if args.cache else ""
        print(f"OK: {checked} file(s) valid{from_cache}")
        return 0
    print(f"FAILED: {len(report.failures)} of {checked} file(s) invalid")
    return 1


if __name__ == "__main__":  # pragma: no cover
    # Only the CLI turns the progress log on. Tests call main() directly, so under the test
    # runner the records go nowhere.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
