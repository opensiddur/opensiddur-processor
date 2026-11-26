"""Every typography setting must be documented.

A setting nobody can find is a setting nobody can use, and the reference in
``doc/typography.md`` is only true for as long as somebody remembers to update
it. This walks the model tree instead, so adding a field without a row in the
table fails here rather than going unnoticed.
"""

import typing
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from opensiddur.exporter import typography as typography_module
from opensiddur.exporter.typography import Styles, TextStyle, TypographyConfig

DOC = Path(__file__).resolve().parents[3] / "doc" / "typography.md"

# `page_header` and `page_footer` are running heads, documented as a section of
# their own with their template codes rather than as a field tree; `fonts` is an
# open mapping of user-chosen names, so it has no fixed paths to enumerate.
_DOCUMENTED_AS_PROSE = {"page_header", "page_footer", "fonts"}


def _model_of(annotation: object) -> type[BaseModel] | None:
    """The model a field holds, looking through Optional and unions."""
    candidates = (annotation,) + tuple(typing.get_args(annotation) or ())
    for candidate in candidates:
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def _setting_paths(model: type[BaseModel], prefix: str = "") -> list[str]:
    """Every dotted key path a settings file may write.

    ``TextStyle`` is not descended into: its eight attributes are the same for
    every role and are documented once, in their own table, rather than
    repeated two hundred times.
    """
    paths: list[str] = []
    for name, field in model.model_fields.items():
        # The alias where there is one: the reference documents the settings file, and a
        # field aliased because its name is a Python keyword is written under the alias.
        path = f"{prefix}{field.alias or name}"
        if path in _DOCUMENTED_AS_PROSE:
            continue
        paths.append(path)
        nested = _model_of(field.annotation)
        if nested is not None and nested is not TextStyle:
            paths.extend(_setting_paths(nested, path + "."))
    return paths


class TestEverySettingIsDocumented(unittest.TestCase):
    def setUp(self):
        self.doc = DOC.read_text(encoding="utf-8")

    def test_every_setting_path_appears_in_the_reference(self):
        """Written in full, so that searching the document for the key you have
        in your settings file finds it."""
        missing = [
            path for path in _setting_paths(TypographyConfig) if f"`{path}`" not in self.doc
        ]
        self.assertEqual(
            missing,
            [],
            "settings missing from doc/typography.md: " + ", ".join(missing),
        )

    def test_every_style_role_has_a_row_of_its_own(self):
        """A role's default is not derivable from the attribute table, so each
        one has to be named."""
        missing = [
            f"styles.{role}"
            for role in Styles.model_fields
            if f"styles.{role}" not in self.doc
        ]
        self.assertEqual(missing, [], "roles missing from doc/typography.md: " + ", ".join(missing))

    def test_every_style_attribute_is_documented(self):
        for attribute in TextStyle.model_fields:
            self.assertIn(f"`{attribute}`", self.doc, f"style attribute {attribute}")

    def test_the_prose_sections_are_actually_there(self):
        """The paths skipped above are skipped because they are documented
        another way, not because they are undocumented."""
        headings = [line for line in self.doc.splitlines() if line.startswith("## ")]
        for section in sorted(_DOCUMENTED_AS_PROSE):
            self.assertTrue(
                any(f"`{section}`" in heading for heading in headings),
                f"no section heading for {section}",
            )


class TestExampleSettingsAreValid(unittest.TestCase):
    """The example files are the first thing anyone copies from."""

    def test_examples_validate_against_the_models(self):
        """Structure only: fontconfig is mocked out as unavailable, so this asks
        whether the example is well formed, not whether the machine running the
        tests happens to have the fonts it names."""
        import yaml

        doc_dir = DOC.parent
        for example in sorted(doc_dir.glob("*settings.example.yaml")):
            with self.subTest(example=example.name):
                data = yaml.safe_load(example.read_text(encoding="utf-8"))
                with patch.object(
                    typography_module, "_installed_font_families", return_value=None
                ):
                    TypographyConfig.model_validate(data.get("typography") or {})


if __name__ == "__main__":
    unittest.main()
