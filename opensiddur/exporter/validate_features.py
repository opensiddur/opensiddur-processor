"""Check every declared and tested setting in the projects against the settings registry.

The compiler checks a setting when it reaches one, but only on the files a book transcludes,
and only when the book is built. This walks every file, so a misspelt feature in a text no
book yet includes is found when it is written rather than when it is first printed — or
never, since a condition on a feature nobody sets is quietly undecided.

Settings files are checked separately, by ``books --check``, which validates their
``declarations`` against the same registry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.exporter.constants import JLPTEI_NAMESPACE, TEI_NS
from opensiddur.exporter.feature_registry import check_fs_element

_TEI_FS = f"{{{TEI_NS}}}fs"
_J_DECLARE = f"{{{JLPTEI_NAMESPACE}}}declare"
_J_CONDITIONS = frozenset({
    f"{{{JLPTEI_NAMESPACE}}}conditional",
    f"{{{JLPTEI_NAMESPACE}}}condition",
})


def settings_problems(path: Path) -> Iterator[tuple[int, str]]:
    """(line, problem) for each registry violation in one file."""
    try:
        root = etree.parse(str(path)).getroot()
    except etree.XMLSyntaxError as e:
        yield e.lineno or 0, f"not well-formed XML: {e.msg}"
        return
    for fs in root.iter(_TEI_FS):
        context = None
        for ancestor in fs.iterancestors():
            if ancestor.tag == _J_DECLARE:
                context = False
                break
            if ancestor.tag in _J_CONDITIONS:
                context = True
                break
        if context is None:
            continue  # a feature structure that is not a setting
        for problem in check_fs_element(fs, in_condition=context):
            yield fs.sourceline or 0, problem


def validate(project_directory: Path, projects: list[str] | None = None) -> int:
    """Report every violation under the project directory; the number found."""
    roots = [project_directory / p for p in projects] if projects else [project_directory]
    found = 0
    for root in roots:
        if not root.is_dir():
            print(f"{root}: no such project directory")
            found += 1
            continue
        for path in sorted(root.rglob("*.xml")):
            for line, problem in settings_problems(path):
                print(f"{path.relative_to(project_directory).as_posix()}:{line}: {problem}")
                found += 1
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("projects", nargs="*",
                        help="Check only these projects. Default: all.")
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY,
                        help="Base directory containing project subdirectories.")
    args = parser.parse_args(argv)
    found = validate(args.project_directory, args.projects)
    if found:
        print(f"{found} setting(s) break the registry (opensiddur/exporter/features.yaml)",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
