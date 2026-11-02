"""Bring the opensiddur.org import up to a new monthly export.

One run does what the import's stages do by hand, for the posts the export changed:

1. Download the export at ``--ref`` into ``sourcetexts`` (``download.py``), and compare the
   manifest before and after, by post ID:

   ============== ============================================ ===================================
   class          meaning                                      action
   ============== ============================================ ===================================
   new            newly published, or entered scope            match its URNs and convert it
   changed        its ``last_updated`` differs                 reconvert it
   override-stale changed, and a person decided something      reported, for the decision to be
                  about it (``post_decisions.yaml``)           reviewed; not reconverted
   left-scope     still exported, but no longer a prayer       reported; its projects are removed
                                                               only with ``--prune``
   deleted        no longer exported                           likewise
   ============== ============================================ ===================================

2. Decide the URNs of new posts (``match.py``) and convert new and changed posts
   (``convert.py``), registering new URNs.
3. Write ``output/opensiddur_org_update_<date>.md``, which becomes the description of the
   pull requests for the run.

Decisions about one post's licence lapse when the post is updated or relicensed
(``licences.lapsed``), so a changed post that was held or rejected is asked about again: the
report lists it. A changed post whose rows changed in number has its row URNs reviewed, since
they were decided against its old rows.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, PROJECT_DIRECTORY
from opensiddur.importer.opensiddur_org import match
from opensiddur.importer.opensiddur_org.convert import ConvertRun, convert_posts, print_run
from opensiddur.importer.opensiddur_org.download import (
    DEFAULT_REF,
    UPSTREAM_ENV,
    DownloadResult,
    Upstream,
    default_upstream_directory,
    download,
    load_manifest,
    post_paths,
)
from opensiddur.importer.opensiddur_org.naming import imported_projects
from opensiddur.importer.opensiddur_org.parse_post import Post, load_post, parse_post
from opensiddur.importer.opensiddur_org.post_decisions import PostDecisions, default_post_decisions
from opensiddur.importer.opensiddur_org.scope import table_views
from opensiddur.importer.util.pages import opensiddur_org_data_directory

logger = logging.getLogger(__name__)

NEW, CHANGED, OVERRIDE_STALE, LEFT_SCOPE, DELETED = "new", "changed", "override-stale", "left-scope", "deleted"


@dataclass
class Change:
    post_id: int
    kind: str
    #: Why: the decisions a stale override holds, or why a post left scope.
    reason: str = ""


def classify(previous: dict, result: DownloadResult, exported: set[int]) -> list[Change]:
    """Each post the download wrote or removed, by what happened to it upstream. ``previous``
    is the manifest before the download, ``exported`` every post ID in the new export."""
    known = set(previous.get("posts", {}))
    changes = [Change(post_id, CHANGED if str(post_id) in known else NEW) for post_id in result.written]
    for post_id in result.removed:
        if post_id not in exported:
            changes.append(Change(post_id, DELETED))
        else:
            changes.append(Change(post_id, LEFT_SCOPE, result.out_of_scope.get(
                post_id, "no longer filed under Prayers & Praxes")))
    return sorted(changes, key=lambda c: c.post_id)


def overrides(post_id: int, decisions: PostDecisions) -> list[str]:
    """The kinds of decision ``post_decisions.yaml`` holds about a post."""
    return [name for name in ("out_of_scope", "column_languages", "colours", "essays", "layouts")
            if post_id in getattr(decisions, name)]


def mark_stale_overrides(changes: list[Change], decisions: PostDecisions) -> None:
    """A changed post a person decided something about goes back to them: the decision was made
    against the post as it was."""
    for change in changes:
        held = overrides(change.post_id, decisions)
        if change.kind == CHANGED and held:
            change.kind = OVERRIDE_STALE
            change.reason = ", ".join(held)


def row_counts(post: Post) -> list[int]:
    """The number of rows of each of the post's texts."""
    return [len(view.rows) for view in table_views(post)]


def previous_post(data_dir: Path, post_id: int) -> Post | None:
    """The post as ``sourcetexts`` last committed it, if it did."""
    path = (data_dir / "posts" / f"{post_id}.json").resolve()
    try:
        top = Path(subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                                  check=True, capture_output=True, text=True).stdout.strip())
        raw = subprocess.run(["git", "-C", str(top), "show", f"HEAD:{path.relative_to(top).as_posix()}"],
                             check=True, capture_output=True).stdout
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None
    return parse_post(json.loads(raw))


# --------------------------------------------------------------------------------------------
# Pruning
# --------------------------------------------------------------------------------------------

