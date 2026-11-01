"""Tests for the ReferenceDatabase class."""

import unittest
import sqlite3
import tempfile
from pathlib import Path
import time
import os
from unittest import mock
from lxml import etree
from lxml.etree import ElementBase
from opensiddur.exporter import refdb
from opensiddur.exporter.refdb import (
    ReferenceDatabase,
    UrnMapping,
    Reference,
    find_end_of_mapping,
)


class TestCodeVersion(unittest.TestCase):
    """The database's version stamp follows the indexing code, not its comments."""

    CODE = 'def f(x):\n    """Doc."""\n    return x + 1  # one\n'

    def test_comments_and_docstrings_do_not_change_it(self):
        reworded = 'def f(x):\n    """Other words."""\n    return x + 1  # two\n'
        self.assertEqual(refdb._code_version(self.CODE), refdb._code_version(reworded))

    def test_code_does(self):
        changed = 'def f(x):\n    """Doc."""\n    return x + 2  # one\n'
        self.assertNotEqual(refdb._code_version(self.CODE), refdb._code_version(changed))


class TestReferenceDatabaseBasics(unittest.TestCase):
    """Test basic Reference Database functionality."""

    def setUp(self):
        """Set up a temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_urn.db'
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)
    
    def _create_element_with_corresp(self, corresp: str, element_type: str = None) -> ElementBase:
        """Helper method to create an element with a corresp attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem.set("corresp", corresp)
        if element_type:
            elem.set("type", element_type)
        return elem

    def test_database_initialization(self):
        """Test that database and tables are created properly."""
        # Check that database file exists
        self.assertTrue(self.db_path.exists())
        
        # Check that urn_mappings table exists
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='urn_mappings'")
        result = cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'urn_mappings')
        
        # Check that element_references table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='element_references'")
        result = cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'element_references')

    def test_add_urn_mapping(self):
        """Test adding a URN mapping."""
        project = "test_project"
        file_name = "doc1.xml"
        elem = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        
        self.db.add_urn_mapping(project, file_name, elem)
        
        # Verify it was added
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT * FROM urn_mappings WHERE urn = ?', ("urn:x-opensiddur:text:doc1",))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row['urn'], "urn:x-opensiddur:text:doc1")
        self.assertEqual(row['project'], project)
        self.assertEqual(row['file_name'], file_name)

    def test_reindexing_the_same_element_is_idempotent(self):
        """Re-indexing a project must not fail on mappings it already holds."""
        project = "test_project"
        elem = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")

        self.db.add_urn_mapping(project, "file1.xml", elem)
        self.db.add_urn_mapping(project, "file1.xml", elem)

        cursor = self.db.conn.cursor()
        cursor.execute('SELECT COUNT(*) AS n FROM urn_mappings WHERE urn = ? AND project = ?',
                      ("urn:x-opensiddur:text:doc1", project))
        self.assertEqual(cursor.fetchone()['n'], 1)

    def test_the_same_urn_twice_in_one_project_keeps_the_first_and_warns(self):
        """A source may declare the same text twice; the repeat is reported, not mapped.

        Letting it pass silently is how MAM's repeated Decalogue milestones went unnoticed.
        """
        project = "test_project"
        elem1 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        self.assertTrue(self.db.add_urn_mapping(project, "file1.xml", elem1))

        elem2 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        with self.assertLogs("opensiddur.exporter.refdb", level="WARNING") as logs:
            self.assertFalse(self.db.add_urn_mapping(project, "file2.xml", elem2))
        self.assertIn("urn:x-opensiddur:text:doc1", "".join(logs.output))
        mappings = self.db.get_urn_mappings("urn:x-opensiddur:text:doc1", project)
        self.assertEqual([m.file_name for m in mappings], ["file1.xml"])

    def test_a_second_location_in_the_same_file_keeps_the_first(self):
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        first = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        first.set("corresp", "urn:x-opensiddur:text:doc1")
        second = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        second.set("corresp", "urn:x-opensiddur:text:doc1")

        self.db.add_urn_mapping("test_project", "file1.xml", first)
        with self.assertLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("test_project", "file1.xml", second)
        mappings = self.db.get_urn_mappings("urn:x-opensiddur:text:doc1", "test_project")
        self.assertEqual(len(mappings), 1)
        self.assertTrue(mappings[0].element_path.endswith("div[1]"), mappings[0].element_path)

    def test_an_update_rewrites_every_column(self):
        """Re-mapping a URN at the same place replaces its tag and type as well."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        div = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        div.set("corresp", "urn:x-opensiddur:text:doc1")
        div.set("type", "chapter")
        self.db.add_urn_mapping("test_project", "file1.xml", div)
        div.set("type", "section")
        self.db.add_urn_mapping("test_project", "file1.xml", div)
        row = self.db.conn.execute(
            "SELECT element_type FROM urn_mappings WHERE urn = ?",
            ("urn:x-opensiddur:text:doc1",)).fetchone()
        self.assertEqual(row["element_type"], "section")

    def test_add_urn_mapping_multiple_projects(self):
        """Test that same URN can exist in multiple projects."""
        elem1 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        elem2 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        
        self.db.add_urn_mapping("project1", "file1.xml", elem1)
        self.db.add_urn_mapping("project2", "file2.xml", elem2)
        
        # Verify both exist
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT project, file_name FROM urn_mappings WHERE urn = ? ORDER BY project', 
                      ("urn:x-opensiddur:text:doc1",))
        rows = cursor.fetchall()
        
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['project'], "project1")
        self.assertEqual(rows[1]['project'], "project2")


class TestInstructionUrnCollisions(unittest.TestCase):
    """An instruction URN may repeat, but not with two different rubrics in one project.

    The refdb keeps one row per (urn, project), so when two notes in a project word the
    same instruction differently only one survives — and the compiler substitutes that one
    at both places. Nothing raises, so the warning is the only signal.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = ReferenceDatabase(Path(self.temp_dir.name) / 'test_urn.db')
        self.addCleanup(self.db.close)

    def _note(self, corresp: str, text: str = "") -> ElementBase:
        """An instruction note, of the shape the Birnbaum projects use."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        note = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}note")
        note.set("type", "instruction")
        note.set("corresp", corresp)
        if text:
            note.text = text
        return note

    def test_the_same_rubric_twice_is_not_a_collision(self):
        """A speaker label repeated at each place it applies is ordinary markup."""
        urn = "urn:x-opensiddur:instruction:role/reader"
        with self.assertNoLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("proj", "qedushah.xml", self._note(urn, "Reader"))
            self.db.add_urn_mapping("proj", "amidah.xml", self._note(urn, "Reader"))

    def test_two_different_rubrics_under_one_urn_warn(self):
        urn = "urn:x-opensiddur:instruction:role/reader"
        self.db.add_urn_mapping("proj", "qedushah.xml", self._note(urn, "Reader"))
        with self.assertLogs("opensiddur.exporter.refdb", level="WARNING") as caught:
            self.db.add_urn_mapping(
                "proj", "birkat_kohanim.xml",
                self._note(urn, "Priestly blessing recited by Reader:"),
            )
        message = caught.output[0]
        self.assertIn(urn, message)
        self.assertIn("qedushah.xml", message)
        self.assertIn("birkat_kohanim.xml", message)
        self.assertIn("Reader", message)
        self.assertIn("Priestly blessing recited by Reader:", message)

    def test_an_empty_occurrence_is_a_reference_not_a_definition(self):
        """Most instruction notes carry no text; they point at a rubric defined elsewhere."""
        urn = "urn:x-opensiddur:instruction:role/congregation"
        with self.assertNoLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("proj", "shalom.xml", self._note(urn, "Congregation"))
            self.db.add_urn_mapping("proj", "shalom.xml", self._note(urn))
            self.db.add_urn_mapping("proj", "qedushah.xml", self._note(urn))

    def test_different_projects_may_word_one_instruction_differently(self):
        """Alternative wordings across projects are the feature; settings choose between them."""
        urn = "urn:x-opensiddur:instruction:role/reader"
        with self.assertNoLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("he_project", "qedushah.xml", self._note(urn, "Reader"))
            self.db.add_urn_mapping("en_project", "qedushah.xml", self._note(urn, "Reader:"))

    def test_reindexing_one_element_is_not_a_collision(self):
        """Re-indexing a changed file re-adds its own notes; that is an update, not a clash."""
        urn = "urn:x-opensiddur:instruction:role/reader"
        with self.assertNoLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("proj", "qedushah.xml", self._note(urn, "Reader"))
            self.db.add_urn_mapping("proj", "qedushah.xml", self._note(urn, "Reader:"))

    def test_text_is_whitespace_normalized_across_child_elements(self):
        """Wrapping a word in an element must not read as a different rubric."""
        urn = "urn:x-opensiddur:instruction:role/reader"
        plain = self._note(urn, "Reader and congregation")

        marked = self._note(urn, "Reader\n  and ")
        emphasis = etree.SubElement(marked, "{http://www.tei-c.org/ns/1.0}hi")
        emphasis.text = "congregation"

        with self.assertNoLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("proj", "a.xml", plain)
            self.db.add_urn_mapping("proj", "b.xml", marked)

    def test_non_instruction_note_urns_are_not_checked(self):
        """A note URN names a kind of note shared across books; wording is free to differ."""
        urn = "urn:x-opensiddur:note:footnote"
        with self.assertNoLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.add_urn_mapping("proj", "a.xml", self._note(urn, "one wording"))
            self.db.add_urn_mapping("proj", "b.xml", self._note(urn, "another wording"))


class TestVersionStamp(unittest.TestCase):
    """A database built by other indexing code is rebuilt rather than trusted (#165)."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.db_path = Path(temp_dir.name) / 'reference.db'

    def _populate(self):
        with ReferenceDatabase(self.db_path) as db:
            root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
            div = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
            div.set("corresp", "urn:x-opensiddur:text:test/1")
            db.add_urn_mapping("proj", "doc.xml", div)
            db.conn.execute(
                "INSERT INTO indexed_files (project, file_name, content_hash) "
                "VALUES ('proj', 'doc.xml', 'abc')")
            db.conn.commit()

    def _stored_version(self, db):
        return db.conn.execute(
            "SELECT value FROM refdb_meta WHERE key = 'version'").fetchone()['value']

    def test_same_version_keeps_the_data(self):
        self._populate()
        with ReferenceDatabase(self.db_path) as db:
            self.assertEqual(len(db.get_urns_by_project("proj")), 1)
            self.assertEqual(db.get_files_by_project("proj"), ["doc.xml"])
            self.assertEqual(self._stored_version(db), refdb.REFDB_VERSION)

    def test_a_different_version_rebuilds_from_scratch(self):
        self._populate()
        with mock.patch.object(refdb, 'REFDB_VERSION', 'some-other-version'):
            with ReferenceDatabase(self.db_path) as db:
                self.assertEqual(db.get_urns_by_project("proj"), [])
                self.assertEqual(db.list_projects(), [])
                self.assertEqual(self._stored_version(db), 'some-other-version')

    def test_a_database_without_a_stamp_is_rebuilt_on_the_current_shape(self):
        # A database from before the stamp existed, on the pre-element_text shape.
        old = sqlite3.connect(self.db_path)
        old.execute("""
            CREATE TABLE urn_mappings (
                urn TEXT NOT NULL,
                project TEXT NOT NULL,
                file_name TEXT NOT NULL,
                element_path TEXT NOT NULL,
                element_tag TEXT NOT NULL,
                element_type TEXT,
                end_element_path TEXT,
                end_includes_tail BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (urn, project)
            )
        """)
        old.execute(
            "INSERT INTO urn_mappings (urn, project, file_name, element_path, element_tag) "
            "VALUES ('urn:x-opensiddur:instruction:role/reader', 'proj', 'old.xml', '/a', 'note')"
        )
        old.commit()
        old.close()

        with ReferenceDatabase(self.db_path) as db:
            columns = {row[1] for row in db.conn.execute("PRAGMA table_info(urn_mappings)")}
            self.assertIn('element_text', columns)
            self.assertEqual(db.list_projects(), [])
            self.assertEqual(self._stored_version(db), refdb.REFDB_VERSION)


class TestReferenceDatabaseGetUrnMappings(unittest.TestCase):
    """Test get_urn_mappings functionality."""

    def setUp(self):
        """Set up a temporary database with test data."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_urn.db'
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)
        self._setup_test_data()
    
    def _create_element_with_corresp(self, corresp: str, element_type: str = None) -> ElementBase:
        """Helper method to create an element with a corresp attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem.set("corresp", corresp)
        if element_type:
            elem.set("type", element_type)
        return elem
    
    def _setup_test_data(self):
        """Set up test data after helper method is defined."""
        # Add test data
        elem1 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        elem2 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        elem3 = self._create_element_with_corresp("urn:x-opensiddur:test:doc2", "chapter")
        self.db.add_urn_mapping("wlc", "doc1.xml", elem1)
        self.db.add_urn_mapping("jps1917", "doc1.xml", elem2)
        self.db.add_urn_mapping("wlc", "doc2.xml", elem3)

    def test_get_urn_mappings_without_filters(self):
        """Test getting all URN mappings."""
        results = self.db.get_urn_mappings()
        
        self.assertEqual(len(results), 3)
        
    def test_get_urn_mappings_with_urn(self):
        """Test getting URN mappings filtered by URN."""
        results = self.db.get_urn_mappings(urn="urn:x-opensiddur:text:doc1")
        
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result.urn, "urn:x-opensiddur:text:doc1")
        
    def test_get_urn_mappings_with_project(self):
        """Test getting URN mappings filtered by project."""
        results = self.db.get_urn_mappings(project="wlc")
        
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result.project, "wlc")
            
    def test_get_urn_mappings_with_urn_and_project(self):
        """Test getting URN mappings filtered by both URN and project."""
        results = self.db.get_urn_mappings(urn="urn:x-opensiddur:text:doc1", project="wlc")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].urn, "urn:x-opensiddur:text:doc1")
        self.assertEqual(results[0].project, "wlc")


