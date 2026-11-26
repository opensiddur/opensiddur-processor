"""End-to-end integration tests for parallel text compilation."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from opensiddur.exporter.compiler import JLPTEI_NAMESPACE, PROCESSING_NAMESPACE
from opensiddur.exporter.conditional_markers import check_pairing
from opensiddur.exporter.external_compiler import TEI_NS, ExternalCompilerProcessor
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.exporter.urn import ResolvedUrn, UrnResolver

P_NS = PROCESSING_NAMESPACE
J_NS = JLPTEI_NAMESPACE
XML_NS = "http://www.w3.org/XML/1998/namespace"

# ── Shared XML fixtures ──────────────────────────────────────────────────────

_PRIMARY_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="he">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>Primary</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor>
          <tei:ref target="http://example.org">Example</tei:ref>
        </tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/publicdomain/zero/1.0/">CC0</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc>
        <tei:bibl xml:id="s1"><tei:title>Primary Source</tei:title></tei:bibl>
      </tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="he">
    <tei:body>
      <tei:div corresp="urn:x-test:section">
        <tei:p>
          <tei:milestone unit="verse" n="1" corresp="urn:x-test:section/1"/>Hebrew verse 1.
          <tei:milestone unit="verse" n="2" corresp="urn:x-test:section/2"/>Hebrew verse 2.
        </tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""

_PARALLEL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="en">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>Parallel</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor>
          <tei:ref target="http://example.org">Example</tei:ref>
        </tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/licenses/by/4.0/">CC-BY</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc>
        <tei:bibl xml:id="s2"><tei:title>Parallel Source</tei:title></tei:bibl>
      </tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="en">
    <tei:body>
      <tei:div corresp="urn:x-test:section">
        <tei:p>
          <tei:milestone unit="verse" n="1" corresp="urn:x-test:section/1"/>English verse 1.
          <tei:milestone unit="verse" n="2" corresp="urn:x-test:section/2"/>English verse 2.
        </tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""


class _E2EBase(unittest.TestCase):

    PRIMARY_PROJECT = "primary-proj"
    PARALLEL_PROJECT = "parallel-proj"
    PARALLEL_CORRESP = {
        # The root document's own URN: both fixtures carry it on tei:body/tei:div/@corresp,
        # so they genuinely correspond and root-level parallel applies to them.
        "urn:x-test:section",
        "urn:x-test:section/1",
        "urn:x-test:section/2",
    }

    def setUp(self):
        reset_linear_data()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        base = Path(self.temp_dir.name)
        (base / self.PRIMARY_PROJECT).mkdir()
        (base / self.PRIMARY_PROJECT / "index.xml").write_bytes(_PRIMARY_XML)
        (base / self.PARALLEL_PROJECT).mkdir()
        (base / self.PARALLEL_PROJECT / "index.xml").write_bytes(_PARALLEL_XML)

        self.linear_data = get_linear_data()
        self.linear_data.xml_cache.base_path = base
        self.linear_data.parallel_projects = [self.PARALLEL_PROJECT]
        self.linear_data.project_priority = [self.PRIMARY_PROJECT, self.PARALLEL_PROJECT]

    def _mock_resolve_range(self, urn):
        """Return a resolved URN pointing to the parallel project for known milestone corresp values."""
        base_urn = urn.rsplit("@", 1)[0] if "@" in urn else urn
        if base_urn in self.PARALLEL_CORRESP:
            return [ResolvedUrn(
                urn=base_urn, project=self.PARALLEL_PROJECT,
                file_name="index.xml", element_path="/TEI")]
        return []

    def _compile_primary(self):
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)
        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            return proc.process()


# ── Root trigger integration ─────────────────────────────────────────────────

class TestRootTriggerE2E(_E2EBase):

    def test_output_contains_p_parallel(self):
        result = self._compile_primary()

        parallels = [el for r in result for el in r.iter(f"{{{P_NS}}}parallel")]
        self.assertGreater(len(parallels), 0, "Expected at least one p:parallel in output")

    def test_output_has_primary_and_parallel_items(self):
        result = self._compile_primary()

        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        primary_items = root.findall(f".//{{{P_NS}}}parallelItem[@role='primary']")
        parallel_items = root.findall(f".//{{{P_NS}}}parallelItem[@role='parallel']")
        self.assertGreater(len(primary_items), 0)
        self.assertGreater(len(parallel_items), 0)
        self.assertEqual(len(primary_items), len(parallel_items))

    def test_primary_items_have_hebrew_lang(self):
        result = self._compile_primary()
        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        primary_items = root.findall(f".//{{{P_NS}}}parallelItem[@role='primary']")
        for item in primary_items:
            lang = item.get(f"{{{XML_NS}}}lang")
            self.assertEqual(lang, "he", f"Expected primary item xml:lang='he', got {lang!r}")

    def test_parallel_items_have_english_lang(self):
        result = self._compile_primary()
        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        parallel_items = root.findall(f".//{{{P_NS}}}parallelItem[@role='parallel']")
        for item in parallel_items:
            lang = item.get(f"{{{XML_NS}}}lang")
            self.assertEqual(lang, "en", f"Expected parallel item xml:lang='en', got {lang!r}")

    def test_milestones_appear_in_both_streams(self):
        result = self._compile_primary()
        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        for item in root.findall(f".//{{{P_NS}}}parallelItem"):
            milestones = item.findall(f".//{{{TEI_NS}}}milestone")
            # Each parallelItem should preserve the milestone elements
            for ms in milestones:
                corresp = ms.get("corresp")
                self.assertIsNotNone(corresp)

    def test_result_serializes_without_error(self):
        result = self._compile_primary()
        for el in result:
            xml_str = etree.tostring(el, encoding="unicode")
            self.assertIsInstance(xml_str, str)
            self.assertGreater(len(xml_str), 0)

    def test_tei_structure_preserved(self):
        """The outer tei:TEI element and tei:teiHeader are preserved in the result."""
        result = self._compile_primary()
        self.assertEqual(len(result), 1)
        tei_el = result[0]
        self.assertEqual(tei_el.tag, f"{{{TEI_NS}}}TEI")

        header = tei_el.find(f"{{{TEI_NS}}}teiHeader")
        self.assertIsNotNone(header)

    def test_no_parallel_fallback_when_parallel_file_missing(self):
        """If parallel project file doesn't exist, result should be normal (no p:parallel)."""
        import shutil
        shutil.rmtree(Path(self.temp_dir.name) / self.PARALLEL_PROJECT)

        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)
        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            result = proc.process()

        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        self.assertNotIn(f"{{{P_NS}}}parallel", result_xml)


