"""Convert a downloaded Sefaria work into its Hebrew and English JLPTEI projects.

The stages, for each work in ``works.yaml``:

1. Read the download (``source.py``) and the work's structure table
   (``structure/<work>.yaml``): every node of Sefaria's schema must be placed.
2. Align each leaf's Hebrew and English segments (``align.py``).
3. Divide each leaf into its texts and the rubrics between them (``blocks.py``).
4. Decide each text's URN, reusing the collection's (``match.py``), recorded at once in
   ``specs/sefaria/metsudah_urns.jsonl``.
5. Write both projects (``tei_builder.py``), validating every file before it is written, and
   remove files an earlier run wrote that this one did not.
6. With ``--register``, add the new URNs (texts, and ``siddur:`` places) to
   ``specs/urn_registry/``.

``output/sefaria_<work>_report.md`` lists what needs a person's eye: leaves aligned by the
trailing rule, URNs decided this run, and decisions that lapsed. See ``specs/SEFARIA_IMPORT.md``.

Run::

    uv run python -m opensiddur.importer.sefaria.convert [--work KEY ...] [--register]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from opensiddur.common.constants import OUTPUT_DIRECTORY, PROJECT_DIRECTORY
from opensiddur.common.urn_registry import REGISTRY_DIRECTORY
from opensiddur.common.validate_names import Spellings
from opensiddur.importer.sefaria.align import Alignment, Pair, align_work, load_decisions
from opensiddur.importer.sefaria.blocks import Item, TextBlock, divide, is_phrase
from opensiddur.importer.sefaria.download import load_manifest
from opensiddur.importer.sefaria.conditions import Conditions, load_conditions
from opensiddur.importer.sefaria.equivalents import apply_joins, load_equivalents
from opensiddur.importer.sefaria.markup import HebrewKind, plain_text
from opensiddur.importer.sefaria.match import (
    URNS_PATH,
    Decisions,
    TextRecord,
    decide_work,
    excluded_projects,
    load_records,
    registry_urns,
    save_records,
    scripture_verses,
    verse_length,
)
from opensiddur.importer.sefaria.phrases import recorded_phrases, text_path
from opensiddur.importer.sefaria.source import PATH_SEPARATOR, WorkSource, load_work_source
from opensiddur.importer.sefaria.tei_builder import (
    Notes,
    SourceInfo,
    VariantPrinting,
    document,
    document_header,
    file_stem,
    index_body,
    index_header,
    leaf_body,
    node_body,
    siddur_urn,
    text_body,
    variant_urn,
)
from opensiddur.importer.sefaria.works import LANGUAGES, Work, load_works, select_works
from opensiddur.importer.util.incipit import TEXT_PREFIX, IncipitIndex, load_incipit_index
from opensiddur.importer.util.tei_project import prune_stale_files, validate_and_write

logger = logging.getLogger(__name__)

INCIPIT_CACHE = OUTPUT_DIRECTORY / "sefaria_incipits.json"


class ConvertError(RuntimeError):
    pass


def load_structure(work: Work, source: WorkSource, path: Path | None = None) -> dict[str, str | None]:
    """The work's structure table, checked against its schema: every node and leaf placed,
    nothing placed that the schema lacks, a leaf with text never left unplaced."""
    path = path or work.structure_file()
    table = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    paths = [node.path for node in source.nodes] + [leaf.path for leaf in source.leaves]
    problems = [f"{p}: not placed in {path.name}" for p in paths if p not in table]
    problems += [f"{p}: placed in {path.name} but not in the schema" for p in table if p not in paths]
    for leaf in source.leaves:
        if leaf.path in table and table[leaf.path] is None and any(s.strip() for s in leaf.he + leaf.en):
            problems.append(f"{leaf.path}: has text but no place in {path.name}")
    places = [v for v in table.values() if v]
    problems += [f"{p}: placed twice" for p in sorted({p for p in places if places.count(p) > 1})]
    if problems:
        raise ConvertError("\n".join(problems))
    return {k: (str(v) if v else None) for k, v in table.items()}


@dataclass
class WorkPlan:
    """Everything decided about a work, before any file is written."""

    work: Work
    source: WorkSource
    structure: dict[str, str | None]
    alignments: list[Alignment]
    items: dict[str, list[Item]]
    decisions: Decisions
    #: the verses of scripture each text quotes: (leaf, block) -> phrase position -> verse URN
    verses: dict[tuple[str, int], dict[int, str]] = field(default_factory=dict)
    #: the length in words of each verse whose length the index knows
    verse_lengths: dict[str, int] = field(default_factory=dict)
    #: the conditions the book prints (conditions.yaml)
    conditions: Conditions = field(default_factory=Conditions)

    def record(self, leaf_path: str, block: TextBlock) -> TextRecord:
        return self.decisions.records[(self.work.key, leaf_path, block.first_index)]


def plan_work(work: Work, source: WorkSource, *, index: IncipitIndex,
              records: dict[tuple[str, str, int], TextRecord], taken: set[str],
              phrases: dict[str, dict[int, str]] | None = None,
              structure_path: Path | None = None,
              decisions_path: Path | None = None,
              spellings: Spellings | None = None,
              own_phrases: dict[str, dict[int, str]] | None = None,
              equivalents_path: Path | None = None,
              registered: set[str] | None = None,
              conditions_path: Path | None = None) -> WorkPlan:
    structure = load_structure(work, source, structure_path)
    alignments = align_work(work.key, source.leaves,
                            load_decisions(decisions_path) if decisions_path else load_decisions())
    equivalents = load_equivalents(equivalents_path) if equivalents_path else load_equivalents()
    items = {a.leaf.path: apply_joins(a.leaf.path, divide(a.pairs), equivalents)
             for a in alignments if structure.get(a.leaf.path)}
    decisions = decide_work(work.key, list(items.items()), index, records, taken,
                            recorded_phrases=phrases, spellings=spellings,
                            places={path: place for path, place in structure.items() if place},
                            own_phrases=own_phrases, equivalents=equivalents, registered=registered)
    # The verses each text the project writes quotes. A project carries a URN once, so a verse
    # quoted by two texts is marked in the first.
    verses: dict[tuple[str, int], dict[int, str]] = {}
    marked: set[str] = set()
    for leaf, leaf_items in items.items():
        for block in leaf_items:
            if not isinstance(block, TextBlock):
                continue
            record = decisions.records[(work.key, leaf, block.first_index)]
            if record.kind not in ("existing", "new"):
                continue
            found: dict[int, str] = {}
            for position, urn in sorted(scripture_verses(block, index).items()):
                if urn == record.urn or record.urn.startswith(urn + "/") or urn.startswith(record.urn + "/"):
                    continue  # the text is that verse (or chapter): its URN is already on the division
                if urn not in marked:  # a verse repeated, even within one text, is marked once
                    marked.add(urn)
                    found[position] = urn
            if found:
                verses[(leaf, block.first_index)] = found
    lengths = {urn: n for found in verses.values() for urn in found.values()
               if (n := verse_length(urn, index)) is not None}
    return WorkPlan(work, source, structure, alignments, items, decisions, verses, lengths,
                    load_conditions(conditions_path) if conditions_path else load_conditions())


@dataclass
class ProjectFiles:
    files: dict[str, str] = field(default_factory=dict)

    def add(self, stem: str, xml: str) -> None:
        if stem in self.files:
            raise ConvertError(f"two files would be named {stem}.xml")
        self.files[stem] = xml


def _preorder(source: WorkSource) -> list[tuple[str, ...]]:
    """Every node and leaf's keys, in the order the schema lists them."""
    order: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for leaf in source.leaves:
        for depth in range(1, len(leaf.keys) + 1):
            prefix = leaf.keys[:depth]
            if prefix not in seen:
                seen.add(prefix)
                order.append(prefix)
    return order