class TestReferenceDatabaseGetByProject(unittest.TestCase):
    """Test project-level query functionality."""

    def setUp(self):
        """Set up a temporary database with test data."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_urn.db'
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)
        self._setup_test_data()
    
    def _create_element_with_corresp(self, corresp: str, element_type: str = None) -> ElementBase:
        """Helper method to create an element with a corresp attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem.set("corresp", corresp)
        if element_type:
            elem.set("type", element_type)
        return elem
    
    def _setup_test_data(self):
        """Set up test data after helper method is defined."""
        # Add test data
        elem1 = self._create_element_with_corresp("urn:x-opensiddur:text:doc1", "chapter")
        elem2 = self._create_element_with_corresp("urn:x-opensiddur:test:doc2", "chapter")
        elem3 = self._create_element_with_corresp("urn:x-opensiddur:test:doc3", "chapter")
        self.db.add_urn_mapping("wlc", "doc1.xml", elem1)
        self.db.add_urn_mapping("wlc", "doc2.xml", elem2)
        self.db.add_urn_mapping("jps1917", "doc3.xml", elem3)

    def test_get_urns_by_project(self):
        """Test getting all URNs for a project."""
        results = self.db.get_urns_by_project("wlc")
        
        self.assertEqual(len(results), 2)
        urns = {r.urn for r in results}
        self.assertEqual(urns, {"urn:x-opensiddur:text:doc1", "urn:x-opensiddur:test:doc2"})
        
        # All should be in wlc project
        for result in results:
            self.assertEqual(result.project, "wlc")

    def test_get_urns_by_nonexistent_project(self):
        """Test getting URNs for non-existent project returns empty list."""
        results = self.db.get_urns_by_project("nonexistent")
        
        self.assertEqual(results, [])
    
    def test_get_files_by_project(self):
        """Test getting list of files in a project."""
        files = self.db.get_files_by_project("wlc")
        
        self.assertEqual(len(files), 2)
        self.assertIn("doc1.xml", files)
        self.assertIn("doc2.xml", files)
    
    def test_get_files_by_project_sorted(self):
        """Test that files are returned in sorted order."""
        files = self.db.get_files_by_project("wlc")
        
        self.assertEqual(files, ["doc1.xml", "doc2.xml"])
    
    def test_get_files_by_project_single_file(self):
        """Test getting files for project with single file."""
        files = self.db.get_files_by_project("jps1917")
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], "doc3.xml")
    
    def test_get_files_by_nonexistent_project(self):
        """Test getting files for non-existent project returns empty list."""
        files = self.db.get_files_by_project("nonexistent")
        
        self.assertEqual(files, [])
    
    def test_get_files_by_project_no_duplicates(self):
        """Test that files list contains no duplicates."""
        # Add multiple URNs to same file
        self.db.add_urn_mapping("wlc", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:text:doc1/new", "chapter"))
        self.db.add_urn_mapping("wlc", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:text:doc1/another", "chapter"))
        
        files = self.db.get_files_by_project("wlc")
        
        # Should still be 2 files (doc1.xml and doc2.xml), not more
        self.assertEqual(len(files), 2)
        self.assertEqual(files.count("doc1.xml"), 1)  # No duplicates
    
    def test_list_projects(self):
        """Test listing all projects in the database."""
        projects = self.db.list_projects()
        
        self.assertEqual(len(projects), 2)
        self.assertIn("wlc", projects)
        self.assertIn("jps1917", projects)
    
    def test_list_projects_sorted(self):
        """Test that projects are returned in sorted order."""
        projects = self.db.list_projects()
        
        self.assertEqual(projects, ["jps1917", "wlc"])
    
    def test_list_projects_single(self):
        """Test listing when only one project exists."""
        # Remove jps1917 project
        self.db.remove_project("jps1917")
        
        projects = self.db.list_projects()
        
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0], "wlc")
    
    def test_list_projects_empty(self):
        """Test listing projects when database is empty."""
        # Remove all projects
        self.db.remove_project("wlc")
        self.db.remove_project("jps1917")
        
        projects = self.db.list_projects()
        
        self.assertEqual(projects, [])


