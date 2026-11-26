"""Real compilation regressions for conditionally absent parallel ranges."""

import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.linear import ConditionalSettingEntry, LinearData
from opensiddur.exporter.refdb import ReferenceDatabase

T = "http://www.tei-c.org/ns/1.0"
J = "http://jewishliturgy.org/ns/jlptei/2"
P = "http://jewishliturgy.org/ns/processing"
ROOT = "urn:x-opensiddur:text:prayer:example"
V = "urn:x-opensiddur:text:bible:genesis/1/1"
S = "urn:x-opensiddur:text:poem:example/1"
NS = {"t": T, "j": J, "p": P}
FS = '<tei:fs type="opensiddur:variant"><tei:f name="urn:x-opensiddur:condition:synthetic_english_available"><tei:binary value="true"/></tei:f></tei:fs>'


def doc(body, lang="he", notes=""):
    return f'<tei:TEI xmlns:tei="{T}" xmlns:j="{J}" xml:lang="{lang}"><tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>Synthetic</tei:title></tei:titleStmt></tei:fileDesc></tei:teiHeader>{notes}<tei:text><tei:body>{body}</tei:body></tei:text></tei:TEI>'


def run(
    kind,
    available,
    note_kind,
    missing=False,
    whole_file=False,
    fallback=False,
    front=False,
    once=False,
):
    target = ROOT if kind == "root" else V if kind == "verse" else S
    unit = "verse" if kind != "stanza" else "stanza"
    marker = (
        "" if kind == "root" else f'<tei:milestone unit="{unit}" corresp="{target}"/>'
    )
    end = "" if kind == "root" else f'<tei:milestone unit="{unit}"/>'
    note_target = target
    he_notes = (
        f'<tei:standOff type="notes"><tei:note type="commentary" target="{note_target}"><tei:p>HE-PRIMARY-NOTE</tei:p></tei:note></tei:standOff>'
        if note_kind == "independent"
        else ""
    )
    cond = (
        f"<j:condition><j:all>{FS}</j:all></j:condition>"
        if note_kind == "conditional"
        else ""
    )
    en_notes = (
        f'<tei:standOff type="notes"><tei:note type="commentary" target="{note_target}">{cond}<tei:p>EN-{note_kind.upper()}-NOTE</tei:p></tei:note></tei:standOff>'
        if note_kind != "none"
        else ""
    )
    he = doc(
        f'<tei:div corresp="{ROOT}"><tei:p>{marker}<tei:pb n="1" facs="https://example.org/he/1"/>PRIMARY-WORDS{end}</tei:p></tei:div>',
        notes=he_notes,
    )
    en_root = ROOT if not missing else ROOT + "/unrelated"
    enmarker = marker if not missing else ""
    enend = end if not missing else ""
    en = doc(
        f'<tei:div corresp="{en_root}"><j:conditional xml:id="available"><j:all>{FS}</j:all></j:conditional><tei:p>{enmarker}<tei:pb n="1" facs="https://example.org/en/1"/>ENGLISH-WORDS{enend}</tei:p><j:endConditional target="#available"/></tei:div>',
        "en",
        en_notes,
    )
    if front:
        en = en.replace(
            "<tei:body>",
            "<tei:front><tei:p>EN-FRONT-ONLY</tei:p></tei:front><tei:body>",
        )
    declare = FS.replace('value="true"', f'value="{str(available).lower()}"')
    spine = doc(
        f'<tei:div><j:declare xml:id="context">{declare}</j:declare><j:transclude target="{target}" type="external"/><j:endDeclare target="#context"/></tei:div>'
    )
    with tempfile.TemporaryDirectory(prefix="empty-counterpart-") as tmp:
        tmp = Path(tmp)
        db = ReferenceDatabase(tmp / "refs.sqlite")
        for project, content in [
            ("he", he),
            ("en", en),
            ("spine", spine),
            (
                "other",
                doc(
                    f'<tei:div corresp="{ROOT}"><tei:p>{marker}FALLBACK-WORDS{end}</tei:p></tei:div>',
                    "en",
                ),
            ),
        ]:
            d = tmp / project
            d.mkdir()
            p = d / "text.xml"
            p.write_text(content)
            db.index_file(p, project, "text.xml")
        ld = LinearData(
            project_priority=["he"],
            instruction_priority=["he"],
            parallel_projects=["en", "other"] if fallback else ["en"],
            annotation_projects=["he", "en"],
        )
        if once:
            ld.annotation_print_once_types = {"commentary"}
        if whole_file:
            ld.conditional_settings.append(
                ConditionalSettingEntry(
                    declare_id="settings",
                    fs_type="opensiddur:variant",
                    feature_name="urn:x-opensiddur:condition:synthetic_english_available",
                    value=available,
                    source="init",
                )
            )
        ld.xml_cache.base_path = tmp
        result = ExternalCompilerProcessor(
            "he" if whole_file else "spine",
            "text.xml",
            linear_data=ld,
            reference_database=db,
        ).process()
        out = etree.Element("output")
        for x in result:
            out.append(x)
        xml = etree.tostring(out, encoding="unicode")
        text = " ".join("".join(out.itertext()).split())
        rows = out.xpath(".//p:parallel", namespaces=NS)
        cols = out.xpath(".//p:parallelItem", namespaces=NS)
        result = {
            "kind": kind,
            "available": available,
            "notes": note_kind,
            "missing": missing,
            "text": text,
            "rows": len(rows),
            "columns": len(cols),
            "parallel_blocks": len(out.xpath(".//p:parallel", namespaces=NS)),
            "page_urls": out.xpath(".//t:pb/@facs", namespaces=NS),
            "output_xml": xml,
        }
        db.conn.close()
        return result


