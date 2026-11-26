"""Exercise the same Lua geometry used by the PDF preamble, without real sources."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opensiddur.exporter.tex.scan_links import MARGIN_PLACEMENT_LUA


@unittest.skipUnless(shutil.which("texlua"), "texlua required")
class TestScanLinkPlacement(unittest.TestCase):
    def run_lua(self, assertions):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/"placement.lua"
            script.write_text(MARGIN_PLACEMENT_LUA + "\n" + assertions, encoding="utf-8")
            result = subprocess.run(["texlua", str(script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_same_line_links_use_distinct_bounded_lanes(self):
        self.run_lua("""
local x1,y1 = OSScanLinks.place(1, 80, 400, true, 600, 800, 10, 8, 2, 10, 2)
local x2,y2 = OSScanLinks.place(1, 80, 400, true, 600, 800, 10, 8, 2, 10, 2)
assert(x1 == 0 and y1 == 0 and x2 >= 12 and y2 == 0)
for _,b in ipairs(OSScanLinks.pages[1]) do
  assert(b[1] >= 2 and b[3] < 80 and b[2] >= 2 and b[4] <= 798)
end
""")

    def test_nearby_baselines_and_crowding_do_not_overlap(self):
        self.run_lua("""
for i=1,6 do
  OSScanLinks.place(1, 40, 400+i, true, 600, 800, 10, 8, 2, 10, 2)
end
for i,a in ipairs(OSScanLinks.pages[1]) do
  for j,b in ipairs(OSScanLinks.pages[1]) do
    if not (i == j) then
      assert(a[1] >= b[3]+2 or a[3]+2 <= b[1]
             or a[2] >= b[4]+2 or a[4]+2 <= b[2])
    end
  end
  assert(a[1] >= 2 and a[3] <= 598 and a[2] >= 2 and a[4] <= 798)
end
""")

    def test_physical_pages_and_opposite_margins_are_independent(self):
        self.run_lua("""
OSScanLinks.place(1, 80, 400, true, 600, 800, 10, 8, 2, 10, 2)
local x,y = OSScanLinks.place(2, 80, 400, true, 600, 800, 10, 8, 2, 10, 2)
assert(x == 0 and y == 0)
x,y = OSScanLinks.place(1, 520, 400, false, 600, 800, 10, 8, 2, 10, 2)
assert(x == 0 and y == 0)
""")

    def test_narrow_margin_uses_another_row(self):
        self.run_lua("""
OSScanLinks.place(1, 30, 400, true, 600, 800, 10, 8, 2, 10, 2)
local x,y = OSScanLinks.place(1, 30, 400, true, 600, 800, 10, 8, 2, 10, 2)
assert(x == 0 and math.abs(y) >= 12)
""")

    def test_crowded_markers_fail_before_leaving_nearby_text_rows(self):
        self.run_lua("""
local ok,message = pcall(function()
  for i=1,11 do
    OSScanLinks.place(1, 40, 400, true, 600, 800, 10, 8, 2, 10, 2, 370, 430)
  end
end)
assert(not ok and string.find(message, "Source%-link margin full"))
for _,b in ipairs(OSScanLinks.pages[1]) do assert(b[2]>=370 and b[4]<=430) end
""")

    def test_last_baseline_keeps_a_symbol_with_descender(self):
        self.run_lua("""
local baseline, maxdepth = 100, 5
local x,y = OSScanLinks.place(1, 80, baseline, true, 600, 800,
                              10, 8, 2, 10, 2, baseline-maxdepth, 700)
assert(x == 0 and y == 0)
""")

    def test_unknown_first_pass_does_not_reserve_a_lane(self):
        self.run_lua("""
local x,y = OSScanLinks.place(0, 80, 400, true, 600, 800, 10, 8, 2, 10, 2)
assert(x == 0 and y == 0 and next(OSScanLinks.pages) == nil)
x,y = OSScanLinks.place(1, 80, 0, true, 600, 800, 10, 8, 2, 10, 2)
assert(x == 0 and y == 0 and next(OSScanLinks.pages) == nil)
""")

    def test_insufficient_margin_fails_instead_of_clipping(self):
        self.run_lua("""
local ok,message = pcall(OSScanLinks.place, 1, 15, 400, true,
                        600, 800, 10, 8, 2, 10, 2)
assert(not ok and string.find(message, "Source%-link margin full"))
""")


@unittest.skipUnless(shutil.which("lualatex"), "requires LuaLaTeX")
class TestScanLinkPdf(unittest.TestCase):
    def test_same_line_margin_links_have_separate_click_targets(self):
        from pypdf import PdfReader

        from opensiddur.tests.exporter.stylesheet_helpers import transform
        for lang, words, numbered in [("en", "First short words.", False),
                                      ("he", "מלים ראשונות", False),
                                      ("he", "מלים ראשונות", True)]:
            with self.subTest(lang=lang, numbered=numbered), tempfile.TemporaryDirectory() as directory:
                xml = (f'<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:p="http://jewishliturgy.org/ns/processing" xml:lang="{lang}">'
                       '<tei:text><tei:body><tei:p>'
                       '<tei:pb p:scan-link="true" facs="https://example.org/scan/1"/>' + words +
                       '<tei:pb p:scan-link="true" facs="https://example.org/scan/2"/>' + words +
                       '</tei:p></tei:body></tei:text></tei:TEI>')
                tex = transform(xml, {"markers": {"scan_links": {"placement": "margin"}},
                                      "line_numbers": {"enabled": numbered}})
                root = Path(directory)
                (root/"book.tex").write_text(tex, encoding="utf-8")
                for _ in range(3):
                    run = subprocess.run(
                        ["lualatex", "-interaction=nonstopmode", "-halt-on-error", "book.tex"],
                        cwd=root, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stdout[-3000:])
                reader = PdfReader(root/"book.pdf")
                targets = []
                for page in reader.pages:
                    for item in page.get("/Annots", []):
                        item = item.get_object()
                        uri = item.get("/A", {}).get("/URI", "")
                        if uri.startswith("https://example.org/scan/"):
                            rectangle = list(map(float, item["/Rect"]))
                            self.assertGreaterEqual(rectangle[0], 0)
                            self.assertLessEqual(rectangle[2], float(page.mediabox.width))
                            self.assertGreaterEqual(rectangle[1], 0)
                            self.assertLessEqual(rectangle[3], float(page.mediabox.height))
                            self.assertGreaterEqual(rectangle[2]-rectangle[0], 8)
                            self.assertGreaterEqual(rectangle[3]-rectangle[1], 8)
                            targets.append((uri, rectangle))
                self.assertEqual([t[0] for t in targets],
                                 ["https://example.org/scan/1", "https://example.org/scan/2"])
                a, b = targets[0][1], targets[1][1]
                self.assertTrue(a[2] <= b[0] or b[2] <= a[0]
                                or a[3] <= b[1] or b[3] <= a[1], targets)
