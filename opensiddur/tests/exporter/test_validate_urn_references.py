import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lxml import etree

from opensiddur.exporter.refdb import ReferenceDatabase
from opensiddur.exporter.validate_urn_references import (
    UnresolvableUrnReference,
    _format_failure,
    find_coarsened_urn_references,
    main,
    validate_project_contributor_references,
    validate_project_urn_references,
)


TEI_NS = "http://www.tei-c.org/ns/1.0"
JLPTEI_NS = "http://jewishliturgy.org/ns/jlptei/2"
NSMAP = {"tei": TEI_NS, "j": JLPTEI_NS}


def _write_project_xml(base: Path, project: str, filename: str, root: etree._Element) -> Path:
    project_path = base / project
    project_path.mkdir(parents=True, exist_ok=True)
    xml_path = project_path / filename
    etree.ElementTree(root).write(str(xml_path), encoding="utf-8", xml_declaration=True)
    return xml_path


def _add_urn_mapping(db_path: Path, project: str, file_name: str, urn: str) -> None:
    db = ReferenceDatabase(db_path)
    try:
        element = etree.Element(f"{{{TEI_NS}}}milestone")
        element.set("corresp", urn)
        db.add_urn_mapping(project, file_name, element)
    finally:
        db.close()


class TestValidateUrnReferences(unittest.TestCase):
    def test_validates_ptr_and_ref_targets(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(body, f"{{{TEI_NS}}}ptr", target="urn:x-opensiddur:test:doc1")
            etree.SubElement(body, f"{{{TEI_NS}}}ref", target="urn:x-opensiddur:test:doc2/1")

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1")
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc2/1")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
                index_before_validate=False,
            )
            self.assertEqual(failures, [])

    def test_reports_unresolvable_urns(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(body, f"{{{TEI_NS}}}ptr", target="urn:x-opensiddur:test:missing")

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
                index_before_validate=False,
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].file_name, "a.xml")
            self.assertEqual(failures[0].attribute_name, "target")

    def test_missing_optional_page_destination_does_not_hide_required_references(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            root = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            optional = etree.SubElement(root, f"{{{TEI_NS}}}seg", type="optional-page-reference")
            foreign = etree.SubElement(optional, f"{{{TEI_NS}}}foreign")
            prefix = "urn:x-opensiddur:text:prayer:"
            etree.SubElement(foreign, f"{{{TEI_NS}}}ref", type="page", target=prefix+"optional@proj1")
            etree.SubElement(optional, f"{{{TEI_NS}}}ref", target=prefix+"ordinary@proj1")
            etree.SubElement(optional, f"{{{JLPTEI_NS}}}transclude", target=prefix+"prayer@proj1")
            etree.SubElement(root, f"{{{TEI_NS}}}ref", type="page", target=prefix+"required@proj1")
            _write_project_xml(base, "proj1", "a.xml", root)
            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()
            failures = validate_project_urn_references(
                "proj1", project_directory=base, reference_db_path=db_path)
            self.assertEqual([f.urn for f in failures], [
                prefix+"ordinary@proj1", prefix+"prayer@proj1", prefix+"required@proj1"])

    def test_optional_page_reference_still_reports_a_malformed_range(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            root = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            optional = etree.SubElement(root, f"{{{TEI_NS}}}seg", type="optional-page-reference")
            etree.SubElement(optional, f"{{{TEI_NS}}}ref", type="page",
                             target="urn:x-opensiddur:text:prayer:bad@proj1")
            _write_project_xml(base, "proj1", "a.xml", root)
            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()
            with patch("opensiddur.exporter.validate_urn_references.UrnResolver.resolve_range",
                       side_effect=ValueError("malformed range")):
                failures = validate_project_urn_references(
                    "proj1", project_directory=base, reference_db_path=db_path)
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].reason, "malformed range")

    def test_optional_page_reference_with_existing_destination_is_valid(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            root = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            optional = etree.SubElement(root, f"{{{TEI_NS}}}seg", type="optional-page-reference")
            target = "urn:x-opensiddur:text:prayer:existing"
            etree.SubElement(optional, f"{{{TEI_NS}}}ref", type="page", target=target+"@proj1")
            _write_project_xml(base, "proj1", "a.xml", root)
            db_path = base / "ref.db"
            _add_urn_mapping(db_path, "proj1", "a.xml", target)
            self.assertEqual(validate_project_urn_references(
                "proj1", project_directory=base, reference_db_path=db_path), [])

    def test_raises_when_project_directory_missing(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            with self.assertRaises(ValueError) as ctx:
                validate_project_urn_references(
                    "missing_project",
                    project_directory=base,
                    reference_db_path=db_path,
                )
            self.assertIn("Project directory does not exist", str(ctx.exception))

    def test_skips_non_urn_targets(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(body, f"{{{TEI_NS}}}ptr", target="http://example.com/doc")
            etree.SubElement(body, f"{{{TEI_NS}}}ref", target="local/path.xml")

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(failures, [])

    def test_checks_target_on_elements_other_than_ptr_ref_transclude(self):
        """@target/@targetEnd are checked wherever they appear, not just on tei:ptr, tei:ref,
        and j:transclude -- a pointer on some other element must not be silently skipped."""
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(body, f"{{{TEI_NS}}}note", target="urn:x-opensiddur:test:missing")

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project, project_directory=base, reference_db_path=db_path
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].urn, "urn:x-opensiddur:test:missing")

    def test_skips_same_file_id_targets_regardless_of_element(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            etree.SubElement(xml, f"{{{JLPTEI_NS}}}endConditional", target="#cond_x")

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project, project_directory=base, reference_db_path=db_path
            )
            self.assertEqual(failures, [])

    def test_index_before_validate(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            div = etree.SubElement(xml, f"{{{TEI_NS}}}div")
            div.set("corresp", "urn:x-opensiddur:test:doc1")

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
                index_before_validate=True,
            )
            self.assertEqual(failures, [])

    def test_validates_resolvable_transclude(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(failures, [])

    def test_validates_transclude_with_target_end_in_same_project(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1/1",
                targetEnd="urn:x-opensiddur:test:doc1/2",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/1")
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/2")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(failures, [])

    def test_reports_unresolvable_transclude_target(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:missing",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].attribute_name, "target")
            self.assertEqual(failures[0].urn, "urn:x-opensiddur:test:missing")

    def test_reports_unresolvable_transclude_target_end(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1/1",
                targetEnd="urn:x-opensiddur:test:doc1/missing",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/1")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].attribute_name, "targetEnd")

    def test_reports_transclude_target_end_in_wrong_project(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1/1",
                targetEnd="urn:x-opensiddur:test:doc1/2",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/1")
            _add_urn_mapping(db_path, "proj2", "b.xml", "urn:x-opensiddur:test:doc1/1")
            _add_urn_mapping(db_path, "proj2", "b.xml", "urn:x-opensiddur:test:doc1/2")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].attribute_name, "targetEnd")

    def test_validates_resolvable_ranged_transclude_target(self):
        """A @target that is itself a ranged URN (e.g. a haftarah-style reading) must resolve
        without crashing when both ends of the range are indexed (issue #100)."""
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1/9/7-9/15",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/9/7")
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/9/15")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(failures, [])

    def test_reports_unresolvable_ranged_transclude_target(self):
        """A ranged @target where only the start half is indexed must be reported, not crash."""
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1/9/7-9/15",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/9/7")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].attribute_name, "target")
            self.assertEqual(failures[0].urn, "urn:x-opensiddur:test:doc1/9/7-9/15")

    def test_reports_ranged_transclude_target_end(self):
        """@targetEnd must name a single point, not a range: a ranged targetEnd is reported as
        invalid data rather than silently accepted or crashing."""
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body,
                f"{{{JLPTEI_NS}}}transclude",
                target="urn:x-opensiddur:test:doc1/1",
                targetEnd="urn:x-opensiddur:test:doc1/2-3",
            )

            _write_project_xml(base, project, "a.xml", xml)

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/1")
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/2")
            _add_urn_mapping(db_path, project, "a.xml", "urn:x-opensiddur:test:doc1/3")

            failures = validate_project_urn_references(
                project,
                project_directory=base,
                reference_db_path=db_path,
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].attribute_name, "targetEnd")
            self.assertEqual(failures[0].urn, "urn:x-opensiddur:test:doc1/2-3")

    def test_validates_resolvable_file_fragment_ref(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            index_xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            bibl = etree.SubElement(index_xml, f"{{{TEI_NS}}}bibl")
            bibl.set("{http://www.w3.org/XML/1998/namespace}id", "project_source_bibl")
            _write_project_xml(base, project, "index.xml", index_xml)

            leaf_xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            etree.SubElement(
                leaf_xml, f"{{{TEI_NS}}}ptr", target=f"/{project}/index#project_source_bibl"
            )
            _write_project_xml(base, project, "leaf.xml", leaf_xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project, project_directory=base, reference_db_path=db_path, check_urns=False
            )
            self.assertEqual(failures, [])

    def test_reports_unresolvable_file_fragment_ref(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            index_xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            _write_project_xml(base, project, "index.xml", index_xml)

            leaf_xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            etree.SubElement(
                leaf_xml, f"{{{TEI_NS}}}ptr", target=f"/{project}/index#project_source_bibl"
            )
            _write_project_xml(base, project, "leaf.xml", leaf_xml)

            db_path = base / "ref.db"
            ReferenceDatabase(db_path).close()

            failures = validate_project_urn_references(
                project, project_directory=base, reference_db_path=db_path, check_urns=False
            )
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].file_name, "leaf.xml")
            self.assertEqual(
                failures[0].urn, f"/{project}/index#project_source_bibl"
            )

    def test_check_urns_false_ignores_urn_targets_without_touching_refdb(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project = "proj1"

            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            etree.SubElement(xml, f"{{{TEI_NS}}}ptr", target="urn:x-opensiddur:test:missing")
            _write_project_xml(base, project, "a.xml", xml)

            # No reference.db is ever created at this path -- check_urns=False must not open it.
            db_path = base / "does-not-exist" / "ref.db"

            failures = validate_project_urn_references(
                project, project_directory=base, reference_db_path=db_path, check_urns=False
            )
            self.assertEqual(failures, [])

    def test_format_failure(self):
        failure = UnresolvableUrnReference(
            project="proj1",
            file_name="a.xml",
            element_path="/TEI/text/body/ptr[1]",
            attribute_name="target",
            urn="urn:x-opensiddur:test:missing",
        )
        self.assertEqual(
            _format_failure(failure),
            "proj1/a.xml: /TEI/text/body/ptr[1] @target=urn:x-opensiddur:test:missing",
        )



class TestCoarsenedUrnReferences(unittest.TestCase):
    """A reference to a division a project does not carry still resolves, one level up."""

    VERSE = "urn:x-opensiddur:text:bible:genesis/1/31"

    def _project_referring_to(self, base: Path, target: str) -> Path:
        xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
        text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
        body = etree.SubElement(text, f"{{{TEI_NS}}}body")
        etree.SubElement(body, f"{{{JLPTEI_NS}}}transclude", target=target)
        return _write_project_xml(base, "humash", "a.xml", xml)

    def test_reports_a_half_verse_no_project_carries(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            self._project_referring_to(base, f"{self.VERSE}/b")

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, "jps1917", "genesis.xml", self.VERSE)

            coarsened = find_coarsened_urn_references(
                "humash", project_directory=base, reference_db_path=db_path
            )

            self.assertEqual(len(coarsened), 1)
            self.assertEqual(coarsened[0].urn, f"{self.VERSE}/b")
            self.assertEqual(coarsened[0].resolves_as, self.VERSE)

    def test_says_nothing_when_the_reference_resolves_as_written(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            self._project_referring_to(base, f"{self.VERSE}/b")

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, "mam", "genesis.xml", f"{self.VERSE}/b")

            self.assertEqual(
                find_coarsened_urn_references(
                    "humash", project_directory=base, reference_db_path=db_path
                ),
                [],
            )

    def test_says_nothing_when_neither_the_reference_nor_its_container_resolves(self):
        """That is an unresolvable reference, which the other check reports."""
        with TemporaryDirectory() as td:
            base = Path(td)
            self._project_referring_to(base, f"{self.VERSE}/b")

            db_path = base / "ref.db"
            _add_urn_mapping(db_path, "mam", "exodus.xml", "urn:x-opensiddur:text:bible:exodus/1/1")

            self.assertEqual(
                find_coarsened_urn_references(
                    "humash", project_directory=base, reference_db_path=db_path
                ),
                [],
            )

    def test_reports_a_range_whose_ends_are_both_below_the_verse(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            self._project_referring_to(
                base, "urn:x-opensiddur:text:bible:nahum/2/2/b-2/3/a"
            )

            db_path = base / "ref.db"
            for urn in ("urn:x-opensiddur:text:bible:nahum/2/2",
                        "urn:x-opensiddur:text:bible:nahum/2/3"):
                _add_urn_mapping(db_path, "jps1917", "nahum.xml", urn)

            coarsened = find_coarsened_urn_references(
                "humash", project_directory=base, reference_db_path=db_path
            )

            self.assertEqual(len(coarsened), 1)
            self.assertEqual(
                coarsened[0].resolves_as, "urn:x-opensiddur:text:bible:nahum/2/2-/2/3"
            )


if __name__ == "__main__":
    unittest.main()


CONTRIBUTOR = "urn:x-opensiddur:contributor:"


def _write_registry(base: Path, *urns: str) -> Path:
    """A registry directory holding exactly ``urns``, so no test reads specs/."""
    directory = base / "registry"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "contributor.jsonl").write_text(
        "".join(
            json.dumps({"urn": urn, "status": "canonical", "label_en": "Someone"}) + "\n"
            for urn in urns
        ),
        encoding="utf-8",
    )
    return directory


def _write_credits(base: Path, project: str, filename: str, *refs: str) -> Path:
    """A project file crediting ``refs``, one tei:respStmt each."""
    xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
    header = etree.SubElement(xml, f"{{{TEI_NS}}}teiHeader")
    file_desc = etree.SubElement(header, f"{{{TEI_NS}}}fileDesc")
    title_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}titleStmt")
    for ref in refs:
        resp_stmt = etree.SubElement(title_stmt, f"{{{TEI_NS}}}respStmt")
        etree.SubElement(resp_stmt, f"{{{TEI_NS}}}resp", key="trl").text = "Translated by"
        etree.SubElement(resp_stmt, f"{{{TEI_NS}}}name", ref=ref).text = "Someone"
    return _write_project_xml(base, project, filename, xml)