class TestReferenceDatabaseIndexing(unittest.TestCase):
    """Test URN indexing functionality."""

    def setUp(self):
        """Set up temporary database and XML files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_urn.db'
        self.project_dir = Path(self.temp_dir.name) / 'projects'
        self.test_project_dir = self.project_dir / 'test_project'
        self.test_project_dir.mkdir(parents=True)
        
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)

    def _create_test_xml(self, filename, urns):
        """Helper to create a test XML file with URNs."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        root.set("{http://www.w3.org/XML/1998/namespace}id", "test")
        
        for urn in urns:
            elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
            elem.set("corresp", urn)
        
        xml_path = self.test_project_dir / filename
        tree = etree.ElementTree(root)
        tree.write(str(xml_path), encoding='utf-8', xml_declaration=True)
        return xml_path

    def test_index_file(self):
        """Test indexing a single XML file."""
        urns = [
            "urn:x-opensiddur:text:doc1",
            "urn:x-opensiddur:text:doc1/1",
            "urn:x-opensiddur:text:doc1/1/1",
        ]
        xml_path = self._create_test_xml("doc1.xml", urns)
        
        count = self.db.index_file(xml_path, "test_project", "doc1.xml")
        
        self.assertEqual(count, 3)
        
        # Verify URNs were indexed
        for urn in urns:
            results = self.db.get_urn_mappings(urn=urn)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].project, "test_project")
            self.assertEqual(results[0].file_name, "doc1.xml")

    def test_index_file_ignores_non_opensiddur_urns(self):
        """Test that indexing ignores URNs not starting with urn:x-opensiddur:."""
        urns = [
            "urn:x-opensiddur:text:doc1",
            "urn:other:test:doc2",  # Should be ignored
            "http://example.com",   # Should be ignored
        ]
        xml_path = self._create_test_xml("doc1.xml", urns)
        
        count = self.db.index_file(xml_path, "test_project", "doc1.xml")
        
        self.assertEqual(count, 1)  # Only one valid URN

    def test_index_urns(self):
        """Test indexing all XML files in a project directory."""
        # Create multiple XML files
        self._create_test_xml("doc1.xml", ["urn:x-opensiddur:text:doc1"])
        self._create_test_xml("doc2.xml", ["urn:x-opensiddur:test:doc2"])
        self._create_test_xml("doc3.xml", ["urn:x-opensiddur:test:doc3"])
        
        total = self.db.index_project("test_project", self.project_dir)
        
        self.assertEqual(total, 3)
        
        # Verify all were indexed
        results = self.db.get_urns_by_project("test_project")
        self.assertEqual(len(results), 3)

    def test_index_urns_nonexistent_project(self):
        """Test indexing non-existent project raises ValueError."""
        with self.assertRaises(ValueError):
            self.db.index_project("nonexistent_project", self.project_dir)

    def test_index_file_with_namespaces(self):
        """Test indexing file with multiple namespaces."""
        # Create XML with both tei and j namespaces
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem1 = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem1.set("corresp", "urn:x-opensiddur:test:tei")
        
        elem2 = etree.SubElement(root, "{http://jewishliturgy.org/ns/jlptei/2}ptr")
        elem2.set("corresp", "urn:x-opensiddur:test:jlptei")
        
        xml_path = self.test_project_dir / "test.xml"
        tree = etree.ElementTree(root)
        tree.write(str(xml_path), encoding='utf-8', xml_declaration=True)
        
        count = self.db.index_file(xml_path, "test_project", "test.xml")
        
        self.assertEqual(count, 2)