# ── Marker structure verification ────────────────────────────────────────────

class TestMarkerStructureE2E(_E2EBase):

    def test_structural_elements_with_milestones_get_markers(self):
        """Compiler output should be reconstructed (no raw p:start/p:end markers)."""
        result = self._compile_primary()
        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        # Reconstruction happens in the compiler now, so markers should not survive
        start_markers = root.findall(f".//*[@{{{P_NS}}}start]")
        end_markers = root.findall(f".//*[@{{{P_NS}}}end]")
        self.assertEqual(len(start_markers), 0, "p:start markers should be consumed by reconstruction")
        self.assertEqual(len(end_markers), 0, "p:end markers should be consumed by reconstruction")

        # Still expect parallel structure to exist in compiled output
        parallels = root.findall(f".//{{{P_NS}}}parallel")
        self.assertGreater(len(parallels), 0)

    def test_start_end_marker_ids_match(self):
        """Legacy marker pairing test: markers should not be present post-reconstruct."""
        result = self._compile_primary()
        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        self.assertEqual(len(root.findall(f".//*[@{{{P_NS}}}start]")), 0)
        self.assertEqual(len(root.findall(f".//*[@{{{P_NS}}}end]")), 0)

    def test_column_order_attribute(self):
        """p:parallel elements should have a column-order attribute."""
        result = self._compile_primary()
        all_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{all_xml}</root>")

        parallels = root.findall(f".//{{{P_NS}}}parallel")
        self.assertGreater(len(parallels), 0)
        for p in parallels:
            self.assertIn("column-order", p.attrib)


# ── parallel-compilation suppression end-to-end ─────────────────────────────

