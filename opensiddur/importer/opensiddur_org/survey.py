"""Triage the downloaded opensiddur.org posts: what can be converted, and what is in the way.

Writes ``output/opensiddur_org_triage.json`` (one record per post) and
``output/opensiddur_org_triage.md`` (counts by reason, category, language set and licence,
the categories best suited to a pilot, and the licences and posts that need a decision).
Neither is committed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from opensiddur.common.constants import OUTPUT_DIRECTORY, PROJECT_DIRECTORY
from opensiddur.importer.opensiddur_org.convert import load_context, plan_post, select_posts
from opensiddur.importer.opensiddur_org.match import load_incipit_index, propose, registry_labels
from opensiddur.importer.opensiddur_org.parse_post import load_post
from opensiddur.importer.opensiddur_org.scope import project_columns
from opensiddur.importer.util.pages import opensiddur_org_data_directory

TRIAGE_JSON = OUTPUT_DIRECTORY / "opensiddur_org_triage.json"
TRIAGE_MD = OUTPUT_DIRECTORY / "opensiddur_org_triage.md"


def category_path(permalink: str, depth: int = 3) -> str:
    parts = [p for p in urlparse(permalink).path.split("/") if p]
    return "/".join(parts[: min(depth, max(len(parts) - 1, 1))])


def _reason_key(reason: str) -> str:
    """A reason without its particulars, for counting."""
    if reason.startswith("column "):
        return "column: " + reason.split(": ", 1)[-1].split(" says")[0].split(",")[0]
    return reason.split(":")[0]


def survey(data_dir: Path, *, posts: list[int] | None, categories: list[int] | None,
           project_directory: Path = PROJECT_DIRECTORY) -> list[dict[str, Any]]:
    context = load_context(data_dir)
    index = load_incipit_index(OUTPUT_DIRECTORY / "opensiddur_org_incipits.json", project_directory)
    labels = registry_labels()
    records = []
    for post_id in select_posts(data_dir, posts=posts, categories=categories):
        post = load_post(data_dir / "posts" / f"{post_id}.json")
        plan = plan_post(post, context)
        reasons = [r for r in plan.reasons if r != "no URN decision"]
        urns = context.post_urns.get(post_id)
        proposal = None if urns else propose(post, index, labels)
        records.append({
            "post_id": post_id,
            "title": post.title,
            "permalink": post.permalink,
            "category": category_path(post.permalink),
            "languages": [column.key for column in project_columns(post)],
            "licence": post.licence_url,
            "columns": {column.key: "allow" for column, _ in plan.columns} | {
                lang: why for lang, why in plan.skipped_columns.items()},
            "class": "standard" if not reasons else "irregular",
            "reasons": reasons,
            "urn": urns.urn if urns else None,
            "urn_proposal": json.loads(proposal.to_json()) if proposal else None,
            "contributor_candidates": plan.candidates,
        })
    return records


def report(records: list[dict[str, Any]]) -> str:
    out: list[str] = ["# opensiddur.org triage", ""]
    total = len(records)
    standard = sum(r["class"] == "standard" for r in records)
    out.append(f"{total} in-scope posts: {standard} standard, {total - standard} irregular.")
    out.append("")

    def table(title: str, counter: Counter, limit: int = 40) -> None:
        out.extend([f"## {title}", "", "| count | value |", "|---:|---|"])
        for value, count in counter.most_common(limit):
            out.append(f"| {count} | {value} |")
        out.append("")

    table("Irregularities", Counter(_reason_key(x) for r in records for x in r["reasons"]))
    table("Language sets", Counter(" + ".join(r["languages"]) or "(none)" for r in records))
    table("Licences", Counter(r["licence"] or "(none)" for r in records))

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_category[record["category"]].append(record)
    out.extend(["## Categories", "",
                "| category | posts | standard | he + en | standard he + en | URN proposals |",
                "|---|---:|---:|---:|---:|---:|"])
    for category, rows in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        he_en = [r for r in rows if sorted(r["languages"]) == ["en", "he"]]
        out.append(
            f"| {category} | {len(rows)} | {sum(r['class'] == 'standard' for r in rows)} | {len(he_en)} | "
            f"{sum(r['class'] == 'standard' for r in he_en)} | {sum(bool(r['urn_proposal']) for r in rows)} |"
        )
    out.append("")

    undecided = [r for r in records if any(not v == "allow" and v.startswith("undecided") for v in r["columns"].values())]
    out.extend(["## Licences awaiting a decision", ""])
    for record in undecided:
        why = "; ".join(f"{lang}: {v}" for lang, v in record["columns"].items() if v != "allow")
        out.append(f"- [{record['post_id']}]({record['permalink']}) {record['title']} — {why}")
    out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--post", type=int, action="append")
    parser.add_argument("--category", type=int, action="append")
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY)
    args = parser.parse_args(argv)

    records = survey(opensiddur_org_data_directory(args.sourcetexts_root),
                     posts=args.post, categories=args.category, project_directory=args.project_directory)
    TRIAGE_JSON.parent.mkdir(parents=True, exist_ok=True)
    TRIAGE_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    TRIAGE_MD.write_text(report(records), encoding="utf-8")
    print(f"Wrote {TRIAGE_MD} ({len(records)} posts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
