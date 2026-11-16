import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.sefaria.convert import ConvertError, convert_work, load_structure
from opensiddur.importer.util.incipit import IncipitIndex, words

from .support import MORNING, STRUCTURE, WORK, make_source, write_structure, write_work_dir

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
        return convert_work(WORK, sourcetexts_root=self.sources, project_directory=self.projects,
                            registry_directory=self.registry, urns_path=self.urns, index=self.index,
                            output_directory=self.output, structure_path=self.structure, **kwargs)

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