def children_by_parent(plan: WorkPlan) -> dict[tuple[str, ...], list[str]]:
    """Each node's placed children, as ``siddur:`` URNs in schema order; the root's under ()."""
    children: dict[tuple[str, ...], list[str]] = {}
    for keys in _preorder(plan.source):
        place = plan.structure.get(PATH_SEPARATOR.join(keys))
        if place:
            children.setdefault(keys[:-1], []).append(siddur_urn(place))
    return children


def _norm(text: str) -> str:
    return " ".join(text.split())


def leading_condition(plan: WorkPlan, item: TextBlock) -> Pair | None:
    """The last condition rubric a text block opens with, before its first phrase."""
    found = None
    for pair in item.pairs:
        if is_phrase(pair):
            break
        if pair.he_kind is HebrewKind.EMPTY and plan.conditions.for_rubric(plain_text(pair.en)):
            found = pair
    return found


def first_printing_rubrics(plan: WorkPlan) -> dict[str, str]:
    """For each text written from its first printing, the condition rubric it opens with."""
    found: dict[str, str] = {}
    for leaf_path, items in plan.items.items():
        for item in items:
            if isinstance(item, TextBlock):
                record = plan.record(leaf_path, item)
                if record.kind not in ("repeat", "variant") and (pair := leading_condition(plan, item)):
                    found[record.urn] = _norm(plain_text(pair.en))
    return found


