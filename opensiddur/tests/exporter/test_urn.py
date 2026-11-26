"""Tests for the UrnResolver class."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from opensiddur.exporter.refdb import UrnMapping
from opensiddur.exporter.urn import (
    ResolvedUrn,
    ResolvedUrnRange,
    UrnResolver,
    coarsen,
    split_range,
)


def make_urn_mapping(
    project: str,
    file_name: str,
    urn: str,
    element_path: str = "/TEI/div[1]",
    element_tag: str = "{http://www.tei-c.org/ns/1.0}div",
    element_type: str | None = "chapter",
    end_element_path: str | None = None,
    end_includes_tail: bool = False,
) -> UrnMapping:
    """Helper to create UrnMapping test instances with the new end fields."""
    return UrnMapping(
        project=project,
        file_name=file_name,
        urn=urn,
        element_path=element_path,
        element_tag=element_tag,
        element_type=element_type,
        end_element_path=end_element_path or element_path,
        end_includes_tail=end_includes_tail,
    )


def make_resolved_urn(
    project: str,
    file_name: str,
    urn: str,
    element_path: str = "/TEI/div[1]",
    end_element_path: str | None = None,
    end_includes_tail: bool = False,
) -> ResolvedUrn:
    """Helper to create ResolvedUrn test instances with the new end fields."""
    return ResolvedUrn(
        project=project,
        file_name=file_name,
        urn=urn,
        element_path=element_path,
        end_element_path=end_element_path or element_path,
        end_includes_tail=end_includes_tail,
    )


class TestUrnResolverResolve(unittest.TestCase):
    """Test URN resolution functionality."""

    def setUp(self):
        """Set up with mocked database."""
        self.mock_db = Mock()
        self.resolver = UrnResolver(reference_database=self.mock_db)

    def test_resolve_without_project(self):
        """Test resolving URN without project specifier returns all matches."""
        # Mock database to return mappings for two projects
        self.mock_db.get_urn_mappings.return_value = [
            make_urn_mapping(project="wlc", file_name="doc1.xml", urn="urn:x-opensiddur:test:doc1"),
            make_urn_mapping(project="jps1917", file_name="doc1.xml", urn="urn:x-opensiddur:test:doc1"),
        ]

        results = self.resolver.resolve("urn:x-opensiddur:test:doc1")
        
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], ResolvedUrn)
        self.assertIsInstance(results[1], ResolvedUrn)
        
        # Check both projects are present
        projects = {r.project for r in results}
        self.assertEqual(projects, {"wlc", "jps1917"})
        
        # Check URN is correct
        for result in results:
            self.assertEqual(result.urn, "urn:x-opensiddur:test:doc1")
            self.assertEqual(result.file_name, "doc1.xml")
            self.assertEqual(result.element_path, "/TEI/div[1]")
        
        # Verify database was called correctly
        self.mock_db.get_urn_mappings.assert_called_once_with("urn:x-opensiddur:test:doc1")

    def test_resolve_with_project(self):
        """Test resolving URN with @project specifier."""
        # Mock database to return mapping for specific project
        self.mock_db.get_urn_mappings.return_value = [
            make_urn_mapping(project="wlc", file_name="doc1.xml", urn="urn:x-opensiddur:test:doc1"),
        ]

        results = self.resolver.resolve("urn:x-opensiddur:test:doc1@wlc")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].urn, "urn:x-opensiddur:test:doc1")
        self.assertEqual(results[0].project, "wlc")
        self.assertEqual(results[0].file_name, "doc1.xml")
        self.assertEqual(results[0].element_path, "/TEI/div[1]")
        
        # Verify database was called with both urn and project
        self.mock_db.get_urn_mappings.assert_called_once_with("urn:x-opensiddur:test:doc1", "wlc")

    def test_resolve_with_nonexistent_project(self):
        """Test resolving URN with non-existent project returns empty list."""
        # Mock database to return empty list
        self.mock_db.get_urn_mappings.return_value = []
        
        results = self.resolver.resolve("urn:x-opensiddur:test:doc1@nonexistent")
        
        self.assertEqual(results, [])

    def test_resolve_nonexistent_urn(self):
        """Test resolving non-existent URN returns empty list."""
        # Mock database to return empty list
        self.mock_db.get_urn_mappings.return_value = []
        
        results = self.resolver.resolve("urn:x-opensiddur:test:nonexistent")
        
        self.assertEqual(results, [])

    def test_resolve_returns_list(self):
        """Test that resolve always returns a list."""
        # Existing URN
        self.mock_db.get_urn_mappings.return_value = [
            make_urn_mapping(project="wlc", file_name="doc1.xml", urn="urn:x-opensiddur:test:doc1"),
        ]
        result = self.resolver.resolve("urn:x-opensiddur:test:doc1")
        self.assertIsInstance(result, list)
        
        # Non-existing URN
        self.mock_db.get_urn_mappings.return_value = []
        result = self.resolver.resolve("urn:x-opensiddur:test:nonexistent")
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])


class TestUrnResolverGetByProject(unittest.TestCase):
    """Test get_urns_by_project functionality."""

    def setUp(self):
        """Set up with mocked database."""
        self.mock_db = Mock()
        self.resolver = UrnResolver(reference_database=self.mock_db)

    def test_get_urns_by_project(self):
        """Test getting all URNs for a project."""
        # Mock database to return URNs for wlc project
        self.mock_db.get_urn_mappings.return_value = [
            make_urn_mapping(project="wlc", file_name="doc1.xml", urn="urn:x-opensiddur:test:doc1"),
            make_urn_mapping(project="wlc", file_name="doc2.xml", urn="urn:x-opensiddur:test:doc2", element_path="/TEI/div[2]", end_element_path="/TEI/div[2]"),
        ]
        
        results = self.resolver.get_urns_by_project("wlc")
        
        self.assertEqual(len(results), 2)
        urns = {r.urn for r in results}
        self.assertEqual(urns, {"urn:x-opensiddur:test:doc1", "urn:x-opensiddur:test:doc2"})
        
        # All should be in wlc project
        for result in results:
            self.assertEqual(result.project, "wlc")
        
        # Verify database was called with project parameter
        self.mock_db.get_urn_mappings.assert_called_once_with(project="wlc")

    def test_get_urns_by_nonexistent_project(self):
        """Test getting URNs for non-existent project returns empty list."""
        # Mock database to return empty list
        self.mock_db.get_urn_mappings.return_value = []
        
        results = self.resolver.get_urns_by_project("nonexistent")
        
        self.assertEqual(results, [])


class TestUrnResolverRange(unittest.TestCase):
    """Test URN range resolution functionality."""

    def setUp(self):
        """Set up with mocked database."""
        self.mock_db = Mock()
        self.resolver = UrnResolver(reference_database=self.mock_db)

    def test_resolve_range_simple(self):
        """Test resolving a simple verse range."""
        # Mock database to return mappings for start and end URNs
        def mock_get_urn_mappings(urn, project=None):
            if urn == "urn:x-opensiddur:test:bible:genesis/1/1":
                return [
                    make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse"),
                    make_urn_mapping(project="jps1917", file_name="genesis.xml", urn=urn, element_type="verse"),
                ]
            elif urn == "urn:x-opensiddur:test:bible:genesis/1/2":
                return [
                    make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse"),
                    make_urn_mapping(project="jps1917", file_name="genesis.xml", urn=urn, element_type="verse"),
                ]
            return []

        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings

        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1-2")
        
        self.assertEqual(len(results), 2)  # wlc and jps1917
        
        for result in results:
            self.assertIsInstance(result, ResolvedUrnRange)
            self.assertEqual(result.start.urn, "urn:x-opensiddur:test:bible:genesis/1/1")
            self.assertEqual(result.end.urn, "urn:x-opensiddur:test:bible:genesis/1/2")
            self.assertEqual(result.start.project, result.end.project)
            self.assertEqual(result.start.file_name, result.end.file_name)
            self.assertEqual(result.start.element_path, "/TEI/div[1]")
            self.assertEqual(result.end.element_path, "/TEI/div[1]")

    def test_resolve_range_with_project(self):
        """Test resolving range with @project specifier."""
        # Mock database to return mappings for specific project
        def mock_get_urn_mappings(urn, project=None):
            if project == "wlc":
                if urn == "urn:x-opensiddur:test:bible:genesis/1/1":
                    return [make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse")]
                elif urn == "urn:x-opensiddur:test:bible:genesis/1/2":
                    return [make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse")]
            return []
        
        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings
        
        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1-2@wlc")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].start.project, "wlc")
        self.assertEqual(results[0].end.project, "wlc")

    def test_resolve_range_multi_component(self):
        """Test resolving range with multi-component end (e.g., 1/1-2/3)."""
        # Mock database
        def mock_get_urn_mappings(urn, project=None):
            if urn == "urn:x-opensiddur:test:bible:genesis/1/1":
                return [
                    make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse"),
                    make_urn_mapping(project="jps1917", file_name="genesis.xml", urn=urn, element_type="verse"),
                ]
            elif urn == "urn:x-opensiddur:test:bible:genesis/2/3":
                return [
                    make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse"),
                    make_urn_mapping(project="jps1917", file_name="genesis.xml", urn=urn, element_type="verse"),
                ]
            return []
        
        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings
        
        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1-2/3")
        
        self.assertEqual(len(results), 2)
        
        for result in results:
            self.assertEqual(result.start.urn, "urn:x-opensiddur:test:bible:genesis/1/1")
            self.assertEqual(result.end.urn, "urn:x-opensiddur:test:bible:genesis/2/3")
            self.assertEqual(result.start.element_path, "/TEI/div[1]")
            self.assertEqual(result.end.element_path, "/TEI/div[1]")

    def test_resolve_range_chapter(self):
        """Test resolving chapter range."""
        # Mock database
        def mock_get_urn_mappings(urn, project=None):
            if urn == "urn:x-opensiddur:test:bible:genesis/1":
                return [
                    make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse"),
                    make_urn_mapping(project="jps1917", file_name="genesis.xml", urn=urn, element_type="verse"),
                ]
            elif urn == "urn:x-opensiddur:test:bible:genesis/2":
                return [
                    make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse"),
                    make_urn_mapping(project="jps1917", file_name="genesis.xml", urn=urn, element_type="verse"),
                ]
            return []
        
        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings
        
        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1-2")
        
        self.assertEqual(len(results), 2)
        
        for result in results:
            self.assertEqual(result.start.urn, "urn:x-opensiddur:test:bible:genesis/1")
            self.assertEqual(result.end.urn, "urn:x-opensiddur:test:bible:genesis/2")
            self.assertEqual(result.start.element_path, "/TEI/div[1]")
            self.assertEqual(result.end.element_path, "/TEI/div[1]")

    def test_resolve_range_nonexistent_start(self):
        """Test resolving range with non-existent start returns empty list."""
        # Mock database to return empty for start URN
        self.mock_db.get_urn_mappings.return_value = []
        
        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/99/1-2")
        
        self.assertEqual(results, [])

    def test_resolve_range_nonexistent_end(self):
        """Test resolving range with non-existent end returns empty list."""
        # Mock database
        def mock_get_urn_mappings(urn, project=None):
            if urn == "urn:x-opensiddur:test:bible:genesis/1/1":
                return [make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse")]
            return []

        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings

        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1-99")
        
        self.assertEqual(results, [])

    def test_resolve_range_absolute_end(self):
        """A range from a half-verse to a whole verse, stated absolutely."""
        def mock_get_urn_mappings(urn, project=None):
            if urn in ("urn:x-opensiddur:test:bible:nahum/2/2/b",
                       "urn:x-opensiddur:test:bible:nahum/2/5"):
                return [make_urn_mapping(project="mam", file_name="nahum.xml", urn=urn, element_type="verse")]
            return []

        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings

        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:nahum/2/2/b-/2/5")

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ResolvedUrnRange)
        self.assertEqual(results[0].start.urn, "urn:x-opensiddur:test:bible:nahum/2/2/b")
        self.assertEqual(results[0].end.urn, "urn:x-opensiddur:test:bible:nahum/2/5")

    def test_resolve_range_absolute_end_with_project(self):
        """The @project suffix lands on both ends of an absolute range."""
        def mock_get_urn_mappings(urn, project=None):
            if project == "mam" and urn in (
                "urn:x-opensiddur:test:bible:nahum/2/2/b",
                "urn:x-opensiddur:test:bible:nahum/2/5",
            ):
                return [make_urn_mapping(project="mam", file_name="nahum.xml", urn=urn, element_type="verse")]
            return []

        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings

        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:nahum/2/2/b-/2/5@mam")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].start.project, "mam")
        self.assertEqual(results[0].end.project, "mam")

    def test_resolve_range_absolute_end_not_found(self):
        """An absolute end that no project carries is an empty result, not an exception."""
        def mock_get_urn_mappings(urn, project=None):
            if urn == "urn:x-opensiddur:test:bible:nahum/2/2/b":
                return [make_urn_mapping(project="mam", file_name="nahum.xml", urn=urn, element_type="verse")]
            return []

        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings

        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:nahum/2/2/b-/2/99")

        self.assertEqual(results, [])

    def test_resolve_range_malformed_range_raises(self):
        """A relative end deeper than its start is rejected rather than silently missed."""
        self.mock_db.get_urn_mappings.return_value = []

        with self.assertRaises(ValueError):
            self.resolver.resolve_range("urn:x-opensiddur:test:bible:nahum/2/2-2/3/a")

    def test_resolve_range_not_a_range(self):
        """Test resolving URN without dash calls resolve() and returns results."""
        # Mock database
        self.mock_db.get_urn_mappings.return_value = [
            make_urn_mapping(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:bible:genesis/1/1", element_type="verse"),
            make_urn_mapping(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:bible:genesis/1/1", element_type="verse"),
        ]

        results = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1")
        
        # Should call resolve() and return ResolvedUrn objects (not ResolvedUrnRange)
        self.assertEqual(len(results), 2)  # wlc and jps1917
        for result in results:
            self.assertIsInstance(result, ResolvedUrn)
            self.assertEqual(result.urn, "urn:x-opensiddur:test:bible:genesis/1/1")
            self.assertEqual(result.element_path, "/TEI/div[1]")

    def test_resolve_range_returns_list(self):
        """Test that resolve_range always returns a list."""
        # Valid range
        def mock_get_urn_mappings(urn, project=None):
            if urn == "urn:x-opensiddur:test:bible:genesis/1/1":
                return [make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse")]
            elif urn == "urn:x-opensiddur:test:bible:genesis/1/2":
                return [make_urn_mapping(project="wlc", file_name="genesis.xml", urn=urn, element_type="verse")]
            return []

        self.mock_db.get_urn_mappings.side_effect = mock_get_urn_mappings
        result = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1-2")
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        
        # Non-ranged URN (calls resolve())
        self.mock_db.get_urn_mappings.return_value = [
            make_urn_mapping(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:bible:genesis/1/1", element_type="verse"),
        ]
        result = self.resolver.resolve_range("urn:x-opensiddur:test:bible:genesis/1/1")
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)  # Should return resolved URNs, not empty list

    @patch('opensiddur.exporter.urn.UrnResolver.resolve')
    def test_resolve_range_calls_resolve_for_non_ranged_urn(self, mock_resolve):
        """Test that resolve_range calls resolve() when given a non-ranged URN."""
        # Setup mock to return a known result
        expected_result = [ResolvedUrn(project="test", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")]
        mock_resolve.return_value = expected_result
        
        # Call resolve_range with a non-ranged URN
        result = self.resolver.resolve_range("urn:x-opensiddur:test:doc")
        
        # Verify resolve() was called with the correct URN
        mock_resolve.assert_called_once_with("urn:x-opensiddur:test:doc")
        
        # Verify the result is what resolve() returned
        self.assertEqual(result, expected_result)

    @patch('opensiddur.exporter.urn.UrnResolver.resolve')
    def test_resolve_range_calls_resolve_for_non_ranged_urn_with_project(self, mock_resolve):
        """Test that resolve_range calls resolve() with @project for non-ranged URN."""
        # Setup mock to return a known result
        expected_result = [ResolvedUrn(project="wlc", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")]
        mock_resolve.return_value = expected_result
        
        # Call resolve_range with a non-ranged URN with @project
        result = self.resolver.resolve_range("urn:x-opensiddur:test:doc@wlc")
        
        # Verify resolve() was called with the correct URN including @project
        mock_resolve.assert_called_once_with("urn:x-opensiddur:test:doc@wlc")
        
        # Verify the result is what resolve() returned
        self.assertEqual(result, expected_result)

    @patch('opensiddur.exporter.urn.UrnResolver.resolve')
    def test_resolve_range_calls_resolve_for_urn_with_dash_not_in_last_part(self, mock_resolve):
        """Test that resolve_range calls resolve() for URNs with dash in non-final component."""
        # Setup mock
        expected_result = [ResolvedUrn(project="test", file_name="some-book.xml", urn="urn:x-opensiddur:text:some-book/1", element_path="/TEI/div[1]")]
        mock_resolve.return_value = expected_result
        
        # URN with dash in book name (not in last component)
        result = self.resolver.resolve_range("urn:x-opensiddur:text:some-book/1")
        
        # Verify resolve() was called
        mock_resolve.assert_called_once_with("urn:x-opensiddur:text:some-book/1")
        self.assertEqual(result, expected_result)


class TestSplitRange(unittest.TestCase):
    """Test the range notation itself, without a database behind it."""

    BASE = "urn:x-opensiddur:test:bible:"

    def assertSplits(self, ranged: str, start: str, end: str):
        self.assertEqual(
            split_range(self.BASE + ranged),
            (self.BASE + start, self.BASE + end),
            f"splitting {ranged!r}",
        )

    def test_relative_end_single_component(self):
        self.assertSplits("genesis/1/1-2", "genesis/1/1", "genesis/1/2")

    def test_relative_end_multi_component(self):
        self.assertSplits("genesis/1/1-2/3", "genesis/1/1", "genesis/2/3")

    def test_relative_end_at_chapter_level(self):
        self.assertSplits("genesis/1-2", "genesis/1", "genesis/2")

    def test_relative_end_between_half_verses(self):
        """Both ends below the verse, at the same depth, so the relative form reaches."""
        self.assertSplits("nahum/2/2/b-2/3/a", "nahum/2/2/b", "nahum/2/3/a")

    def test_relative_end_between_verse_parts(self):
        self.assertSplits(
            "exodus/34/6/adonai_adonai-34/7/venakeh",
            "exodus/34/6/adonai_adonai",
            "exodus/34/7/venakeh",
        )

    def test_absolute_end_from_half_verse_to_whole_verse(self):
        """The ends are at different depths, which only the absolute form can state."""
        self.assertSplits("nahum/2/2/b-/2/5", "nahum/2/2/b", "nahum/2/5")

    def test_absolute_end_from_verse_to_whole_chapter(self):
        self.assertSplits("genesis/1/1-/3", "genesis/1/1", "genesis/3")

    def test_absolute_end_from_verse_to_half_verse(self):
        self.assertSplits("nahum/2/2-/2/3/a", "nahum/2/2", "nahum/2/3/a")

    def test_absolute_end_deeper_than_start(self):
        """Relative notation cannot reach downward; absolute notation can."""
        self.assertSplits("genesis/1-/2/3", "genesis/1", "genesis/2/3")

    def test_not_a_range(self):
        self.assertIsNone(split_range(self.BASE + "genesis/1/1"))

    def test_dash_in_the_work_component_is_not_a_range(self):
        """'x-opensiddur' and a hyphenated book name both live in component 0."""
        self.assertIsNone(split_range("urn:x-opensiddur:text:some-book/1"))
        self.assertIsNone(split_range("urn:x-opensiddur:test:doc"))

    def test_relative_end_deeper_than_start_raises(self):
        """The case that used to build a URN with the scheme sliced off it."""
        with self.assertRaises(ValueError) as caught:
            split_range(self.BASE + "nahum/2/2-2/3/a")
        self.assertIn("-/2/3/a", str(caught.exception))

    def test_missing_end_raises(self):
        with self.assertRaises(ValueError):
            split_range(self.BASE + "genesis/1/1-")

    def test_missing_start_raises(self):
        with self.assertRaises(ValueError):
            split_range(self.BASE + "genesis/1/-2")

    def test_empty_component_in_absolute_end_raises(self):
        with self.assertRaises(ValueError):
            split_range(self.BASE + "genesis/1/1-//3")


class TestUrnResolverGetPathFromUrn(unittest.TestCase):
    """Test the get_path_from_urn method."""

    def test_get_path_from_urn_basic(self):
        """Test basic path construction from ResolvedUrn."""
        resolved = ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        
        result = UrnResolver.get_path_from_urn(resolved)
        
        # Should construct path as: PROJECT_DIRECTORY / project / file_name
        from opensiddur.common.constants import PROJECT_DIRECTORY
        expected = PROJECT_DIRECTORY / "wlc" / "genesis.xml"
        self.assertEqual(result, expected)

    def test_get_path_from_urn_with_custom_project_directory(self):
        """Test path construction with custom project directory."""
        resolved = ResolvedUrn(project="jps1917", file_name="exodus.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        custom_dir = Path("/custom/project/dir")
        
        result = UrnResolver.get_path_from_urn(resolved, project_directory=custom_dir)
        
        expected = custom_dir / "jps1917" / "exodus.xml"
        self.assertEqual(result, expected)

    def test_get_path_from_urn_different_projects(self):
        """Test path construction for different projects."""
        resolved1 = ResolvedUrn(project="wlc", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        resolved2 = ResolvedUrn(project="jps1917", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        
        result1 = UrnResolver.get_path_from_urn(resolved1)
        result2 = UrnResolver.get_path_from_urn(resolved2)
        
        # Should be different paths even though file_name is the same
        self.assertNotEqual(result1, result2)
        self.assertIn("wlc", str(result1))
        self.assertIn("jps1917", str(result2))

    def test_get_path_from_urn_different_files(self):
        """Test path construction for different files in same project."""
        resolved1 = ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc1", element_path="/TEI/div[1]")
        resolved2 = ResolvedUrn(project="wlc", file_name="exodus.xml", urn="urn:x-opensiddur:test:doc2", element_path="/TEI/div[1]")
        
        result1 = UrnResolver.get_path_from_urn(resolved1)
        result2 = UrnResolver.get_path_from_urn(resolved2)
        
        # Should be different paths
        self.assertNotEqual(result1, result2)
        self.assertTrue(str(result1).endswith("genesis.xml"))
        self.assertTrue(str(result2).endswith("exodus.xml"))

    def test_get_path_from_urn_is_classmethod(self):
        """Test that get_path_from_urn can be called without an instance."""
        resolved = ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        
        # Should be callable as a class method
        result = UrnResolver.get_path_from_urn(resolved)
        
        self.assertIsInstance(result, Path)

    def test_get_path_from_urn_returns_path_object(self):
        """Test that get_path_from_urn returns a Path object."""
        resolved = ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        
        result = UrnResolver.get_path_from_urn(resolved)
        
        self.assertIsInstance(result, Path)

    def test_get_path_from_urn_with_nested_project(self):
        """Test path construction with project that looks like a path."""
        # Some projects might have dashes or special characters
        resolved = ResolvedUrn(project="some-project", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]")
        custom_dir = Path("/base")
        
        result = UrnResolver.get_path_from_urn(resolved, project_directory=custom_dir)
        
        expected = Path("/base/some-project/test.xml")
        self.assertEqual(result, expected)


class TestUrnResolverPrioritizeRange(unittest.TestCase):
    """Test the prioritize_range method."""

    def test_prioritize_range_with_resolved_urns(self):
        """Test prioritizing a list of ResolvedUrn objects."""
        urns = [
            ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # wlc should have priority
        priority = ["wlc", "jps1917"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, ResolvedUrn)
        self.assertEqual(result.project, "wlc")
        
    def test_prioritize_range_with_resolved_urn_ranges(self):
        """Test prioritizing a list of ResolvedUrnRange objects."""
        ranges = [
            ResolvedUrnRange(
                start=ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/1", element_path="/TEI/div[1]"),
                end=ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/2", element_path="/TEI/div[1]")
            ),
            ResolvedUrnRange(
                start=ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/1", element_path="/TEI/div[1]"),
                end=ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/2", element_path="/TEI/div[1]")
            ),
            ResolvedUrnRange(
                start=ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/1", element_path="/TEI/div[1]"),
                end=ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/2", element_path="/TEI/div[1]")
            ),
        ]
        
        # jps1917 should have priority
        priority = ["jps1917", "wlc"]
        result = UrnResolver.prioritize_range(ranges, priority)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, ResolvedUrnRange)
        self.assertEqual(result.start.project, "jps1917")
        
    def test_prioritize_range_mixed_types(self):
        """Test prioritizing a mixed list of ResolvedUrn and ResolvedUrnRange objects."""
        mixed = [
            ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrnRange(
                start=ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/1", element_path="/TEI/div[1]"),
                end=ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/2", element_path="/TEI/div[1]")
            ),
            ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # wlc should have priority even though it's a ResolvedUrnRange
        priority = ["wlc", "jps1917", "other"]
        result = UrnResolver.prioritize_range(mixed, priority)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, ResolvedUrnRange)
        self.assertEqual(result.start.project, "wlc")
        
    def test_prioritize_range_empty_list(self):
        """Test prioritizing an empty list returns None."""
        result = UrnResolver.prioritize_range([], ["wlc", "jps1917"])
        
        self.assertIsNone(result)
        
    def test_prioritize_range_empty_priority_list(self):
        """Test prioritizing with empty priority list returns None."""
        urns = [
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        result = UrnResolver.prioritize_range(urns, [])
        
        self.assertIsNone(result)
        
    def test_prioritize_range_no_matching_projects(self):
        """Test prioritizing when no URNs match the priority list returns None."""
        urns = [
            ResolvedUrn(project="other1", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="other2", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Priority list doesn't include other1 or other2
        priority = ["wlc", "jps1917"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        self.assertIsNone(result)
        
    def test_prioritize_range_partial_matching_projects(self):
        """Test prioritizing when only some URNs match the priority list."""
        urns = [
            ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Only wlc and jps1917 are in priority list
        priority = ["wlc", "jps1917"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.project, "wlc")
        
    def test_prioritize_range_single_urn(self):
        """Test prioritizing a single URN."""
        urns = [
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        priority = ["wlc", "jps1917"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.project, "wlc")
        
    def test_prioritize_range_respects_priority_order(self):
        """Test that priority order is respected (first in list is highest priority)."""
        urns = [
            ResolvedUrn(project="project1", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="project2", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="project3", file_name="test.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # project2 should win
        priority = ["project2", "project1", "project3"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.project, "project2")
        
        # project3 should win
        priority = ["project3", "project2", "project1"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.project, "project3")
        
    def test_prioritize_range_with_duplicate_projects(self):
        """Test prioritizing when multiple URNs have the same project."""
        urns = [
            ResolvedUrn(project="wlc", file_name="file1.xml", urn="urn:x-opensiddur:test:doc1", element_path="/TEI/div[1]"),
            ResolvedUrn(project="wlc", file_name="file2.xml", urn="urn:x-opensiddur:test:doc2", element_path="/TEI/div[1]"),
            ResolvedUrn(project="jps1917", file_name="file3.xml", urn="urn:x-opensiddur:test:doc3", element_path="/TEI/div[1]"),
        ]
        
        priority = ["wlc", "jps1917"]
        result = UrnResolver.prioritize_range(urns, priority)
        
        # Should return the first wlc entry
        self.assertIsNotNone(result)
        self.assertEqual(result.project, "wlc")
        self.assertEqual(result.file_name, "file1.xml")
        
    def test_prioritize_range_is_classmethod(self):
        """Test that prioritize_range can be called without an instance."""
        urns = [
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Should be callable as a class method
        result = UrnResolver.prioritize_range(urns, ["wlc"])
        
        self.assertIsNotNone(result)
        self.assertEqual(result.project, "wlc")
        
    def test_prioritize_range_return_all_with_matching_results(self):
        """Test prioritize_range with return_all=True when there are matching results."""
        urns = [
            ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Only wlc and jps1917 are in priority list
        priority = ["wlc", "jps1917"]
        results = UrnResolver.prioritize_range(urns, priority, return_all=True)
        
        self.assertIsNotNone(results)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)  # Only wlc and jps1917 should be returned
        
        # Results should be sorted by priority (wlc first, then jps1917)
        self.assertEqual(results[0].project, "wlc")
        self.assertEqual(results[1].project, "jps1917")
        
    def test_prioritize_range_return_all_with_no_matching_results(self):
        """Test prioritize_range with return_all=True when there are no matching results."""
        urns = [
            ResolvedUrn(project="other1", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="other2", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Priority list doesn't include other1 or other2
        priority = ["wlc", "jps1917"]
        results = UrnResolver.prioritize_range(urns, priority, return_all=True)
        
        self.assertIsNone(results)  # Should return None when no matches
        
    def test_prioritize_range_return_all_with_mixed_types(self):
        """Test prioritize_range with return_all=True with mixed ResolvedUrn and ResolvedUrnRange objects."""
        mixed = [
            ResolvedUrn(project="jps1917", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrnRange(
                start=ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/1", element_path="/TEI/div[1]"),
                end=ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc/2", element_path="/TEI/div[1]")
            ),
            ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Only wlc and jps1917 are in priority list
        priority = ["wlc", "jps1917"]
        results = UrnResolver.prioritize_range(mixed, priority, return_all=True)
        
        self.assertIsNotNone(results)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)  # Only wlc and jps1917 should be returned
        
        # Results should be sorted by priority (wlc first, then jps1917)
        self.assertEqual(results[0].start.project, "wlc")  # First result is ResolvedUrnRange
        self.assertEqual(results[1].project, "jps1917")    # Second result is ResolvedUrn
        
    def test_prioritize_range_return_all_empty_list(self):
        """Test prioritize_range with return_all=True with empty input list."""
        results = UrnResolver.prioritize_range([], ["wlc", "jps1917"], return_all=True)
        
        self.assertIsNone(results)
        
    def test_prioritize_range_return_all_single_match(self):
        """Test prioritize_range with return_all=True with single matching result."""
        urns = [
            ResolvedUrn(project="wlc", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
            ResolvedUrn(project="other", file_name="genesis.xml", urn="urn:x-opensiddur:test:doc", element_path="/TEI/div[1]"),
        ]
        
        # Only wlc is in priority list
        priority = ["wlc"]
        results = UrnResolver.prioritize_range(urns, priority, return_all=True)
        
        self.assertIsNotNone(results)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].project, "wlc")



class TestCoarsen(unittest.TestCase):
    """A sub-verse reference falls back on its verse, and nothing else falls back at all."""

    NAHUM = "urn:x-opensiddur:text:bible:nahum"

    def test_a_half_verse_falls_back_on_its_verse(self):
        self.assertEqual(coarsen(f"{self.NAHUM}/2/2/b"), f"{self.NAHUM}/2/2")

    def test_the_project_is_kept(self):
        self.assertEqual(coarsen(f"{self.NAHUM}/2/2/b@jps1917"), f"{self.NAHUM}/2/2@jps1917")

    def test_an_end_that_is_a_whole_verse_stays(self):
        """2:2b-2:5 is 2:2-2:5, not 2:2 to the end of chapter 2."""
        self.assertEqual(coarsen(f"{self.NAHUM}/2/2/b-/2/5"), f"{self.NAHUM}/2/2-/2/5")

    def test_both_sub_verse_ends_fall_back(self):
        self.assertEqual(coarsen(f"{self.NAHUM}/2/2/b-2/3/a"), f"{self.NAHUM}/2/2-/2/3")

    def test_an_end_that_resolves_is_kept(self):
        resolves = {f"{self.NAHUM}/2/3/a"}.__contains__
        self.assertEqual(coarsen(f"{self.NAHUM}/2/2/b-2/3/a", resolves=resolves),
                         f"{self.NAHUM}/2/2-/2/3/a")

    def test_a_reference_that_resolves_is_not_coarsened(self):
        self.assertIsNone(coarsen(f"{self.NAHUM}/2/2/b", resolves=lambda urn: True))

    def test_a_whole_verse_is_not_widened(self):
        self.assertIsNone(coarsen(f"{self.NAHUM}/2/2"))

    def test_a_part_of_a_reading_is_not_a_part_of_a_verse(self):
        self.assertIsNone(coarsen("urn:x-opensiddur:text:bible:reading/shavuot_ii/haftarah/1"))

    def test_a_part_of_a_prayer_is_not_the_whole_prayer(self):
        self.assertIsNone(coarsen("urn:x-opensiddur:text:prayer:amidah/avot"))


if __name__ == '__main__':
    unittest.main()
