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

Changes are found against the manifest ``sourcetexts`` last committed, not the one on disk, so
a run that stops partway, or follows a download run by hand, is simply run again: it finds the
same changes. (Move the ``sourcetexts`` checkout to its latest commit first.)

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
from dataclasses import dataclass, field
from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, PROJECT_DIRECTORY
from opensiddur.importer.opensiddur_org import match
from opensiddur.importer.opensiddur_org.match import PROPOSALS_PATH
from opensiddur.exporter.urn import split_project, split_range
from opensiddur.importer.opensiddur_org.convert import CANDIDATES_PATH, ConvertRun, convert_posts, print_run
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
from opensiddur.importer.opensiddur_org.licences import LicenceDecisions, lapsed, load_decisions
from opensiddur.importer.opensiddur_org.naming import imported_projects
from opensiddur.importer.opensiddur_org.parse_post import Post, load_post, parse_post
from opensiddur.importer.opensiddur_org.post_decisions import PostDecisions, default_post_decisions
from opensiddur.importer.opensiddur_org.scope import table_views
from opensiddur.importer.opensiddur_org.urns import load_post_urns
from opensiddur.importer.util.pages import opensiddur_org_data_directory

logger = logging.getLogger(__name__)

NEW, CHANGED, OVERRIDE_STALE, LEFT_SCOPE, DELETED = "new", "changed", "override-stale", "left-scope", "deleted"


@dataclass
class Change:
    post_id: int
    kind: str
    #: Why: the decisions a stale override holds, or why a post left scope.
    reason: str = ""


def classify(baseline: dict, current: dict, out_of_scope: dict[int, str], exported: set[int]) -> list[Change]:
    """Each post that differs between the manifest ``baseline`` (as last imported) and
    ``current`` (as just downloaded). ``out_of_scope`` gives why the download left posts out,
    ``exported`` is every post ID in the new export."""
    before: dict[str, dict] = baseline.get("posts", {})
    after: dict[str, dict] = current.get("posts", {})
    changes = []
    for key, entry in after.items():
        if key not in before:
            changes.append(Change(int(key), NEW))
        elif before[key].get("last_updated") != entry.get("last_updated"):
            changes.append(Change(int(key), CHANGED))
    for key in before:
        if key in after:
            continue
        post_id = int(key)
        if post_id not in exported:
            changes.append(Change(post_id, DELETED))
        else:
            changes.append(Change(post_id, LEFT_SCOPE, out_of_scope.get(
                post_id, "no longer a prayer, or no longer filed under Prayers & Praxes")))
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


def committed(path: Path) -> bytes | None:
    """A file as the git repository holding it last committed it, if it did."""
    path = path.resolve()
    try:
        top = Path(subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                                  check=True, capture_output=True, text=True).stdout.strip())
        return subprocess.run(["git", "-C", str(top), "show", f"HEAD:{path.relative_to(top).as_posix()}"],
                              check=True, capture_output=True).stdout
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None


def previous_post(data_dir: Path, post_id: int) -> Post | None:
    """The post as ``sourcetexts`` last committed it, if it did."""
    raw = committed(data_dir / "posts" / f"{post_id}.json")
    try:
        return parse_post(json.loads(raw)) if raw else None
    except ValueError:
        return None


# --------------------------------------------------------------------------------------------
# Pruning
# --------------------------------------------------------------------------------------------

_CORRESP_RE = re.compile(r'\bcorresp="(urn:x-opensiddur:[^"]+)"')
_TARGET_RE = re.compile(r'\btarget(?:End)?="(urn:x-opensiddur:[^"]+)"')