class TestInParallelCompilationE2E(_E2EBase):

    def test_in_parallel_mode_produces_no_parallel_elements(self):
        """Inside a parallel sub-compilation, no p:parallel is produced."""
        self.linear_data.parallel_compilation_depth = 1
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)
        proc.marker_stack = []  # enable marker mode

        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            result = proc.process()

        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        self.assertNotIn(f"{{{P_NS}}}parallel", result_xml)

    def test_in_parallel_mode_still_produces_markers(self):
        """Even without p:parallel, marker elements should appear when marker_stack is set."""
        self.linear_data.parallel_compilation_depth = 1
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)
        proc.marker_stack = []

        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            result = proc.process()

        # Find any element with p:start attribute
        start_markers = [
            el for r in result
            for el in r.iter()
            if el.get(f"{{{P_NS}}}start") is not None
        ]
        self.assertGreater(len(start_markers), 0, "Expected p:start markers in marker-mode output")


# ── 3-way transclusion ───────────────────────────────────────────────────────

class TestThreeWayTransclusionE2E(_E2EBase):
    """A → transcludes B, B has milestones, B has a parallel in parallel-proj."""

    _B_PRIMARY = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="he">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>B Primary</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor><tei:ref target="http://e.org">e</tei:ref></tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/publicdomain/zero/1.0/">CC0</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc><tei:bibl xml:id="bsrc"><tei:title>B</tei:title></tei:bibl></tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="he">
    <tei:body>
      <tei:div xml:id="b-section">
        <tei:p>
          <tei:milestone unit="verse" n="b1" corresp="urn:x-test:section/b1"/>B Hebrew verse 1.
        </tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""

    _B_PARALLEL = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="en">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>B Parallel</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor><tei:ref target="http://e.org">e</tei:ref></tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/licenses/by/4.0/">CC-BY</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc><tei:bibl xml:id="bpsrc"><tei:title>BP</tei:title></tei:bibl></tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="en">
    <tei:body>
      <tei:div xml:id="b-section">
        <tei:p>
          <tei:milestone unit="verse" n="b1" corresp="urn:x-test:section/b1"/>B English verse 1.
        </tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""

    _A_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="he">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>A</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor><tei:ref target="http://e.org">e</tei:ref></tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/publicdomain/zero/1.0/">CC0</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc><tei:bibl xml:id="asrc"><tei:title>A</tei:title></tei:bibl></tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="he">
    <tei:body>
      <tei:div>
        <tei:p>Before transclusion.</tei:p>
        <j:transclude type="external" target="urn:x-test:b-section@primary-proj"/>
        <tei:p>After transclusion.</tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""

    B_CORRESP = {"urn:x-test:section/b1"}

    def setUp(self):
        super().setUp()
        base = Path(self.temp_dir.name)
        (base / self.PRIMARY_PROJECT / "b.xml").write_bytes(self._B_PRIMARY)
        (base / self.PARALLEL_PROJECT / "b.xml").write_bytes(self._B_PARALLEL)
        (base / self.PRIMARY_PROJECT / "index.xml").write_bytes(self._A_XML)

        self.linear_data.project_priority = [self.PRIMARY_PROJECT]

    def _mock_resolve_range_3way(self, urn):
        base_urn = urn.rsplit("@", 1)[0] if "@" in urn else urn
        project_hint = urn.rsplit("@", 1)[1] if "@" in urn else None

        if base_urn == "urn:x-test:b-section":
            proj = project_hint or self.PRIMARY_PROJECT
            # Parse b.xml to get the xml:id element path
            xml_content = self._B_PRIMARY if proj == self.PRIMARY_PROJECT else self._B_PARALLEL
            tree_root = etree.fromstring(xml_content)
            tree = tree_root.getroottree()
            xml_ns = "http://www.w3.org/XML/1998/namespace"
            b_section = tree_root.xpath("//*[@xml:id='b-section']", namespaces={"xml": xml_ns})
            if b_section:
                element_path = tree.getpath(b_section[0])
                return [ResolvedUrn(
                    urn=base_urn, project=proj,
                    file_name="b.xml", element_path=element_path,
                    end_element_path=element_path, end_includes_tail=False)]
        if base_urn in self.B_CORRESP:
            return [ResolvedUrn(
                urn=base_urn, project=self.PARALLEL_PROJECT,
                file_name="b.xml", element_path="/TEI")]
        return []

    def _mock_prioritize_range(self, urns, priority_list, return_all=False):
        return urns[0] if urns else None

    def test_transclusion_trigger_produces_p_parallel_inside_p_transclude(self):
        """When a j:transclude is compiled in parallel mode, result has p:transclude(p:parallel(...))."""
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)

        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range_3way):
            with patch.object(UrnResolver, "prioritize_range", side_effect=self._mock_prioritize_range):
                result = proc.process()

        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{result_xml}</root>")

        # Should have p:transclude wrapping p:parallel
        transcludes = root.findall(f".//{{{P_NS}}}transclude")
        self.assertGreater(len(transcludes), 0)
        for tc in transcludes:
            parallels = tc.findall(f"{{{P_NS}}}parallel")
            self.assertGreater(len(parallels), 0, "p:transclude should contain p:parallel")

    def test_transclusion_does_not_nest_parallels(self):
        """The compiled output must satisfy both parallel invariants end to end.

        See specs/COMPILER_SPECIFICATION.md, Parallel Compilation.
        """
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)

        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range_3way):
            with patch.object(UrnResolver, "prioritize_range", side_effect=self._mock_prioritize_range):
                result = proc.process()

        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{result_xml}</root>")

        for par in root.iter(f"{{{P_NS}}}parallel"):
            self.assertNotIn(
                f"{{{P_NS}}}parallel", [a.tag for a in par.iterancestors()],
                "p:parallel must never have a p:parallel ancestor")
        for item in root.iter(f"{{{P_NS}}}parallelItem"):
            nested = [
                t for t in item.iter(f"{{{P_NS}}}transclude")
                if t.get("type") in (None, "external")
            ]
            self.assertEqual(
                nested, [],
                "p:parallelItem must not contain an external p:transclude")

    def test_translation_does_not_leak_into_the_primary_column(self):
        """Shape assertions alone would miss the user-visible symptom.

        When the block failed to end at the transclusion, the translation was flattened into
        the primary column and rendered in that column's direction (reversed Latin).

        This fixture's mock does not resolve the parallel side of b.xml, so the inner parallel
        item is empty here and the positive "translation reaches its own column" case cannot be
        asserted — that is checked against the real projects instead. The leak assertion is
        still meaningful and is the one that fails when the invariant breaks.
        """
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml",
            linear_data=self.linear_data)

        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range_3way):
            with patch.object(UrnResolver, "prioritize_range", side_effect=self._mock_prioritize_range):
                result = proc.process()

        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        root = etree.fromstring(f"<root>{result_xml}</root>")

        primary_text = " ".join(
            "".join(i.itertext())
            for i in root.findall(f".//{{{P_NS}}}parallelItem[@role='primary']"))
        parallel_text = " ".join(
            "".join(i.itertext())
            for i in root.findall(f".//{{{P_NS}}}parallelItem[@role='parallel']"))

        self.assertIn("B Hebrew verse 1", primary_text)
        self.assertNotIn("English verse", primary_text,
                         "translation must not leak into the primary column")
        self.assertIn("English verse", parallel_text)


