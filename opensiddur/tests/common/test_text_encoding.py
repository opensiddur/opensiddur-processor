"""Every text file the package opens names its encoding.

Without ``encoding=``, Python decodes and encodes text in the locale's encoding, which on
Windows is a code page such as cp1252, not UTF-8 (until Python 3.15 turns UTF-8 mode on by
default). Reading Hebrew that way does not always fail: a settings file read as cp1252
succeeds and returns mojibake, which then goes into a book. This is the check ruff's
``PLW1514`` (unspecified-encoding) makes, done here because the project does not run ruff.
"""

import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]

# Modules whose own ``open`` takes no text encoding.
NON_TEXT_MODULES = frozenset({"gzip", "bz2", "lzma", "tarfile", "zipfile", "Image", "os"})


def _constant(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _mode(call: ast.Call, position: int) -> str | None:
    """The call's mode, ``"r"`` when it is left out, or None when it is not a literal."""
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return _constant(keyword.value)
    if len(call.args) > position:
        return _constant(call.args[position])
    return "r"


def unspecified_encodings(source: str) -> list[tuple[int, str]]:
    """(line, call) for each text-mode open, read or write in ``source`` without an encoding."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        keywords = {keyword.arg for keyword in node.keywords}
        if "encoding" in keywords or None in keywords:  # None: a **kwargs
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id == "open":
            mode = _mode(node, 1)
        elif isinstance(function, ast.Attribute) and function.attr == "open":
            owner = function.value
            if isinstance(owner, ast.Name) and owner.id in NON_TEXT_MODULES:
                continue
            mode = _mode(node, 0)  # Path.open(mode)
        elif isinstance(function, ast.Attribute) and function.attr in ("read_text", "write_text"):
            # read_text(encoding) and write_text(data, encoding) can name it positionally.
            if len(node.args) > (0 if function.attr == "read_text" else 1):
                continue
            found.append((node.lineno, function.attr))
            continue
        else:
            continue
        if mode is not None and "b" not in mode:
            found.append((node.lineno, "open"))
    return sorted(found)


class TestUnspecifiedEncodings(unittest.TestCase):
    def test_finds_each_kind_of_call(self):
        source = "\n".join([
            "open(p)",
            "open(p, 'w')",
            "p.open()",
            "p.read_text()",
            "p.write_text(t)",
        ])
        self.assertEqual(
            [(1, "open"), (2, "open"), (3, "open"), (4, "read_text"), (5, "write_text")],
            unspecified_encodings(source))

    def test_passes_binary_modes_named_encodings_and_other_modules(self):
        source = "\n".join([
            "open(p, 'rb')",
            "p.open('wb')",
            "open(p, encoding='utf-8')",
            "p.read_text('utf-8')",
            "p.write_text(t, 'utf-8')",
            "gzip.open(p)",
            "open(p, **options)",
        ])
        self.assertEqual([], unspecified_encodings(source))

    def test_the_package_names_every_text_encoding(self):
        problems = []
        for path in sorted(PACKAGE.rglob("*.py")):
            if "tests" in path.relative_to(PACKAGE).parts:
                continue
            for line, call in unspecified_encodings(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(PACKAGE.parent).as_posix()}:{line}: {call}")
        self.assertEqual([], problems, "pass encoding=\"utf-8\" (or open in binary mode)")


if __name__ == "__main__":
    unittest.main()
