"""Checks of the importer's hand-kept tables against the downloaded works.

They read ``sourcetexts`` and are skipped where it is absent (CI checks out no submodules);
the importer's logic is tested on synthetic data elsewhere.
"""

import unittest

from opensiddur.importer.sefaria.align import align_work, load_decisions
from opensiddur.importer.sefaria.convert import load_structure
from opensiddur.importer.sefaria.source import load_work_source
from opensiddur.importer.sefaria.works import load_works


class TestCuration(unittest.TestCase):
    def works(self):
        found = []
        for work in load_works().values():
            directory = work.data_directory()
            if (directory / "manifest.json").exists():
                found.append((work, load_work_source(directory)))
        if not found:
            raise unittest.SkipTest("no Sefaria work is downloaded in sourcetexts")
        return found

    def test_every_node_is_placed(self):
        for work, source in self.works():
            with self.subTest(work=work.key):
                load_structure(work, source)

    def test_every_leaf_aligns(self):
        decisions = load_decisions()
        for work, source in self.works():
            with self.subTest(work=work.key):
                align_work(work.key, source.leaves, decisions)


if __name__ == "__main__":
    unittest.main()
