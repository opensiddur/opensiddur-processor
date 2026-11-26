"""Is every Hebrew run in a built PDF actually set right to left?

A missing direction wrapper does not fail the build, does not fail validation and does not
show up in the emitted TeX as anything but an absence. It shows up in the PDF as a word
whose letters run the wrong way -- `אהליך` set as `דילהא` -- and the apparatus catchword
was set that way on every lemma-keyed note in the book before anyone noticed.

Two ways of checking for it that do **not** work, both tried first:

- *Grepping the TeX for Hebrew outside `\\texthebrew`.* A regex that captures one line after
  `\\Bfootnote{` never examines a multi-paragraph note, and `[^{}]*` cannot strip a
  `\\texthebrew` group that contains braces. That check reported a clean book while the
  defect was still on the page. Match balanced braces or do not match at all.
- *Reading the order of characters out of the extractor.* `pdftotext` reorders RTL runs, and
  `mutool ... -F stext` normalises some lines to logical order and leaves others in visual
  order, so "the characters came out left to right" is not evidence of anything.

What does work is the glyphs' own x coordinates against the text the source asked for. Sort
a line's glyphs by x and you have what a reader sees, left to right. Hebrew set correctly
reads *backwards* in that order; Hebrew set left to right reads forwards. So score both
directions against the source's own letter n-grams and take the larger: no per-run pairing,
no font tables, and nothing to hand-tune.

Run it against a build, with the `--tex-output` TeX kept beside the PDF::

    python -m opensiddur.importer.scan.pdf_direction \\
        output/book.pdf output/book.tex

`--control` re-runs the whole check over reversed runs. An assertion that cannot fail proves
nothing, and this one is cheap to prove: the control should flag nearly everything.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from lxml import etree

#: Hebrew letters, without the points. A run's direction is carried by its letters; the
#: points sit on top of their letter and share its x, so they say nothing about order.
LETTER = re.compile(r"[א-ת]")

#: Long enough to be a word rather than a coincidence, short enough that a two-word lemma
#: still scores. The apparatus is full of three- and four-letter catchwords.
K = 4

#: Glyphs the Hebrew font hands back in its private use area rather than as Unicode.
#: Anything not mapped is dropped from both the rendered run and its reverse, so dropping
#: it cannot favour either direction.
PRIVATE_USE = {0xE802: "ך"}


def letters(text: str) -> str:
    return "".join(c for c in text if LETTER.match(c))


def base(char: str) -> str | None:
    """The plain letter a rendered glyph stands for, or None if it is not a letter."""
    point = ord(char)
    if 0x05D0 <= point <= 0x05EA:
        return char
    if 0xFB1D <= point <= 0xFB4F:                      # vav-with-dagesh, alternative ayin...
        parts = [p for p in unicodedata.decomposition(char).split() if not p.startswith("<")]
        if parts:
            letter = chr(int(parts[0], 16))
            if LETTER.match(letter):
                return letter
    return PRIVATE_USE.get(point)


def corpus_of(tex: Path) -> set[str]:
    """Every K-gram of Hebrew letters the source asks for, in the order it asks for them."""
    source = letters(tex.read_text(encoding="utf-8"))
    return {source[i:i + K] for i in range(len(source) - K + 1)}


def score(run: str, corpus: set[str]) -> int:
    return sum(1 for i in range(len(run) - K + 1) if run[i:i + K] in corpus)


def runs_of(line) -> list[str]:
    """A line's Hebrew runs as a reader sees them: glyphs by x, split at anything else.

    A space keeps a run open -- `עת רצון` is one phrase and its two words have to be
    checked together, because a single word looks right either way round (the shaper sets
    Hebrew right to left within a run whatever the surrounding direction is; it is the
    words that come out in the wrong order).
    """
    out: list[str] = []
    run: list[str] = []
    for char in sorted(line.iter("char"), key=lambda c: float(c.get("x"))):
        text = char.get("c")
        if not text or unicodedata.category(text) == "Mn":
            continue
        letter = base(text)
        if letter:
            run.append(letter)
        elif text == " " and run:
            continue
        else:
            if run:
                out.append("".join(run))
            run = []
    if run:
        out.append("".join(run))
    return out


def stext(pdf: Path) -> Path:
    out = Path(tempfile.mkdtemp()) / "stext.xml"
    subprocess.run(["mutool", "draw", "-F", "stext", "-o", str(out), str(pdf)],
                   check=True, capture_output=True)
    return out


def check(extracted: Path, corpus: set[str], *, reverse: bool = False):
    """Every Hebrew run that scores better read left to right than right to left."""
    flagged, total = [], 0
    page = None
    for event, element in etree.iterparse(extracted, events=("start", "end")):
        if event == "start" and element.tag == "page":
            page = int(element.get("id")[len("page"):])
            continue
        if event != "end" or element.tag != "line":
            continue
        top = float(element.get("bbox").split()[1])
        for run in runs_of(element):
            if reverse:
                run = run[::-1]
            if len(run) < K:
                continue
            total += 1
            if score(run, corpus) > score(run[::-1], corpus):
                flagged.append((page, top, run))
        element.clear()
    return flagged, total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("tex", type=Path, help="The TeX the PDF was built from.")
    parser.add_argument("--control", action="store_true",
                        help="Also run the check over reversed runs, to show it can fail.")
    args = parser.parse_args(argv)

    corpus = corpus_of(args.tex)
    extracted = stext(args.pdf)

    flagged, total = check(extracted, corpus)
    for page, top, run in flagged:
        print(f"  page {page} at y={top:.1f}: {run}")
    print(f"{len(flagged)} of {total} Hebrew runs are set left to right")

    if total == 0:
        print("No measurable Hebrew runs; direction is unverified")
        return 2

    if args.control:
        control, _ = check(extracted, corpus, reverse=True)
        print(f"control: {len(control)} of {total} flagged when every run is reversed")
        if not control:
            print("the check cannot fail, so it proves nothing")
            return 2
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