class TestConditionalCounterpart(unittest.TestCase):
    def test_false_counterpart_has_missing_counterpart_fallback(self):
        for kind in ("root", "verse", "stanza"):
            for notes in ("none", "conditional", "independent"):
                with self.subTest(kind=kind, notes=notes):
                    absent = run(kind, False, notes)
                    missing = run(kind, False, notes, missing=True)
                    self.assertEqual(absent["text"], missing["text"])
                    self.assertEqual(absent["page_urls"], ["https://example.org/he/1"])
                    self.assertEqual(absent["parallel_blocks"], 0)
                    self.assertIn("PRIMARY-WORDS", absent["text"])
                    if notes == "independent":
                        self.assertIn("HE-PRIMARY-NOTE", absent["text"])
                        self.assertIn("EN-INDEPENDENT-NOTE", absent["text"])
                    else:
                        self.assertNotIn("EN-CONDITIONAL-NOTE", absent["text"])

    def test_available_counterpart_retains_text_pages_and_notes(self):
        for kind in ("root", "verse", "stanza"):
            for notes in ("none", "conditional", "independent"):
                with self.subTest(kind=kind, notes=notes):
                    present = run(kind, True, notes)
                    self.assertIn("PRIMARY-WORDS", present["text"])
                    self.assertIn("ENGLISH-WORDS", present["text"])
                    self.assertGreater(present["parallel_blocks"], 0)
                    self.assertEqual(
                        present["page_urls"],
                        ["https://example.org/he/1", "https://example.org/en/1"],
                    )
                    if notes != "none":
                        self.assertIn(f"EN-{notes.upper()}-NOTE", present["text"])

    def test_whole_file_counterpart_also_falls_back(self):
        for notes in ("none", "conditional", "independent"):
            with self.subTest(notes=notes):
                absent = run("root", False, notes, whole_file=True)
                missing = run("root", False, notes, missing=True, whole_file=True)
                self.assertEqual(absent["text"], missing["text"])
                self.assertEqual(absent["parallel_blocks"], 0)
                present = run("root", True, notes, whole_file=True)
                self.assertIn("ENGLISH-WORDS", present["text"])
                self.assertGreater(present["parallel_blocks"], 0)

    def test_empty_candidate_does_not_hide_next_configured_project(self):
        for kind, whole_file in (
            ("root", False),
            ("verse", False),
            ("stanza", False),
            ("root", True),
        ):
            with self.subTest(kind=kind, whole_file=whole_file):
                result = run(
                    kind, False, "independent", fallback=True, whole_file=whole_file
                )
                self.assertIn("FALLBACK-WORDS", result["text"])
                self.assertIn("EN-INDEPENDENT-NOTE", result["text"])
                self.assertNotIn("ENGLISH-WORDS", result["text"])

    def test_front_matter_cannot_make_an_empty_body_a_counterpart(self):
        absent = run("root", False, "independent", whole_file=True, front=True)
        missing = run("root", False, "independent", whole_file=True, missing=True)
        self.assertEqual(absent["text"], missing["text"])
        self.assertEqual(absent["parallel_blocks"], 0)

    def test_discarded_counterpart_does_not_claim_print_once_notes(self):
        for whole_file in (False, True):
            with self.subTest(whole_file=whole_file):
                absent = run(
                    "root", False, "independent", whole_file=whole_file, once=True
                )
                self.assertEqual(absent["text"].count("EN-INDEPENDENT-NOTE"), 1)
                missing = run(
                    "root",
                    False,
                    "independent",
                    whole_file=whole_file,
                    once=True,
                    missing=True,
                )
                self.assertEqual(absent["text"], missing["text"])
