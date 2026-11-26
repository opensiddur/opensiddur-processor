"""Per-face sizes must survive actual NFSS and polyglossia font switches."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opensiddur.exporter import typography
from opensiddur.exporter.tex.typography_tex import build_typography_preamble
from opensiddur.exporter.typography import TypographyConfig


class TestFontSizeResolution(unittest.TestCase):
    def test_python_resolution_keeps_the_selected_entry_size(self):
        with patch.object(typography, "_installed_font_families", return_value=frozenset({"available"})):
            config = TypographyConfig.model_validate({"fonts": {"latin": [
                {"name": "Missing", "normal_size": 18},
                {"name": "Available", "normal_size": 12},
            ]}})
            tex = build_typography_preamble(config)
        self.assertIn(r"\OSRegisterFontSize{\rmfamily}{12.0}", tex)
        self.assertNotIn("Missing", tex)
        self.assertNotIn(r"{18}", tex)

    def test_deferred_resolution_pairs_each_face_with_its_size(self):
        with patch.object(typography, "_installed_font_families", return_value=None):
            config = TypographyConfig.model_validate({"fonts": {"latin": [
                {"name": "First", "normal_size": 12},
                {"name": "Second", "normal_size": 14},
                "Legacy",
            ]}})
            tex = build_typography_preamble(config)
        self.assertIn(r"{First}\OSRegisterFontSize{\rmfamily}{12.0}", tex)
        self.assertIn(r"{Second}\OSRegisterFontSize{\rmfamily}{14.0}", tex)
        self.assertNotIn(r"{Legacy}\OSRegisterFontSize", tex)


@unittest.skipUnless(shutil.which("lualatex"), "LuaLaTeX is not installed")
class TestRenderedFontSizes(unittest.TestCase):
    def test_nested_switches_relative_and_absolute_sizes(self):
        installed = typography._installed_font_families()
        if installed is None or "freeserif" not in installed:
            self.skipTest("FreeSerif is required for the rendering fixture")
        for deferred, sized_latin in [(False, True), (True, True), (False, False)]:
            with self.subTest(deferred=deferred, sized_latin=sized_latin), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "cache").mkdir()
                # Identical font faces under two family keys must still have
                # independent sizes. A missing first fallback must not donate its size.
                with patch.object(typography, "_installed_font_families", return_value=None if deferred else installed):
                    config = TypographyConfig.model_validate({
                        "fonts": {
                            "hebrew": [
                                {"name": "OpenSiddur Deliberately Missing Font", "normal_size": 30},
                                {"name": "FreeSerif", "normal_size": 12},
                            ],
                            "latin": [{"name": "FreeSerif", "normal_size": 11}] if sized_latin else ["FreeSerif"],
                            "display": [{"name": "FreeSerif", "normal_size": 16}],
                        },
                        "styles": {"heading1": {"size": "9pt"}},
                    })
                    preamble = build_typography_preamble(config)
                source = r"""\documentclass[11pt]{book}
\usepackage{fontspec}
\usepackage{polyglossia}
\setdefaultlanguage{english}
\setotherlanguage{hebrew}
\usepackage{reledmac}
\usepackage{hyperref}
""" + preamble + r"""
\makeatletter
\newcommand{\report}[1]{\typeout{SIZE:#1:\f@size:BASE:\f@baselineskip}}
\makeatother
\begin{document}
\report{english}English
\texthebrew{\report{hebrew}שָׁלוֹם
  \textenglish{\report{nested}hello}
  \report{restored}\selectfont\bfseries\report{repeated}עוֹלָם}
{\large\report{largeenglish}\texthebrew{\report{largehebrew}שָׁלוֹם}}
{\small\texthebrew{\report{smallhebrew}שָׁלוֹם}}
{\OSfontDisplay\report{custom}Display\rmfamily\report{customrestored}}
\OSheadA{\report{absoluteenglish}\texthebrew{\report{absolutehebrew}שָׁלוֹם}}
\report{finalenglish}
\end{document}
"""
                (root / "proof.tex").write_text(source)
                result = subprocess.run(
                    ["lualatex", "-interaction=nonstopmode", "-halt-on-error", "proof.tex"],
                    cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    timeout=120, env={**os.environ, "TEXMFVAR": str(root / "cache"), "TEXMFCACHE": str(root / "cache")},
                )
                self.assertEqual(result.returncode, 0, result.stdout[-6000:])
                sizes = {key: (float(size), float(baseline)) for key, size, baseline in re.findall(
                    r"SIZE:([a-z]+):([\d.]+):BASE:([\d.]+)pt", result.stdout
                )}
                latin_size = 11 if sized_latin else 10.95
                expected = {
                    "english": latin_size, "hebrew": 12, "nested": latin_size, "restored": 12,
                    "repeated": 12, "largeenglish": 12 * latin_size / 10.95,
                    "largehebrew": 12 * 12 / 10.95, "smallhebrew": 10 * 12 / 10.95,
                    "custom": 16, "customrestored": latin_size,
                    "absoluteenglish": 9, "absolutehebrew": 9, "finalenglish": latin_size,
                }
                for key, value in expected.items():
                    self.assertAlmostEqual(sizes[key][0], value, places=4, msg=key)
                self.assertAlmostEqual(sizes["hebrew"][1], 13.6 * 12 / 10.95, places=4)
                self.assertAlmostEqual(sizes["absolutehebrew"][1], 10.8, places=4)