@dataclass
class ReferenceIndex:
    """What each project holds (its ``corresp`` URNs) and refers to (its ``target`` and
    ``targetEnd`` URNs, as (URN, pinned project or None), with ranges read as both their
    ends). Built once per run. ``source`` attributes are citations, not references a book
    resolves, and are not read."""

    holds: dict[str, set[str]]
    refers: dict[str, set[tuple[str, str | None]]]

    @classmethod
    def build(cls, project_directory: Path) -> "ReferenceIndex":
        holds: dict[str, set[str]] = {}
        refers: dict[str, set[tuple[str, str | None]]] = {}
        for project in sorted(Path(project_directory).iterdir()):
            if not project.is_dir():
                continue
            held, referred = holds.setdefault(project.name, set()), refers.setdefault(project.name, set())
            for xml in project.glob("*.xml"):
                text = xml.read_text(encoding="utf-8")
                held.update(_CORRESP_RE.findall(text))
                for target in _TARGET_RE.findall(text):
                    urn, pin = split_project(target)
                    try:
                        ends = split_range(urn) or (urn,)
                    except ValueError:
                        ends = (urn,)
                    referred.update((end, pin) for end in ends)
        return cls(holds, refers)

    def blocking(self, projects: set[str]) -> list[str]:
        """The URNs other projects refer to that, without ``projects``, nothing would hold: a
        reference pinned to one of them, or one whose nearest held URN (itself, else the
        nearest enclosing one) only they hold."""
        own = set().union(*(self.holds.get(p, set()) for p in projects))
        others = set().union(*(held for p, held in self.holds.items() if p not in projects))
        blocked = set()
        for project, referred in self.refers.items():
            if project in projects:
                continue
            for urn, pin in referred:
                if pin is not None:
                    if pin in projects:
                        blocked.add(urn)
                    continue
                for ancestor in _ancestors(urn):
                    if ancestor in others:
                        break
                    if ancestor in own:
                        blocked.add(urn)
                        break
        return sorted(blocked)