class TestReferenceDatabaseRemoval(unittest.TestCase):
    """Test URN removal functionality."""

    def setUp(self):
        """Set up a temporary database with test data."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_urn.db'
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)
        self._setup_test_data()
    
    def _create_element_with_corresp(self, corresp: str, element_type: str = None) -> ElementBase:
        """Helper method to create an element with a corresp attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem.set("corresp", corresp)
        if element_type:
            elem.set("type", element_type)
        return elem
    
    def _setup_test_data(self):
        """Set up test data after helper method is defined."""
        # Add test data
        self.db.add_urn_mapping("wlc", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:text:doc1/1", "chapter"))
        self.db.add_urn_mapping("wlc", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:text:doc1/2", "chapter"))
        self.db.add_urn_mapping("wlc", "doc2.xml", self._create_element_with_corresp("urn:x-opensiddur:test:doc2/1", "chapter"))
        self.db.add_urn_mapping("jps1917", "doc3.xml", self._create_element_with_corresp("urn:x-opensiddur:test:doc3/1", "chapter"))
        self.db.add_urn_mapping("jps1917", "doc4.xml", self._create_element_with_corresp("urn:x-opensiddur:test:doc4/1", "chapter"))

    def test_remove_file(self):
        """Test removing all URNs for a specific file."""
        # Remove doc1.xml from wlc project
        removed_count = self.db.remove_file("doc1.xml", "wlc")
        
        self.assertEqual(removed_count, 2)
        
        # Verify doc1.xml URNs are gone
        results = self.db.get_urn_mappings(urn="urn:x-opensiddur:text:doc1/1")
        self.assertEqual(results, [])
        
        # Verify other files still exist
        results = self.db.get_urn_mappings(urn="urn:x-opensiddur:test:doc2/1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_name, "doc2.xml")

    def test_remove_file_nonexistent(self):
        """Test removing non-existent file returns 0."""
        removed_count = self.db.remove_file("nonexistent.xml", "wlc")
        
        self.assertEqual(removed_count, 0)

    def test_remove_file_only_affects_specified_project(self):
        """Test that removing a file only affects the specified project."""
        # Add same file name in different project
        self.db.add_urn_mapping("jps1917", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:text:doc1/1", "chapter"))
        
        # Remove from wlc only
        removed_count = self.db.remove_file("doc1.xml", "wlc")
        
        self.assertEqual(removed_count, 2)
        
        # Verify jps1917 version still exists
        results = self.db.get_urn_mappings(urn="urn:x-opensiddur:text:doc1/1", project="jps1917")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].project, "jps1917")

    def test_remove_project(self):
        """Test removing all URNs for an entire project."""
        # Remove entire wlc project
        removed_count = self.db.remove_project("wlc")
        
        self.assertEqual(removed_count, 3)  # doc1/1, doc1/2, doc2/1
        
        # Verify wlc URNs are gone
        results = self.db.get_urns_by_project("wlc")
        self.assertEqual(results, [])
        
        # Verify jps1917 still exists
        results = self.db.get_urns_by_project("jps1917")
        self.assertEqual(len(results), 2)

    def test_remove_project_nonexistent(self):
        """Test removing non-existent project returns 0."""
        removed_count = self.db.remove_project("nonexistent")
        
        self.assertEqual(removed_count, 0)

    def test_remove_project_all_files(self):
        """Test that removing project removes all files in that project."""
        # Remove jps1917 project
        removed_count = self.db.remove_project("jps1917")
        
        self.assertEqual(removed_count, 2)  # doc3/1, doc4/1
        
        # Verify all jps1917 URNs are gone
        for urn in ["urn:x-opensiddur:test:doc3/1", "urn:x-opensiddur:test:doc4/1"]:
            results = self.db.get_urn_mappings(urn=urn, project="jps1917")
            self.assertEqual(results, [])


class TestReferenceDatabaseSync(unittest.TestCase):
    """Test URN synchronization functionality."""

    def setUp(self):
        """Set up temporary database and file system."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_urn.db'
        self.project_dir = Path(self.temp_dir.name) / 'projects'
        self.project_dir.mkdir()
        
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)
    
    def _create_element_with_corresp(self, corresp: str, element_type: str = None) -> ElementBase:
        """Helper method to create an element with a corresp attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem.set("corresp", corresp)
        if element_type:
            elem.set("type", element_type)
        return elem

    def _create_xml_file(self, project: str, file_name: str, urns: list[str]):
        """Helper to create an XML file with URNs."""
        project_path = self.project_dir / project
        project_path.mkdir(exist_ok=True)
        
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        for urn in urns:
            elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
            elem.set("corresp", urn)
        
        file_path = project_path / file_name
        tree = etree.ElementTree(root)
        tree.write(str(file_path), encoding='utf-8', xml_declaration=True)
        return file_path

    def test_sync_file_add_new(self):
        """Test syncing a new file adds it to database."""
        # Create file on disk
        self._create_xml_file("test_proj", "doc1.xml", ["urn:x-opensiddur:test:1"])
        
        # Sync the file
        result = self.db.sync_file("doc1.xml", "test_proj", self.project_dir)
        
        self.assertEqual(result['action'], 'added')
        self.assertEqual(result['references'], 1)
        
        # Verify it's in database
        urns = self.db.get_urns_by_project("test_proj")
        self.assertEqual(len(urns), 1)

    def test_sync_file_unchanged(self):
        """Test syncing unchanged file skips it."""
        # Create and index file
        file_path = self._create_xml_file("test_proj", "doc1.xml", ["urn:x-opensiddur:test:1"])
        
        # Set file modification time to the past
        past_time = time.time() - 10
        os.utime(file_path, (past_time, past_time))
        
        # Index the file
        self.db.index_file(file_path, "test_proj", "doc1.xml")
        
        # Sync again without modifications
        result = self.db.sync_file("doc1.xml", "test_proj", self.project_dir)
        
        self.assertEqual(result['action'], 'skipped')
        self.assertEqual(result['references'], 0)

    def test_sync_file_updated(self):
        """Test syncing modified file updates database."""
        # Create and index file
        file_path = self._create_xml_file("test_proj", "doc1.xml", ["urn:x-opensiddur:test:1"])
        self.db.index_file(file_path, "test_proj", "doc1.xml")
        
        # Modify file
        self._create_xml_file("test_proj", "doc1.xml", ["urn:x-opensiddur:test:1", "urn:x-opensiddur:test:2"])
        
        # Sync the modified file
        result = self.db.sync_file("doc1.xml", "test_proj", self.project_dir)
        
        self.assertEqual(result['action'], 'updated')
        self.assertEqual(result['references'], 2)
        
        # Verify updated content
        urns = self.db.get_urns_by_project("test_proj")
        self.assertEqual(len(urns), 2)

    def test_sync_file_removed(self):
        """Test syncing removed file deletes from database."""
        # Index a file that doesn't exist
        self.db.add_urn_mapping("test_proj", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:test:1", "chapter"))
        
        # Sync (file doesn't exist)
        result = self.db.sync_file("doc1.xml", "test_proj", self.project_dir)
        
        self.assertEqual(result['action'], 'removed')
        self.assertEqual(result['references'], 1)
        
        # Verify removed from database
        urns = self.db.get_urns_by_project("test_proj")
        self.assertEqual(len(urns), 0)

    def test_sync_project_add_files(self):
        """Test syncing project adds new files."""
        # Create files on disk
        self._create_xml_file("test_proj", "doc1.xml", ["urn:x-opensiddur:test:1"])
        self._create_xml_file("test_proj", "doc2.xml", ["urn:x-opensiddur:test:2"])
        
        # Sync project
        result = self.db.sync_project("test_proj", self.project_dir)
        
        self.assertEqual(result['action'], 'project_synced')
        self.assertEqual(result['added'], 2)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['removed'], 0)
        self.assertEqual(result['skipped'], 0)

    def test_sync_project_remove_orphaned(self):
        """Test syncing project removes orphaned files."""
        # Add file to database that doesn't exist on disk
        self.db.add_urn_mapping("test_proj", "orphan.xml", self._create_element_with_corresp("urn:x-opensiddur:test:orphan", "chapter"))
        
        # Create one real file
        self._create_xml_file("test_proj", "doc1.xml", ["urn:x-opensiddur:test:1"])
        
        # Sync project
        result = self.db.sync_project("test_proj", self.project_dir)
        
        self.assertEqual(result['removed'], 1)  # orphan.xml removed
        self.assertEqual(result['added'], 1)    # doc1.xml added
        
        # Verify orphan is gone
        files = self.db.get_files_by_project("test_proj")
        self.assertNotIn("orphan.xml", files)
        self.assertIn("doc1.xml", files)

    def test_sync_project_nonexistent(self):
        """Test syncing non-existent project removes it from database."""
        # Add project to database
        self.db.add_urn_mapping("nonexistent", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:test:1", "chapter"))
        
        # Sync non-existent project
        result = self.db.sync_project("nonexistent", self.project_dir)
        
        self.assertEqual(result['action'], 'project_removed')
        self.assertGreater(result['removed'], 0)
        
        # Verify project is gone
        projects = self.db.list_projects()
        self.assertNotIn("nonexistent", projects)

    def test_sync_projects_all(self):
        """Test syncing all projects."""
        # Create projects on disk
        self._create_xml_file("proj1", "doc1.xml", ["urn:x-opensiddur:test:1"])
        self._create_xml_file("proj2", "doc2.xml", ["urn:x-opensiddur:test:2"])
        
        # Add orphaned project to database
        self.db.add_urn_mapping("orphaned_proj", "orphan.xml", self._create_element_with_corresp("urn:x-opensiddur:test:orphan", "chapter"))
        
        # Sync all projects
        result = self.db.sync_projects(self.project_dir)
        
        self.assertEqual(result['action'], 'projects_synced')
        self.assertEqual(result['total_added'], 2)
        self.assertEqual(result['orphaned_projects_removed'], 1)
        
        # Verify projects
        projects = self.db.list_projects()
        self.assertIn("proj1", projects)
        self.assertIn("proj2", projects)
        self.assertNotIn("orphaned_proj", projects)

    def test_sync_projects_empty_directory(self):
        """Test syncing with empty project directory."""
        # Add some data to database
        self.db.add_urn_mapping("proj1", "doc1.xml", self._create_element_with_corresp("urn:x-opensiddur:test:1", "chapter"))
        
        # Sync with empty directory
        result = self.db.sync_projects(self.project_dir)
        
        self.assertEqual(result['orphaned_projects_removed'], 1)
        
        # Database should be empty
        projects = self.db.list_projects()
        self.assertEqual(projects, [])


class TestIncrementalSync(unittest.TestCase):
    """Incremental sync decides by content, and ends where a fresh build would (#165)."""

    TEI = "http://www.tei-c.org/ns/1.0"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project_dir = Path(self.temp_dir.name) / 'projects'
        self.project_dir.mkdir()
        self.db = self._open('incremental.db')

    def _open(self, name: str) -> ReferenceDatabase:
        db = ReferenceDatabase(Path(self.temp_dir.name) / name)
        self.addCleanup(db.close)
        return db

    def _write(self, project: str, file_name: str, urns=(), targets=()) -> Path:
        """Write a synthetic file carrying `urns` as div/@corresp and `targets` as ptr/@target."""
        project_path = self.project_dir / project
        project_path.mkdir(exist_ok=True)
        root = etree.Element(f"{{{self.TEI}}}TEI")
        text = etree.SubElement(root, f"{{{self.TEI}}}text")
        for urn in urns:
            etree.SubElement(text, f"{{{self.TEI}}}div").set("corresp", urn)
        for target in targets:
            etree.SubElement(text, f"{{{self.TEI}}}ptr").set("target", target)
        file_path = project_path / file_name
        etree.ElementTree(root).write(str(file_path), encoding='utf-8', xml_declaration=True)
        return file_path

    @staticmethod
    def _dump(db: ReferenceDatabase) -> tuple[list, list, list]:
        """Everything the database says, without the timestamps that differ between builds."""
        urns = db.conn.execute(
            "SELECT urn, project, file_name, element_path, element_tag, element_type, "
            "end_element_path, end_includes_tail, element_text FROM urn_mappings "
            "ORDER BY project, urn").fetchall()
        references = db.conn.execute(
            "SELECT element_path, element_tag, element_type, target_start, target_end, "
            "target_is_id, corresponding_urn, project, file_name FROM element_references "
            "ORDER BY project, file_name, element_path, target_start").fetchall()
        files = db.conn.execute(
            "SELECT project, file_name, content_hash FROM indexed_files "
            "ORDER BY project, file_name").fetchall()
        return ([tuple(r) for r in urns], [tuple(r) for r in references],
                [tuple(r) for r in files])

    def test_incremental_sync_matches_a_fresh_build(self):
        self._write("proj1", "a.xml", urns=["urn:x-opensiddur:text:t/a"])
        self._write("proj1", "b.xml", urns=["urn:x-opensiddur:text:t/b"],
                    targets=["urn:x-opensiddur:text:t/a"])
        self._write("proj1", "c.xml", urns=["urn:x-opensiddur:text:t/c"])
        self._write("proj1", "old_name.xml", targets=["#x"])
        self._write("proj2", "d.xml", urns=["urn:x-opensiddur:text:t/d"])
        self._write("proj3", "e.xml", targets=["urn:x-opensiddur:text:t/a"])
        self.db.sync_projects(self.project_dir)

        # Modify, add, delete, rename a file, and delete a project whose files carry
        # only references.
        self._write("proj1", "b.xml", urns=["urn:x-opensiddur:text:t/b2"],
                    targets=["urn:x-opensiddur:text:t/c"])
        self._write("proj1", "new.xml", urns=["urn:x-opensiddur:text:t/new"])
        (self.project_dir / "proj1" / "c.xml").unlink()
        (self.project_dir / "proj1" / "old_name.xml").rename(
            self.project_dir / "proj1" / "new_name.xml")
        (self.project_dir / "proj3" / "e.xml").unlink()
        (self.project_dir / "proj3").rmdir()

        result = self.db.sync_projects(self.project_dir)

        self.assertEqual(result['total_files_added'], 2)    # new.xml, new_name.xml
        self.assertEqual(result['total_files_updated'], 1)  # b.xml
        self.assertEqual(result['total_files_removed'], 2)  # c.xml, old_name.xml
        self.assertEqual(result['total_skipped'], 2)        # a.xml, d.xml
        self.assertEqual(result['orphaned_projects_removed'], 1)  # proj3

        fresh = self._open('fresh.db')
        fresh.sync_projects(self.project_dir)
        self.assertEqual(self._dump(self.db), self._dump(fresh))
        self.assertNotIn("proj3", self.db.list_projects())

    def test_newer_mtime_with_the_same_content_is_skipped(self):
        file_path = self._write("proj", "a.xml", urns=["urn:x-opensiddur:text:t/a"])
        self.db.sync_projects(self.project_dir)

        # What a fresh checkout does to every file.
        future = time.time() + 3600
        os.utime(file_path, (future, future))

        result = self.db.sync_file("a.xml", "proj", self.project_dir)
        self.assertEqual(result['action'], 'skipped')

    def test_changed_content_with_the_same_mtime_is_updated(self):
        file_path = self._write("proj", "a.xml", urns=["urn:x-opensiddur:text:t/a"])
        past = time.time() - 3600
        os.utime(file_path, (past, past))
        self.db.sync_projects(self.project_dir)

        self._write("proj", "a.xml", urns=["urn:x-opensiddur:text:t/a2"])
        os.utime(file_path, (past, past))

        result = self.db.sync_file("a.xml", "proj", self.project_dir)
        self.assertEqual(result['action'], 'updated')
        self.assertEqual([m.urn for m in self.db.get_urns_by_project("proj")],
                         ["urn:x-opensiddur:text:t/a2"])

    def test_a_file_with_nothing_to_index_is_skipped_once_seen(self):
        self._write("proj", "empty.xml")
        self.assertEqual(self.db.sync_file("empty.xml", "proj", self.project_dir)['action'],
                         'added')
        self.assertEqual(self.db.sync_file("empty.xml", "proj", self.project_dir)['action'],
                         'skipped')

    def test_a_file_that_fails_to_index_is_retried(self):
        project_path = self.project_dir / "proj"
        project_path.mkdir()
        (project_path / "broken.xml").write_text("<TEI><unclosed></TEI>")

        with self.assertLogs("opensiddur.exporter.refdb", level="ERROR"):
            first = self.db.sync_file("broken.xml", "proj", self.project_dir)
            second = self.db.sync_file("broken.xml", "proj", self.project_dir)

        self.assertEqual(first['action'], 'added')
        self.assertEqual(second['action'], 'added')
        self.assertIsNone(self.db._get_indexed_hash("broken.xml", "proj"))

    def test_a_dropped_repeat_takes_over_when_its_holder_lets_go(self):
        """An incremental sync ends where a fresh build does after the holder gives a URN up."""
        for name in ("a.xml", "b.xml"):
            self._write("proj", name, urns=["urn:x-opensiddur:text:t/u"])
        with self.assertLogs("opensiddur.exporter.refdb", level="WARNING"):
            self.db.sync_projects(self.project_dir)
        held_by = self.db.get_urn_mappings("urn:x-opensiddur:text:t/u", "proj")[0].file_name
        self._write("proj", held_by, urns=["urn:x-opensiddur:text:t/other"])
        self.db.sync_projects(self.project_dir)

        fresh = self._open("fresh.db")
        fresh.sync_projects(self.project_dir)
        self.assertEqual(self._dump(self.db), self._dump(fresh))
        other = ({"a.xml", "b.xml"} - {held_by}).pop()
        self.assertEqual(
            [m.file_name for m in self.db.get_urn_mappings("urn:x-opensiddur:text:t/u", "proj")],
            [other])

    def test_a_file_that_fails_partway_leaves_nothing_behind(self):
        """A file is indexed whole or not at all, and the failure is recorded for the sync.

        Indexed row by row, a failure partway left the URNs before it resolvable and the ones
        after it not, while the sync still reported success.
        """
        self._write("proj", "a.xml", urns=["urn:x-opensiddur:text:t/a"])
        self._write("proj", "b.xml", urns=["urn:x-opensiddur:text:t/stale"], targets=["#x"])
        with mock.patch.object(self.db, "add_reference", side_effect=RuntimeError("boom")), \
                self.assertLogs("opensiddur.exporter.refdb", level="ERROR"):
            self.db.sync_projects(self.project_dir)
        self.assertIsNone(self.db._get_indexed_hash("b.xml", "proj"))
        self.assertNotIn("urn:x-opensiddur:text:t/stale",
                         [m.urn for m in self.db.get_urns_by_project("proj")])
        self.assertIn("urn:x-opensiddur:text:t/a",
                      [m.urn for m in self.db.get_urns_by_project("proj")])
        self.assertEqual(len(self.db.errors), 1)
        self.assertIn("b.xml", self.db.errors[0])

        # Once the failure is gone the retry leaves exactly what a fresh build does.
        self.db.sync_projects(self.project_dir)
        fresh = self._open('fresh.db')
        fresh.sync_projects(self.project_dir)
        self.assertEqual(self._dump(self.db), self._dump(fresh))

    def test_a_deleted_reference_only_file_is_removed(self):
        self._write("proj", "a.xml", urns=["urn:x-opensiddur:text:t/a"])
        self._write("proj", "refs.xml", targets=["urn:x-opensiddur:text:t/a"])
        self.db.sync_projects(self.project_dir)
        self.assertEqual(len(self.db.get_references_by_project("proj")), 1)

        (self.project_dir / "proj" / "refs.xml").unlink()
        self.db.sync_projects(self.project_dir)

        self.assertEqual(self.db.get_references_by_project("proj"), [])
        self.assertEqual(self.db.get_files_by_project("proj"), ["a.xml"])


class TestReferenceDatabaseReferences(unittest.TestCase):
    """Test reference tracking functionality."""

    def setUp(self):
        """Set up a temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / 'test_ref.db'
        self.db = ReferenceDatabase(self.db_path)
        self.addCleanup(self.db.close)

    def _create_element_with_target(self, target: str, element_type: str = None, 
                                   target_end: str = None, corresp: str = None):
        """Helper to create an element with target attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}ptr")
        elem.set("target", target)
        if element_type:
            elem.set("type", element_type)
        if target_end:
            elem.set("targetEnd", target_end)
        if corresp:
            elem.set("corresp", corresp)
        return elem
    
    def _create_element_with_corresp(self, corresp: str, element_type: str = None) -> ElementBase:
        """Helper method to create an element with a corresp attribute."""
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        elem.set("corresp", corresp)
        if element_type:
            elem.set("type", element_type)
        return elem

    def test_add_reference_with_urn_target(self):
        """Test adding a reference with URN target."""
        elem = self._create_element_with_target(
            target="urn:x-opensiddur:text:doc1",
            element_type="transclude",
            corresp="urn:x-opensiddur:ref:1"
        )
        
        self.db.add_reference("test_project", "test.xml", elem)
        
        # Verify it was added
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT * FROM element_references WHERE target_start = ?', 
                      ("urn:x-opensiddur:text:doc1",))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row['target_start'], "urn:x-opensiddur:text:doc1")
        self.assertEqual(row['element_type'], "transclude")
        self.assertEqual(row['corresponding_urn'], "urn:x-opensiddur:ref:1")
        self.assertFalse(row['target_is_id'])
        self.assertEqual(row['project'], "test_project")
        self.assertEqual(row['file_name'], "test.xml")

    def test_add_reference_with_id_target(self):
        """Test adding a reference with ID target (#id format)."""
        elem = self._create_element_with_target(
            target="#verse1",
            element_type="link"
        )
        
        self.db.add_reference("test_project", "test.xml", elem)
        
        # Verify it was added
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT * FROM element_references WHERE target_start = ?', ("#verse1",))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row['target_start'], "#verse1")
        self.assertTrue(row['target_is_id'])

    def test_add_reference_with_target_range(self):
        """Test adding a reference with targetEnd."""
        elem = self._create_element_with_target(
            target="urn:x-opensiddur:text:doc1/1",
            target_end="urn:x-opensiddur:text:doc1/5",
            element_type="range"
        )
        
        self.db.add_reference("test_project", "test.xml", elem)
        
        # Verify range was stored
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT * FROM element_references WHERE target_start = ?', 
                      ("urn:x-opensiddur:text:doc1/1",))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        self.assertEqual(row['target_end'], "urn:x-opensiddur:text:doc1/5")

    def test_add_reference_with_multiple_targets(self):
        """Test adding a reference with space-separated targets."""
        elem = self._create_element_with_target(
            target="urn:x-opensiddur:text:doc1 urn:x-opensiddur:test:doc2",
            element_type="multi"
        )
        
        self.db.add_reference("test_project", "test.xml", elem)
        
        # Verify both targets were added as separate rows
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT * FROM element_references WHERE project = ? AND file_name = ?', 
                      ("test_project", "test.xml"))
        rows = cursor.fetchall()
        
        self.assertEqual(len(rows), 2)
        targets = {row['target_start'] for row in rows}
        self.assertEqual(targets, {"urn:x-opensiddur:text:doc1", "urn:x-opensiddur:test:doc2"})

    def test_add_reference_stores_element_path(self):
        """Test that element path is correctly stored."""
        elem = self._create_element_with_target(target="urn:x-opensiddur:text:doc1")
        
        self.db.add_reference("test_project", "test.xml", elem)
        
        # Verify element path was stored
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT element_path FROM element_references WHERE target_start = ?', 
                      ("urn:x-opensiddur:text:doc1",))
        row = cursor.fetchone()
        
        self.assertIsNotNone(row)
        # Path should be like /ns0:TEI/ns0:ptr or /TEI[1]/ptr[1]
        # Just verify it has "ptr" in it
        self.assertIn("ptr", row['element_path'])

    def test_get_references_to_urn(self):
        """Test retrieving references to a URN."""
        # Create two different XML trees so elements have different paths
        root1 = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        elem1 = etree.SubElement(root1, "{http://www.tei-c.org/ns/1.0}ptr")
        elem1.set("target", "urn:x-opensiddur:test:target")
        elem1.set("type", "type1")
        elem1.set("corresp", "urn:x-opensiddur:ref:1")
        
        root2 = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        div = etree.SubElement(root2, "{http://www.tei-c.org/ns/1.0}div")
        elem2 = etree.SubElement(div, "{http://www.tei-c.org/ns/1.0}ptr")
        elem2.set("target", "urn:x-opensiddur:test:target")
        elem2.set("type", "type2")
        elem2.set("corresp", "urn:x-opensiddur:ref:2")
        
        self.db.add_reference("proj1", "file1.xml", elem1)
        self.db.add_reference("proj1", "file2.xml", elem2)
        
        # Get references to the target URN
        results = self.db.get_references_to(urn="urn:x-opensiddur:test:target")
        
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], Reference)
        element_types = {r.element_type for r in results}
        self.assertEqual(element_types, {"type1", "type2"})

    def test_reference_tag_filter_keeps_notes_and_excludes_transclusions(self):
        target = "urn:x-opensiddur:test:target"
        root = etree.Element("root")
        for tag in ["{http://www.tei-c.org/ns/1.0}note", "{http://jewishliturgy.org/ns/jlptei/2}transclude"]:
            element = etree.SubElement(root, tag, target=target)
            self.db.add_reference("synthetic", "index.xml", element)
        self.assertEqual(len(self.db.get_references_to(urn=target)), 2)
        notes = self.db.get_references_to(urn=target, element_tag="{http://www.tei-c.org/ns/1.0}note")
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].element_tag, "{http://www.tei-c.org/ns/1.0}note")

    def _create_first_standoff_note(self, target: str) -> ElementBase:
        """Helper to create the first note of a standoff notes file.

        Every notes file has this shape, so the note's element path is the same in all of them.
        """
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        standoff = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}standOff")
        note = etree.SubElement(standoff, "{http://www.tei-c.org/ns/1.0}note")
        note.set("target", target)
        return note

    def test_get_references_to_urn_same_path_different_files(self):
        """References at the same element path in different files are all returned."""
        target = "urn:x-opensiddur:test:target"
        self.db.add_reference("proj1", "notes_a.xml", self._create_first_standoff_note(target))
        self.db.add_reference("proj1", "notes_b.xml", self._create_first_standoff_note(target))

        results = self.db.get_references_to(urn=target)

        self.assertEqual(len(results), 2)
        self.assertEqual(len({r.element_path for r in results}), 1)
        self.assertEqual({r.file_name for r in results}, {"notes_a.xml", "notes_b.xml"})

    def test_get_references_to_urn_same_path_different_projects(self):
        """References at the same element path in different projects are all returned."""
        target = "urn:x-opensiddur:test:target"
        self.db.add_reference("projA", "notes.xml", self._create_first_standoff_note(target))
        self.db.add_reference("projB", "notes.xml", self._create_first_standoff_note(target))

        results = self.db.get_references_to(urn=target)

        self.assertEqual(len(results), 2)
        self.assertEqual({r.project for r in results}, {"projA", "projB"})

    def test_get_references_to_row_found_by_both_queries_returned_once(self):
        """A reference that both the URN and the ID query find is returned once."""
        self.db.add_reference("proj1", "file1.xml", self._create_element_with_target(target="#verse1"))

        results = self.db.get_references_to(
            urn="#verse1", id="verse1", project="proj1", file_name="file1.xml")

        self.assertEqual(len(results), 1)

    def test_get_references_to_id(self):
        """Test retrieving references to an ID."""
        elem = self._create_element_with_target(target="#verse1")
        self.db.add_reference("proj1", "file1.xml", elem)
        
        # Get references to the ID
        results = self.db.get_references_to(id="verse1", project="proj1", file_name="file1.xml")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].target_start, "#verse1")
        self.assertTrue(results[0].target_is_id)

    def test_get_references_by_project(self):
        """Test retrieving all references for a project."""
        elem1 = self._create_element_with_target(target="urn:x-opensiddur:text:doc1")
        elem2 = self._create_element_with_target(target="urn:x-opensiddur:test:doc2")
        elem3 = self._create_element_with_target(target="urn:x-opensiddur:test:doc3")
        
        self.db.add_reference("proj1", "file1.xml", elem1)
        self.db.add_reference("proj1", "file2.xml", elem2)
        self.db.add_reference("proj2", "file3.xml", elem3)
        
        # Get references for proj1
        results = self.db.get_references_by_project("proj1")
        
        self.assertEqual(len(results), 2)
        projects = {r.project for r in results}
        self.assertEqual(projects, {"proj1"})

    def test_index_file_with_references(self):
        """Test that indexing a file also indexes references."""
        # Create XML with both URNs and references
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        
        # Element with corresp (URN)
        div = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        div.set("corresp", "urn:x-opensiddur:text:doc1")
        
        # Element with target (reference)
        ptr = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}ptr")
        ptr.set("target", "urn:x-opensiddur:test:target")
        ptr.set("type", "link")
        
        # Write to file
        xml_path = Path(self.temp_dir.name) / "test.xml"
        tree = etree.ElementTree(root)
        tree.write(str(xml_path), encoding='utf-8', xml_declaration=True)
        
        # Index the file
        count = self.db.index_file(xml_path, "test_project", "test.xml")
        
        # Should have indexed both URN and reference
        self.assertEqual(count, 2)
        
        # Verify URN was indexed
        urns = self.db.get_urn_mappings(project="test_project")
        self.assertEqual(len(urns), 1)
        
        # Verify reference was indexed
        refs = self.db.get_references_by_project("test_project")
        self.assertEqual(len(refs), 1)

    def test_remove_file_removes_references(self):
        """Test that removing a file also removes its references."""
        elem = self._create_element_with_target(target="urn:x-opensiddur:text:doc1")
        self.db.add_reference("proj1", "file1.xml", elem)
        
        # Also add a URN mapping
        self.db.add_urn_mapping("proj1", "file1.xml", self._create_element_with_corresp("urn:x-opensiddur:test:urn1", "chapter"))
        
        # Remove the file
        removed_count = self.db.remove_file("file1.xml", "proj1")
        
        # Should have removed both URN and reference
        self.assertEqual(removed_count, 2)
        
        # Verify references are gone
        refs = self.db.get_references_by_project("proj1")
        self.assertEqual(len(refs), 0)

    def test_remove_project_removes_references(self):
        """Test that removing a project also removes its references."""
        elem = self._create_element_with_target(target="urn:x-opensiddur:text:doc1")
        self.db.add_reference("proj1", "file1.xml", elem)
        self.db.add_urn_mapping("proj1", "file1.xml", self._create_element_with_corresp("urn:x-opensiddur:test:urn1", "chapter"))
        
        # Remove the project
        removed_count = self.db.remove_project("proj1")
        
        # Should have removed both URN and reference
        self.assertEqual(removed_count, 2)
        
        # Verify references are gone
        refs = self.db.get_references_by_project("proj1")
        self.assertEqual(len(refs), 0)

    def test_integration_get_references_to_id(self):
        """Integration test: Verify get_references_to finds references to elements with xml:id."""
        # Create XML structure with:
        # 1. An element with xml:id="verse1"
        # 2. Another element with target="#verse1" that references it
        
        root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
        
        # Create the target element with xml:id
        target_div = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
        target_div.set("{http://www.w3.org/XML/1998/namespace}id", "verse1")
        target_div.text = "This is verse 1"
        
        # Create a referencing element
        ref_ptr = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}ptr")
        ref_ptr.set("target", "#verse1")
        ref_ptr.set("type", "link")
        
        # Create another referencing element to the same ID
        ref_note = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}note")
        ref_note.set("target", "#verse1")
        ref_note.set("type", "comment")
        ref_note.text = "This references verse 1"
        
        # Create a reference to a different ID that doesn't exist
        ref_missing = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}ptr")
        ref_missing.set("target", "#nonexistent")
        ref_missing.set("type", "link")
        
        # Write to file and index it using the real workflow
        xml_path = Path(self.temp_dir.name) / "test.xml"
        tree = etree.ElementTree(root)
        tree.write(str(xml_path), encoding='utf-8', xml_declaration=True)
        
        # Use index_file() to process the XML file
        count = self.db.index_file(xml_path, "test_project", "test.xml")
        self.assertEqual(count, 3, "Should have indexed 3 references")
        
        # Test 1: Get references to "verse1" by ID (without # prefix)
        results = self.db.get_references_to(id="verse1", project="test_project", file_name="test.xml")
        self.assertEqual(len(results), 2, "Should find 2 references to verse1")
        
        # Verify the results contain the expected references
        element_types = {r.element_type for r in results}
        self.assertEqual(element_types, {"link", "comment"})
        
        # Verify all references point to the correct target
        for result in results:
            self.assertEqual(result.target_start, "#verse1")
            self.assertTrue(result.target_is_id)
            self.assertEqual(result.project, "test_project")
            self.assertEqual(result.file_name, "test.xml")
        
        # Test 2: Get references to "verse1" by ID (with # prefix)
        results_with_hash = self.db.get_references_to(id="#verse1", project="test_project", file_name="test.xml")
        self.assertEqual(len(results_with_hash), 2, "Should find 2 references with # prefix too")
        
        # Test 3: Get references to nonexistent ID
        results_nonexistent = self.db.get_references_to(id="nonexistent", project="test_project", file_name="test.xml")
        self.assertEqual(len(results_nonexistent), 1, "Should find 1 reference to nonexistent ID")
        
        # Verify it's the reference to #nonexistent
        self.assertEqual(results_nonexistent[0].target_start, "#nonexistent")
        
        # Test 4: Get references to a completely different ID
        results_different = self.db.get_references_to(id="different", project="test_project", file_name="test.xml")
        self.assertEqual(len(results_different), 0, "Should find no references to different ID")
        
        # Test 5: Verify element paths are stored and are unique
        paths = {r.element_path for r in results}
        self.assertEqual(len(paths), 2, "Should have 2 unique element paths")
        
        # Test 6: Verify we can get all references for the project
        all_project_refs = self.db.get_references_by_project("test_project")
        self.assertEqual(len(all_project_refs), 3, "Should have 3 total references in project")
        
        # Test 7: Verify the references contain the expected element tags
        element_tags = {r.element_tag for r in all_project_refs}
        self.assertEqual(element_tags, {"{http://www.tei-c.org/ns/1.0}ptr", "{http://www.tei-c.org/ns/1.0}note"})