def text_printings(plan: WorkPlan) -> dict[str, list[VariantPrinting]]:
    """Each text's variants -- its later printings with words of their own -- in book order."""
    found: dict[str, list[VariantPrinting]] = {}
    for leaf_path, items in plan.items.items():
        for item in items:
            if isinstance(item, TextBlock):
                record = plan.record(leaf_path, item)
                if record.kind == "variant" and record.variant:
                    found.setdefault(record.urn, []).append(VariantPrinting(
                        record.variant, item, record.phrases or [],
                        {int(n): u for n, u in (record.parts or {}).items()}))
    return found


def build_project(plan: WorkPlan, lang: str, info: SourceInfo) -> ProjectFiles:
    work = plan.work
    out = ProjectFiles()
    children = children_by_parent(plan)
    titles = {n.path: n.titles[-1] for n in plan.source.nodes}
    titles.update({leaf.path: leaf.titles[-1] for leaf in plan.source.leaves})
    gates = {siddur_urn(plan.structure[leaf.path]): gate for leaf in plan.source.leaves
             if plan.structure.get(leaf.path) and (gate := plan.conditions.leaf_gate(work.key, leaf.path))}
    for node in plan.source.nodes:
        place = plan.structure.get(node.path)
        if not place:
            continue
        urn = siddur_urn(place)
        body = node_body(urn, titles[node.path], children.get(node.keys, []), lang, gates)
        title = titles[node.path][1 if lang == "he" else 0]
        out.add(file_stem(urn), document(document_header(work, lang, title), body, lang))
    printings = text_printings(plan)
    opened = first_printing_rubrics(plan)
    for leaf in plan.source.leaves:
        place = plan.structure.get(leaf.path)
        if not place:
            continue
        items = plan.items[leaf.path]
        text_urns: dict[int, str] = {}
        declarations: dict[int, list[tuple[str, bool]]] = {}
        leading: dict[int, Pair] = {}
        for item in items:
            if not isinstance(item, TextBlock):
                continue
            record = plan.record(leaf.path, item)
            text_urns[id(item)] = record.urn
            variants = printings.get(record.urn, ())
            if variants:
                # Which of the text's variants this place prints, and which it does not.
                declarations[id(item)] = [(variant_urn(record.urn, v.name), v.name == record.variant)
                                          for v in variants]
            if record.kind in ("repeat", "variant"):
                # Its condition rubric, unless the first printing's file opens with it too.
                pair = leading_condition(plan, item)
                if pair is not None and _norm(plain_text(pair.en)) != opened.get(record.urn):
                    leading[id(item)] = pair
                continue
            numbers = record.phrases or list(range(1, len(item.phrases) + 1))
            notes = Notes(prefix="note")
            body = text_body(record.urn, item, numbers, lang, notes, tuple(variants),
                             plan.verses.get((leaf.path, item.first_index)), plan.verse_lengths,
                             plan.conditions)
            english = next((plain_text(p.en) for p in item.phrases if plain_text(p.en)), "")
            title = record.incipit if lang == "he" else f"{leaf.title_en}: {english[:60]}".rstrip(": ")
            out.add(file_stem(record.urn), document(document_header(work, lang, title), body, lang, notes))
        urn = siddur_urn(place)
        notes = Notes(prefix="note")
        body = leaf_body(urn, titles[leaf.path], items, text_urns, lang, notes, declarations, plan.conditions,
                         leading)
        title = titles[leaf.path][1 if lang == "he" else 0]
        out.add(file_stem(urn), document(document_header(work, lang, title), body, lang, notes))
    out.add("index", document(index_header(work, lang, info), index_body(work, children.get((), []), lang, gates), lang))
    return out


def source_info(work: Work, directory: Path) -> SourceInfo:
    manifest = load_manifest(directory)
    if not manifest:
        raise ConvertError(f"{directory}: no manifest; run the download first")
    files = manifest["files"]
    for lang in LANGUAGES:
        licence = files[f"{lang}.json"].get("license")
        if licence != "CC-BY":
            # works.yaml records CC BY 3.0 for Sefaria's "CC-BY"; anything else needs a decision.
            raise ConvertError(
                f"{work.key}: the {lang} version is licensed {licence!r}, not CC-BY; decide whether it "
                "can still be imported, and record the licence in works.yaml, before converting")
    return SourceInfo(
        last_export=manifest["last_export"],
        version_url={lang: f"https://www.sefaria.org/{work.schema_file_title}" for lang in LANGUAGES},
        md5={lang: files[f"{lang}.json"]["md5Hash"] for lang in LANGUAGES},
    )


