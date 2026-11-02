"""Convert opensiddur.org posts from ``sourcetexts`` into JLPTEI projects.

Only standard posts are converted (see :mod:`scope`). For each one, every column with text
becomes a project ``<title>-<author>-<date>-<lang>`` (see :mod:`naming`), unless its licence
is rejected or undecided. Every file is validated before it is written; stale files in the
post's projects, and projects the post no longer has -- a language it lost, or a name its
retitling changed -- are removed. A post's projects are found by the post ID their
``index.xml`` records.

A post needs a URN decision in ``specs/opensiddur_org/post_urns.jsonl`` (see
:mod:`match`) and every person it credits registered in
``specs/urn_registry/contributor.jsonl``. ``--register`` adds the registry records a post's
new URNs need; ``--emit-contributor-candidates`` writes the lines for unregistered people to
``output/`` for review, and never registers anyone.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from opensiddur.common.constants import OUTPUT_DIRECTORY, PROJECT_DIRECTORY
from opensiddur.common.urn_registry import REGISTRY_DIRECTORY
from opensiddur.exporter.validate_urn_references import (
    validate_project_contributor_references,
    validate_project_urn_references,
)
from opensiddur.importer.opensiddur_org.contributors import (
    Contributors,
    candidate_line,
    post_credits,
    registered_contributors,
    unregistered,
)
from opensiddur.importer.opensiddur_org.download import MANIFEST_NAME, load_manifest
from opensiddur.importer.opensiddur_org.licences import LicenceDecision, LicenceDecisions, load_decisions
from opensiddur.importer.opensiddur_org.naming import Candidate, assign_project_ids, imported_projects
from opensiddur.importer.opensiddur_org.parse_post import Column, Post, load_post
from opensiddur.importer.opensiddur_org.scope import (
    content_scope,
    descendant_categories,
    irregularities,
    posts_in_categories,
    project_columns,
    table_views,
)
from opensiddur.importer.opensiddur_org.tei_builder import (
    build_project,
    essay_language,
    front_language,
    row_numbers,
    titles_by_language,
)
from opensiddur.importer.opensiddur_org.urns import (
    POST_URNS_PATH,
    PostUrns,
    load_post_urns,
    registry_lines,
)
from opensiddur.importer.util.pages import opensiddur_org_data_directory
from opensiddur.importer.util.tei_project import prune_stale_files, validate_and_write

logger = logging.getLogger(__name__)

CANDIDATES_PATH = OUTPUT_DIRECTORY / "opensiddur_org_contributor_candidates.jsonl"


@dataclass
class PostPlan:
    """What converting one post would do, or why it cannot be done."""

    post: Post
    reasons: list[str] = field(default_factory=list)
    #: (column, licence decision) for each project the post makes.
    columns: list[tuple[Column, LicenceDecision]] = field(default_factory=list)
    skipped_columns: dict[str, str] = field(default_factory=dict)
    candidates: list[str] = field(default_factory=list)

    @property
    def standard(self) -> bool:
        return not self.reasons


@dataclass
class Context:
    data_dir: Path
    contributors: Contributors
    decisions: LicenceDecisions
    post_urns: dict[int, PostUrns]
    registered: set[str]
    upstream_commit: str
    upstream_commit_date: str


def load_context(
    data_dir: Path,
    *,
    post_urns_path: Path = POST_URNS_PATH,
    registry_directory: Path = REGISTRY_DIRECTORY,
    decisions: LicenceDecisions | None = None,
) -> Context:
    manifest = load_manifest(data_dir)
    if not manifest:
        raise SystemExit(f"No {MANIFEST_NAME} in {data_dir}; run the download first.")
    return Context(
        data_dir=data_dir,
        contributors=Contributors.load(data_dir / "contributors_by_id.json"),
        decisions=decisions or load_decisions(),
        post_urns=load_post_urns(post_urns_path),
        registered=registered_contributors(registry_directory),
        upstream_commit=manifest["upstream_commit"],
        upstream_commit_date=manifest["upstream_commit_date"],
    )


def plan_post(post: Post, context: Context) -> PostPlan:
    plan = PostPlan(post)
    scope = content_scope(post)
    if not scope.in_scope:
        plan.reasons.append(f"out of scope: {scope.reason}")
        return plan
    plan.reasons.extend(irregularities(post))

    credits = post_credits(post, context.contributors)
    missing = unregistered(credits, context.registered)
    if missing:
        plan.reasons.append("unregistered contributor(s): " + ", ".join(c.slug for c in missing))
        plan.candidates = [candidate_line(c) for c in missing]

    if post.post_id not in context.post_urns:
        plan.reasons.append("no URN decision")

    for column in project_columns(post):
        decision = context.decisions.for_column(post, column)
        if decision.status == "allow":
            plan.columns.append((column, decision))
        else:
            plan.skipped_columns[column.key] = f"{decision.status}: {decision.basis}"
    if not plan.columns and not plan.reasons:
        plan.reasons.append("no column may be imported: " + "; ".join(
            f"{lang} {why}" for lang, why in sorted(plan.skipped_columns.items())))
    return plan


def is_rejected(plan: PostPlan) -> bool:
    """Whether every column with text was rejected, so that nothing of the post is imported."""
    return not plan.columns and bool(plan.skipped_columns) and all(
        why.startswith("reject") for why in plan.skipped_columns.values()
    )


def _compact(document: str) -> str:
    """Drop the newlines between tags that the document template puts there, so that the
    pretty-printer can indent while keeping meaningful spaces between inline elements."""
    return re.sub(r">\s*\n\s*<", "><", document)


def project_ids(plans: list[PostPlan], project_directory: Path,
                existing: dict[int, list[Path]] | None = None) -> dict[tuple[int, str], str]:
    """The project each column of the standard ``plans`` is written to, keyed by
    ``(post_id, lang)``. Pass every post of the export, not only those being converted, so
    that a name is given the same way whichever posts a run converts."""
    directory = Path(project_directory)
    if existing is None:
        existing = imported_projects(directory)
    named = {plan.post.post_id for plan in plans if plan.standard}
    rejected = {plan.post.post_id for plan in plans if is_rejected(plan)}
    # A name a post being named holds stays its own (see assign_project_ids). A rejected post's
    # projects are about to be removed, so their names are free, as are empty directories (a
    # failed conversion's leftovers). Any other name is taken.
    held = {path.name: post_id for post_id, paths in existing.items() if post_id in named
            for path in paths}
    freed = {path.name for post_id, paths in existing.items() if post_id in rejected for path in paths}
    taken = ([p.name for p in directory.iterdir()
              if p.is_dir() and any(p.iterdir()) and p.name not in held and p.name not in freed]
             if directory.is_dir() else [])
    return assign_project_ids(
        (Candidate(plan.post, column) for plan in plans if plan.standard for column, _ in plan.columns),
        taken,
        held,
    )


def convert_post(
    plan: PostPlan, context: Context, project_directory: Path, *,
    ids: dict[tuple[int, str], str],
    existing: dict[int, list[Path]] | None = None,
    registry_directory: Path = REGISTRY_DIRECTORY,
) -> list[str]:
    """Write the post's projects, named by ``ids`` (see :func:`project_ids`). Returns their IDs.

    All or nothing: when a file or a reference check fails, every directory the post touched
    is put back as it was, and the error is raised."""
    project_directory = Path(project_directory)
    if existing is None:
        existing = imported_projects(project_directory)
    touched = sorted({project_directory / pid for (post_id, _), pid in ids.items()
                      if post_id == plan.post.post_id}
                     | set(existing.get(plan.post.post_id, [])))
    with tempfile.TemporaryDirectory() as backup:
        saved = []
        for directory in touched:
            if directory.is_dir():
                shutil.copytree(directory, Path(backup) / directory.name)
                saved.append(directory)
        try:
            return _write_post(plan, context, project_directory, ids=ids, existing=existing,
                               registry_directory=registry_directory)
        except Exception:
            for directory in touched:
                if directory.exists():
                    shutil.rmtree(directory)
            for directory in saved:
                shutil.copytree(Path(backup) / directory.name, directory)
            raise


def _write_post(
    plan: PostPlan, context: Context, project_directory: Path, *,
    ids: dict[tuple[int, str], str],
    existing: dict[int, list[Path]],
    registry_directory: Path,
) -> list[str]:
    post = plan.post
    urns = context.post_urns[post.post_id]
    credits = post_credits(post, context.contributors)
    languages = [column.lang for column, _ in plan.columns]
    front_lang = front_language(post, languages)
    # The first project in that language has it, not a variant.
    front_key = next((column.key for column, _ in plan.columns if column.lang == front_lang), None)
    # An introduction in several languages: each in the first project of its language.
    own_intro_keys = {next(column.key for column, _ in plan.columns if column.lang == lang)
                      for lang in post.intros_by_language if lang in languages}
    for lang in sorted(set(post.intros_by_language) - set(languages)):
        logger.warning("%s: its introduction in %s has no project of that language; not imported",
                       post.post_id, lang)
    essay_lang = essay_language(post, languages) if post.essay else None
    essay_key = next((column.key for column, _ in plan.columns if column.lang == essay_lang), None)
    written_projects: list[str] = []
    for column, decision in plan.columns:
        files = build_project(
            post, column,
            urns=urns, credits=credits, licence=decision,
            upstream_commit=context.upstream_commit,
            upstream_commit_date=context.upstream_commit_date,
            with_front=column.key == front_key,
            with_essay=column.key == essay_key,
            with_own_introduction=column.key in own_intro_keys,
            project_id=ids[(post.post_id, column.key)],
        )
        project_dir = project_directory / files.project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        for stem, document in files.files.items():
            validate_and_write(_compact(document), stem, project_dir, keep_blank_text=True)
        prune_stale_files(project_dir, set(files.files))
        written_projects.append(files.project_id)

    # A language the post no longer has (or may no longer import), or a name its retitling
    # changed, leaves no project behind.
    # A name another post is given this run is that post's project now, whatever was there.
    given = set(ids.values())
    for stale in existing.get(post.post_id, []):
        if stale.is_dir() and stale.name not in given:
            shutil.rmtree(stale)
            logger.info("%s: removed %s, which it no longer makes", post.post_id, stale.name)

    for pid in written_projects:
        problems = validate_project_urn_references(pid, project_directory=project_directory, check_urns=False)
        problems += validate_project_contributor_references(
            pid, project_directory=project_directory, registry_directory=registry_directory
        )
        if problems:
            raise RuntimeError(f"{pid}: {problems}")
    return written_projects


def register_urns(plans: list[PostPlan], context: Context, registry_directory: Path) -> int:
    """Append the registry records the converted posts' new URNs need. Returns how many."""
    existing: set[str] = set()
    for path in registry_directory.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.add(json.loads(line)["urn"])
    added = 0
    for plan in plans:
        urns = context.post_urns[plan.post.post_id]
        titles: dict[str, str] = {}
        for lang, title in titles_by_language(plan.post):
            titles.setdefault(lang, title)
        keys = {column.key for column, _ in plan.columns}
        views = table_views(plan.post)
        lines = []
        essay_urn = None
        if plan.post.essay:
            # The essay, and the passages it quotes as its part.
            lines += registry_lines(urns, [], label_en=titles.get("en", ""), label_he=titles.get("he", ""))
            essay_urn, urns = urns.urn, urns.quoted()
            titles = {"en": f"{titles.get('en', '')} (quoted passages)".strip()}
        elif len(views) > 1:
            # The post as a whole, whose tables are its parts.
            lines += registry_lines(urns, [], label_en=titles.get("en", ""), label_he=titles.get("he", ""))
        for number, view in enumerate(views, 1):
            imported = [i for i, column in enumerate(view.columns) if column.key in keys]
            rows_with_text = [
                n for row_index, n in row_numbers(view).items()
                if any(not view.rows[row_index].cells[i].is_empty for i in imported)
            ]
            table_urns = urns.table(number, len(views))
            label = titles.get("en", "") if len(views) == 1 else f"{titles.get('en', '')} / {number}".strip(" /")
            lines += registry_lines(
                table_urns, rows_with_text, label_en=label,
                label_he=titles.get("he", "") if len(views) == 1 else "",
                parent=essay_urn or (urns.urn if table_urns is not urns and table_urns.urn.startswith(urns.urn + "/") else None),
            )
        for line in lines:
            if line["urn"] in existing:
                continue
            path = registry_directory / f"{str(line['urn']).split(':')[3]}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
            existing.add(str(line["urn"]))
            added += 1
    return added