class TestContributorReferences(unittest.TestCase):
    """A misspelt contributor URN is a different person in the credits, so it must fail."""

    def _failures(self, credits, registered=()):
        with TemporaryDirectory() as td:
            base = Path(td)
            registry = _write_registry(base, *registered)
            _write_credits(base / "project", "proj", "a.xml", *credits)
            return validate_project_contributor_references(
                "proj",
                project_directory=base / "project",
                registry_directory=registry,
            )

    def test_a_registered_contributor_passes(self):
        urn = CONTRIBUTOR + "opensiddur.org/eve-feinstein"
        self.assertEqual(self._failures([urn], registered=[urn]), [])

    def test_a_malformed_ref_fails(self):
        # The shape the older importers emitted: no `contributor:` type segment.
        failures = self._failures(["urn:x-opensiddur:opensiddur.org/eve-feinstein"])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].project, "proj")
        self.assertEqual(failures[0].file_name, "a.xml")
        self.assertIn("contributor", failures[0].reason)

    def test_an_unregistered_identifier_of_ours_fails(self):
        failures = self._failures(
            [CONTRIBUTOR + "opensiddur.org/eve-fienstein"],
            registered=[CONTRIBUTOR + "opensiddur.org/eve-feinstein"],
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("not registered", failures[0].reason)

    def test_an_unregistered_wiki_username_passes(self):
        # Wikisource usernames are harvested by importers, so the roster does not gate them.
        self.assertEqual(self._failures([CONTRIBUTOR + "en.wikisource.org/Prosody"]), [])

    def test_a_bad_ref_on_another_element_is_still_caught(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            registry = _write_registry(base)
            xml = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)
            text = etree.SubElement(xml, f"{{{TEI_NS}}}text")
            body = etree.SubElement(text, f"{{{TEI_NS}}}body")
            etree.SubElement(
                body, f"{{{TEI_NS}}}persName",
                ref="urn:x-opensiddur:opensiddur.org/eve-feinstein",
            )
            _write_project_xml(base / "project", "proj", "a.xml", xml)

            failures = validate_project_contributor_references(
                "proj", project_directory=base / "project", registry_directory=registry
            )
            self.assertEqual(len(failures), 1)
            self.assertIn("persName", failures[0].element_path)

    def test_a_project_with_no_refs_passes(self):
        self.assertEqual(self._failures([]), [])

    def test_a_non_contributor_ref_fails(self):
        # @ref carries contributor URNs only; a text URN there is a mistake.
        failures = self._failures(["urn:x-opensiddur:text:prayer:ashrei"])
        self.assertEqual(len(failures), 1)

    def test_a_missing_project_directory_raises(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            (base / "project").mkdir()
            with self.assertRaises(ValueError):
                validate_project_contributor_references(
                    "absent",
                    project_directory=base / "project",
                    registry_directory=_write_registry(base),
                )


class TestMainExitCode(unittest.TestCase):
    def test_a_bad_contributor_ref_exits_2(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project_directory = base / "project"
            _write_credits(
                project_directory, "proj", "a.xml",
                "urn:x-opensiddur:opensiddur.org/eve-feinstein",
            )
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = main([
                    "proj",
                    "--project-directory", str(project_directory),
                    "--reference-db", str(base / "ref.db"),
                ])
            self.assertEqual(code, 2)
            self.assertIn("a.xml", stdout.getvalue())

    def test_a_clean_project_exits_0(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project_directory = base / "project"
            _write_credits(
                project_directory, "proj", "a.xml",
                CONTRIBUTOR + "en.wikisource.org/Prosody",
            )
            with patch("sys.stdout", io.StringIO()):
                code = main([
                    "proj",
                    "--project-directory", str(project_directory),
                    "--reference-db", str(base / "ref.db"),
                ])
            self.assertEqual(code, 0)

    def test_several_projects_exit_2_when_any_is_bad(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            project_directory = base / "project"
            _write_credits(project_directory, "good", "a.xml", CONTRIBUTOR + "en.wikisource.org/Prosody")
            _write_credits(project_directory, "bad", "b.xml", "urn:x-opensiddur:opensiddur.org/eve-feinstein")
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = main([
                    "bad", "good",
                    "--project-directory", str(project_directory),
                    "--reference-db", str(base / "ref.db"),
                ])
            self.assertEqual(code, 2)
            self.assertIn("b.xml", stdout.getvalue())
