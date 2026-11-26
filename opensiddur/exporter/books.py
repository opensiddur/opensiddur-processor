""" Build the electronic book (HTML) and the printed one (PDF) for every settings file in a
settings directory.

The settings directory (opensiddur-projects/settings/) has one subdirectory per book, named for
the project it is built from, holding that book's settings files:
settings/chumash-opensiddur-he/annual.yaml, settings/chumash-opensiddur-he/triennial.yaml. Each
names the root file it formats in its `book:` key and says how it differs from its siblings in
`description:`. Each month, opensiddur-projects is tagged with a date (vYYYYMMDD) and every book
is built and attached to that release (.github/workflows/release-projects.yml), named
<book>-<settings>[-<tag>].pdf and .html.

The books are built with the latest opensiddur-processor release. Each settings file declares in
`requires_processor:` the processor versions that build it; `--list`, which is what the release
builds, leaves out a book whose requirement the processor running it does not meet. The
requirement is read before the rest of the file is validated, because a book waiting for a newer
release usually uses a key an older processor does not know.

Each book is built in the formats its settings list in `formats:`, both unless it says
otherwise. `--format pdf` or `--format html` builds only that one, for the books that list it;
a book that does not is skipped, not failed. The electronic book is one self-contained
<book>-<settings>[-<tag>].html (opensiddur/exporter/html/html.py). It is compiled separately,
with `--destination electronic`, which leaves the settings a reader supplies for the reader's
device to decide. `--formats` prints the formats one book lists, for the release workflow.

`--check` validates without building: the YAML parses and matches the settings schema, it
declares `requires_processor:` and this processor meets it, the project and file the book names
exist, and every font chain the book will be typeset with has
an installed font. Pull requests to opensiddur-projects run it.

A book that fails is reported and skipped; the others are still built. The exit status is
nonzero if any book failed, so a partial set of books is never mistaken for a full one.

The reference database must already be built (python -m opensiddur.exporter.refdb):
the compiler reads it from its default location.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image
from pydantic import ValidationError
import yaml

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.version import processor_version, satisfies
from opensiddur.exporter.settings import BookTarget, SettingsYaml, read_settings
from opensiddur.exporter import notices, typography


@dataclass
class BookResult:
    settings_file: Path
    name: str
    book: Optional[BookTarget] = None
    # The formats its settings say it is built in, and those asked for that it is not.
    formats: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    output_pdf: Optional[Path] = None
    output_html: Optional[Path] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def default_settings_directory(project_directory: Path) -> Path:
    """ The settings directory is a sibling of the project directory. """
    return project_directory.parent / "settings"


def discover(settings_directory: Path) -> list[Path]:
    """ Every settings file under the directory, in name order.

    Includes files that are not where a book's settings belong (directly in the settings
    directory, or nested deeper than a book's subdirectory), so that `check` reports them
    instead of their being silently left out of the release.
    """
    if not settings_directory.is_dir():
        return []
    return sorted(p for p in settings_directory.rglob("*.yaml") if p.is_file())


def book_name(settings_file: Path, settings_directory: Path) -> str:
    """ <book>/<settings>, e.g. chumash-opensiddur-he/annual. """
    return settings_file.relative_to(settings_directory).with_suffix("").as_posix()


FORMATS = ("pdf", "html")


def output_name(name: str, suffix: Optional[str] = None, extension: str = "pdf") -> str:
    stem = name.replace("/", "-")
    return f"{stem}-{suffix}.{extension}" if suffix else f"{stem}.{extension}"


def _check_fonts(settings: SettingsYaml) -> Optional[str]:
    """ Every font chain the book is typeset with, defaults included, has an installed font.

    Settings validation checks only the chains a file names, and skips even those when
    fontconfig is unavailable; here, a chain nothing on this machine can set is an error,
    because the book could not be built.
    """
    if typography._installed_font_families() is None:
        return "cannot check fonts: fontconfig (fc-list) is not available"
    for family, spec in sorted(settings.typography.fonts.items()):
        try:
            typography.resolve_font(spec.names)
        except ValueError as e:
            return f"font `{family}`: {e}"
    return None


def check(settings_file: Path, settings_directory: Path, project_directory: Path) -> BookResult:
    """ Validate a settings file and the book it names, without building anything. """
    name = book_name(settings_file, settings_directory)
    result = BookResult(settings_file=settings_file, name=name)
    if name.count("/") != 1:
        result.error = ("misplaced: a book's settings files go in its own subdirectory, "
                        "settings/<book>/<settings>.yaml")
        return result
    try:
        settings = read_settings(settings_file, project_directory=project_directory)
    except ValidationError as e:
        result.error = f"invalid settings: {e}"
        return result
    except (OSError, yaml.YAMLError) as e:
        result.error = f"unreadable settings: {e}"
        return result
    if settings.book is None:
        result.error = "no `book:` key; every file in the settings directory must name its book"
        return result
    if settings.requires_processor is None:
        result.error = ("no `requires_processor:` key; every book must declare the "
                        "opensiddur-processor versions that build it, such as `>=0.7.0`")
        return result
    result.book = settings.book
    result.formats = tuple(settings.formats)
    result.error = _check_fonts(settings) or _check_logo(settings, settings_file)
    return result


def read_raw(settings_file: Path) -> dict:
    """ A settings file's YAML, unvalidated. Raises OSError or yaml.YAMLError if it cannot be
    read, and TypeError if it is not a mapping. """
    with open(settings_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise TypeError(f"{settings_file} is not a mapping")
    return data


def buildable(settings_file: Path) -> bool:
    """ Whether this processor meets the `requires_processor:` a settings file declares.

    Read from the YAML before it is validated: a book that waits for a newer processor usually
    uses a key this one refuses. A file whose requirement cannot be read counts as buildable,
    so that its build fails and shows why.
    """
    try:
        requirement = read_raw(settings_file)["requires_processor"]
        installed = processor_version()
        return installed is None or satisfies(requirement, installed)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError):
        return True


def _check_logo(settings: SettingsYaml, settings_file: Path) -> Optional[str]:
    """ Why the distribution notice's logo cannot be set, or None if it can. """
    notice = notices.distribution_notice(settings.distribution)
    if notice is None:
        return None
    try:
        logo = notices.resolve_logo(notice, settings_file)
        if logo is not None:
            with Image.open(logo) as image:
                image.verify()
    except FileNotFoundError as e:
        return str(e)
    except (OSError, SyntaxError) as e:
        return f"distribution notice logo {notice.logo!r} is not a readable image: {e}"
    return None