def select_posts(data_dir: Path, *, posts: list[int] | None, categories: list[int] | None) -> list[int]:
    manifest = load_manifest(data_dir)
    available = sorted(int(k) for k in manifest.get("posts", {}))
    if posts:
        return [p for p in posts if p in available]
    if categories:
        category_list = json.loads((data_dir / "categories.json").read_text(encoding="utf-8"))
        wanted = posts_in_categories(category_list, descendant_categories(category_list, set(categories)))
        return [p for p in available if p in wanted]
    return available


@dataclass
class ConvertRun:
    """What a conversion run did with each post it was asked about."""

    plans: list[PostPlan]
    converted: list[int] = field(default_factory=list)
    #: Post ID -> the error that stopped it.
    failed: dict[int, str] = field(default_factory=dict)
    #: Post ID -> why it was not converted.
    skipped: dict[int, str] = field(default_factory=dict)
    #: Post ID -> the projects removed because the post is now rejected.
    removed: dict[int, list[str]] = field(default_factory=dict)
    #: Post ID -> projects converted earlier and left as they were.
    left: dict[int, list[str]] = field(default_factory=dict)


def convert_posts(
    data_dir: Path,
    project_directory: Path,
    *,
    posts: list[int] | None = None,
    categories: list[int] | None = None,
    register: bool = False,
    dry_run: bool = False,
    candidates_path: Path | None = None,
    context: Context | None = None,
    registry_directory: Path = REGISTRY_DIRECTORY,
) -> ConvertRun:
    """Convert the standard posts among those selected (default: all), and report the rest."""
    context = context or load_context(data_dir)
    # Every post is planned, so that names are given against the whole export. One that cannot
    # be read is reported, and stops only a run that asked for it.
    every_plan: dict[int, PostPlan] = {}
    selected = select_posts(data_dir, posts=posts, categories=categories)
    for post_id in select_posts(data_dir, posts=None, categories=None):
        try:
            every_plan[post_id] = plan_post(load_post(data_dir / "posts" / f"{post_id}.json"), context)
        except Exception:
            if post_id in selected:
                raise
            logger.warning("%s: could not be read; its names are given without it", post_id)
    plans = [every_plan[post_id] for post_id in selected]
    run = ConvertRun(plans)
    existing = imported_projects(project_directory)
    ids = project_ids(list(every_plan.values()), project_directory, existing)

    if candidates_path is not None:
        lines = sorted({line for plan in plans for line in plan.candidates})
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        print(f"{len(lines)} contributor candidate(s) written to {candidates_path}")

    for plan in plans:
        post_id = plan.post.post_id
        if not plan.standard:
            run.skipped[post_id] = "; ".join(plan.reasons)
            earlier = sorted(existing.get(post_id, []))
            if not earlier:
                continue
            if is_rejected(plan):
                # A decision not to import the post: what an earlier run wrote must go.
                if not dry_run:
                    for path in earlier:
                        shutil.rmtree(path)
                run.removed[post_id] = [p.name for p in earlier]
            else:
                run.left[post_id] = [p.name for p in earlier]
            continue
        if any((post_id, column.key) not in ids for column, _ in plan.columns):
            run.skipped[post_id] = "a project of it could not be named"
            continue
        if not dry_run:
            try:
                convert_post(plan, context, project_directory, ids=ids, existing=existing,
                             registry_directory=registry_directory)
            except Exception as error:  # one post's failure must not stop the others
                run.failed[post_id] = str(error)
                continue
            if register:
                register_urns([plan], context, registry_directory)
        run.converted.append(post_id)
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--post", type=int, action="append", help="convert this post; repeatable")
    parser.add_argument("--category", type=int, action="append", help="convert posts in this category and below")
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument("--register", action="store_true",
                        help="append the registry records new post URNs need")
    parser.add_argument("--emit-contributor-candidates", action="store_true",
                        help=f"write lines for unregistered contributors to {CANDIDATES_PATH}")
    parser.add_argument("--dry-run", action="store_true", help="report what would be converted; write nothing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    run = convert_posts(
        opensiddur_org_data_directory(args.sourcetexts_root), args.project_directory,
        posts=args.post, categories=args.category, register=args.register, dry_run=args.dry_run,
        candidates_path=CANDIDATES_PATH if args.emit_contributor_candidates else None,
    )
    print_run(run, dry_run=args.dry_run)
    return 1 if run.failed else 0


def print_run(run: ConvertRun, *, dry_run: bool = False) -> None:
    for post_id, error in run.failed.items():
        print(f"{post_id}: FAILED: {error}")
    for plan in run.plans:
        if plan.post.post_id in run.converted:
            for lang, why in sorted(plan.skipped_columns.items()):
                print(f"{plan.post.post_id}: {lang} not imported ({why})")
    for post_id, why in run.skipped.items():
        print(f"{post_id}: skipped: {why}")
        if post_id in run.removed:
            print(f"{post_id}: removed {', '.join(run.removed[post_id])} (rejected)")
        if post_id in run.left:
            print(f"{post_id}: WARNING: {', '.join(run.left[post_id])} "
                  "were converted earlier and are left as they were")
    print(f"{'Would convert' if dry_run else 'Converted'} {len(run.converted)} of {len(run.plans)} post(s).")
    if run.failed:
        print(f"{len(run.failed)} post(s) failed: {', '.join(map(str, run.failed))}")


if __name__ == "__main__":
    sys.exit(main())
