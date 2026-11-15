"""Tests for the schema-validation CI gate.

Every fixture here is synthetic, built in a temporary directory -- never the real
``project/`` data, so these tests do not break when that data changes (see the top-level
CLAUDE.md). Validation runs against the real, built schema (``bash scripts/build-schema.sh``
must have run first, exactly as the rest of the suite requires).
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from opensiddur.exporter import validate_schema as validate_schema_module
from opensiddur.exporter.validate_schema import (
    ValidationCache,
    _file_hash,
    format_annotation,
    iter_target_files,
    main,
    schema_fingerprint,
    validate_file,
    validate_schema,
)

VALID_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
         xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
         xml:lang="en">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt>
        <tei:title type="main" xml:lang="en">Test Document</tei:title>
        <tei:respStmt>
          <tei:resp key="mrk">Markup editor</tei:resp>
          <tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/test-editor">Test Editor</tei:name>
        </tei:respStmt>
      </tei:titleStmt>
      <tei:publicationStmt>
        <tei:distributor>
          <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
        </tei:distributor>
        <tei:idno type="urn">urn:x-opensiddur:test:doc1@synthetic_project</tei:idno>
        <tei:availability status="free">
          <tei:licence target="http://www.creativecommons.org/publicdomain/zero/1.0/">Creative Commons Zero (Public Domain Dedication)</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc>
        <tei:p>Synthetic fixture, not real project data.</tei:p>
      </tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text xml:lang="en">
    <tei:body>
      <tei:div corresp="urn:x-opensiddur:test:doc1" n="doc1">
        <tei:head>Test Heading</tei:head>
        <tei:p>
          <tei:milestone unit="verse" n="1" corresp="urn:x-opensiddur:test:doc1/1"/>Test verse one.
          <tei:milestone unit="verse" n="2" corresp="urn:x-opensiddur:test:doc1/2"/>Test verse two.
        </tei:p>
      </tei:div>
    </tei:body>
  </tei:text>
</tei:TEI>
"""

# Schema-invalid: tei:p is not a permitted child of tei:titleStmt.
INVALID_DOC = VALID_DOC.replace(
    "<tei:titleStmt>",
    "<tei:titleStmt><tei:p>not allowed here</tei:p>",
)

# Schema-invalid: targetEnd must name a single point, not a range (issue #100).
RANGED_TARGET_END_DOC = VALID_DOC.replace(
    "</tei:body>",
    '<j:transclude target="urn:x-opensiddur:test:doc2/1"'
    ' targetEnd="urn:x-opensiddur:test:doc2/2-3"/></tei:body>',
)

MALFORMED_DOC = "<tei:TEI xmlns:tei=\"http://www.tei-c.org/ns/1.0\"><tei:text>"


