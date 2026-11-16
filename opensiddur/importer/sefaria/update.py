"""Bring the Sefaria imports up to a new monthly export.

Sefaria re-exports its library around the first of each month and overwrites the bucket's
files in place, so nothing upstream says what changed. This compares the manifest a fresh
download writes with the one ``sourcetexts`` last committed, leaf by leaf (each leaf's
segment counts and a hash of each version's segments, ``source.leaf_hashes``):

================  ==========================================  =================================
class             meaning                                     action
================  ==========================================  =================================
unchanged         the same segments                           nothing
text-changed      different words, the same number of         reconverted; its phrases keep
                  segments in each version                    their numbers
resegmented       a version's number of segments changed      reported; its alignment decision
                                                              and its texts' phrase numbers
                                                              must be reviewed before converting
added / removed   a leaf the schema gained or lost            reported; the structure table
                                                              must place it first
metadata          a version's title, licence or source        reported; a new licence must be
                  changed                                     decided before converting
================  ==========================================  =================================

When nothing needs review, the work is converted (``convert.py --register``), which re-decides
the URNs of texts whose words changed (their records lapse) and lists them in its report.
``output/sefaria_update_<date>.md`` becomes the description of the run's pull requests.

Run (after moving the ``sourcetexts`` checkout to its latest commit)::

    uv run python -m opensiddur.importer.sefaria.update [--work KEY ...] [--no-download]
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opensiddur.common.constants import OUTPUT_DIRECTORY
from opensiddur.importer.sefaria.download import MANIFEST_NAME, Client, download, load_manifest
from opensiddur.importer.sefaria.works import Work, select_works

logger = logging.getLogger(__name__)

#: Manifest fields of a version file whose change needs a decision.
METADATA_FIELDS = ("version_title", "license", "url")


@dataclass
class Changes:
    work: str
    unchanged: list[str] = field(default_factory=list)
    text_changed: list[str] = field(default_factory=list)
    resegmented: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    metadata: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return bool(self.resegmented or self.added or self.removed or self.metadata)

    @property
    def changed(self) -> bool:
        return bool(self.text_changed) or self.needs_review


def classify(work: str, before: dict[str, Any], after: dict[str, Any]) -> Changes:
    changes = Changes(work)
    old, new = before.get("leaves", {}), after.get("leaves", {})
    for path in new:
        if path not in old:
            changes.added.append(path)
            continue
        a, b = old[path], new[path]
        if (a["he_segments"], a["en_segments"]) != (b["he_segments"], b["en_segments"]):
            changes.resegmented.append(path)
        elif (a["he"], a["en"]) != (b["he"], b["en"]):
            changes.text_changed.append(path)
        else:
            changes.unchanged.append(path)
    changes.removed = [path for path in old if path not in new]
    old_files, new_files = before.get("files", {}), after.get("files", {})
    for name in ("he.json", "en.json"):
        for key in METADATA_FIELDS:
            was, now = old_files.get(name, {}).get(key), new_files.get(name, {}).get(key)
            if old_files and was != now:
                changes.metadata.append(f"{name} {key}: {was!r} -> {now!r}")
    return changes


def committed_manifest(directory: Path) -> dict[str, Any]:
    """The manifest as the ``sourcetexts`` repository last committed it, or {} when it has
    none (a first import)."""
    try:
        text = subprocess.run(
            ["git", "-C", str(directory), "show", f"HEAD:./{MANIFEST_NAME}"],
            check=True, capture_output=True, text=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    return json.loads(text)


def report(all_changes: list[Changes], converted: dict[str, str]) -> str:
    lines = [f"# Sefaria update, {datetime.date.today().isoformat()}", ""]
    for changes in all_changes:
        lines += [f"## {changes.work}", ""]
        if not changes.changed:
            lines += ["No leaf changed.", ""]
            continue
        for title, paths in (("Text changed (reconverted)", changes.text_changed),
                             ("Resegmented (review alignment and phrase numbers)", changes.resegmented),
                             ("Added (place in the structure table)", changes.added),
                             ("Removed", changes.removed),
                             ("Version metadata changed (decide before converting)", changes.metadata)):
            if paths:
                lines.append(f"### {title}")
                lines += [f"- {p}" for p in paths]
                lines.append("")
        lines += [converted.get(changes.work, "Not converted: review the changes above first."), ""]
    return "\n".join(lines)


def update(works: list[Work], *, sourcetexts_root: Path | None = None, fetch: bool = True,
           client: Client | None = None, convert: bool = True,
           output_directory: Path = OUTPUT_DIRECTORY) -> tuple[list[Changes], Path]:
    befores = {work.key: committed_manifest(work.data_directory(sourcetexts_root))
               or load_manifest(work.data_directory(sourcetexts_root)) for work in works}
    if fetch:
        download(works, client or Client(), sourcetexts_root)
    all_changes: list[Changes] = []
    converted: dict[str, str] = {}
    for work in works:
        after = load_manifest(work.data_directory(sourcetexts_root))
        changes = classify(work.key, befores[work.key], after)
        all_changes.append(changes)
        if convert and changes.changed and not changes.needs_review:
            from opensiddur.importer.sefaria.convert import convert_work

            plan = convert_work(work, sourcetexts_root=sourcetexts_root, do_register=True)
            converted[work.key] = (f"Converted: {len(plan.decisions.decided)} text URN(s) decided again; "
                                   f"see output/sefaria_{work.key}_report.md.")
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / f"sefaria_update_{datetime.date.today().isoformat()}.md"
    path.write_text(report(all_changes, converted), encoding="utf-8")
    return all_changes, path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", action="append", help="a key from works.yaml; repeatable. Default: all")
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument("--no-download", action="store_true", help="compare what is on disk")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    changes, path = update(select_works(args.work), sourcetexts_root=args.sourcetexts_root,
                           fetch=not args.no_download)
    print(f"Report: {path}")
    return 1 if any(c.needs_review for c in changes) else 0


if __name__ == "__main__":
    sys.exit(main())
