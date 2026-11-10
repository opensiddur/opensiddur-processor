"""Typography must reach the HTML renderer and the browser's computed styles."""

import html
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from opensiddur.exporter.html.css import STYLE_SELECTORS, style_css, typography_css, xslt_parameters
from opensiddur.exporter.html.html import build_book
from opensiddur.exporter.typography import TypographyConfig, Styles
from opensiddur.tests.exporter.test_html_book import INDEX, _compiled, _render

CHROME = shutil.which("google-chrome") or shutil.which("chromium")


class TestHtmlTypography(unittest.TestCase):
    def config(self, data):
        return TypographyConfig.model_validate(data, context={"resolve_fonts": False})

    def test_character_highlights_keep_text_and_reader_style_classes(self):
        root = _render('<tei:p>שְׁמַ<tei:c rend="large">ע</tei:c> '
                       '<tei:c rend="small superscript">ד</tei:c></tei:p>')
        ns = {"h": "http://www.w3.org/1999/xhtml"}
        characters = root.xpath('//h:span[contains(concat(" ", @class, " "), " c ")]', namespaces=ns)
        self.assertEqual([c.text for c in characters], ['ע', 'ד'])
        self.assertIn('rend-large', characters[0].get('class').split())
        self.assertTrue({'rend-small', 'rend-superscript'} <= set(characters[1].get('class').split()))

    def test_every_text_role_has_a_selector_except_print_line_numbers(self):
        self.assertEqual(set(STYLE_SELECTORS), set(Styles.model_fields) - {"line_number"})

    def test_the_highlight_and_qere_looks_reader_css_had_are_the_defaults(self):
        css = typography_css(self.config({}))
        for selector, declaration in (
            (".rend-italic", "font-style: italic;"),
            (".rend-bold", "font-weight: bold;"),
            (".rend-small-caps, .rend-smallcaps", "font-variant: small-caps;"),
            (".read", "font-style: italic;"),
        ):
            with self.subTest(selector=selector):
                rule = next(line for line in css.splitlines()
                            if line.startswith(f":is(.os-book, .os-about) :is({selector}) {{"))
                self.assertIn(declaration, rule)
        self.assertNotIn(":is(.foreign)", css)

    def test_a_superscript_size_is_the_raised_texts_size(self):
        """As in the PDF: reader.css's reduction is cancelled rather than applied to it."""
        rule = next(r for r in style_css(self.config({"styles": {"highlight_superscript": {"size": "small"}}}))
                    if ".rend-sup" in r)
        self.assertIn("--os-rend-scale: 1;", rule)
        self.assertFalse([r for r in style_css(self.config({})) if ".rend-sup" in r])

    def test_all_style_attributes_are_emitted_for_each_applicable_role(self):
        for role in STYLE_SELECTORS:
            with self.subTest(role=role):
                style = {
                    "font": "display", "size": "9pt", "weight": "normal",
                    "style": "italic", "variant": "small-caps",
                }
                config = self.config({
                    "fonts": {"display": [{"name": "Synthetic Display", "normal_size": 17}]},
                    "styles": {role: style},
                })
                selector = STYLE_SELECTORS[role]
                scoped = selector if role == "body" else f":is(.os-book, .os-about) :is({selector})"
                css = next(rule for rule in style_css(config) if rule.startswith(scoped + " {"))
                self.assertIn('--os-role-family: "Synthetic Display", serif;', css)
                self.assertIn("--os-role-normal: var(--normal-display);", css)
                self.assertIn("--normal-display: 17pt;", typography_css(config))
                self.assertIn("--os-absolute-size: 9pt;", css)
                self.assertIn("font-weight: normal;", css)
                self.assertIn("font-style: italic;", css)
                self.assertIn("font-variant: small-caps;", css)

    def test_paragraph_list_block_style_and_parallel_geometry(self):
        config = self.config({
            "paragraphs": {"indent": "13pt", "spacing": "7pt", "line_spacing": 1.5, "alignment": "right"},
            "lists": {"item_indent": "14pt"},
            "styles": {"title_main": {"align": "left", "space_before": "3pt", "space_after": "4pt"}},
            "parallel": {"column_width": "40%", "column_position": "left"},
        })
        css = typography_css(config)
        for value in (
            "--paragraph-indent: 13pt", "--paragraph-spacing: 7pt",
            "--line-spacing: 2.025", "--text-align: right", "--list-indent: 14pt",
            "--os-role-align: left", "margin-block-start: 3pt",
            "margin-block-end: 4pt", "repeat(2, 40%)", "justify-content: left",
        ):
            self.assertIn(value, css)

    def test_interleaved_translation_and_note_anchor_settings(self):
        config = self.config({
            "parallel": {"layout": "interleaved", "interleaved": {
                "translation_size": "8pt", "translation_indent": "17pt", "spacing": "19pt",
            }},
            "notes": {"anchor": "inline"},
        })
        css = typography_css(config)
        for value in ("grid-template-columns: 1fr", "row-gap: 19pt", "margin-inline: 17pt",
                      "--os-absolute-size: 8pt", ".note-ref { vertical-align: baseline; }"):
            self.assertIn(value, css)
        css = typography_css(self.config({"notes": {"anchor": "interlinear"}}))
        self.assertIn(".note-ref { position: absolute;", css)

    def test_note_marks_and_suppression_reach_xslt(self):
        for kind, expected in (("numeric", "1"), ("alpha", "a"), ("roman", "i"), ("symbol", "*")):
            with self.subTest(kind=kind):
                main = _render("<tei:p>Text<tei:note>A note</tei:note></tei:p>",
                               **xslt_parameters(self.config({"notes": {"mark": kind}})))
                mark = main.xpath("//*[local-name()='button' and @class='note-ref']")[0]
                self.assertEqual(mark.text, expected)
        main = _render("<tei:p>Text<tei:note>A note</tei:note></tei:p>",
                       **xslt_parameters(self.config({"notes": {"placement": "none"}})))
        self.assertNotIn("A note", "".join(main.itertext()))

    @unittest.skipUnless(CHROME, "Chrome or Chromium is required for computed-style checks")
    def test_browser_font_language_sizes_and_styles(self):
        settings = {
            "book": {"project": "proj", "file_name": "index.xml"},
            "distribution": {"notice": "none", "back_notice": "none"},
            "typography": {
                "page": {"base_font_size": "12pt"},
                "fonts": {
                    "latin": [{"name": "DejaVu Sans", "normal_size": 10}],
                    "hebrew": [{"name": "DejaVu Serif", "normal_size": 15}],
                    "display": [{"name": "DejaVu Sans Mono", "normal_size": 18}],
                },
                "paragraphs": {"indent": "6pt", "spacing": "8pt", "line_spacing": 1.5, "alignment": "left"},
                "lists": {"item_indent": "9pt"},
                "styles": {
                    "heading1": {"font": "display", "size": "large", "weight": "bold", "align": "right"},
                    "heading2": {"size": "9pt", "style": "italic"},
                    "heading_translation": {"font": "display", "size": "small"},
                    "title_main": {"font": "display", "size": "14pt", "align": "left",
                                   "space_before": "3pt", "space_after": "4pt"},
                    "list_label": {"variant": "small-caps"},
                },
                "table_of_contents": {"depth": 2},
            },
        }
        body = '''
<tei:p corresp="he">Hebrew <tei:foreign xml:lang="en" corresp="en">English
 <tei:foreign xml:lang="he" corresp="nested-he">Hebrew</tei:foreign>
 <tei:foreign xml:lang="he-Latn" corresp="translit">shalom</tei:foreign>
</tei:foreign><tei:seg corresp="restored">Hebrew</tei:seg></tei:p>
<tei:div><tei:head p:heading-level="1" corresp="heading">Heading</tei:head>
 <tei:head p:heading-level="1" xml:lang="en" corresp="alt-heading">Translation</tei:head>
 <tei:p>Body</tei:p></tei:div>
<tei:div><tei:head p:heading-level="2" corresp="absolute">Heading
 <tei:foreign xml:lang="en" corresp="absolute-en">English</tei:foreign></tei:head></tei:div>
<tei:list><tei:label corresp="label">Label</tei:label><tei:item corresp="item">Item</tei:item></tei:list>
'''
        script = """
<script>
const proof = {};
for (const id of ["he", "en", "nested-he", "translit", "restored", "heading", "alt-heading", "absolute", "absolute-en", "label", "item", "title"]) {
  const style = getComputedStyle(document.getElementById(id));
  proof[id] = Object.fromEntries(["fontFamily","fontSize","fontWeight","fontStyle","fontVariant","textIndent","marginTop","marginBottom","marginLeft","lineHeight","textAlign"].map(key => [key, style[key]]));
}
const result = document.createElement("pre");
result.id = "typography-proof";
result.textContent = JSON.stringify(proof);
document.body.append(result);
</script>
"""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "proj").mkdir()
            (base / "proj/index.xml").write_text(INDEX)
            source = base / "compiled.xml"
            compiled = _compiled(body, lang="he").replace(
                b"<tei:text><tei:body>",
                b'<tei:text><tei:front><tei:titlePage><tei:docTitle>'
                b'<tei:titlePart type="main" corresp="title">Title</tei:titlePart>'
                b'</tei:docTitle></tei:titlePage></tei:front><tei:body>',
            )
            source.write_bytes(compiled)
            config = base / "settings.yaml"
            config.write_text(yaml.safe_dump(settings))
            page = build_book(source, config, base)
            self.assertIn('"contentsDepth":2', page)
            output = base / "book.html"
            output.write_text(page.replace("</body>", script + "</body>"))
            command = [
                CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", f"--user-data-dir={base / 'profile'}",
                "--dump-dom", output.as_uri(),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            match = re.search(r'<pre id="typography-proof">(.*?)</pre>', result.stdout)
            self.assertIsNotNone(match, result.stderr[-2000:])
            proof = json.loads(html.unescape(match[1]))
        for key in ("he", "nested-he", "restored"):
            self.assertIn("DejaVu Serif", proof[key]["fontFamily"])
            self.assertAlmostEqual(float(proof[key]["fontSize"].rstrip("px")), 20, places=3)
        for key in ("en", "translit"):
            self.assertIn("DejaVu Sans", proof[key]["fontFamily"])
            self.assertAlmostEqual(float(proof[key]["fontSize"].rstrip("px")), 10 * 4 / 3, places=3)
        self.assertIn("DejaVu Sans Mono", proof["heading"]["fontFamily"])
        self.assertAlmostEqual(float(proof["heading"]["fontSize"].rstrip("px")), 18 * 1.2 * 4 / 3, places=3)
        self.assertEqual(proof["heading"]["fontWeight"], "700")
        self.assertEqual(proof["heading"]["textAlign"], "right")
        self.assertIn("DejaVu Sans Mono", proof["alt-heading"]["fontFamily"])
        self.assertAlmostEqual(float(proof["alt-heading"]["fontSize"].rstrip("px")), 18 / 1.2 * 4 / 3, places=3)
        self.assertEqual(proof["title"]["textAlign"], "left")
        self.assertEqual(proof["title"]["marginTop"], "4px")
        self.assertAlmostEqual(float(proof["title"]["marginBottom"].rstrip("px")), 4 * 4 / 3, places=3)
        self.assertAlmostEqual(float(proof["title"]["fontSize"].rstrip("px")), 14 * 4 / 3, places=3)
        for key in ("absolute", "absolute-en"):
            self.assertEqual(proof[key]["fontSize"], "12px")
            self.assertEqual(proof[key]["fontStyle"], "italic")
        self.assertEqual(proof["he"]["textIndent"], "8px")
        self.assertAlmostEqual(float(proof["he"]["marginBottom"].rstrip("px")), 8 * 4 / 3, places=3)
        self.assertAlmostEqual(float(proof["he"]["lineHeight"].rstrip("px")), 20 * 2.025, places=3)
        self.assertEqual(proof["item"]["marginLeft"], "12px")
        self.assertEqual(proof["label"]["fontVariant"], "small-caps")