_CORRESP_RE = re.compile(r'\bcorresp="(urn:x-opensiddur:[^"]+)"')
_TARGET_RE = re.compile(r'\btarget(?:End)?="(urn:x-opensiddur:[^"]+)"')


def _urns(paths: Iterable[Path], pattern: re.Pattern) -> set[str]:
    found: set[str] = set()
    for project in paths:
        for xml in project.glob("*.xml"):
            found.update(pattern.findall(xml.read_text(encoding="utf-8")))
    return found


def blocking_references(projects: list[Path], project_directory: Path) -> list[str]:
    """The URNs that only ``projects`` hold and other projects refer to: removing ``projects``
    would leave those references with nothing to resolve to."""
    own = {p.resolve() for p in projects}
    others = [p for p in Path(project_directory).iterdir() if p.is_dir() and p.resolve() not in own]
    held = _urns(projects, _CORRESP_RE) - _urns(others, _CORRESP_RE)
    referred = _urns(others, _TARGET_RE)
    return sorted(urn for urn in held if any(ref == urn or ref.startswith(urn + "/") for ref in referred))


@dataclass
class Removal:
    post_id: int
    projects: list[str]
    pruned: bool
    #: URNs other projects still need, which kept the projects.
    blocked_by: list[str] = field(default_factory=list)


def remove_projects(changes: list[Change], project_directory: Path, *, prune: bool,
                    dry_run: bool = False) -> list[Removal]:
    """The projects of posts that left scope or were deleted: removed with ``prune``, when
    nothing else refers to what only they hold."""
    existing = imported_projects(project_directory)
    removals = []
    for change in changes:
        if change.kind not in (LEFT_SCOPE, DELETED) or change.post_id not in existing:
            continue
        projects = sorted(existing[change.post_id])
        names = [p.name for p in projects]
        if not prune:
            removals.append(Removal(change.post_id, names, pruned=False))
            continue
        blocked = blocking_references(projects, project_directory)
        if not blocked and not dry_run:
            for path in projects:
                shutil.rmtree(path)
        removals.append(Removal(change.post_id, names, pruned=not blocked, blocked_by=blocked))
    return removals


# --------------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------------


@dataclass
class UpdateResult:
    download: DownloadResult
    upstream_commit_date: str
    changes: list[Change] = field(default_factory=list)
    conversion: ConvertRun | None = None
    removals: list[Removal] = field(default_factory=list)
    #: Changed posts whose rows changed in number: post ID -> (before, after) per text.
    rows_changed: dict[int, tuple[list[int], list[int]]] = field(default_factory=dict)


def update(
    *,
    upstream: Upstream,
    ref: str = DEFAULT_REF,
    data_dir: Path | None = None,
    project_directory: Path = PROJECT_DIRECTORY,
    prune: bool = False,
    fetch: bool = True,
    decisions: PostDecisions | None = None,
    match_argv: list[str] | None = None,
) -> UpdateResult:
    data_dir = data_dir or opensiddur_org_data_directory()
    decisions = decisions or default_post_decisions()
    previous = load_manifest(data_dir)
    result = download(upstream=upstream, ref=ref, data_dir=data_dir, fetch=fetch)
    manifest = load_manifest(data_dir)
    run = UpdateResult(result, manifest.get("upstream_commit_date", ""))
    if result.noop:
        return run

    run.changes = classify(previous, result, set(post_paths(upstream, result.commit)))
    mark_stale_overrides(run.changes, decisions)
    new = [c.post_id for c in run.changes if c.kind == NEW]
    changed = [c.post_id for c in run.changes if c.kind == CHANGED]

    for post_id in changed:
        before = previous_post(data_dir, post_id)
        if before is None:
            continue
        counts = (row_counts(before), row_counts(load_post(data_dir / "posts" / f"{post_id}.json")))
        if counts[0] != counts[1]:
            run.rows_changed[post_id] = counts

    if new:
        match.main([*(match_argv or []), "--sourcetexts-root", str(data_dir.parent),
                    "--project-directory", str(project_directory),
                    *[arg for post_id in new for arg in ("--post", str(post_id))]])
    if new or changed:
        run.conversion = convert_posts(data_dir, project_directory, posts=sorted(new + changed), register=True)
        print_run(run.conversion)
    run.removals = remove_projects(run.changes, project_directory, prune=prune)
    return run


# --------------------------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------------------------