def _ancestors(urn: str) -> list[str]:
    """``urn`` and each URN enclosing it, nearest first: ``a/b/c``, ``a/b``, ``a``."""
    parts = urn.split("/")
    return ["/".join(parts[:n]) for n in range(len(parts), 0, -1)]


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
    nothing else needs what only they hold (:meth:`ReferenceIndex.blocking`)."""
    existing = imported_projects(project_directory)
    departed = [c for c in changes if c.kind in (LEFT_SCOPE, DELETED) and c.post_id in existing]
    index = ReferenceIndex.build(project_directory) if prune and departed else None
    removals = []
    for change in departed:
        projects = sorted(existing[change.post_id])
        names = [p.name for p in projects]
        if index is None:
            removals.append(Removal(change.post_id, names, pruned=False))
            continue
        blocked = index.blocking(set(names))
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
    #: Posts whose licence decision lapsed: post ID -> what it had decided.
    lapsed_licences: dict[int, str] = field(default_factory=dict)
    #: New posts' URN decisions: post ID -> "existing <urn>" or "new <urn>".
    decided: dict[int, str] = field(default_factory=dict)
    #: New posts that already had a URN decision (they left the import and came back).
    redecided: list[int] = field(default_factory=list)
    #: Each changed or departed post's title, as last imported or as now exported.
    titles: dict[int, str] = field(default_factory=dict)


def update(
    *,
    upstream: Upstream,
    ref: str = DEFAULT_REF,
    data_dir: Path | None = None,
    project_directory: Path = PROJECT_DIRECTORY,
    prune: bool = False,
    fetch: bool = True,
    decisions: PostDecisions | None = None,
    licence_decisions: LicenceDecisions | None = None,
    post_urns_path: Path | None = None,
) -> UpdateResult:
    data_dir = data_dir or opensiddur_org_data_directory()
    decisions = decisions or default_post_decisions()
    licence_decisions = licence_decisions or load_decisions()
    on_disk = load_manifest(data_dir)
    raw = committed(data_dir / "manifest.json")
    baseline = json.loads(raw) if raw else on_disk
    result = download(upstream=upstream, ref=ref, data_dir=data_dir, fetch=fetch)
    current = load_manifest(data_dir)
    run = UpdateResult(result, current.get("upstream_commit_date", ""))
    run.changes = classify(baseline, current, result.out_of_scope, set(post_paths(upstream, result.commit)))
    if not run.changes:
        return run
    mark_stale_overrides(run.changes, decisions)

    def now(post_id: int) -> Post | None:
        path = data_dir / "posts" / f"{post_id}.json"
        return load_post(path) if path.is_file() else None

    for change in run.changes:
        post, before = now(change.post_id), previous_post(data_dir, change.post_id)
        if (post or before) is not None:
            run.titles[change.post_id] = (post or before).title
        if post is None:
            continue
        entry = licence_decisions.posts.get(change.post_id)
        if entry is not None and lapsed(entry, post):
            what = next((k for k in ("hold", "reject", "allow") if k in entry), "decision")
            run.lapsed_licences[change.post_id] = f"{what}: {entry.get(what) if what != 'allow' else entry.get('reason', '')}"
        if change.kind in (CHANGED, OVERRIDE_STALE) and before is not None:
            counts = (row_counts(before), row_counts(post))
            if counts[0] != counts[1]:
                run.rows_changed[change.post_id] = counts

    new = [c.post_id for c in run.changes if c.kind == NEW]
    changed = [c.post_id for c in run.changes if c.kind == CHANGED]
    if new:
        records = load_post_urns(post_urns_path) if post_urns_path else load_post_urns()
        run.redecided = [post_id for post_id in new if post_id in records]
        status = match.main(["--sourcetexts-root", str(data_dir.parent), "--project-directory", str(project_directory),
                             *[arg for post_id in new for arg in ("--post", str(post_id))]])
        if status:
            raise RuntimeError(f"matching the new posts' URNs failed ({status})")
        records = load_post_urns(post_urns_path) if post_urns_path else load_post_urns()
        for post_id in new:
            if post_id in records and post_id not in run.redecided:
                run.decided[post_id] = f"{records[post_id].kind} {records[post_id].urn}"
    if new or changed:
        run.conversion = convert_posts(data_dir, project_directory, posts=sorted(new + changed), register=True,
                                       candidates_path=CANDIDATES_PATH)
        print_run(run.conversion)
    run.removals = remove_projects(run.changes, project_directory, prune=prune)
    return run


# --------------------------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------------------------


def report(run: UpdateResult) -> str:
    """The run as Markdown, for the description of its pull requests."""
    commit = run.download.commit

    def name(post_id: int) -> str:
        label = run.titles.get(post_id, "")
        return f"{post_id}" + (f" ({label})" if label else "")

    lines = [f"# opensiddur.org update: export of {run.upstream_commit_date}", "",
             f"Upstream commit `{commit[:10]}`.", ""]
    if not run.changes:
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
    if run.decided:
        lines += ["## URNs of new posts", "",
                  *[f"- {name(p)}: {what}" for p, what in sorted(run.decided.items())],
                  "", f"Proposals that matched existing texts are in `{PROPOSALS_PATH.name}` (in `output/`).", ""]

    review: list[str] = []
    for change in by_kind.get(OVERRIDE_STALE, []):
        review.append(f"- {name(change.post_id)}: changed since a decision about it ({change.reason}) "
                      "in `post_decisions.yaml`; review the decision, then convert it")
    for post_id, what in sorted(run.lapsed_licences.items()):
        review.append(f"- {name(post_id)}: the licence decision about it lapsed ({what}); decide again "
                      "in `licence_decisions.yaml`")
    if conversion is not None:
        for post_id, error in conversion.failed.items():
            review.append(f"- {name(post_id)}: failed: {error}")
        for post_id, why in conversion.skipped.items():
            review.append(f"- {name(post_id)}: not converted: {why}")
        for plan in conversion.plans:
            if plan.post.post_id in conversion.converted:
                for lang, why in sorted(plan.skipped_columns.items()):
                    review.append(f"- {name(plan.post.post_id)}: {lang} not imported ({why})")
        for post_id, projects in conversion.left.items():
            review.append(f"- {name(post_id)}: earlier projects left as they were: {', '.join(projects)}")
        for post_id, projects in conversion.removed.items():
            review.append(f"- {name(post_id)}: now rejected; removed {', '.join(projects)}")
    for post_id, (before, after) in sorted(run.rows_changed.items()):
        review.append(f"- {name(post_id)}: rows changed from {before} to {after}; review its row URNs "
                      "in `specs/opensiddur_org/post_urns.jsonl`")
    for post_id in run.redecided:
        review.append(f"- {name(post_id)}: came back with its earlier URN decision; check it against its rows")
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
                             "unless other projects need what only they hold")
    parser.add_argument("--no-fetch", action="store_true", help="do not fetch the upstream first")
    parser.add_argument("--report", type=Path, default=None,
                        help="where to write the report (default: output/opensiddur_org_update_<date>.md)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    run = update(
        upstream=Upstream(args.upstream_dir or default_upstream_directory()),
        ref=args.ref, data_dir=opensiddur_org_data_directory(args.sourcetexts_root),
        project_directory=args.project_directory, prune=args.prune, fetch=not args.no_fetch,
    )
    path = args.report or OUTPUT_DIRECTORY / f"opensiddur_org_update_{run.upstream_commit_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report(run), encoding="utf-8")
    print(f"Report written to {path}")
    return 1 if run.conversion is not None and run.conversion.failed else 0


if __name__ == "__main__":
    sys.exit(main())
