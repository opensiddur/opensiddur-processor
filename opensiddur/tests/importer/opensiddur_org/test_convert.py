import json
import shutil
import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.opensiddur_org.convert import (
    convert_post,
    load_context,
    plan_post,
    project_ids,
    register_urns,
    select_posts,
)
from opensiddur.importer.opensiddur_org.licences import load_decisions
from opensiddur.importer.opensiddur_org.parse_post import parse_post
from opensiddur.importer.opensiddur_org.urns import PostUrns, save_post_urns
from opensiddur.tests.importer.opensiddur_org.support import (
    FIXTURES,
    NEW_PERSON,
    TRANSLATOR,
    make_post,
    write_data_dir,
)

URN = "urn:x-opensiddur:text:prayer:a_song"


def imported_index(post_id: int) -> str:
    """An index.xml as a converted post's, as far as finding its projects goes."""
    return (f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>'
            f'<bibl xml:id="project_source_bibl"><idno type="opensiddur.org">{post_id}</idno></bibl>'
            f'</teiHeader></TEI>')


class ConvertTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.registry = root / "registry"
        self.registry.mkdir()
        shutil.copy(FIXTURES / "contributor.jsonl", self.registry / "contributor.jsonl")
        (self.registry / "prayer.jsonl").write_text("", encoding="utf-8")
        self.projects = root / "project"
        self.projects.mkdir()
        self.post_urns = root / "post_urns.jsonl"
        self.posts = [
            make_post(101),
            make_post(102, slug="needs-urn"),
            make_post(103, slug="new-person", coauthors=[TRANSLATOR, NEW_PERSON]),
            make_post(104, slug="unlicensed", licence=""),
            make_post(502, slug="rejected"),
        ]
        self.data_dir = write_data_dir(root / "sources", self.posts)
        save_post_urns({pid: PostUrns(pid, "new", f"{URN}_{pid}") for pid in (101, 103, 104, 502)}, self.post_urns)
        self.context = load_context(
            self.data_dir, post_urns_path=self.post_urns, registry_directory=self.registry,
            decisions=load_decisions(FIXTURES / "licence_decisions.yaml"),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def plan(self, index: int):
        return plan_post(parse_post(self.posts[index]), self.context)

    def convert(self, index: int) -> list[str]:
        ids = project_ids([self.plan(i) for i in range(len(self.posts))], self.projects)
        return convert_post(self.plan(index), self.context, self.projects, ids=ids,
                            registry_directory=self.registry)


class TestPlans(ConvertTestCase):
    def test_standard(self) -> None:
        plan = self.plan(0)
        self.assertTrue(plan.standard, plan.reasons)
        self.assertEqual([column.lang for column, _ in plan.columns], ["he", "en"])

    def test_no_urn_decision(self) -> None:
        self.assertIn("no URN decision", self.plan(1).reasons)

    def test_unregistered_contributor(self) -> None:
        plan = self.plan(2)
        self.assertIn("unregistered contributor(s): new-person-transcription", plan.reasons)
        self.assertEqual(len(plan.candidates), 1)

    def test_undecided_licence_imports_nothing(self) -> None:
        plan = self.plan(3)
        self.assertEqual(plan.columns, [])
        self.assertTrue(plan.reasons[0].startswith("no column may be imported"))

    def test_rejected_post(self) -> None:
        self.assertEqual(set(self.plan(4).skipped_columns.values()), {"reject: Rejected after review."})

    def test_select_posts(self) -> None:
        self.assertEqual(select_posts(self.data_dir, posts=[101, 999], categories=None), [101])
        self.assertEqual(select_posts(self.data_dir, posts=None, categories=[201]), [103, 104])
        self.assertEqual(len(select_posts(self.data_dir, posts=None, categories=None)), 5)


class TestConversion(ConvertTestCase):
    def test_writes_valid_projects(self) -> None:
        written = self.convert(0)
        # The source is the poet's, of its year; the translation is the translator's.
        self.assertEqual(written, ["a_song-poet-2020-he", "a_song-translator-en"])
        self.assertEqual(sorted(p.name for p in (self.projects / "a_song-translator-en").iterdir()),
                         ["a_song_101.xml", "index.xml"])

    def test_removes_projects_the_post_no_longer_makes(self) -> None:
        # A language it lost, or a name its retitling changed: found by the post ID, not the name.
        for name, post_id in (("old_title-poet-2020-de", 101), ("a_song-poet-2020-yi", 1010)):
            (self.projects / name).mkdir()
            (self.projects / name / "index.xml").write_text(imported_index(post_id), encoding="utf-8")
        (self.projects / "tanakh-wlc-he").mkdir()  # a project no post made
        self.convert(0)
        self.assertFalse((self.projects / "old_title-poet-2020-de").exists())
        self.assertTrue((self.projects / "a_song-poet-2020-yi").exists())
        self.assertTrue((self.projects / "tanakh-wlc-he").exists())

    def test_a_name_another_project_has_adds_the_post_id(self) -> None:
        (self.projects / "a_song-poet-2020-he").mkdir()  # a project no post made
        self.assertEqual(self.convert(0), ["a_song-poet-2020-101-he", "a_song-translator-en"])

    def test_a_post_keeps_its_name_from_an_older_post(self) -> None:
        # Post 900 already has the name; post 101, the same song, becomes convertible later.
        newer = parse_post(make_post(900))
        self.context.post_urns[900] = PostUrns(900, "new", f"{URN}_900")
        (self.projects / "a_song-poet-2020-he").mkdir()
        (self.projects / "a_song-poet-2020-he" / "index.xml").write_text(imported_index(900), encoding="utf-8")
        plans = [self.plan(0), plan_post(newer, self.context)]
        ids = project_ids(plans, self.projects)
        self.assertEqual(ids[(900, "he")], "a_song-poet-2020-he")
        self.assertEqual(ids[(101, "he")], "a_song-poet-2020-101-he")
        for plan in plans:
            convert_post(plan, self.context, self.projects, ids=ids, registry_directory=self.registry)
        # Neither held the English name, so the older post has it.
        self.assertEqual(ids[(101, "en")], "a_song-translator-en")
        self.assertEqual(sorted(p.name for p in self.projects.iterdir()),
                         ["a_song-poet-2020-101-he", "a_song-poet-2020-he",
                          "a_song-translator-900-en", "a_song-translator-en"])

    def test_a_name_another_post_is_given_is_not_removed_as_stale(self) -> None:
        # Post 900 held the name, but no longer wants it; post 101 is given it and writes there.
        (self.projects / "a_song-poet-2020-he").mkdir()
        (self.projects / "a_song-poet-2020-he" / "index.xml").write_text(imported_index(900), encoding="utf-8")
        newer = parse_post(make_post(900, title="Another Song"))
        self.context.post_urns[900] = PostUrns(900, "new", f"{URN}_900")
        plans = [self.plan(0), plan_post(newer, self.context)]
        ids = project_ids(plans, self.projects)
        self.assertEqual(ids[(101, "he")], "a_song-poet-2020-he")
        for plan in plans:
            convert_post(plan, self.context, self.projects, ids=ids, registry_directory=self.registry)
        self.assertIn("101", (self.projects / "a_song-poet-2020-he" / "index.xml").read_text(encoding="utf-8"))

    def test_rerun_is_identical(self) -> None:
        self.convert(0)
        before = {p: p.read_bytes() for p in self.projects.rglob("*.xml")}
        self.convert(0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.projects.rglob("*.xml")})

    def test_register_new_urns_once(self) -> None:
        self.assertEqual(register_urns([self.plan(0)], self.context, self.registry), 3)
        self.assertEqual(register_urns([self.plan(0)], self.context, self.registry), 0)
        lines = [json.loads(l) for l in (self.registry / "prayer.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([l["urn"] for l in lines], [f"{URN}_101", f"{URN}_101/1", f"{URN}_101/2"])
        self.assertEqual((lines[0]["label_en"], lines[0]["label_he"]), ("A Song", "שִׁירָה"))



class TestRejection(ConvertTestCase):
    def test_a_wholly_rejected_post(self) -> None:
        from opensiddur.importer.opensiddur_org.convert import is_rejected

        self.assertTrue(is_rejected(self.plan(4)))
        self.assertFalse(is_rejected(self.plan(3)))  # undecided is not rejected
        self.assertFalse(is_rejected(self.plan(0)))

    def test_only_rows_with_text_are_registered(self) -> None:
        from opensiddur.tests.importer.opensiddur_org.support import cell, table

        rows = [[cell("heb-Hebr", "liturgy", "שָׁלוֹם"), cell("eng-Latn", "english", "Peace")],
                [cell("heb-Hebr", "liturgy", ""), cell("eng-Latn", "english", "")],
                [cell("heb-Hebr", "liturgy", "עוֹד"), cell("eng-Latn", "english", "More")]]
        post = make_post(101, content=table(["Source (Hebrew)", "Translation (English)"], rows))
        plan = plan_post(parse_post(post), self.context)
        register_urns([plan], self.context, self.registry)
        urns = [json.loads(l)["urn"] for l in (self.registry / "prayer.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(urns, [f"{URN}_101", f"{URN}_101/1", f"{URN}_101/3"])


class TestRegisteringParts(ConvertTestCase):
    def registered(self, post) -> list[dict]:
        register_urns([plan_post(post, self.context)], self.context, self.registry)
        return [json.loads(l) for l in (self.registry / "prayer.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_each_table_is_a_part_of_the_post(self) -> None:
        from opensiddur.tests.importer.opensiddur_org.support import cell, table

        one = table(["Source (Hebrew)"], [[cell("heb-Hebr", "liturgy", "א")]])
        lines = self.registered(parse_post(make_post(101, content=one + one)))
        self.assertEqual([(l["urn"], l.get("parent")) for l in lines], [
            (f"{URN}_101", None), (f"{URN}_101/1", f"{URN}_101"), (f"{URN}_101/1/1", f"{URN}_101/1"),
            (f"{URN}_101/2", f"{URN}_101"), (f"{URN}_101/2/1", f"{URN}_101/2")])

    def test_an_essay_and_its_quoted_passages(self) -> None:
        from opensiddur.importer.opensiddur_org.post_decisions import PostDecisions

        content = ('<p>An essay.</p><blockquote><div lang="heb-Hebr">א</div><div lang="eng-Latn">A</div></blockquote>'
                   '<p>More.</p>')
        post = parse_post(make_post(101, content=content), PostDecisions(essays={101: "an essay"}))
        lines = self.registered(post)
        self.assertEqual([(l["urn"], l.get("parent")) for l in lines], [
            (f"{URN}_101", None), (f"{URN}_101/quoted", f"{URN}_101"),
            (f"{URN}_101/quoted/1", f"{URN}_101/quoted")])


if __name__ == "__main__":
    unittest.main()