def write_project(files: ProjectFiles, project_dir: Path) -> list[Path]:
    project_dir.mkdir(parents=True, exist_ok=True)
    for stem, xml in files.files.items():
        validate_and_write(xml, stem, project_dir)
    return prune_stale_files(project_dir, set(files.files))


def check_phrase_paths(records: dict[tuple[str, str, int], TextRecord]) -> None:
    """A ``metsudah:`` path names one text: a ``prayer:`` and a ``poem:`` with the same path
    would share their phrases' URNs."""
    by_path: dict[str, set[str]] = {}
    for record in records.values():
        by_path.setdefault(text_path(record.urn), set()).add(record.urn)
    clashes = {p: sorted(u) for p, u in by_path.items() if len(u) > 1}
    if clashes:
        raise ConvertError("texts that would share metsudah: phrase URNs: " + "; ".join(
            f"{p}: {', '.join(u)}" for p, u in sorted(clashes.items())))


def registry_lines(plan: WorkPlan, existing: set[str]) -> list[dict[str, object]]:
    """Registry records for the new URNs a plan uses: minted texts and ``siddur:`` places
    (with any parent place not yet registered)."""
    lines: list[dict[str, object]] = []
    seen = set(existing)
    titles = {n.path: n.titles[-1] for n in plan.source.nodes}
    titles.update({leaf.path: leaf.titles[-1] for leaf in plan.source.leaves})

    def add(line: dict[str, object]) -> None:
        if line["urn"] not in seen:
            seen.add(str(line["urn"]))
            lines.append(line)

    for path, place in plan.structure.items():
        if not place:
            continue
        parts = place.split("/")
        for depth in range(1, len(parts)):
            add({"urn": siddur_urn("/".join(parts[:depth])), "status": "canonical",
                 **({"parent": siddur_urn("/".join(parts[:depth - 1]))} if depth > 1 else {}),
                 "label_en": " / ".join(parts[:depth]).replace("_", " ")})
        en, he = titles[path]
        line: dict[str, object] = {"urn": siddur_urn(place), "status": "canonical"}
        if len(parts) > 1:
            line["parent"] = siddur_urn("/".join(parts[:-1]))
        line["label_en"] = en
        if he:
            line["label_he"] = he
        add(line)
    for record in plan.decisions.records.values():
        if record.work != plan.work.key or record.kind != "new":
            continue
        add({"urn": record.urn, "status": "canonical", "label_he": record.incipit,
             "label_en": record.urn.rsplit(":", 1)[-1].replace("_", " ")})
    return lines