class TestMilestoneScoping(unittest.TestCase):
    """Test that a milestone's URN scope ends at the right following milestone.

    A milestone scopes to the next milestone of the same unit, or of a unit that contains it.
    Reading divisions overlap on purpose, so they must not terminate each other.
    """

    TEI = "http://www.tei-c.org/ns/1.0"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = ReferenceDatabase(Path(self.temp_dir.name) / 'test_urn.db')
        self.addCleanup(self.db.close)

    def _document(self, *milestones: tuple[str, str, str]) -> list[ElementBase]:
        """Build a doc of `(unit, n, corresp)` milestones separated by text-bearing segs.

        Returns the milestone elements in document order.
        """
        root = etree.Element(f"{{{self.TEI}}}TEI")
        text = etree.SubElement(root, f"{{{self.TEI}}}text")
        body = etree.SubElement(text, f"{{{self.TEI}}}body")
        created = []
        for index, (unit, n, corresp) in enumerate(milestones):
            milestone = etree.SubElement(body, f"{{{self.TEI}}}milestone")
            if unit is not None:
                milestone.set("unit", unit)
            milestone.set("n", n)
            milestone.set("corresp", corresp)
            created.append(milestone)
            seg = etree.SubElement(body, f"{{{self.TEI}}}seg")
            seg.set("{http://www.w3.org/XML/1998/namespace}id", f"seg{index}")
            seg.text = f"text {index}"
        return created

    def _scope_end(self, milestone: ElementBase) -> str:
        end_path, _ = find_end_of_mapping(milestone)
        return end_path

    def test_verse_ends_at_next_verse(self):
        verse1, _verse2 = self._document(
            ("verse", "1", "urn:x-opensiddur:text:bible:genesis/1/1"),
            ("verse", "2", "urn:x-opensiddur:text:bible:genesis/1/2"),
        )
        self.assertTrue(self._scope_end(verse1).endswith("seg[1]"))

    def test_verse_ends_at_next_chapter(self):
        """A chapter contains verses, so it closes the last verse of the previous chapter.

        Without this, a range ending on a chapter boundary would swallow the following
        chapter milestone and render a spurious chapter number.
        """
        verse, _chapter = self._document(
            ("verse", "31", "urn:x-opensiddur:text:bible:genesis/1/31"),
            ("chapter", "2", "urn:x-opensiddur:text:bible:genesis/2"),
        )
        self.assertTrue(self._scope_end(verse).endswith("seg[1]"))

    def test_chapter_does_not_end_at_verse(self):
        """Containment is one-directional: a verse must not close the chapter holding it."""
        chapter, _verse, _next_chapter = self._document(
            ("chapter", "1", "urn:x-opensiddur:text:bible:genesis/1"),
            ("verse", "1", "urn:x-opensiddur:text:bible:genesis/1/1"),
            ("chapter", "2", "urn:x-opensiddur:text:bible:genesis/2"),
        )
        # Ends just before chapter 2, i.e. after the second seg, not the first.
        self.assertTrue(self._scope_end(chapter).endswith("seg[2]"))

    def test_verse_does_not_end_at_a_half_verse_inside_it(self):
        """A verse holding sub-verse milestones still runs to the next verse.

        If the halves closed the verse, every verse carrying them would silently shrink to
        its first half wherever it were transcluded.
        """
        verse, _a, _b, _next_verse = self._document(
            ("verse", "31", "urn:x-opensiddur:text:bible:genesis/1/31"),
            ("half-verse", "a", "urn:x-opensiddur:text:bible:genesis/1/31/a"),
            ("half-verse", "b", "urn:x-opensiddur:text:bible:genesis/1/31/b"),
            ("verse", "1", "urn:x-opensiddur:text:bible:genesis/2/1"),
        )
        self.assertTrue(self._scope_end(verse).endswith("seg[3]"))

    def test_half_verse_ends_at_the_next_half_verse(self):
        verse_a = self._document(
            ("verse", "31", "urn:x-opensiddur:text:bible:genesis/1/31"),
            ("half-verse", "a", "urn:x-opensiddur:text:bible:genesis/1/31/a"),
            ("half-verse", "b", "urn:x-opensiddur:text:bible:genesis/1/31/b"),
        )[1]
        self.assertTrue(self._scope_end(verse_a).endswith("seg[2]"))

    def test_half_verse_ends_at_the_next_verse(self):
        """The second half runs to the end of its verse and no further."""
        verse_b = self._document(
            ("verse", "31", "urn:x-opensiddur:text:bible:genesis/1/31"),
            ("half-verse", "b", "urn:x-opensiddur:text:bible:genesis/1/31/b"),
            ("verse", "1", "urn:x-opensiddur:text:bible:genesis/2/1"),
        )[1]
        self.assertTrue(self._scope_end(verse_b).endswith("seg[2]"))

    def test_a_verse_part_is_not_ended_by_a_half_verse(self):
        """The two sub-verse divisions cut at different points and must not close each other.

        The Thirteen Attributes end one word past the etnachta of Exodus 34:7, so a named
        part really does straddle the accentual boundary.
        """
        venakeh = self._document(
            ("verse", "7", "urn:x-opensiddur:text:bible:exodus/34/7"),
            ("verse-part", "venakeh", "urn:x-opensiddur:text:bible:exodus/34/7/venakeh"),
            ("half-verse", "b", "urn:x-opensiddur:text:bible:exodus/34/7/b"),
            ("verse-part", "lo_yenakeh", "urn:x-opensiddur:text:bible:exodus/34/7/lo_yenakeh"),
        )[1]
        self.assertTrue(self._scope_end(venakeh).endswith("seg[3]"))

    def test_maftir_does_not_end_the_seventh_aliyah(self):
        """Maftir re-reads the close of aliyah 7; it opens inside it rather than ending it."""
        aliyah7, _maftir, _parsha = self._document(
            ("aliyah.annual", "7", "urn:x-opensiddur:text:bible:parsha/bereshit/aliyah/7"),
            ("maftir.annual", "maftir", "urn:x-opensiddur:text:bible:parsha/bereshit/maftir"),
            ("parsha.annual", "noach", "urn:x-opensiddur:text:bible:parsha/noach"),
        )
        # Runs past the maftir milestone to the end of the parsha.
        self.assertTrue(self._scope_end(aliyah7).endswith("seg[2]"))

    def test_overlapping_reading_schemes_do_not_terminate_each_other(self):
        """Weekday and triennial aliyot subdivide/cut across the annual ones."""
        annual1, _weekday2, _triennial1, _annual2 = self._document(
            ("aliyah.annual", "1", "urn:x-opensiddur:text:bible:parsha/bereshit/aliyah/1"),
            ("aliyah.weekday", "2", "urn:x-opensiddur:text:bible:parsha/bereshit/weekday/2"),
            ("aliyah.triennial", "1", "urn:x-opensiddur:text:bible:parsha/bereshit/triennial/1/1"),
            ("aliyah.annual", "2", "urn:x-opensiddur:text:bible:parsha/bereshit/aliyah/2"),
        )
        self.assertTrue(self._scope_end(annual1).endswith("seg[3]"))

    def test_parsha_ends_an_aliyah(self):
        """Aliyot do not cross parsha boundaries."""
        aliyah7, _parsha = self._document(
            ("aliyah.annual", "7", "urn:x-opensiddur:text:bible:parsha/bereshit/aliyah/7"),
            ("parsha.annual", "noach", "urn:x-opensiddur:text:bible:parsha/noach"),
        )
        self.assertTrue(self._scope_end(aliyah7).endswith("seg[1]"))

    def test_a_combined_aliyah_crosses_the_parsha_it_runs_into(self):
        """Two parshiyot read together divide as one reading, across the boundary between them."""
        combined1, _second_parsha, _combined2 = self._document(
            ("aliyah.combined", "4",
             "urn:x-opensiddur:text:bible:parsha/vayakhel_pekudei/aliyah_combined/4"),
            ("parsha.annual", "pekudei", "urn:x-opensiddur:text:bible:parsha/pekudei"),
            ("aliyah.combined", "5",
             "urn:x-opensiddur:text:bible:parsha/vayakhel_pekudei/aliyah_combined/5"),
        )
        # Runs past where Pekudei begins, to the next combined aliyah.
        self.assertTrue(self._scope_end(combined1).endswith("seg[2]"))

    def test_a_combined_reading_ends_the_divisions_it_contains(self):
        combined_aliyah, _pair = self._document(
            ("aliyah.combined", "7",
             "urn:x-opensiddur:text:bible:parsha/vayakhel_pekudei/aliyah_combined/7"),
            ("parsha.combined", "chukat_balak",
             "urn:x-opensiddur:text:bible:parsha/chukat_balak"),
        )
        self.assertTrue(self._scope_end(combined_aliyah).endswith("seg[1]"))

    def test_a_triennial_variation_is_scoped_by_the_pair_not_by_either_parshah(self):
        """Behar read alone in one cycle runs into Bechukotai, so the pair is what ends it."""
        variation, _second_parsha, _pair = self._document(
            ("aliyah.triennial.behar.IL3.2", "IL3.2.7",
             "urn:x-opensiddur:text:bible:parsha/behar/triennial/il3/2/7"),
            ("parsha.annual", "bechukotai", "urn:x-opensiddur:text:bible:parsha/bechukotai"),
            ("parsha.combined", "behar_bechukotai",
             "urn:x-opensiddur:text:bible:parsha/behar_bechukotai"),
        )
        self.assertTrue(self._scope_end(variation).endswith("seg[2]"))

    def test_falls_back_to_urn_depth_without_units(self):
        """Milestones with no @unit keep the original URN-depth heuristic."""
        verse, _chapter = self._document(
            (None, "1", "urn:x-opensiddur:text:prayer:ashrei/1/1"),
            (None, "2", "urn:x-opensiddur:text:prayer:ashrei/2"),
        )
        self.assertTrue(self._scope_end(verse).endswith("seg[1]"))

    def test_unknown_unit_falls_back_to_urn_depth(self):
        """A unit absent from the containment table still terminates by URN depth."""
        first, _second = self._document(
            ("stanza", "1", "urn:x-opensiddur:text:poem:example/1"),
            ("stanza", "2", "urn:x-opensiddur:text:poem:example/2"),
        )
        self.assertTrue(self._scope_end(first).endswith("seg[1]"))

    def test_scope_runs_to_end_of_file_when_nothing_terminates(self):
        only, = self._document(
            ("aliyah.annual", "1", "urn:x-opensiddur:text:bible:parsha/bereshit/aliyah/1"),
        )
        # A lone seg carries no positional predicate in the lxml path.
        self.assertTrue(self._scope_end(only).endswith("seg"))


