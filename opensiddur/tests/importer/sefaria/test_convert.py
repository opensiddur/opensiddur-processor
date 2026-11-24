import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.common.validate_names import Spellings
from opensiddur.importer.sefaria.convert import ConvertError, convert_work, load_structure
from opensiddur.importer.util.incipit import IncipitIndex, words

from .support import BLESSINGS, MORNING, STRUCTURE, WORK, make_source, write_structure, write_work_dir

T = "urn:x-opensiddur:text:"
NS = {"tei": "http://www.tei-c.org/ns/1.0", "j": "http://jewishliturgy.org/ns/jlptei/2"}


class TestLoadStructure(unittest.TestCase):
    def test_every_node_must_be_placed(self):
        with tempfile.TemporaryDirectory() as tmp:
            partial = dict(STRUCTURE)
            del partial["Blessings"]
            partial["Nowhere"] = "x/y"
            path = write_structure(Path(tmp) / "s.yaml", partial)
            with self.assertRaises(ConvertError) as caught:
                load_structure(WORK, make_source(), path)
        self.assertIn("Blessings: not placed", str(caught.exception))
        self.assertIn("Nowhere: placed in s.yaml but not in the schema", str(caught.exception))

    def test_a_place_is_used_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            doubled = dict(STRUCTURE, Blessings="chol/shacharit/amidah")
            path = write_structure(Path(tmp) / "s.yaml", doubled)
            with self.assertRaisesRegex(ConvertError, "placed twice"):
                load_structure(WORK, make_source(), path)