# ── Arrangement projects (a wrapper that holds no text of its own) ────────────

class TestArrangementProjectRootE2E(_E2EBase):
    """A wrapper project that only arranges transclusions has no document-level counterpart.

    Regression: the root document used to be paired with whichever parallel project merely
    contained a file of the same name. Every project has an index.xml, so an arrangement
    project (a humash built by transcluding Tanakh verses) was paired with an unrelated
    index, and that pairing suppressed the per-transclusion parallels that were the only
    real correspondence. The result was a Hebrew source facing itself, with the translation
    absent from the output entirely.
    """

    WRAPPER_URN = "urn:x-test:arrangement"
    ENGLISH_PROJECT = "english-proj"

    _UNRELATED_INDEX_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="he">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>Whole Collection</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor><tei:ref target="http://e.org">e</tei:ref></tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/publicdomain/zero/1.0/">CC0</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc><tei:bibl xml:id="usrc"><tei:title>U</tei:title></tei:bibl></tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="he">
    <tei:body>
      <tei:div corresp="urn:x-test:collection">
        <tei:p>Front matter of the whole collection.</tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""

    _WRAPPER_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="he">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt><tei:title>Arrangement</tei:title></tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor><tei:ref target="http://e.org">e</tei:ref></tei:distributor>
        <tei:availability status="free">
          <tei:licence target="http://creativecommons.org/publicdomain/zero/1.0/">CC0</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc><tei:bibl xml:id="wsrc"><tei:title>W</tei:title></tei:bibl></tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="he">
    <tei:body>
      <tei:div corresp="urn:x-test:arrangement">
        <tei:head>Arrangement</tei:head>
        <j:transclude type="external" target="urn:x-test:section/1"/>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>"""

    def setUp(self):
        super().setUp()
        base = Path(self.temp_dir.name)
        (base / self.ENGLISH_PROJECT).mkdir()

        # The wrapper is the compilation root and holds no text of its own.
        (base / self.PRIMARY_PROJECT / "index.xml").write_bytes(self._WRAPPER_XML)
        # The Hebrew project plays MAM's role: it supplies the transcluded verses *and*
        # owns an index.xml that has nothing to do with the wrapper. That file-name
        # collision is what used to be mistaken for a correspondence.
        (base / self.PARALLEL_PROJECT / "index.xml").write_bytes(self._UNRELATED_INDEX_XML)
        (base / self.PARALLEL_PROJECT / "verses.xml").write_bytes(_PRIMARY_XML)
        # The English project plays jps1917's role: the translation, listed second.
        (base / self.ENGLISH_PROJECT / "verses.xml").write_bytes(_PARALLEL_XML)

        # Hebrew first, exactly as the real settings list MAM before jps1917.
        self.linear_data.parallel_projects = [self.PARALLEL_PROJECT, self.ENGLISH_PROJECT]
        self.linear_data.project_priority = [
            self.PRIMARY_PROJECT, self.PARALLEL_PROJECT, self.ENGLISH_PROJECT]

    def _milestone_path(self, xml_bytes, n):
        tree_root = etree.fromstring(xml_bytes)
        milestone = tree_root.xpath(
            f"//tei:milestone[@n='{n}']",
            namespaces={"tei": TEI_NS})[0]
        return tree_root.getroottree().getpath(milestone)

    def _mock_resolve_range(self, urn):
        base_urn, _, hint = urn.partition("@")
        # The wrapper's own URN is private to the arrangement project: no parallel
        # project contains it, so no root-level pairing is possible.
        if base_urn == self.WRAPPER_URN:
            return []
        if base_urn == "urn:x-test:collection":
            return [ResolvedUrn(
                urn=base_urn, project=self.PARALLEL_PROJECT, file_name="index.xml",
                element_path="/tei:TEI")]
        if base_urn == "urn:x-test:section/1":
            if hint == self.ENGLISH_PROJECT:
                project, xml_bytes = self.ENGLISH_PROJECT, _PARALLEL_XML
            else:
                project, xml_bytes = self.PARALLEL_PROJECT, _PRIMARY_XML
            path = self._milestone_path(xml_bytes, "1")
            return [ResolvedUrn(
                urn=base_urn, project=project, file_name="verses.xml",
                element_path=path, end_element_path=path, end_includes_tail=True)]
        return []

    def _compile_wrapper(self):
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml", linear_data=self.linear_data)
        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            with patch.object(UrnResolver, "prioritize_range",
                              side_effect=lambda urns, priority, return_all=False: (
                                  urns[0] if urns else None)):
                return proc.process()

    def _compiled_root(self):
        result = self._compile_wrapper()
        result_xml = "".join(etree.tostring(el, encoding="unicode") for el in result)
        return etree.fromstring(f"<root>{result_xml}</root>")

    def test_no_root_parallel_is_selected(self):
        """The wrapper's URN resolves in no parallel project, so root pairing is declined."""
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml", linear_data=self.linear_data)
        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            self.assertIsNone(proc._select_root_parallel_project())

    def test_same_file_name_does_not_make_a_counterpart(self):
        """The Hebrew project's index.xml exists but is a different document, so it loses.

        Both files are named index.xml; only their URNs distinguish them.
        """
        proc = ExternalCompilerProcessor(
            self.PRIMARY_PROJECT, "index.xml", linear_data=self.linear_data)
        self.assertEqual(proc._root_correspondence_urn(), self.WRAPPER_URN)
        with patch.object(UrnResolver, "resolve_range", side_effect=self._mock_resolve_range):
            self.assertIsNone(proc._process_parallel_root())

    def test_translation_reaches_the_output(self):
        """The whole point: English must be present, via the per-transclusion parallel."""
        root = self._compiled_root()

        parallel_text = " ".join(
            "".join(item.itertext())
            for item in root.findall(f".//{{{P_NS}}}parallelItem[@role='parallel']"))
        self.assertIn("English verse 1", parallel_text)

    def test_columns_are_not_the_same_source(self):
        """No row may draw both of its columns from the same project."""
        parallels = self._compiled_root().findall(f".//{{{P_NS}}}parallel")
        self.assertGreater(len(parallels), 0, "expected per-transclusion parallels")

        for par in parallels:
            primary = par.find(f"{{{P_NS}}}parallelItem[@role='primary']")
            parallel = par.find(f"{{{P_NS}}}parallelItem[@role='parallel']")
            self.assertNotEqual(
                primary.get(f"{{{P_NS}}}project"),
                parallel.get(f"{{{P_NS}}}project"),
                "a parallel row must not have the same source in both columns")

    def test_columns_carry_distinct_languages(self):
        root = self._compiled_root()
        for par in root.findall(f".//{{{P_NS}}}parallel"):
            primary = par.find(f"{{{P_NS}}}parallelItem[@role='primary']")
            parallel = par.find(f"{{{P_NS}}}parallelItem[@role='parallel']")
            self.assertEqual(primary.get(f"{{{XML_NS}}}lang"), "he")
            self.assertEqual(parallel.get(f"{{{XML_NS}}}lang"), "en")

    def test_no_parallel_block_is_wrapped_in_a_div(self):
        """The invariant the TeX stage depends on: p:parallel is a flat sibling of the flow.

        The wrapper's tei:div encloses the transclusion in the source, so before
        document-wide marker mode the compiled block came out as
        body/div/transclude/p:parallel. reledmac.xslt groups on p:parallel among the
        top-level nodes of the (transclude-flattened) body, so a block behind a div was
        invisible to it: no \\begin{pairs} was emitted at all and both columns were run
        together into one numbered stream.
        """
        root = self._compiled_root()
        parallels = root.findall(f".//{{{P_NS}}}parallel")
        self.assertGreater(len(parallels), 0, "expected per-transclusion parallels")

        for par in parallels:
            div_ancestors = [a for a in par.iterancestors(f"{{{TEI_NS}}}div")]
            self.assertEqual(
                div_ancestors, [],
                "a p:parallel must not have a tei:div ancestor")

    def test_the_enclosing_structure_is_reproduced_inside_each_column(self):
        """Structure is not discarded to achieve that — it is copied into the columns."""
        root = self._compiled_root()

        rows_with_content = [
            par for par in root.findall(f".//{{{P_NS}}}parallel")
            if "".join(par.itertext()).strip()
        ]
        self.assertGreater(len(rows_with_content), 0)

        for par in rows_with_content:
            for item in par.findall(f"{{{P_NS}}}parallelItem"):
                self.assertIsNotNone(
                    item.find(f"{{{TEI_NS}}}div"),
                    "each column must carry its own copy of the source's div")

    def test_the_wrapper_div_still_encloses_its_own_heading(self):
        """Marker-ifying the wrapper must not lose it: its head is still inside a div."""
        root = self._compiled_root()
        heads = root.findall(f".//{{{TEI_NS}}}div/{{{TEI_NS}}}head")
        self.assertIn("Arrangement", [h.text for h in heads])


