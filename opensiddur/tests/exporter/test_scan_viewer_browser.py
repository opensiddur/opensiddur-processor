"""The scan viewer in a browser: opening, zooming, panning, layouts and closing.

reader.js runs only in a page, so the book is built and opened in headless Chrome, and a script
added to it drives the viewer and writes down what it saw. The scan is a data: image, so
nothing is fetched. Skipped without Chrome or Chromium.
"""

import base64
import html
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

from opensiddur.exporter.html.html import build_book
from opensiddur.tests.exporter.test_html_book import INDEX, _compiled
from opensiddur.tests.exporter.test_html_typography import CHROME


def _png(width: int, height: int) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 180, 150)).save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# Drives the viewer and records what it sees after each step, in <pre id="viewer-proof">.
_SCRIPT = """
<script>
window.addEventListener("load", function () {
  var proof = {};
  var link = document.querySelector("a.scan-link[data-scan-view]");
  var start = location.href;
  function state() { return window.OSScanViewer.state(); }
  function done() {
    proof.navigated = location.href !== start;
    var pre = document.createElement("pre");
    pre.id = "viewer-proof";
    pre.textContent = JSON.stringify(proof);
    document.body.appendChild(pre);
  }
  link.click();
  setTimeout(function () {
    proof.opened = state();
    proof.openedClass = document.body.className;
    window.OSScanViewer.zoomBy(1.25);
    proof.zoomed = state();
    window.OSScanViewer.panBy(-30, -20);
    proof.panned = state();
    window.OSScanViewer.zoomBy(1000);
    proof.maxed = state();
    window.OSScanViewer.fit();
    proof.fitted = state();
    proof.layouts = {};
    ["full", "horizontal", "vertical"].forEach(function (name) {
      window.OSScanViewer.setLayout(name, true);
      proof.layouts[name] = document.body.className;
    });
    proof.remembered = localStorage.getItem("opensiddur:" + %(book_id)s + ":viewer");
    var viewer = document.querySelector(".os-viewer");
    viewer.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    proof.closed = state();
    proof.closedClass = document.body.className;
    done();
  }, 600);
});
</script>
"""


@unittest.skipUnless(CHROME, "Chrome or Chromium is required to drive the scan viewer")
class TestScanViewerInABrowser(unittest.TestCase):

    def _run(self, viewer: str) -> dict:
        image = _png(400, 600)
        settings = {
            "book": {"project": "proj", "file_name": "index.xml"},
            "distribution": {"notice": "none", "back_notice": "none"},
            "typography": {"markers": {"scan_links": {"placement": "margin"}}},
            "electronic": {"scan_viewer": viewer},
        }
        body = (f'<tei:p><tei:pb n="7" ed="1" facs="{image}"/>The words of the page.</tei:p>'
                + "<tei:p>More words.</tei:p>" * 40)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "proj").mkdir()
            (base / "proj/index.xml").write_text(INDEX)
            source = base / "compiled.xml"
            source.write_bytes(_compiled(body, lang="he"))
            config = base / "settings.yaml"
            config.write_text(yaml.safe_dump(settings))
            page = build_book(source, config, base)
            book = json.loads(re.search(
                r'<script type="application/json" id="os-book">(.*?)</script>', page, re.S)[1])
            script = _SCRIPT % {"book_id": json.dumps(book["id"])}
            output = base / "book.html"
            output.write_text(page.replace("</body>", script + "</body>"))
            result = subprocess.run(
                [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
                 "--disable-dev-shm-usage", f"--user-data-dir={base / 'profile'}",
                 "--window-size=1200,800", "--virtual-time-budget=5000",
                 "--dump-dom", output.as_uri()],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            match = re.search(r'<pre id="viewer-proof">(.*?)</pre>', result.stdout)
            self.assertIsNotNone(match, result.stderr[-2000:])
            return json.loads(html.unescape(match[1]))

    def test_the_viewer_opens_zooms_pans_changes_layout_and_closes(self):
        proof = self._run("vertical")
        opened = proof["opened"]
        self.assertTrue(opened["open"])
        self.assertEqual("image", opened["kind"])
        self.assertTrue(opened["src"].startswith("data:image/png"))
        self.assertIn("os-viewing-vertical", proof["openedClass"])
        self.assertFalse(proof["navigated"], "the link opened the viewer, not the page")
        # Opened fitted: the whole page in view.
        self.assertAlmostEqual(opened["scale"], opened["fit"])
        self.assertAlmostEqual(proof["zoomed"]["scale"], opened["fit"] * 1.25)
        self.assertAlmostEqual(proof["panned"]["x"], proof["zoomed"]["x"] - 30)
        self.assertAlmostEqual(proof["panned"]["y"], proof["zoomed"]["y"] - 20)
        self.assertAlmostEqual(proof["maxed"]["scale"], opened["fit"] * 8)
        self.assertAlmostEqual(proof["fitted"]["scale"], opened["fit"])
        for name in ("full", "horizontal", "vertical"):
            self.assertIn(f"os-viewing-{name}", proof["layouts"][name])
        self.assertEqual({"layout": "vertical"}, json.loads(proof["remembered"]))
        self.assertFalse(proof["closed"]["open"])
        self.assertNotIn("os-viewing", proof["closedClass"])

    def test_the_viewer_starts_in_the_books_layout(self):
        proof = self._run("horizontal")
        self.assertEqual("horizontal", proof["opened"]["layout"])
        self.assertIn("os-viewing-horizontal", proof["openedClass"])


if __name__ == "__main__":
    unittest.main()