class TestReferenceDatabaseContextManager(unittest.TestCase):
    """Test Reference Database context manager functionality."""

    def test_context_manager(self):
        """Test using database as context manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'test_urn.db'
            
            with ReferenceDatabase(db_path) as db:
                # Create element with corresp attribute
                root = etree.Element("{http://www.tei-c.org/ns/1.0}TEI")
                elem = etree.SubElement(root, "{http://www.tei-c.org/ns/1.0}div")
                elem.set("corresp", "urn:x-opensiddur:text:doc1")
                elem.set("type", "chapter")
                
                db.add_urn_mapping("test", "doc1.xml", elem)
                results = db.get_urn_mappings(urn="urn:x-opensiddur:text:doc1")
                self.assertEqual(len(results), 1)
            
            # Connection should be closed after context


class TestFindEndOfMapping(unittest.TestCase):
    """Test the end-of-range computation that backs milestone-scoped URNs."""

    def _end_of(self, xml: str, corresp: str) -> tuple[str, bool]:
        """Return (end path, include_tail) for the element carrying `corresp`."""
        root = etree.fromstring(xml.encode('utf-8'))
        element = root.xpath(f"//*[@corresp='{corresp}']")[0]
        return find_end_of_mapping(element)

    def test_non_milestone_ends_at_itself(self):
        """A non-milestone URN scopes to its own element and excludes its tail."""
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div corresp="urn:a"><tei:p>text</tei:p></tei:div></tei:body></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:a")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div")
        self.assertFalse(include_tail)

    def test_ends_at_preceding_sibling_of_next_milestone(self):
        """A milestone scopes up to the element just before the next same-level one."""
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div>
        <tei:milestone unit="verse" corresp="urn:book/1/1"/> one
        <tei:seg>segment</tei:seg> more
        <tei:milestone unit="verse" corresp="urn:book/1/2"/> two
    </tei:div></tei:body></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:book/1/1")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div/tei:seg")
        self.assertTrue(include_tail)

    def test_ends_at_the_element_whose_tail_is_the_last_text(self):
        """The end is the preceding sibling itself, never a node nested inside it.

        Ending at the deepest preceding element would drop the text between that
        element's close and the next milestone -- here, ' more'.
        """
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div>
        <tei:milestone unit="verse" corresp="urn:book/1/1"/> one
        <tei:choice><tei:abbr>abbr</tei:abbr><tei:expan>expansion</tei:expan></tei:choice> more
        <tei:milestone unit="verse" corresp="urn:book/1/2"/> two
    </tei:div></tei:body></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:book/1/1")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div/tei:choice")
        self.assertTrue(include_tail)

    def test_next_milestone_in_another_parent_ends_at_that_parents_predecessor(self):
        """When the next milestone opens a paragraph, the range ends with the previous one."""
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div>
        <tei:p><tei:milestone unit="verse" corresp="urn:book/1/1"/> one</tei:p>
        <tei:p><tei:milestone unit="verse" corresp="urn:book/1/2"/> two</tei:p>
        <tei:p><tei:milestone unit="verse" corresp="urn:book/1/3"/> three</tei:p>
    </tei:div></tei:body></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:book/1/2")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div/tei:p[2]")
        self.assertTrue(include_tail)

    def test_higher_level_milestone_ends_the_range(self):
        """A chapter milestone terminates a verse range."""
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div>
        <tei:milestone unit="verse" corresp="urn:book/1/1"/> one
        <tei:seg>segment</tei:seg> more
        <tei:milestone unit="chapter" corresp="urn:book/2"/> next chapter
    </tei:div></tei:body></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:book/1/1")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div/tei:seg")
        self.assertTrue(include_tail)

    def test_no_following_milestone_ends_at_the_last_sibling(self):
        """The last milestone in a file scopes to the end of its text, here its parent's end."""
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div>
        <tei:milestone unit="verse" corresp="urn:book/1/1"/> one
        <tei:seg>segment</tei:seg>
        <tei:p>last</tei:p>
    </tei:div></tei:body></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:book/1/1")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div/tei:p")
        self.assertTrue(include_tail)

    def test_no_following_milestone_runs_past_its_parent(self):
        """The last chapter of a book does not stop at the end of its first paragraph."""
        xml = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:body><tei:div>
        <tei:p><tei:milestone unit="chapter" corresp="urn:book/9"/> first paragraph</tei:p>
        <tei:p>second paragraph <tei:hi>with</tei:hi> its end</tei:p>
    </tei:div></tei:body><tei:back><tei:p>not the chapter</tei:p></tei:back></tei:text>
