"""The downloads list of a book release: opensiddur-projects/DOWNLOADS.md (opensiddur-processor#275).

Each book release attaches its books to a release of opensiddur-projects, named with the release's
tag (<project>-<variant>-vYYYYMMDD.html and .pdf), so no download URL stays the same from one release
to the next. After a release is published, release-projects.yml rewrites DOWNLOADS.md with this
module: one section per settings file, with the book's title and description and links to the
forms the release has of it.

`uv run python -m opensiddur.release.downloads RELEASE_JSON --settings-directory DIR --output FILE`

RELEASE_JSON is `gh release view <tag> --json tagName,url,publishedAt,body,assets`. The settings
directory is the one the release was built from.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from opensiddur.exporter.books import book_name, discover, output_name, read_raw

# The forms of a book, in the order they are listed.
FORMS = (("html", "Electronic book"), ("pdf", "Printed book"))

BUILT_WITH_RE = re.compile(r"^Built with opensiddur-processor (v\d+\.\d+\.\d+)", re.MULTILINE)


@dataclass(frozen=True)
class BookEntry:
    name: str
    """<project>/<variant>, as books --list gives it."""

    title: str
    """The settings file's `book.title`, or its name if it has none."""

    description: Optional[str] = None


def _text(value) -> Optional[str]:
    """ A YAML value as one line of text, or None if it is not a nonempty string. """
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None


def book_entries(settings_directory: Path) -> list[BookEntry]:
    """ Every settings file's name, title and description, in name order.

    Read from the YAML without validating it: the list is made by a newer processor than the
    one that built the books, but a settings file may use a key it does not know.
    """
    entries = []
    for settings_file in discover(settings_directory):
        name = book_name(settings_file, settings_directory)
        try:
            data = read_raw(settings_file)
        except (OSError, yaml.YAMLError, TypeError):
            data = {}
        book = data.get("book")
        title = _text(book.get("title")) if isinstance(book, dict) else None
        entries.append(BookEntry(name, title or name, _text(data.get("description"))))
    return entries


def human_size(size: int) -> str:
    """ 1536 -> '1.5 KB'. """
    if size < 1024:
        return f"{size} bytes"
    value = size / 1024
    for unit in ("KB", "MB"):
        # Rounded, as it will be printed: 1023.96 KB is 1.0 MB, not 1024.0 KB.
        if round(value, 1) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _link(asset: dict) -> str:
    return f"[{asset['name']}]({asset['url']}) ({human_size(asset['size'])})"


def render_downloads(release: dict, books: list[BookEntry]) -> str:
    """ DOWNLOADS.md for a release, given as `gh release view --json` gives it. """
    tag = release["tagName"]
    assets = {asset["name"]: asset for asset in release.get("assets", [])}
    releases_page = release["url"].rsplit("/tag/", 1)[0]

    intro = f"Books from the opensiddur-projects book release [{tag}]({release['url']})"
    published = (release.get("publishedAt") or "")[:10]
    if published:
        intro += f", published {published}"
    built_with = BUILT_WITH_RE.search(release.get("body") or "")
    if built_with:
        intro += f", built with opensiddur-processor {built_with.group(1)}"
    lines = [
        "# Downloads",
        "",
        f"{intro}. Each book release rewrites this file. Earlier releases are on the "
        f"[releases page]({releases_page}).",
    ]

    missing = []
    for book in books:
        forms = [
            (label, assets.pop(name))
            for extension, label in FORMS
            if (name := output_name(book.name, tag, extension)) in assets
        ]
        if not forms:
            missing.append(book)
            continue
        lines += ["", f"## {book.title}", ""]
        if book.description:
            lines += [book.description, ""]
        lines += [f"- {label}: {_link(asset)}" for label, asset in forms]

    if missing:
        lines += ["", "## Not in this release", ""]
        lines += [f"- {book.title} ({book.name})" for book in missing]
    if assets:
        lines += ["", "## Other files", ""]
        lines += [f"- {_link(assets[name])}" for name in sorted(assets)]
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m opensiddur.release.downloads",
        description="Write the downloads list (DOWNLOADS.md) of a book release.",
    )
    parser.add_argument("release_json", type=Path,
                        help="The release, as `gh release view <tag> --json "
                             "tagName,url,publishedAt,body,assets` prints it.")
    parser.add_argument("--settings-directory", type=Path, required=True,
                        help="The settings directory the release was built from.")
    parser.add_argument("--output", type=Path, required=True, help="The file to write.")
    args = parser.parse_args(argv)

    release = json.loads(args.release_json.read_text(encoding="utf-8"))
    args.output.write_text(render_downloads(release, book_entries(args.settings_directory)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