class TestSplitStructureAcrossParallelsE2E(TestArrangementProjectRootE2E):
    """Two transclusions inside one div: the div is split into segments around them."""

    # Text of the wrapper's own between the two readings, so the enclosing div really is
    # cut into two non-empty segments. Two adjacent transclusions would leave the segment
    # between them empty, and an empty segment is pruned rather than marked.
    _WRAPPER_XML = TestArrangementProjectRootE2E._WRAPPER_XML.replace(
        b'<j:transclude type="external" target="urn:x-test:section/1"/>',
        b'<j:transclude type="external" target="urn:x-test:section/1"/>\n'
        b'        <tei:p>Between the readings.</tei:p>\n'
        b'        <j:transclude type="external" target="urn:x-test:section/2"/>',
    )

    def _mock_resolve_range(self, urn):
        base_urn, _, hint = urn.partition("@")
        if base_urn == "urn:x-test:section/2":
            if hint == self.ENGLISH_PROJECT:
                project, xml_bytes = self.ENGLISH_PROJECT, _PARALLEL_XML
            else:
                project, xml_bytes = self.PARALLEL_PROJECT, _PRIMARY_XML
            path = self._milestone_path(xml_bytes, "2")
            return [ResolvedUrn(
                urn=base_urn, project=project, file_name="verses.xml",
                element_path=path, end_element_path=path, end_includes_tail=True)]
        return super()._mock_resolve_range(urn)

    def test_both_transclusions_reach_the_output(self):
        text = "".join(self._compiled_root().itertext())
        self.assertIn("Hebrew verse 1", text)
        self.assertIn("English verse 1", text)
        self.assertIn("Hebrew verse 2", text)
        self.assertIn("English verse 2", text)

    def test_each_verse_appears_once_per_column(self):
        """Guards the quadratic tail leak at the level it actually mattered: a ranged
        transclusion must carry its own verse and no earlier one."""
        text = "".join(self._compiled_root().itertext())
        self.assertEqual(text.count("Hebrew verse 1"), 1)
        self.assertEqual(text.count("English verse 1"), 1)
        self.assertEqual(text.count("Hebrew verse 2"), 1)
        self.assertEqual(text.count("English verse 2"), 1)

    def test_split_column_segments_are_marked_with_p_part(self):
        """A structural element split across rows is stamped first/middle/last so the
        exporter can tell a continuation from a fresh block."""
        root = self._compiled_root()
        parts = [
            el.get(f"{{{P_NS}}}part")
            for el in root.iter()
            if el.get(f"{{{P_NS}}}part")
        ]
        self.assertIn("first", parts)
        self.assertIn("last", parts)

    def test_no_raw_markers_survive_reconstruction(self):
        """The new top-level pass must consume its markers, not leave them in the output."""
        root = self._compiled_root()
        for attr in ("start", "end", "suspend", "resume", "logical-id"):
            leftovers = root.findall(f".//*[@{{{P_NS}}}{attr}]")
            self.assertEqual(leftovers, [], f"p:{attr} survived reconstruction")


