import unittest
from unittest.mock import patch, call
from pathlib import Path

from opensiddur.common.constants import SOURCETEXTS_ROOT
from opensiddur.common.versification import WLC_PROJECT
from opensiddur.importer.wlc.wlc import (
    make_project_directory,
    get_source_directory,
    get_xslt_directory,
    main,
)


class TestWLCPathFunctions(unittest.TestCase):
    """Test path-related utility functions in wlc module"""
    
    @patch('pathlib.Path.mkdir')
    def test_make_project_directory_custom_path(self, mock_mkdir):
        """make_project_directory respects an explicit project directory."""
        explicit = Path('/tmp/wlc-out')
        result = make_project_directory(explicit)
        self.assertEqual(result, explicit.resolve())
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('pathlib.Path.mkdir')
    def test_make_project_directory(self, mock_mkdir):
        """Test that make_project_directory creates the correct directory"""
        result = make_project_directory()
        
        # Verify mkdir was called with the correct arguments
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        
        # Verify the returned path is the WLC project's
        self.assertEqual(result.name, WLC_PROJECT)
        
        # Verify it's a Path object
        self.assertIsInstance(result, Path)
    
    def test_get_source_directory(self):
        """Test that get_source_directory returns the correct path"""
        result = get_source_directory()
        
        # Verify it returns a Path object
        self.assertIsInstance(result, Path)
        
        # Verify it points to sources/wlc under the configured sourcetexts root
        self.assertTrue(str(result).endswith(str(Path('sources/wlc'))))
        self.assertEqual(result, SOURCETEXTS_ROOT / 'wlc')

    def test_get_source_directory_custom_sourcetexts_root(self):
        custom = Path('/tmp/opensiddur-sourcetexts')
        result = get_source_directory(custom)
        self.assertEqual(result, custom.resolve() / 'wlc')
    
    def test_get_xslt_directory(self):
        """Test that get_xslt_directory returns the wlc module directory"""
        result = get_xslt_directory()
        
        # Verify it returns a Path object
        self.assertIsInstance(result, Path)
        
        # Verify it points to the wlc importer directory (handle both Unix and Windows paths)
        path_str = str(result)
        self.assertTrue(
            path_str.endswith('importer/wlc') or path_str.endswith('importer\\wlc'),
            f"Expected path to end with 'importer/wlc', got: {path_str}"
        )
        
        # Verify the path is under the opensiddur directory
        self.assertIn('opensiddur', str(result))


