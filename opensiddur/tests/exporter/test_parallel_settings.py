"""Tests for parallel text settings loading."""

import tempfile
import unittest
from pathlib import Path

import yaml

from opensiddur.exporter.linear import (
    LinearData,
    ParallelColumnOrder,
    reset_linear_data,
)
from opensiddur.exporter.settings import load_default_settings, load_settings


class TestParallelSettings(unittest.TestCase):
    """Tests for parallel config parsing in settings.py."""

    def setUp(self):
        reset_linear_data()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project_dir = Path(self.temp_dir.name)
        # Create two fake projects
        (self.project_dir / "proj-a").mkdir()
        (self.project_dir / "proj-b").mkdir()
        (self.project_dir / "proj-c").mkdir()

    def _write_yaml(self, data: dict) -> Path:
        path = Path(self.temp_dir.name) / "settings.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        return path

    def _settings_with_patch(self, data: dict) -> LinearData:
        path = self._write_yaml(data)
        return load_settings(path, project_directory=self.project_dir)

    # ── Basic loading ───────────────────────────────────────────────────────

    def test_parallel_projects_populated(self):
        ld = self._settings_with_patch({
            "priority": {"transclusion": ["proj-a", "proj-b"], "instructions": ["proj-a"]},
            "parallel": {"projects": ["proj-b"], "column_order": "primary_last"},
        })
        self.assertEqual(ld.parallel_projects, ["proj-b"])
        self.assertEqual(ld.parallel_column_order, ParallelColumnOrder.PRIMARY_LAST)

    def test_parallel_column_order_default(self):
        ld = self._settings_with_patch({
            "priority": {"transclusion": ["proj-a"], "instructions": ["proj-a"]},
            "parallel": {"projects": ["proj-b"]},
        })
        self.assertEqual(ld.parallel_column_order, ParallelColumnOrder.PRIMARY_FIRST)

    def test_multiple_parallel_projects(self):
        ld = self._settings_with_patch({
            "priority": {"transclusion": ["proj-a", "proj-b", "proj-c"], "instructions": ["proj-a"]},
            "parallel": {"projects": ["proj-b", "proj-c"]},
        })
        self.assertEqual(ld.parallel_projects, ["proj-b", "proj-c"])

    def test_no_parallel_key(self):
        ld = self._settings_with_patch({
            "priority": {"transclusion": ["proj-a"], "instructions": ["proj-a"]},
        })
        self.assertEqual(ld.parallel_projects, [])
        self.assertEqual(ld.parallel_column_order, ParallelColumnOrder.PRIMARY_FIRST)

    # ── Validation ──────────────────────────────────────────────────────────

    def test_invalid_parallel_project_raises(self):
        from pydantic import ValidationError
        with self.assertRaises((ValueError, ValidationError)):
            self._settings_with_patch({
                "priority": {"transclusion": ["proj-a"], "instructions": ["proj-a"]},
                "parallel": {"projects": ["nonexistent-project"]},
            })

    # ── Default settings ────────────────────────────────────────────────────

    def test_load_default_settings_no_parallel(self):
        ld = load_default_settings(
            "proj-a",
            "index.xml",
            project_directory=self.project_dir,
        )
        self.assertEqual(ld.parallel_projects, [])
        self.assertEqual(ld.parallel_column_order, ParallelColumnOrder.PRIMARY_FIRST)
        self.assertEqual(ld.xml_cache.base_path, self.project_dir.resolve())


if __name__ == "__main__":
    unittest.main()