class TestVariants(unittest.TestCase):
    """A text printed twice, the second time with a phrase of its own."""

    def test_one_text_with_a_conditional_insertion(self):
        # The insertion follows the opening phrases, as Nachem does Boneh Yerushalayim's.
        text = [MORNING[1], MORNING[2], ("שֶׁהֶחֱזַֽרְתָּ בִּי נִשְׁמָתִי", "for You have restored my soul")]
        again = [text[0], text[1], ("מְשֻׁנֶּה מְאֹד בְּיוֹתֵר", "changed"), text[2]]
        tree = {"Morning": {"Upon Arising": text, "Again": again}, "Blessings": BLESSINGS}
        structure = {"Morning": "chol/shacharit", "Morning / Upon Arising": "chol/shacharit/upon_arising",
                     "Morning / Again": "chol/shacharit/again", "Blessings": "berakhot/test"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_work_dir(root / "sources" / "sefaria" / WORK.key, tree)
            (root / "project").mkdir()
            (root / "registry").mkdir()
            (root / "decisions.yaml").write_text("{}\n")
            plan = convert_work(WORK, sourcetexts_root=root / "sources", project_directory=root / "project",
                                registry_directory=root / "registry", urns_path=root / "urns.jsonl",
                                index=IncipitIndex(), output_directory=root / "out",
                                structure_path=write_structure(root / "s.yaml", structure),
                                decisions_path=root / "decisions.yaml", spellings=Spellings(frozenset(), {}),
                                works={WORK.key: WORK}, equivalents_path=root / "equivalents.yaml",
                                conditions_path=root / "conditions.yaml")
            variant = [r for r in plan.decisions.records.values() if r.kind == "variant"]
            self.assertEqual(len(variant), 1)
            condition = "urn:x-opensiddur:condition:" + variant[0].urn.split(":", 3)[3] + "/chol_shacharit_again"
            he = root / "project" / WORK.projects["he"]
            text = etree.parse(str(he / (variant[0].urn.rsplit(":", 1)[1] + ".xml")))
            self.assertEqual(text.xpath("//j:conditional//tei:f/@name", namespaces=NS), [condition])
            self.assertEqual(text.xpath("//j:conditional//tei:binary/@value", namespaces=NS), ["true"])
            again = etree.parse(str(he / "siddur_chol_shacharit_again.xml"))
            self.assertEqual(again.xpath("//j:declare//tei:binary/@value", namespaces=NS), ["true"])
            first = etree.parse(str(he / "siddur_chol_shacharit_upon_arising.xml"))
            self.assertEqual(first.xpath("//j:declare//tei:binary/@value", namespaces=NS), ["false"])


class TestOpeningTransclusion(unittest.TestCase):
    """A text that opens with another the volume prints (the full Kaddish, with the half
    Kaddish): its file transcludes that text and holds only its own words."""

    HALF = [("<b>אֵין כֵּאלֹהֵינוּ</b> אֵין כַּאדוֹנֵינוּ", "None like our God"),
            ("אֵין כְּמַלְכֵּנוּ אֵין כְּמוֹשִׁיעֵנוּ", "none like our King")]
    OWN = [("מִי כֵאלֹהֵינוּ מִי כַאדוֹנֵינוּ", "Who is like our God")]
    TABLE = f"""
texts:
  - opens: אין כאלהינו
    ends: אין כמלכנו אין כמושיענו
    urn: {T}prayer:half_text
  - opens: אין כאלהינו
    with: [מי כאלהינו]
    ends: מי כאלהינו מי כאדונינו
    urn: {T}prayer:full_text
    transcludes: {T}prayer:half_text
"""

    def convert(self, full, half_again=None, corrections=""):
        tree = {"Morning": {"Upon Arising": self.HALF, "Again": full}, "Blessings": BLESSINGS}
        structure = {"Morning": "chol/shacharit", "Morning / Upon Arising": "chol/shacharit/upon_arising",
                     "Morning / Again": "chol/shacharit/again", "Blessings": "berakhot/test"}
        if half_again:
            tree["Morning"]["Later"] = half_again
            structure["Morning / Later"] = "chol/shacharit/later"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        write_work_dir(root / "sources" / "sefaria" / WORK.key, tree)
        (root / "project").mkdir()
        (root / "registry").mkdir()
        (root / "decisions.yaml").write_text("{}\n")
        (root / "equivalents.yaml").write_text(self.TABLE, encoding="utf-8")
        (root / "corrections.yaml").write_text(corrections, encoding="utf-8")
        convert_work(WORK, sourcetexts_root=root / "sources", project_directory=root / "project",
                     registry_directory=root / "registry", urns_path=root / "urns.jsonl",
                     index=IncipitIndex(), output_directory=root / "out",
                     structure_path=write_structure(root / "s.yaml", structure),
                     decisions_path=root / "decisions.yaml", spellings=Spellings(frozenset(), {}),
                     works={WORK.key: WORK}, equivalents_path=root / "equivalents.yaml",
                     conditions_path=root / "conditions.yaml", corrections_path=root / "corrections.yaml")
        self.projects = {lang: root / "project" / WORK.projects[lang] for lang in ("he", "en")}
        return {lang: etree.parse(str(self.projects[lang] / "full_text.xml")) for lang in ("he", "en")}

    def place(self, lang, name):
        return etree.parse(str(self.projects[lang] / f"siddur_chol_shacharit_{name}.xml"))

    def test_the_text_it_opens_with_is_transcluded(self):
        for lang, text in self.convert(self.HALF + self.OWN).items():
            with self.subTest(lang=lang):
                div = text.find(".//tei:body/tei:div", namespaces=NS)
                self.assertEqual(div[0].tag, f"{{{NS['j']}}}transclude")
                self.assertEqual(div[0].get("target"), T + "prayer:half_text")
                self.assertEqual(text.xpath("//tei:milestone[@unit='phrase']/@corresp", namespaces=NS),
                                 [T + "metsudah:full_text/3"])

    def test_a_misprint_corrected_in_the_text_it_opens_with_is_transcluded(self):
        full = self.HALF + self.OWN
        self.HALF = [self.HALF[0], ("אֵין כְּמַלְכֵּנוּ אֵין כְּמוֹשִׁיעֵנוּ", "none like out King")]
        corrections = (f"{WORK.key}:\n  - {{leaf: Morning / Upon Arising, lang: en, segment: 2, "
                       "sic: out King, corr: our King}\n")
        texts = self.convert(full, corrections=corrections)
        self.assertEqual(texts["en"].find(".//tei:body/tei:div", namespaces=NS)[0].get("target"),
                         T + "prayer:half_text")
        half = etree.parse(str(self.projects["en"] / "half_text.xml"))
        self.assertEqual([(c.findtext("tei:sic", namespaces=NS), c.findtext("tei:corr", namespaces=NS))
                          for c in half.iterfind(".//tei:choice", namespaces=NS)], [("out King", "our King")])
        # Uncorrected, the English differs, and the full text is written in full.
        self.assert_in_full(self.convert(full))

    def test_in_words_of_its_own_it_is_written_in_full(self):
        changed = [self.HALF[0], ("אֵין כְּמַלְכֵּנוּ אֵין כְּמוֹשִׁיעֵנוּ אַחֵר", "none like our King"), *self.OWN]
        self.assert_in_full(self.convert(changed))

    def test_in_english_or_rubrics_of_its_own_it_is_written_in_full(self):
        english = [self.HALF[0], ("אֵין כְּמַלְכֵּנוּ אֵין כְּמוֹשִׁיעֵנוּ", "none like our Sovereign"), *self.OWN]
        rubric = [self.HALF[0], ("", "<small>Congregation:</small>"), self.HALF[1], *self.OWN]
        for full in (english, rubric):
            with self.subTest(full=full[1]):
                self.assert_in_full(self.convert(full))

    def test_the_place_declares_the_variants_of_the_text_it_opens_with(self):
        # The full text's file holds the half text's first printing: each place transcluding the
        # full text says the half text's variants are not printed there.
        variant = [self.HALF[0], ("אֵין כְּמַלְכֵּנוּ אֵין כְּמוֹשִׁיעֵנוּ לְעוֹלָם", "none like our King ever")]
        for lang, text in self.convert(self.HALF + self.OWN, half_again=variant).items():
            with self.subTest(lang=lang):
                self.assertEqual(text.xpath("//j:transclude/@target", namespaces=NS), [T + "prayer:half_text"])
                place = self.place(lang, "again")
                (declare,) = place.xpath("//j:declare[following-sibling::*[1][@target='%sprayer:full_text']]" % T,
                                         namespaces=NS)
                self.assertEqual(declare.xpath(".//tei:f/@name", namespaces=NS),
                                 ["urn:x-opensiddur:condition:prayer:half_text/chol_shacharit_later"])
                self.assertEqual(declare.xpath(".//tei:binary/@value", namespaces=NS), ["false"])

    def test_an_instruction_the_text_opens_with_is_the_places(self):
        # The text before runs on into the full text, unmarked: the block is cut where it opens,
        # and the instruction between them goes with the full text's block.
        before = ("<b>הוֹדוּ לַיהוָה</b> כִּי טוֹב", "Give thanks to God for He is good")
        lead = ("", "<small>The Chazzan recites the following:</small>")
        unmarked = (self.HALF[0][0].replace("<b>", "").replace("</b>", ""), self.HALF[0][1])
        for lang in ("he", "en"):
            texts = self.convert([before, lead, unmarked, self.HALF[1], *self.OWN])
            with self.subTest(lang=lang):
                self.assertEqual(texts[lang].xpath("//tei:note", namespaces=NS), [])
                self.assertEqual(texts[lang].xpath("//j:transclude/@target", namespaces=NS), [T + "prayer:half_text"])
        place = self.place("en", "again")
        (note,) = place.xpath("//tei:note[following-sibling::j:transclude]", namespaces=NS)
        self.assertEqual(" ".join(note.xpath("string()").split()), "The Chazzan recites the following:")

    def assert_in_full(self, texts):
        for text in texts.values():
            self.assertEqual(text.xpath("//j:transclude", namespaces=NS), [])
            self.assertEqual(len(text.xpath("//tei:milestone[@unit='phrase']/@corresp", namespaces=NS)), 3)


class TestConditionsReachTheFiles(unittest.TestCase):
    def test_a_condition_rubric_becomes_a_conditional_in_both_languages(self):
        text = [MORNING[1], ("", "<small><i>On Rosh Chodesh add:</i></small>"),
                ("יַעֲלֶה וְיָבוֹא", "May it rise"), ("", "<small>When the Holy Ark is opened, say:</small>"),
                MORNING[2]]
        tree = {"Morning": {"Upon Arising": text}, "Blessings": BLESSINGS}
        structure = {"Morning": "chol/shacharit", "Morning / Upon Arising": "chol/shacharit/upon_arising",
                     "Blessings": "berakhot/test"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_work_dir(root / "sources" / "sefaria" / WORK.key, tree)
            (root / "project").mkdir()
            (root / "registry").mkdir()
            (root / "decisions.yaml").write_text("{}\n")
            (root / "conditions.yaml").write_text(
                "rubrics:\n  - match: '^On Rosh Chodesh add:'\n    when: {holiday: {rosh-hodesh: true}}\n"
                "directives: ['^When the Holy Ark is opened']\n"
                f"leaves:\n  - work: {WORK.key}\n    leaf: Blessings\n    when: {{day-of-week: {{hebrew-day: 2}}}}\n")
            convert_work(WORK, sourcetexts_root=root / "sources", project_directory=root / "project",
                         registry_directory=root / "registry", urns_path=root / "urns.jsonl",
                         index=IncipitIndex(), output_directory=root / "out",
                         structure_path=write_structure(root / "s.yaml", structure),
                         decisions_path=root / "decisions.yaml", spellings=Spellings(frozenset(), {}),
                         works={WORK.key: WORK}, equivalents_path=root / "equivalents.yaml",
                         conditions_path=root / "conditions.yaml")
            for lang in ("he", "en"):
                found = [etree.parse(str(f)).xpath("//j:conditional//tei:f/@name", namespaces=NS)
                         for f in (root / "project" / WORK.projects[lang]).glob("*.xml")]
                self.assertIn(["rosh-hodesh"], found)
            report = (root / "out" / f"sefaria_{WORK.key}_report.md").read_text()
            self.assertIn("1× On Rosh Chodesh add:", report)
            # A reviewed directive is not listed as an unmapped condition.
            self.assertIn("not in conditions.yaml (0)", report)
            # The gated leaf, a child of the root, is transcluded conditionally from the index.
            for lang in ("he", "en"):
                index = etree.parse(str(root / "project" / WORK.projects[lang] / "index.xml"))
                self.assertEqual(index.xpath("//j:transclude[preceding-sibling::j:conditional]/@target",
                                             namespaces=NS), ["urn:x-opensiddur:text:siddur:berakhot/test"])


    def test_a_text_printed_elsewhere_without_its_condition_is_gated_where_it_is_printed(self):
        # Psalm 130: in the Ten Days after Yishtabach, and among the winter psalms always.
        own = ["שֶׁאֵין לוֹ מָקוֹר בָּאוֹסֶף", "אֶלָּא כָּאן וְעוֹד דְּבָרִים"]
        once = [MORNING[1], MORNING[2], ("", "<small><i>On Rosh Chodesh add:</i></small>"),
                (own[0], "which has no source"), (own[1], "but here")]
        again = [("<b>" + own[0] + "</b>", "which has no source"), (own[1], "but here")]
        tree = {"Morning": {"Upon Arising": once, "Again": again}, "Blessings": BLESSINGS}
        structure = {"Morning": "chol/shacharit", "Morning / Upon Arising": "chol/shacharit/upon_arising",
                     "Morning / Again": "chol/shacharit/again", "Blessings": "berakhot/test"}
        index = IncipitIndex()
        index.add("urn:x-opensiddur:text:prayer:zeh", words(" ".join(own)))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_work_dir(root / "sources" / "sefaria" / WORK.key, tree)
            (root / "project").mkdir()
            (root / "registry").mkdir()
            (root / "decisions.yaml").write_text("{}\n")
            (root / "conditions.yaml").write_text(
                "rubrics:\n  - match: '^On Rosh Chodesh add:'\n    when: {holiday: {rosh-hodesh: true}}\n")
            plan = convert_work(WORK, sourcetexts_root=root / "sources", project_directory=root / "project",
                                registry_directory=root / "registry", urns_path=root / "urns.jsonl",
                                index=index, output_directory=root / "out",
                                structure_path=write_structure(root / "s.yaml", structure),
                                decisions_path=root / "decisions.yaml", spellings=Spellings(frozenset(), {}),
                                works={WORK.key: WORK}, equivalents_path=root / "equivalents.yaml",
                                conditions_path=root / "conditions.yaml")
            self.assertEqual(sorted(r.urn.rsplit(":", 1)[1] for r in plan.decisions.records.values()
                                    if r.kind != "repeat"), ["haleluyah_haleli_nafshi", "modeh_ani_lefanekha", "zeh"])
            he = root / "project" / WORK.projects["he"]
            text = etree.parse(str(he / "zeh.xml"))
            self.assertEqual(text.xpath("//j:conditional", namespaces=NS), [])
            first = etree.parse(str(he / "siddur_chol_shacharit_upon_arising.xml"))
            self.assertEqual(first.xpath("//j:transclude[preceding-sibling::j:conditional]/@target", namespaces=NS),
                             ["urn:x-opensiddur:text:prayer:zeh"])
            second = etree.parse(str(he / "siddur_chol_shacharit_again.xml"))
            self.assertEqual(second.xpath("//j:conditional", namespaces=NS), [])


class TestConvertWork(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.sources = root / "sources"
        write_work_dir(self.sources / "sefaria" / WORK.key)
        self.projects = root / "project"
        self.projects.mkdir()
        self.registry = root / "registry"
        self.registry.mkdir()
        (self.registry / "prayer.jsonl").write_text("")
        self.urns = root / "urns.jsonl"
        self.structure = write_structure(root / "structure.yaml")
        self.output = root / "out"
        self.index = IncipitIndex()
        self.index.add(T + "prayer:modeh_ani", words(" ".join(h for h, _ in MORNING[1:3])))

    def convert(self, **kwargs):
        # Synthetic configuration throughout: no real spellings, decisions, works, equivalents
        # or conditions (the paths below are not there, and so are empty).
        decisions = Path(self.tmp.name) / "decisions.yaml"
        decisions.write_text("{}\n")
        kwargs.setdefault("equivalents_path", Path(self.tmp.name) / "equivalents.yaml")
        kwargs.setdefault("conditions_path", Path(self.tmp.name) / "conditions.yaml")
        kwargs.setdefault("corrections_path", Path(self.tmp.name) / "corrections.yaml")
        return convert_work(WORK, sourcetexts_root=self.sources, project_directory=self.projects,
                            registry_directory=self.registry, urns_path=self.urns, index=self.index,
                            output_directory=self.output, structure_path=self.structure,
                            decisions_path=decisions, spellings=Spellings(frozenset(), {}),
                            works={WORK.key: WORK}, **kwargs)

    def test_writes_parallel_projects(self):
        plan = self.convert(do_register=True)
        he = self.projects / WORK.projects["he"]
        en = self.projects / WORK.projects["en"]
        self.assertEqual(sorted(p.name for p in he.iterdir()), sorted(p.name for p in en.iterdir()))
        self.assertIn("modeh_ani.xml", {p.name for p in he.iterdir()})
        self.assertIn("siddur_chol_shacharit_upon_arising.xml", {p.name for p in he.iterdir()})

        index = etree.parse(str(he / "index.xml"))
        self.assertEqual(index.xpath("//j:transclude/@target", namespaces=NS),
                         [T + "siddur:chol/shacharit", T + "siddur:berakhot/test"])
        self.assertEqual(index.xpath("//tei:idno[@type='sefaria']/text()", namespaces=NS), [WORK.versions["he"]])

        leaf = etree.parse(str(en / "siddur_chol_shacharit_upon_arising.xml"))
        self.assertEqual(leaf.xpath("//j:transclude/@target", namespaces=NS)[0], T + "prayer:modeh_ani")
        self.assertEqual(leaf.xpath("normalize-space((//tei:note[@type='instruction'])[1])", namespaces=NS),
                         "Upon waking, say:")
        he_leaf = etree.parse(str(he / "siddur_chol_shacharit_upon_arising.xml"))
        self.assertEqual(he_leaf.xpath("//tei:note", namespaces=NS), [])  # English-only rubrics

        kinds = sorted(r.kind for r in plan.decisions.decided)
        self.assertEqual(kinds, ["existing", "new", "new", "new"])
        registered = [json.loads(line)["urn"] for line in (self.registry / "prayer.jsonl").read_text().splitlines()]
        self.assertTrue(all(u.startswith(T + "prayer:") for u in registered))
        self.assertNotIn(T + "prayer:modeh_ani", registered)
        siddur = [json.loads(line)["urn"] for line in (self.registry / "siddur.jsonl").read_text().splitlines()]
        self.assertIn(T + "siddur:chol/shacharit/upon_arising", siddur)
        self.assertIn(T + "siddur:chol", siddur)  # a parent place
        self.assertTrue((self.output / f"sefaria_{WORK.key}_report.md").exists())

    def test_a_second_run_decides_nothing_and_changes_nothing(self):
        self.convert(do_register=True)
        he = self.projects / WORK.projects["he"]
        before = {p.name: p.read_text() for p in he.iterdir()}
        registry_before = (self.registry / "prayer.jsonl").read_text()
        plan = self.convert(do_register=True)
        self.assertEqual(plan.decisions.decided, [])
        self.assertEqual({p.name: p.read_text() for p in he.iterdir()}, before)
        self.assertEqual((self.registry / "prayer.jsonl").read_text(), registry_before)

    def test_a_version_no_longer_cc_by_is_refused(self):
        manifest_path = self.sources / "sefaria" / WORK.key / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["en.json"]["license"] = "CC-BY-NC"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ConvertError, "CC-BY-NC"):
            self.convert()

    def test_stale_files_are_removed(self):
        he = self.projects / WORK.projects["he"]
        he.mkdir(parents=True)
        (he / "left_over.xml").write_text("<x/>")
        self.convert()
        self.assertFalse((he / "left_over.xml").exists())


if __name__ == "__main__":
    unittest.main()
