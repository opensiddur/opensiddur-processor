import json
import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.feinstein_haggadah.align_page_breaks import (
    _enforce_monotonic,
    _interpolate_missing,
    _normalize_hebrew,
    _subseq_ratio,
)
from opensiddur.importer.util.pages import heidenheim_pdf_path
from opensiddur.tests.importer.feinstein_haggadah import support


class TestAlignPageBreaksHelpers(unittest.TestCase):
    def test_normalize_hebrew_strips_marks_and_non_letters(self) -> None:
        self.assertEqual(_normalize_hebrew("קַדֵּשׁ!"), "קדש")

    def test_subseq_ratio(self) -> None:
        self.assertEqual(_subseq_ratio("קדש", "xxקxxדxxש"), 1.0)
        self.assertLess(_subseq_ratio("קדש", "שדק"), 0.5)

    def test_interpolate_missing_uses_neighbors(self) -> None:
        slugs = ["a", "b", "c"]
        filled = _interpolate_missing({"a": 11, "c": 13}, slugs)
        self.assertEqual(filled["b"], 11)

    def test_enforce_monotonic(self) -> None:
        slugs = ["a", "b", "c"]
        result = _enforce_monotonic({"a": 11, "b": 10, "c": 12}, slugs)
        self.assertEqual(result, {"a": 11, "b": 11, "c": 12})

    def test_conversion_does_not_depend_on_this_module(self) -> None:
        """The aligner is a draft tool; the converter must read the curated table only."""
        source = Path(
            "opensiddur/importer/feinstein_haggadah/convert.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("align_page_breaks", source)


class TestAlignPageBreaksIntegration(unittest.TestCase):
    def test_align_writes_json_when_pdf_present(self) -> None:
        pdf_path = heidenheim_pdf_path()
        if pdf_path is None:
            raise unittest.SkipTest("1822 facsimile PDF not checked out")
        compilation = support.require_path(
            support.compilation_path(), "haggadah compilation not checked out"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "feinstein_haggadah_2009").mkdir()
            (root / "heidenheim_haggadah_1822").mkdir()
            (root / "feinstein_haggadah_2009" / "compilation.json").write_text(
                compilation.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            pdf_dest = root / "heidenheim_haggadah_1822" / "heidenheim_1822.pdf"
            pdf_dest.write_bytes(pdf_path.read_bytes())

            from opensiddur.importer.feinstein_haggadah.page_breaks import (
                folio_at_facsimile_page,
            )
            from opensiddur.importer.feinstein_haggadah.align_page_breaks import (
                align_page_breaks,
                write_page_breaks,
            )

            mapping = align_page_breaks(sourcetexts_root=root, pdf_path=pdf_dest)
            self.assertGreaterEqual(len(mapping), 50)
            self.assertLess(mapping["ha_lachma_anya"], mapping["avadim_hayinu"])
            # The opening sections are the ones the header anchors match cleanly, so the
            # draft should agree with the curated table there. Later sections drift, which
            # is why this is a first pass for hand verification and not the source of truth.
            self.assertEqual(folio_at_facsimile_page(mapping["bediqat_chametz"]), "2r")
            self.assertEqual(folio_at_facsimile_page(mapping["eruv_tavshilin"]), "3r")

            out = write_page_breaks(mapping, root)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("bediqat_chametz", data)
            self.assertNotIn("_only", data)


if __name__ == "__main__":
    unittest.main()
