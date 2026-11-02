"""The monthly update against a synthetic export: a git repository made in a temporary
directory, with the URN matching and conversion it hands posts to mocked."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from opensiddur.importer.opensiddur_org.convert import ConvertRun
from opensiddur.importer.opensiddur_org.download import (
    CATEGORIES_PATH,
    CONTRIBUTORS_PATH,
    DownloadResult,
    Upstream,
)
from opensiddur.importer.opensiddur_org.licences import LicenceDecisions
from opensiddur.importer.opensiddur_org.post_decisions import NO_DECISIONS, PostDecisions
from opensiddur.importer.opensiddur_org.update import (
    CHANGED,
    DELETED,
    LEFT_SCOPE,
    NEW,
    OVERRIDE_STALE,
    Change,
    ReferenceIndex,
    Removal,
    UpdateResult,
    classify,
    mark_stale_overrides,
    remove_projects,
    report,
    update,
)
from opensiddur.tests.importer.opensiddur_org.support import (
    FIXTURES,
    HEBREW_EN_ROWS,
    make_post,
    table,
)
from opensiddur.tests.importer.opensiddur_org.test_download import git

MODULE = "opensiddur.importer.opensiddur_org.update"


def imported_index(post_id: int, body: str = "") -> str:
    return (f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>'
            f'<bibl xml:id="project_source_bibl"><idno type="opensiddur.org">{post_id}</idno></bibl>'
            f'</teiHeader><text><body>{body}</body></text></TEI>')


def write_project(directory: Path, name: str, post_id: int | None, body: str) -> Path:
    project = directory / name
    project.mkdir(parents=True)
    (project / "index.xml").write_text(imported_index(post_id) if post_id else "<TEI/>", encoding="utf-8")
    (project / "text.xml").write_text(f"<TEI><text><body>{body}</body></text></TEI>", encoding="utf-8")
    return project


class TestClassify(unittest.TestCase):
    @staticmethod
    def manifest(**posts: str) -> dict:
        return {"posts": {key.lstrip("p"): {"last_updated": updated} for key, updated in posts.items()}}

    def test_classes(self) -> None:
        baseline = self.manifest(p101="2026-09-01", p102="2026-09-01", p103="2026-09-01", p105="2026-09-01")
        current = self.manifest(p101="2026-10-01", p104="2026-10-01", p105="2026-09-01")
        changes = classify(baseline, current, {102: "no prayer text"}, exported={101, 102, 104, 105})
        self.assertEqual([(c.post_id, c.kind, c.reason) for c in changes], [
            (101, CHANGED, ""), (102, LEFT_SCOPE, "no prayer text"), (103, DELETED, ""), (104, NEW, "")])

    def test_a_post_moved_out_of_the_category_left_scope(self) -> None:
        (change,) = classify(self.manifest(p102="2026-09-01"), self.manifest(), {}, exported={102})
        self.assertEqual(change.kind, LEFT_SCOPE)
        self.assertIn("Prayers & Praxes", change.reason)

    def test_a_changed_post_with_a_decision_goes_back_for_review(self) -> None:
        changes = [Change(101, CHANGED), Change(102, NEW), Change(103, CHANGED)]
        mark_stale_overrides(changes, PostDecisions(colours={101: {"green": "amendment"}},
                                                     essays={102: "an essay"}))
        self.assertEqual([(c.kind, c.reason) for c in changes],
                         [(OVERRIDE_STALE, "colours"), (NEW, ""), (CHANGED, "")])


class TestPruning(unittest.TestCase):
    GONE = "urn:x-opensiddur:text:prayer:gone"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.projects = Path(self.tmp.name) / "project"
        self.projects.mkdir()
        self.gone = write_project(self.projects, "gone-en", 102,
                                  f'<div corresp="{self.GONE}"/><milestone corresp="{self.GONE}/1"/>')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def blocking(self) -> list[str]:
        return ReferenceIndex.build(self.projects).blocking({"gone-en"})

    def test_a_reference_to_what_only_it_holds_blocks_removal(self) -> None:
        write_project(self.projects, "book-en", None, f'<transclude target="{self.GONE}/2"/>')
        self.assertEqual(self.blocking(), [f"{self.GONE}/2"])

    def test_a_text_another_project_also_holds_does_not_block(self) -> None:
        write_project(self.projects, "book-en", None, f'<transclude target="{self.GONE}"/>')
        write_project(self.projects, "other-he", 103, f'<div corresp="{self.GONE}"/>')
        self.assertEqual(self.blocking(), [])

    def test_a_part_held_elsewhere_does_not_block(self) -> None:
        write_project(self.projects, "book-en", None, f'<transclude target="{self.GONE}/5"/>')
        write_project(self.projects, "other-he", 103, f'<milestone corresp="{self.GONE}/5"/>')
        self.assertEqual(self.blocking(), [])

    def test_a_reference_pinned_to_it_blocks_even_when_others_hold_the_text(self) -> None:
        write_project(self.projects, "book-en", None, f'<transclude target="{self.GONE}@gone-en"/>')
        write_project(self.projects, "other-he", 103, f'<div corresp="{self.GONE}"/>')
        self.assertEqual(self.blocking(), [self.GONE])

    def test_a_range_is_read_as_both_its_ends(self) -> None:
        write_project(self.projects, "book-en", None,
                      '<transclude target="urn:x-opensiddur:text:prayer:other/1-3"/>'
                      f'<transclude target="urn:x-opensiddur:text:prayer:x" targetEnd="{self.GONE}/1"/>')
        write_project(self.projects, "other-he", 103, '<div corresp="urn:x-opensiddur:text:prayer:other"/>'
                                                      '<div corresp="urn:x-opensiddur:text:prayer:x"/>')
        self.assertEqual(self.blocking(), [f"{self.GONE}/1"])

    def test_removal_only_with_prune(self) -> None:
        changes = [Change(102, DELETED)]
        (kept,) = remove_projects(changes, self.projects, prune=False)
        self.assertEqual((kept.pruned, kept.projects), (False, ["gone-en"]))
        self.assertTrue(self.gone.exists())
        (removed,) = remove_projects(changes, self.projects, prune=True)
        self.assertTrue(removed.pruned)
        self.assertFalse(self.gone.exists())

    def test_a_blocked_removal_keeps_the_projects(self) -> None:
        write_project(self.projects, "book-en", None, f'<transclude target="{self.GONE}"/>')
        (removal,) = remove_projects([Change(102, LEFT_SCOPE, "no prayer text")], self.projects, prune=True)
        self.assertEqual((removal.pruned, removal.blocked_by), (False, [self.GONE]))
        self.assertTrue(self.gone.exists())


class TestReport(unittest.TestCase):
    def test_sections(self) -> None:
        run = UpdateResult(
            DownloadResult("0123456789abcdef", written=[], removed=[], kept=0, out_of_scope={}),
            "2026-12-01",
            changes=[Change(101, CHANGED), Change(104, NEW), Change(105, OVERRIDE_STALE, "colours"),
                     Change(102, LEFT_SCOPE, "no prayer text"), Change(103, DELETED)],
            conversion=ConvertRun(plans=[], converted=[101], failed={}, skipped={104: "no URN decision"}),
            removals=[Removal(102, ["b-en"], pruned=True), Removal(103, ["c-en"], pruned=False)],
            rows_changed={101: ([2], [3])},
            lapsed_licences={105: "hold: until permission"},
            decided={104: "new urn:x-opensiddur:text:prayer:d"},
            titles={101: "A Song"},
        )
        text = report(run)
        self.assertIn("# opensiddur.org update: export of 2026-12-01", text)
        self.assertIn("Posts: 1 new, 1 changed, 1 override-stale, 1 left-scope, 1 deleted.", text)
        self.assertIn("- changed: 101 (A Song)", text)
        self.assertIn("- 105: changed since a decision about it (colours)", text)
        self.assertIn("- 104: not converted: no URN decision", text)
        self.assertIn("- 101 (A Song): rows changed from [2] to [3]", text)
        self.assertIn("- 102: left-scope: no prayer text; removed b-en", text)
        self.assertIn("- 103: deleted; kept c-en (remove with `--prune`)", text)
        self.assertIn("- 105: the licence decision about it lapsed (hold: until permission)", text)
        self.assertIn("- 104: new urn:x-opensiddur:text:prayer:d", text)

    def test_nothing_changed(self) -> None:
        run = UpdateResult(DownloadResult("0123456789abcdef", [], [], 3, {}, noop=True), "2026-12-01", changes=[])
        self.assertIn("Nothing changed since the last import.", report(run))


class TestUpdate(unittest.TestCase):
    """A month of changes: one post edited (a row added), one decided by hand and edited, one
    deleted, one that is no longer a prayer, and one new."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.export = root / "export"
        self.export.mkdir()
        git(self.export, "init", "-q", "-b", "master")
        for target, source in ((CATEGORIES_PATH, "categories.json"), (CONTRIBUTORS_PATH, "contributors_by_id.json")):
            path = self.export / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((FIXTURES / source).read_text(encoding="utf-8"), encoding="utf-8")
        for post_id, slug in ((101, "a-song"), (102, "b"), (103, "c"), (105, "e")):
            self.write_post(make_post(post_id, slug=slug))
        self.commit()
        self.clone = Upstream(root / "clone")
        self.clone.ensure(fetch=False, url=str(self.export))
        # sourcetexts, a git repository, holding the first month's import.
        self.sources = root / "sources"
        self.sources.mkdir()
        git(self.sources, "init", "-q", "-b", "master")
        self.data_dir = self.sources / "opensiddur_org"
        self.projects = root / "project"
        self.projects.mkdir()
        self.run_update()
        git(self.sources, "add", "-A")
        git(self.sources, "commit", "-q", "-m", "first month")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_post(self, post: dict) -> None:
        path = self.export / "posts" / f"{post['slug']}_({post['post_id']}).json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(post, ensure_ascii=False), encoding="utf-8")

    def commit(self) -> None:
        git(self.export, "add", "-A")
        git(self.export, "commit", "-q", "-m", "export")

    def run_update(self, decisions: PostDecisions = NO_DECISIONS, licences: LicenceDecisions | None = None):
        self.clone.ensure(fetch=True)
        with mock.patch(f"{MODULE}.match.main", return_value=0) as self.match, \
                mock.patch(f"{MODULE}.convert_posts", side_effect=lambda data_dir, projects, posts, **kw:
                           ConvertRun(plans=[], converted=list(posts))) as self.convert, \
                mock.patch("sys.stdout"):
            return update(upstream=self.clone, ref="origin/master", data_dir=self.data_dir,
                          project_directory=self.projects, decisions=decisions,
                          licence_decisions=licences or LicenceDecisions({}, {}),
                          post_urns_path=Path(self.tmp.name) / "post_urns.jsonl")

    def month_of_changes(self) -> None:
        three_rows = table(["Source (Hebrew)", "Translation (English)"], HEBREW_EN_ROWS + HEBREW_EN_ROWS[:1])
        self.write_post(make_post(101, slug="a-song", content=three_rows, last_updated="2026-11-15"))
        self.write_post(make_post(102, slug="b", content="<p>Thoughts.</p>", last_updated="2026-11-15"))
        (self.export / "posts" / "c_(103).json").unlink()
        self.write_post(make_post(104, slug="d"))
        self.write_post(make_post(105, slug="e", content=three_rows, last_updated="2026-11-15"))
        self.commit()

    def test_a_month_of_changes(self) -> None:
        self.month_of_changes()
        run = self.run_update(PostDecisions(colours={105: {"green": "amendment"}}))
        self.assertEqual([(c.post_id, c.kind) for c in run.changes], [
            (101, CHANGED), (102, LEFT_SCOPE), (103, DELETED), (104, NEW), (105, OVERRIDE_STALE)])
        # Rows are compared for a stale override too, for whoever reviews it.
        self.assertEqual(run.rows_changed, {101: ([2], [3]), 105: ([2], [3])})
        self.assertEqual(run.titles[103], "שִׁירָה | A Song")  # from the copy last imported
        # Only new posts are matched; new and changed are converted, but not the stale override.
        match_argv = self.match.call_args.args[0]
        self.assertEqual(match_argv[match_argv.index("--sourcetexts-root") + 1], str(self.sources))
        self.assertEqual([match_argv[i + 1] for i, a in enumerate(match_argv) if a == "--post"], ["104"])
        self.assertEqual(self.convert.call_args.kwargs["posts"], [101, 104])

    def test_a_run_that_stopped_is_run_again(self) -> None:
        self.month_of_changes()
        with self.assertRaises(RuntimeError), mock.patch(f"{MODULE}.match.main", return_value=2), \
                mock.patch("sys.stdout"):
            update(upstream=self.clone, ref="origin/master", data_dir=self.data_dir,
                   project_directory=self.projects, licence_decisions=LicenceDecisions({}, {}),
                   post_urns_path=Path(self.tmp.name) / "post_urns.jsonl")
        # The download already wrote the new manifest; the changes are still found.
        run = self.run_update(PostDecisions(colours={105: {"green": "amendment"}}))
        self.assertEqual(len(run.changes), 5)
        self.assertEqual(self.convert.call_args.kwargs["posts"], [101, 104])

    def test_a_lapsed_licence_decision_is_reported(self) -> None:
        self.month_of_changes()
        licences = LicenceDecisions({}, {101: {"hold": "until permission", "as_of": "2026-09-01"}})
        run = self.run_update(licences=licences)
        self.assertEqual(run.lapsed_licences, {101: "hold: until permission"})

    def test_an_unchanged_export_does_nothing(self) -> None:
        run = self.run_update()
        self.assertEqual(run.changes, [])
        self.match.assert_not_called()
        self.convert.assert_not_called()

    def test_the_first_run_finds_every_post_new(self) -> None:
        # setUp's run, from an empty sourcetexts.
        manifest = json.loads((self.data_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(manifest["posts"]), ["101", "102", "103", "105"])


if __name__ == "__main__":
    unittest.main()