def _run(command: list[str], log) -> bool:
    log.write(f"$ {' '.join(command)}\n")
    log.flush()
    completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    return completed.returncode == 0


def build(
    settings_file: Path,
    settings_directory: Path,
    project_directory: Path,
    output_directory: Path,
    suffix: Optional[str] = None,
    formats: Optional[tuple[str, ...]] = None,
) -> BookResult:
    """ Compile and render one book, in each of `formats` its settings list (default: all of
    those). A format asked for that the settings do not list is skipped, not failed.

    The compiler and output stages run as subprocesses: each book gets fresh linear data,
    and a stage that exits outright fails only its own book. Their output goes to
    <output_directory>/<book>-<settings>.log. Each format is compiled separately, an
    electronic book being compiled differently from a printed one.
    """
    result = check(settings_file, settings_directory, project_directory)
    if not result.ok:
        return result
    requested = result.formats if formats is None else formats
    result.skipped = tuple(f for f in requested if f not in result.formats)

    log_file = output_directory / output_name(result.name, extension="log")
    common = ["-s", str(settings_file), "--project-directory", str(project_directory)]
    stages = {
        "pdf": ([], "opensiddur.exporter.pdf.pdf", "typesetting"),
        "html": (["--destination", "electronic"], "opensiddur.exporter.html.html", "rendering"),
    }
    with tempfile.TemporaryDirectory() as temp, open(log_file, "w", encoding="utf-8") as log:
        for extension in (f for f in requested if f in result.formats):
            compile_options, stage, doing = stages[extension]
            compiled = Path(temp) / f"compiled-{extension}.xml"
            output = output_directory / output_name(result.name, suffix, extension)
            if not _run([sys.executable, "-m", "opensiddur.exporter.compiler",
                         "-o", str(compiled), *compile_options, *common], log):
                result.error = f"compilation failed; see {log_file}"
                return result
            if not _run([sys.executable, "-m", stage, str(compiled), str(output), *common], log):
                result.error = f"{doing} failed; see {log_file}"
                return result
            setattr(result, f"output_{extension}", output)
    return result