</tei:TEI>'''
        end_path, include_tail = self._end_of(xml, "urn:book/9")
        self.assertEqual(end_path, "/tei:TEI/tei:text/tei:body/tei:div/tei:p[2]")
        self.assertTrue(include_tail)

    def _end_of_body(self, body: str, urn: str) -> str:
        xml = (f'<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:text><tei:body>{body}'
               '</tei:body></tei:text></tei:TEI>')
        return self._end_of(xml, urn)[0]

    def test_the_end_is_never_cut_into(self):
        """The end is a whole subtree: text after an inner element's close is not lost."""
        end = self._end_of_body(
            '<tei:div><tei:p><tei:milestone unit="verse" corresp="urn:x/1"/>one</tei:p>'
            '<tei:p><tei:seg>two <tei:hi>three</tei:hi></tei:seg> four</tei:p></tei:div>',
            "urn:x/1")
        self.assertEqual(end, "/tei:TEI/tei:text/tei:body/tei:div/tei:p[2]")

    def test_the_end_is_not_inside_a_note(self):
        end = self._end_of_body(
            '<tei:div><tei:p><tei:milestone unit="verse" corresp="urn:x/1"/>one</tei:p>'
            '<tei:p>two<tei:note>n <tei:hi>h</tei:hi></tei:note> four.</tei:p></tei:div>',
            "urn:x/1")
        self.assertEqual(end, "/tei:TEI/tei:text/tei:body/tei:div/tei:p[2]")

    def test_the_scope_stays_in_its_division(self):
        """What follows the division in the body -- a colophon, an empty paragraph -- is not in it."""
        end = self._end_of_body(
            '<tei:div><tei:p><tei:milestone unit="verse" corresp="urn:x/1"/>one</tei:p>'
            '<tei:p>two</tei:p></tei:div><tei:div type="colophon">COLOPHON</tei:div><tei:p/>',
            "urn:x/1")
        self.assertEqual(end, "/tei:TEI/tei:text/tei:body/tei:div[1]/tei:p[2]")

    def test_the_milestone_closing_its_own_parent_ends_at_itself(self):
        end = self._end_of_body(
            '<tei:div><tei:p>one<tei:milestone unit="verse" corresp="urn:x/1"/></tei:p></tei:div>',
            "urn:x/1")
        self.assertEqual(end, "/tei:TEI/tei:text/tei:body/tei:div/tei:p/tei:milestone")

    def test_a_terminator_beyond_the_division_does_not_end_the_scope(self):
        end = self._end_of_body(
            '<tei:div><tei:p><tei:milestone unit="verse" corresp="urn:x/1"/>one</tei:p>'
            '<tei:p>two</tei:p></tei:div>'
            '<tei:div><tei:p><tei:milestone unit="verse"/>other</tei:p></tei:div>',
            "urn:x/1")
        self.assertEqual(end, "/tei:TEI/tei:text/tei:body/tei:div[1]/tei:p[2]")


if __name__ == '__main__':
    unittest.main()



class TestUnitTerminatingMilestone(unittest.TestCase):
    """A milestone with a unit but no corresp closes the scope of that same unit.

    Without it, a scope runs to the end of the file whenever nothing of its unit
    follows, which over-claims wherever a division ends partway through a file. See
    JLPTEI-3.md, "Terminating a scope".
    """

    TEI_NS = "http://www.tei-c.org/ns/1.0"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = ReferenceDatabase(Path(self.temp_dir.name) / "terminator.db")
        self.addCleanup(self.db.close)

    def _index(self, body: str):
        """Index a document body and return its URN mappings."""
        document = (
            f'<tei:TEI xmlns:tei="{self.TEI_NS}" xml:lang="he">'
            f"<tei:text><tei:body><tei:div>{body}</tei:div></tei:body></tei:text></tei:TEI>"
        )
        path = Path(self.temp_dir.name) / "doc.xml"
        path.write_text(document, encoding="utf-8")
        self.db.remove_file("doc.xml", "proj")
        self.db.index_file(path, "proj", "doc.xml")
        return self.db.get_urns_by_project("proj")

    OPEN = ('<tei:milestone unit="prayer" n="1" '
            'corresp="urn:x-opensiddur:text:prayer:alpha"/>')
    TAIL = "<tei:p>one</tei:p><tei:p>two</tei:p><tei:p>after</tei:p>"

    def test_without_a_terminator_the_scope_runs_to_the_end(self):
        mappings = self._index(self.OPEN + self.TAIL)
        self.assertEqual(len(mappings), 1)
        self.assertTrue(mappings[0].end_element_path.endswith("tei:p[3]"))

    def test_a_terminator_closes_the_scope_early(self):
        mappings = self._index(
            self.OPEN
            + "<tei:p>one</tei:p><tei:p>two</tei:p>"
            + '<tei:milestone unit="prayer"/>'
            + "<tei:p>after</tei:p>"
        )
        self.assertEqual(len(mappings), 1)
        self.assertTrue(mappings[0].end_element_path.endswith("tei:p[2]"))

    def test_a_terminator_is_not_itself_indexed(self):
        # It carries no corresp, so it adds no mapping and cannot be referenced.
        mappings = self._index(self.OPEN + '<tei:p>x</tei:p><tei:milestone unit="prayer"/>')
        self.assertEqual([m.urn for m in mappings],
                         ["urn:x-opensiddur:text:prayer:alpha"])

    def test_a_bare_milestone_of_another_unit_does_not_terminate(self):
        mappings = self._index(
            self.OPEN
            + "<tei:p>one</tei:p><tei:p>two</tei:p>"
            + '<tei:milestone unit="citation" n="x"/>'
            + "<tei:p>after</tei:p>"
        )
        self.assertTrue(mappings[0].end_element_path.endswith("tei:p[3]"))

    def test_an_edition_verse_milestone_does_not_terminate_a_verse(self):
        # edition-verse carries @n and never @corresp. Under the path-depth fallback it
        # would otherwise close every verse it follows, silently truncating the scope of
        # canonical verses across WLC, MAM and JPS.
        mappings = self._index(
            '<tei:milestone unit="verse" n="1" '
            'corresp="urn:x-opensiddur:text:bible:genesis/1/1"/>'
            "<tei:p>one</tei:p>"
            '<tei:milestone unit="edition-verse" n="2"/>'
            "<tei:p>still the same canonical verse</tei:p>"
        )
        self.assertEqual(len(mappings), 1)
        self.assertTrue(mappings[0].end_element_path.endswith("tei:p[2]"))

    def test_a_following_milestone_of_the_same_unit_still_terminates(self):
        mappings = self._index(
            self.OPEN
            + "<tei:p>one</tei:p>"
            + '<tei:milestone unit="prayer" n="2" '
              'corresp="urn:x-opensiddur:text:prayer:beta"/>'
            + "<tei:p>two</tei:p>"
        )
        self.assertEqual(len(mappings), 2)
        alpha = next(m for m in mappings if m.urn.endswith("alpha"))
        self.assertTrue(alpha.end_element_path.endswith("tei:p[1]"))

    def test_a_containing_unit_still_terminates(self):
        mappings = self._index(
            '<tei:milestone unit="verse" n="1" '
            'corresp="urn:x-opensiddur:text:bible:genesis/1/1"/>'
            "<tei:p>one</tei:p>"
            '<tei:milestone unit="chapter" n="2" '
            'corresp="urn:x-opensiddur:text:bible:genesis/2"/>'
            "<tei:p>two</tei:p>"
        )
        verse = next(m for m in mappings if m.urn.endswith("1/1"))
        self.assertTrue(verse.end_element_path.endswith("tei:p[1]"))