def _write(base: Path, project: str, filename: str, content: str) -> Path:
    project_path = base / project
    project_path.mkdir(parents=True, exist_ok=True)
    path = project_path / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestValidateFile(unittest.TestCase):
    def test_valid_document(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(Path(td), "proj", "a.xml", VALID_DOC)
            result = validate_file(path)
            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.errors, ())

    def test_schema_invalid_document(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(Path(td), "proj", "a.xml", INVALID_DOC)
            result = validate_file(path)
            self.assertFalse(result.ok)
            self.assertTrue(result.errors)

    def test_ranged_target_end_is_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(Path(td), "proj", "a.xml", RANGED_TARGET_END_DOC)
            result = validate_file(path)
            self.assertFalse(result.ok)
            self.assertTrue(result.errors)

    def test_malformed_document(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(Path(td), "proj", "a.xml", MALFORMED_DOC)
            result = validate_file(path)
            self.assertFalse(result.ok)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("XML syntax error", result.errors[0])
            self.assertIn("line", result.errors[0])


class TestIterTargetFiles(unittest.TestCase):
    def test_defaults_to_every_project(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            a = _write(base, "proj1", "a.xml", VALID_DOC)
            b = _write(base, "proj2", "b.xml", VALID_DOC)
            files, skipped = iter_target_files(project_directory=base)
            self.assertCountEqual(files, [a, b])
            self.assertEqual(skipped, [])

    def test_named_project_only(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            a = _write(base, "proj1", "a.xml", VALID_DOC)
            _write(base, "proj2", "b.xml", VALID_DOC)
            files, skipped = iter_target_files(project_directory=base, projects=["proj1"])
            self.assertEqual(files, [a])
            self.assertEqual(skipped, [])

    def test_missing_project_is_skipped_not_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            files, skipped = iter_target_files(project_directory=base, projects=["gone"])
            self.assertEqual(files, [])
            self.assertEqual(skipped, ["gone"])

    def test_files_from_relative_to_project_directory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj1", "a.xml", VALID_DOC)
            files, skipped = iter_target_files(
                project_directory=base, files_from=[Path("proj1/a.xml")]
            )
            self.assertEqual(files, [base / "proj1" / "a.xml"])


class TestValidateSchema(unittest.TestCase):
    def test_all_valid(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj", "a.xml", VALID_DOC)
            report = validate_schema(project_directory=base)
            self.assertTrue(report.ok)
            self.assertEqual(len(report.results), 1)

    def test_one_invalid_fails_the_report(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj", "good.xml", VALID_DOC)
            _write(base, "proj", "bad.xml", INVALID_DOC)
            report = validate_schema(project_directory=base)
            self.assertFalse(report.ok)
            self.assertEqual(len(report.failures), 1)
            self.assertEqual(report.failures[0].path.name, "bad.xml")

    def test_logs_progress(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj", "a.xml", VALID_DOC)
            _write(base, "proj", "b.xml", VALID_DOC)
            with self.assertLogs(validate_schema_module.logger, level="INFO") as logs:
                validate_schema(project_directory=base)
            messages = [r.getMessage() for r in logs.records]
            self.assertIn("Schema validation: 2 files", messages)
            self.assertTrue(any("2 files done" in m for m in messages), messages)


class TestFormatAnnotation(unittest.TestCase):
    def test_jing_line_becomes_error_annotation(self):
        line = format_annotation("proj/a.xml", "XML:12:34: error: unexpected element")
        self.assertEqual(
            line, "::error file=proj/a.xml,line=12,col=34::error: unexpected element"
        )

    def test_syntax_error_becomes_error_annotation(self):
        error = "XML syntax error: Premature end of data at line 3, column 1"
        line = format_annotation("proj/a.xml", error)
        self.assertEqual(line, f"::error file=proj/a.xml,line=3,col=1::{error}")

    def test_schematron_error_has_no_line(self):
        error = "/tei:TEI[1]: assertion failed"
        line = format_annotation("proj/a.xml", error)
        self.assertEqual(line, f"::error file=proj/a.xml::{error}")


class TestMain(unittest.TestCase):
    def test_exit_zero_when_all_valid(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj", "a.xml", VALID_DOC)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--project-directory", str(base)])
            self.assertEqual(code, 0)
            self.assertIn("OK", out.getvalue())

    def test_exit_one_when_any_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj", "bad.xml", INVALID_DOC)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--project-directory", str(base)])
            self.assertEqual(code, 1)
            self.assertIn("FAIL", out.getvalue())

    def test_github_annotations_emitted(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            _write(base, "proj", "bad.xml", INVALID_DOC)
            out = io.StringIO()
            with redirect_stdout(out):
                main(
                    [
                        "--project-directory",
                        str(base),
                        "--repo-root",
                        str(base),
                        "--github-annotations",
                    ]
                )
            self.assertIn("::error file=proj/bad.xml", out.getvalue())

    def test_missing_project_exits_zero(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--project-directory", str(base), "--project", "gone"])
            self.assertEqual(code, 0)
            self.assertIn("SKIP", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class TestValidationCache(unittest.TestCase):
    """``--cache``: files that passed are not revalidated until their content or the schema changes.

    ``validate_file`` is wrapped (not replaced) so the real validators still run and the
    tests can count how many files were actually validated.
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        self.base = self.root / "project"
        self.cache_path = self.root / "cache.json"
        wrapped = mock.patch.object(
            validate_schema_module,
            "validate_file",
            side_effect=validate_schema_module.validate_file,
        )
        self.validate_file = wrapped.start()
        self.addCleanup(wrapped.stop)

    def _run(self, **kwargs):
        self.validate_file.reset_mock()
        return validate_schema(
            project_directory=self.base, cache_path=self.cache_path, **kwargs
        )

    def _stored(self) -> dict:
        return json.loads(self.cache_path.read_text(encoding="utf-8"))

    def test_unchanged_valid_file_is_not_revalidated(self):
        _write(self.base, "proj", "a.xml", VALID_DOC)
        first = self._run()
        self.assertTrue(first.ok)
        self.assertEqual(self.validate_file.call_count, 1)
        self.assertEqual(first.cached, 0)

        second = self._run()
        self.assertTrue(second.ok)
        self.assertEqual(self.validate_file.call_count, 0)
        self.assertEqual(second.cached, 1)
        self.assertTrue(second.results[0].cached)

    def test_edited_file_is_revalidated(self):
        path = _write(self.base, "proj", "a.xml", VALID_DOC)
        self._run()
        path.write_text(INVALID_DOC, encoding="utf-8")
        report = self._run()
        self.assertEqual(self.validate_file.call_count, 1)
        self.assertFalse(report.ok)

    def test_invalid_file_is_never_cached(self):
        path = _write(self.base, "proj", "bad.xml", INVALID_DOC)
        self._run()
        self.assertNotIn(_file_hash(path), self._stored()["valid"])
        report = self._run()
        self.assertEqual(self.validate_file.call_count, 1)
        self.assertFalse(report.ok)
        self.assertTrue(report.failures[0].errors)

    def test_fingerprint_change_revalidates_everything(self):
        _write(self.base, "proj", "a.xml", VALID_DOC)
        self._run()
        with mock.patch.object(
            validate_schema_module, "schema_fingerprint", return_value="another-schema"
        ):
            report = self._run()
        self.assertEqual(self.validate_file.call_count, 1)
        self.assertEqual(report.cached, 0)
        self.assertEqual(self._stored()["fingerprint"], "another-schema")

    def test_corrupt_cache_file_means_full_validation(self):
        _write(self.base, "proj", "a.xml", VALID_DOC)
        self.cache_path.write_text("{not json", encoding="utf-8")
        report = self._run()
        self.assertTrue(report.ok)
        self.assertEqual(self.validate_file.call_count, 1)
        self.assertEqual(len(self._stored()["valid"]), 1)

    def test_missing_cache_file_is_created(self):
        _write(self.base, "proj", "a.xml", VALID_DOC)
        self.assertFalse(self.cache_path.exists())
        self._run()
        self.assertEqual(self._stored()["fingerprint"], schema_fingerprint())

    def test_deleted_file_is_pruned(self):
        a = _write(self.base, "proj", "a.xml", VALID_DOC)
        b = _write(self.base, "proj", "b.xml", VALID_DOC.replace("Test verse one.", "Other."))
        self._run()
        b_hash = _file_hash(b)
        self.assertIn(b_hash, self._stored()["valid"])
        b.unlink()
        self._run()
        self.assertEqual(self._stored()["valid"], [_file_hash(a)])

    def test_unvalidated_projects_are_kept(self):
        """A run over one project must not drop the cached results for the others."""
        _write(self.base, "proj1", "a.xml", VALID_DOC)
        other = _write(self.base, "proj2", "b.xml", VALID_DOC.replace("Test verse one.", "Other."))
        self._run()
        self._run(projects=["proj1"])
        self.assertIn(_file_hash(other), self._stored()["valid"])

    def test_main_reports_cached_files(self):
        _write(self.base, "proj", "a.xml", VALID_DOC)
        argv = [
            "--project-directory", str(self.base),
            "--repo-root", str(self.base),
            "--cache", str(self.cache_path),
            "-v",
        ]
        with redirect_stdout(io.StringIO()):
            main(argv)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(argv)
        self.assertEqual(code, 0)
        self.assertIn("OK    proj/a.xml (cached)", out.getvalue())
        self.assertIn("OK: 1 file(s) valid (1 from cache)", out.getvalue())


class TestSchemaFingerprint(unittest.TestCase):
    RNG = (
        '<grammar xmlns="http://relaxng.org/ns/structure/1.0">'
        "<!-- generated %s --><start><element name=\"a\"><text/></element></start></grammar>"
    )
    XSLT = (
        '<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0">'
        "<!-- %s --><xsl:template match=\"/\"/></xsl:stylesheet>"
    )

    def _fingerprint(self, rng: str, xslt: str) -> str:
        with tempfile.TemporaryDirectory() as td:
            rng_path = Path(td) / "s.rng"
            xslt_path = Path(td) / "s.xslt"
            rng_path.write_text(rng, encoding="utf-8")
            xslt_path.write_text(xslt, encoding="utf-8")
            return schema_fingerprint(rng_path, xslt_path)

    def test_comments_are_ignored(self):
        self.assertEqual(
            self._fingerprint(self.RNG % "2026-01-01", self.XSLT % "one"),
            self._fingerprint(self.RNG % "2026-09-25", self.XSLT % "two"),
        )

    def test_schema_change_changes_fingerprint(self):
        self.assertNotEqual(
            self._fingerprint(self.RNG % "x", self.XSLT % "x"),
            self._fingerprint(self.RNG.replace('"a"', '"b"') % "x", self.XSLT % "x"),
        )


class TestValidationCacheLoad(unittest.TestCase):
    def test_other_fingerprint_is_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "c.json"
            ValidationCache("old", {"h"}).save(path, keep={"h"})
            self.assertEqual(ValidationCache.load(path, "old").valid, {"h"})
            self.assertEqual(ValidationCache.load(path, "new").valid, set())

    def test_wrong_shape_is_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "c.json"
            path.write_text("[1, 2]", encoding="utf-8")
            self.assertEqual(ValidationCache.load(path, "f").valid, set())