def _report(results: list[BookResult]) -> None:
    for result in results:
        if result.ok:
            target = f"{result.book.project}/{result.book.file_name}"
            outputs = [str(o) for o in (result.output_pdf, result.output_html) if o]
            built = f" -> {', '.join(outputs)}" if outputs else ""
            if result.skipped:
                built += f" (not built in {', '.join(result.skipped)})"
            print(f"ok      {result.name}: {target}{built}")
        else:
            print(f"FAILED  {result.name}: {result.error}")
    failed = sum(not r.ok for r in results)
    print(f"{len(results) - failed} of {len(results)} books ok")


def _select(settings_files: list[Path], settings_directory: Path, names: list[str]) -> list[Path]:
    """ The settings files named: a book (chumash-opensiddur-he) selects all its settings, or one
    (chumash-opensiddur-he/annual). """
    selected: list[Path] = []
    for name in names:
        matches = [p for p in settings_files
                   if book_name(p, settings_directory) == name
                   or book_name(p, settings_directory).startswith(f"{name}/")]
        if not matches:
            raise LookupError(name)
        selected.extend(p for p in matches if p not in selected)
    return selected


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a PDF for every settings file in the settings directory. "
                    "The reference database must be built first (python -m opensiddur.exporter.refdb).")
    parser.add_argument("names", nargs="*",
                        help="Build only these: a book (chumash-opensiddur-he) or one of its settings (chumash-opensiddur-he/annual). "
                             "Default: all.")
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY,
                        help="Base directory containing project subdirectories "
                             "(default: <repo>/opensiddur-projects/project).")
    parser.add_argument("--settings-directory", type=Path, default=None,
                        help="Directory of book settings (default: settings/ beside the project directory).")
    parser.add_argument("--output-directory", "-o", type=Path, default=Path("books"),
                        help="Where to write the PDFs and per-book logs (default: ./books).")
    parser.add_argument("--suffix", default=None,
                        help="Appended to each output's name, e.g. the release tag: chumash-opensiddur-he-annual-v20261201.pdf.")
    parser.add_argument("--format", dest="formats", action="append", choices=FORMATS,
                        help="Build only this format, pdf or html (the electronic book), for "
                             "the books whose settings list it. Repeatable. "
                             "Default: each book's own `formats:`.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true",
                        help="Only validate the settings, the books they name and their fonts; build nothing.")
    action.add_argument("--list", action="store_true",
                        help="Print the names of the settings files (e.g. chumash-opensiddur-he/annual) as a JSON list, "
                             "leaving out those whose requires_processor this processor does not meet; "
                             "build nothing. The release workflow builds one book per name.")
    action.add_argument("--formats", dest="list_formats", action="store_true",
                        help="Print the formats one settings file lists (e.g. [\"html\"]) as JSON; "
                             "build nothing. The release workflow builds only those.")
    args = parser.parse_args(argv)

    project_directory = args.project_directory.resolve()
    settings_directory = (args.settings_directory or default_settings_directory(project_directory)).resolve()
    settings_files = discover(settings_directory)
    if args.names:
        try:
            settings_files = _select(settings_files, settings_directory, args.names)
        except LookupError as e:
            parser.error(f"no book or settings file named {e.args[0]} in {settings_directory}")
    if args.list:
        print(json.dumps([book_name(f, settings_directory) for f in settings_files
                          if buildable(f)]))
        return 0
    if args.list_formats:
        if len(settings_files) != 1:
            parser.error("--formats needs exactly one settings file, "
                         f"not {len(settings_files)}")
        result = check(settings_files[0], settings_directory, project_directory)
        if not result.ok:
            print(f"FAILED  {result.name}: {result.error}", file=sys.stderr)
            return 1
        print(json.dumps(list(result.formats)))
        return 0
    if not settings_files:
        print(f"No settings files in {settings_directory}")
        return 0

    if args.check:
        results = [check(f, settings_directory, project_directory) for f in settings_files]
    else:
        args.output_directory.mkdir(parents=True, exist_ok=True)
        output_directory = args.output_directory.resolve()
        formats = tuple(dict.fromkeys(args.formats)) if args.formats else None
        results = [build(f, settings_directory, project_directory, output_directory, args.suffix,
                         formats)
                   for f in settings_files]
    _report(results)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