def register(lines: list[dict[str, object]], registry_directory: Path) -> int:
    for line in lines:
        namespace = str(line["urn"])[len(TEXT_PREFIX):].split(":", 1)[0]
        with (registry_directory / f"{namespace}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    return len(lines)


def report(plan: WorkPlan, written: dict[str, int], pruned: dict[str, list[Path]]) -> str:
    lines = [f"# Sefaria import: {plan.work.key}", ""]
    for lang, count in written.items():
        lines.append(f"- {plan.work.projects[lang]}: {count} files written, "
                     f"{len(pruned[lang])} stale removed")
    trailing = [a for a in plan.alignments if a.policy == "trailing"]
    lines += ["", f"## Leaves aligned by the trailing rule ({len(trailing)})", ""]
    for a in trailing:
        lines.append(f"- {a.leaf.path}: {len(a.leaf.he)} Hebrew, {len(a.leaf.en)} English")
    lines += ["", f"## URNs decided this run ({len(plan.decisions.decided)})", ""]
    for r in plan.decisions.decided:
        lines.append(f"- `{r.kind}` {r.leaf} @{r.block}: `{r.urn}` — {r.incipit} — {'; '.join(r.evidence)}")
    lines += ["", f"## Decisions that lapsed ({len(plan.decisions.lapsed)})", ""]
    for r in plan.decisions.lapsed:
        lines.append(f"- {r.leaf} @{r.block}: was `{r.urn}`")
    matched, unmatched = condition_rubrics(plan)
    lines += ["", f"## Condition rubrics ({sum(matched.values())} printed, {len(matched)} kinds)", ""]
    lines += [f"- {n}× {text}" for text, n in sorted(matched.items())]
    lines += ["", f"## Rubrics that read like conditions, not in conditions.yaml ({len(unmatched)})", "",
              "Each stays an instruction. Add the ones that say when a passage is said to conditions.yaml.", ""]
    lines += [f"- {n}× {text}" for text, n in sorted(unmatched.items())]
    return "\n".join(lines) + "\n"


#: How a rubric that says when the passage after it is said begins.
CONDITION_LIKE = re.compile(r"^\(?\*?(On |During |From |When |If there |Between |In a leap |After |A woman |"
                            r"A man |Tachanun is |The following (\w+ )*(is|are) (said|recited|added|omitted) "
                            r"(on|during|only|in|when))")


def condition_rubrics(plan: WorkPlan) -> tuple[dict[str, int], dict[str, int]]:
    """The book's English rubrics the conditions table matches, and those that read like a
    condition but it does not: text -> how often printed."""
    matched: dict[str, int] = {}
    unmatched: dict[str, int] = {}
    for alignment in plan.alignments:
        for pair in alignment.pairs:
            if pair.he_kind is not HebrewKind.EMPTY:
                continue
            text = " ".join(plain_text(pair.en).split())
            if not text:
                continue
            if plan.conditions.for_rubric(text) is not None:
                matched[text[:120]] = matched.get(text[:120], 0) + 1
            elif CONDITION_LIKE.match(text) and not plan.conditions.is_directive(text):
                unmatched[text[:120]] = unmatched.get(text[:120], 0) + 1
    return matched, unmatched


def convert_work(work: Work, *, sourcetexts_root: Path | None = None,
                 project_directory: Path = PROJECT_DIRECTORY,
                 registry_directory: Path = REGISTRY_DIRECTORY,
                 urns_path: Path = URNS_PATH, do_register: bool = False,
                 index: IncipitIndex | None = None,
                 output_directory: Path = OUTPUT_DIRECTORY,
                 structure_path: Path | None = None,
                 decisions_path: Path | None = None,
                 spellings: Spellings | None = None,
                 works: dict[str, Work] | None = None,
                 equivalents_path: Path | None = None,
                 conditions_path: Path | None = None) -> WorkPlan:
    directory = work.data_directory(sourcetexts_root)
    source = load_work_source(directory)
    info = source_info(work, directory)
    records = load_records(urns_path)
    taken = registry_urns(registry_directory) | {r.urn for r in records.values()}
    own = {project_directory / work.projects[lang] for lang in LANGUAGES}
    excluded = excluded_projects(project_directory)
    if index is None:
        index = load_incipit_index(INCIPIT_CACHE, project_directory, excluded | own)
    # The Hebrew projects of the other Sefaria works, whose phrases this one may share.
    hebrew_projects = {w.projects["he"] for w in (load_works() if works is None else works).values()
                       if w.key != work.key}
    other_volumes = [d for d in excluded if d.name in hebrew_projects]
    plan = plan_work(work, source, index=index, records=records, taken=taken,
                     phrases=recorded_phrases(other_volumes), structure_path=structure_path,
                     decisions_path=decisions_path, spellings=spellings,
                     equivalents_path=equivalents_path, registered=registry_urns(registry_directory),
                     conditions_path=conditions_path,
                     own_phrases=recorded_phrases([project_directory / work.projects["he"]]
                                                  if (project_directory / work.projects["he"]).exists() else []))
    check_phrase_paths({k: r for k, r in plan.decisions.records.items()
                        if r.kind in ("existing", "new") and r.work == work.key})
    written: dict[str, int] = {}
    pruned: dict[str, list[Path]] = {}
    for lang in LANGUAGES:
        files = build_project(plan, lang, info)
        pruned[lang] = write_project(files, project_directory / work.projects[lang])
        written[lang] = len(files.files)
    save_records(plan.decisions.records, urns_path)
    lines = registry_lines(plan, registry_urns(registry_directory))
    if do_register:
        register(lines, registry_directory)
    elif lines:
        logger.warning("%d URN(s) are not registered; rerun with --register", len(lines))
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / f"sefaria_{work.key}_report.md").write_text(
        report(plan, written, pruned), encoding="utf-8")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", action="append", help="a key from works.yaml; repeatable. Default: all")
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument("--project-directory", type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument("--register", action="store_true", help="add new URNs to specs/urn_registry/")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for work in select_works(args.work):
        plan = convert_work(work, sourcetexts_root=args.sourcetexts_root,
                            project_directory=args.project_directory, do_register=args.register)
        kinds = {k: sum(1 for r in plan.decisions.decided if r.kind == k) for k in ("existing", "new", "repeat", "variant")}
        print(f"{work.key}: {len(plan.decisions.decided)} text(s) decided this run {kinds}; "
              f"{len(plan.decisions.lapsed)} lapsed; report in "
              f"{OUTPUT_DIRECTORY / f'sefaria_{work.key}_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