def report(run: UpdateResult, *, title: dict[int, str] | None = None) -> str:
    """The run as Markdown, for the description of its pull requests."""
    title = title or {}
    commit = run.download.commit

    def name(post_id: int) -> str:
        label = title.get(post_id, "")
        return f"{post_id}" + (f" ({label})" if label else "")

    lines = [f"# opensiddur.org update: export of {run.upstream_commit_date}", "",
             f"Upstream commit `{commit[:10]}`.", ""]
    if run.download.noop:
        return "\n".join(lines + ["Nothing changed since the last import.", ""])
    by_kind: dict[str, list[Change]] = {}
    for change in run.changes:
        by_kind.setdefault(change.kind, []).append(change)
    counts = ", ".join(f"{len(by_kind.get(kind, []))} {kind}"
                       for kind in (NEW, CHANGED, OVERRIDE_STALE, LEFT_SCOPE, DELETED))
    lines += [f"Posts: {counts}.", ""]

    conversion = run.conversion
    if conversion is not None:
        lines += ["## Converted", ""]
        for kind in (NEW, CHANGED):
            done = [c.post_id for c in by_kind.get(kind, []) if c.post_id in conversion.converted]
            if done:
                lines.append(f"- {kind}: {', '.join(name(p) for p in done)}")
        lines.append("")

    review: list[str] = []
    for change in by_kind.get(OVERRIDE_STALE, []):
        review.append(f"- {name(change.post_id)}: changed since a decision about it ({change.reason}) "
                      "in `post_decisions.yaml`; review the decision, then convert it")
    if conversion is not None:
        for post_id, error in conversion.failed.items():
            review.append(f"- {name(post_id)}: failed: {error}")
        for post_id, why in conversion.skipped.items():
            review.append(f"- {name(post_id)}: not converted: {why}")
        for post_id, projects in conversion.left.items():
            review.append(f"- {name(post_id)}: earlier projects left as they were: {', '.join(projects)}")
        for post_id, projects in conversion.removed.items():
            review.append(f"- {name(post_id)}: now rejected; removed {', '.join(projects)}")
    for post_id, (before, after) in sorted(run.rows_changed.items()):
        review.append(f"- {name(post_id)}: rows changed from {before} to {after}; review its row URNs "
                      "in `specs/opensiddur_org/post_urns.jsonl`")
    if review:
        lines += ["## Needs review", "", *review, ""]

    removed = [c for c in run.changes if c.kind in (LEFT_SCOPE, DELETED)]
    if removed:
        lines += ["## Left the import", ""]
        removals = {r.post_id: r for r in run.removals}
        for change in removed:
            why = f"{change.kind}" + (f": {change.reason}" if change.reason else "")
            removal = removals.get(change.post_id)
            if removal is None:
                outcome = "no projects"
            elif removal.pruned:
                outcome = f"removed {', '.join(removal.projects)}"
            elif removal.blocked_by:
                outcome = (f"kept {', '.join(removal.projects)}: other projects refer to "
                           f"{', '.join(removal.blocked_by)}")
            else:
                outcome = f"kept {', '.join(removal.projects)} (remove with `--prune`)"
            lines.append(f"- {name(change.post_id)}: {why}; {outcome}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ref", default=DEFAULT_REF, help="upstream commit or ref (default: %(default)s)")
    parser.add_argument("--upstream-dir", type=Path, default=None,
                        help=f"the export's clone (default: ${UPSTREAM_ENV} or opensiddur-repos/opensiddur.org)")
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument("--prune", action="store_true",
                        help="remove the projects of posts that left scope or were deleted, "
                             "unless other projects refer to what only they hold")
    parser.add_argument("--no-fetch", action="store_true", help="do not fetch the upstream first")
    parser.add_argument("--report", type=Path, default=None,
                        help="where to write the report (default: output/opensiddur_org_update_<date>.md)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    data_dir = opensiddur_org_data_directory(args.sourcetexts_root)
    run = update(
        upstream=Upstream(args.upstream_dir or default_upstream_directory()),
        ref=args.ref, data_dir=data_dir, project_directory=args.project_directory,
        prune=args.prune, fetch=not args.no_fetch,
    )
    titles = {}
    for change in run.changes:
        path = data_dir / "posts" / f"{change.post_id}.json"
        if path.is_file():
            titles[change.post_id] = load_post(path).title
    text = report(run, title=titles)
    path = args.report or OUTPUT_DIRECTORY / f"opensiddur_org_update_{run.upstream_commit_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Report written to {path}")
    return 1 if run.conversion is not None and run.conversion.failed else 0


if __name__ == "__main__":
    sys.exit(main())