class TestWLCMain(unittest.TestCase):
    """Test the main function that orchestrates the WLC transformation"""
    
    @patch('opensiddur.importer.wlc.wlc.add_subverse_milestones_to_file')
    @patch('opensiddur.importer.wlc.wlc.validate')
    @patch('opensiddur.importer.wlc.wlc.os.listdir')
    @patch('opensiddur.importer.wlc.wlc.xslt_transform')
    @patch('opensiddur.importer.wlc.wlc.get_xslt_directory')
    @patch('opensiddur.importer.wlc.wlc.make_project_directory')
    def test_main_transforms_and_validates_all_files(
        self,
        mock_make_project_directory,
        mock_get_xslt_dir,
        mock_xslt_transform,
        mock_listdir,
        mock_validate,
        mock_add_subverse,
    ):
        """Test that main transforms index and books, then validates all output files"""
        
        # Set up mock paths
        mock_project_dir = Path('/mock/project/wlc')
        mock_source_dir = Path('/mock/sources/wlc').resolve()
        mock_sourcetexts_root = Path('/mock/sources')
        mock_xslt_dir = Path('/mock/opensiddur/importer/wlc')
        
        mock_make_project_directory.return_value = mock_project_dir
        mock_get_xslt_dir.return_value = mock_xslt_dir
        
        # Mock os.listdir to return different values for different calls
        # First call: source_directory / "Books" - return book files
        # Second call: project_directory - return transformed files
        source_books = [
            'Genesis.xml',
            'Exodus.xml', 
            'Leviticus.xml',
            'TanachHeader.xml',  # Should be skipped
            'TanachIndex.xml',   # Should be skipped
            'Genesis.DH.xml'     # Should be skipped (ends with .DH.xml)
        ]
        
        project_files = [
            'index.xml',
            'genesis.xml',
            'exodus.xml',
            'leviticus.xml'
        ]
        
        mock_listdir.side_effect = [source_books, project_files]
        
        # Mock validate to return success
        mock_validate.return_value = (True, [])
        
        # Run main with explicit dirs (sourcetexts root contains wlc/Books)
        result = main(
            [
                "--project-dir",
                str(mock_project_dir),
                "--sourcetexts-root",
                str(mock_sourcetexts_root),
            ]
        )
        
        # Verify return value
        self.assertEqual(result, 0)
        
        mock_wlc_uri = mock_source_dir.resolve().as_uri()
        if not mock_wlc_uri.endswith("/"):
            mock_wlc_uri += "/"
        expected_index_call = call(
            mock_xslt_dir / "transform_index.xslt",
            mock_source_dir / "Books" / "TanachHeader.xml",
            mock_project_dir / "index.xml",
            xslt_params={"wlc-root-uri": mock_wlc_uri, "project": WLC_PROJECT},
        )
        self.assertIn(expected_index_call, mock_xslt_transform.call_args_list)
        
        # Verify xslt_transform was called for each valid book (not the excluded ones)
        expected_book_calls = [
            call(
                mock_xslt_dir / "transform_book.xslt",
                mock_source_dir / "Books" / "Genesis.xml",
                mock_project_dir / "genesis.xml",
                xslt_params={"project": WLC_PROJECT},
            ),
            call(
                mock_xslt_dir / "transform_book.xslt",
                mock_source_dir / "Books" / "Exodus.xml",
                mock_project_dir / "exodus.xml",
                xslt_params={"project": WLC_PROJECT},
            ),
            call(
                mock_xslt_dir / "transform_book.xslt",
                mock_source_dir / "Books" / "Leviticus.xml",
                mock_project_dir / "leviticus.xml",
                xslt_params={"project": WLC_PROJECT},
            ),
        ]
        
        for expected_call in expected_book_calls:
            self.assertIn(expected_call, mock_xslt_transform.call_args_list)
        
        # Verify total number of xslt_transform calls (1 index + 3 books)
        self.assertEqual(mock_xslt_transform.call_count, 4)
        
        # Verify validate was called for every .xml file in project directory
        expected_validate_calls = [
            call(mock_project_dir / "index.xml"),
            call(mock_project_dir / "genesis.xml"),
            call(mock_project_dir / "exodus.xml"),
            call(mock_project_dir / "leviticus.xml")
        ]
        
        for expected_call in expected_validate_calls:
            self.assertIn(expected_call, mock_validate.call_args_list)
        
        # Verify validate was called for each file
        self.assertEqual(mock_validate.call_count, 4)

        # Every transformed book gets its sub-verse milestones; the index has no verses.
        self.assertEqual(
            mock_add_subverse.call_args_list,
            [
                call(mock_project_dir / book, language="he", project=WLC_PROJECT)
                for book in ("genesis.xml", "exodus.xml", "leviticus.xml")
            ],
        )

    @patch('opensiddur.importer.wlc.wlc.add_subverse_milestones_to_file')
    @patch('opensiddur.importer.wlc.wlc.validate')
    @patch('opensiddur.importer.wlc.wlc.os.listdir')
    @patch('opensiddur.importer.wlc.wlc.xslt_transform')
    @patch('opensiddur.importer.wlc.wlc.get_xslt_directory')
    @patch('opensiddur.importer.wlc.wlc.make_project_directory')
    def test_main_handles_validation_errors(
        self,
        mock_make_project_directory,
        mock_get_xslt_dir,
        mock_xslt_transform,
        mock_listdir,
        mock_validate,
        mock_add_subverse,
    ):
        """Test that main handles validation errors gracefully"""
        
        # Set up mock paths
        mock_project_dir = Path('/mock/project/wlc')
        mock_sourcetexts_root = Path('/mock/sources')
        mock_xslt_dir = Path('/mock/opensiddur/importer/wlc')

        mock_make_project_directory.return_value = mock_project_dir
        mock_get_xslt_dir.return_value = mock_xslt_dir

        # Mock os.listdir
        source_books = ['Genesis.xml']
        project_files = ['index.xml', 'genesis.xml']
        mock_listdir.side_effect = [source_books, project_files]
        
        # Mock validate to return an error for one file
        mock_validate.side_effect = [
            (True, []),  # index.xml is valid
            (False, ['Error: Invalid XML structure'])  # genesis.xml has errors
        ]
        
        # Run main - should not raise an exception. The failure is reported on the module
        # logger, so assertLogs both checks that it is reported and keeps the record from
        # reaching the last-resort handler, where it would read as a failure of this test.
        with self.assertLogs("opensiddur.importer.wlc.wlc", level="ERROR") as logs:
            result = main(
                [
                    "--project-dir",
                    str(mock_project_dir),
                    "--sourcetexts-root",
                    str(mock_sourcetexts_root),
                ]
            )

        self.assertEqual(len(logs.records), 1)
        self.assertIn("genesis.xml", logs.output[0])
        self.assertIn("Invalid XML structure", logs.output[0])

        # Should still return 0 even with validation errors
        self.assertEqual(result, 0)
        
        # Verify validate was called for both files
        self.assertEqual(mock_validate.call_count, 2)


if __name__ == '__main__':
    unittest.main()