class TestUndecidedScopesAroundTransclusionsE2E(TestSplitStructureAcrossParallelsE2E):
    """Undecided conditionals around transclusions inside one div keep both of their ends.

    The shape of Birnbaum's "Men say: / Women say:" blessings: each scope opens, transcludes
    one reading, and closes, all inside the div that the transclusions split into segments.
    The closer lands alone in the segment that resumes after its transclusion; that segment
    has no words, and pruning it used to take the closer with it, leaving the scope open
    to the end of the book.
    """

    _CONDITION = (
        b'<tei:note type="instruction" xml:lang="en">%s say:</tei:note>'
        b'<tei:fs type="t:person"><tei:f name="gender"><tei:symbol value="%s"/></tei:f></tei:fs>')

    _WRAPPER_XML = TestArrangementProjectRootE2E._WRAPPER_XML.replace(
        b'<j:transclude type="external" target="urn:x-test:section/1"/>',
        b'<j:conditional xml:id="men">' + _CONDITION % (b"Men", b"male") + b'</j:conditional>\n'
        b'        <j:transclude type="external" target="urn:x-test:section/1"/>\n'
        b'        <j:endConditional target="#men"/>\n'
        b'        <j:conditional xml:id="women">' + _CONDITION % (b"Women", b"female")
        + b'</j:conditional>\n'
        b'        <j:transclude type="external" target="urn:x-test:section/2"/>\n'
        b'        <j:endConditional target="#women"/>',
    )

    def test_undecided_scopes_are_paired(self):
        root = self._compiled_root()
        self.assertEqual(len(root.findall(f".//{{{J_NS}}}conditional")), 2)
        self.assertEqual(check_pairing(root), [])

    def test_each_scope_still_governs_its_reading(self):
        """In document order: open men, verse 1, close men, open women, verse 2, close women."""
        root = self._compiled_root()
        events = []
        for el in root.iter(f"{{{J_NS}}}conditional", f"{{{J_NS}}}endConditional",
                            f"{{{TEI_NS}}}milestone"):
            if el.tag == f"{{{TEI_NS}}}milestone":
                if next(el.iterancestors(f"{{{P_NS}}}parallelItem")).get("role") == "primary":
                    events.append(f"verse {el.get('n')}")
            elif el.tag == f"{{{J_NS}}}conditional":
                events.append("open " + el.get(f"{{{XML_NS}}}id").split("_")[0])
            else:
                events.append("close " + el.get("target")[1:].split("_")[0])
        self.assertEqual(
            events,
            ["open men", "verse 1", "close men", "open women", "verse 2", "close women"])


if __name__ == "__main__":
    unittest.main()
