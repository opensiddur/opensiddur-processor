"""Compare scan readings with independent readings or OCR.

Compare word skeletons first, then Hebrew pointing within matching words.
Whitespace differences remain separate. Verdicts require image adjudication;
comparison alone never decides which reading the print supports.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from opensiddur.importer.util.hebrew import to_nfkd

#: Buckets. Every difference is in exactly one.
WHITESPACE = "whitespace"
CONSONANTS = "consonants"
VOWELS = "vowels"
BUCKETS = (WHITESPACE, CONSONANTS, VOWELS)

#: Verdicts. Which reading the page itself supported, once someone looked again.
UNRESOLVED = "unresolved"
PRINT = "print"  # the page said what was read off it; the transcription departs from it
READING = "reading"  # the transcription was right and the page was misread
VERDICTS = (UNRESOLVED, PRINT, READING)

# A maqqef joins two words in print and is written as a separator here, so that a
# transcription setting a space where the page sets a maqqef is a whitespace
# difference rather than a consonantal one.
MAQQEF = "־"
_SEPARATOR = re.compile(rf"[\s{MAQQEF}]+")


#: Optional Birnbaum settlement policy: that edition prints one qamats glyph,
#: while its Wikisource comparison distinguishes phonological qatan. Callers
#: must explicitly opt in; other editions require their own image evidence.
QAMATS, QAMATS_QATAN = "\u05b8", "\u05c7"


def is_qamats_qatan_only(ours: str, theirs: str) -> bool:
    """Whether two words differ in nothing but qamats against qamats qatan.

    Folding the two characters together has to make the words identical. A word where
    something *else* also differs is not settled by the rule, and saying so is the point:
    `קָדָשִׁים` against `קׇדָשִׁים` is the rule, and a meteg or a dagesh riding along with
    it is not.
    """
    fold = lambda word: word.replace(QAMATS_QATAN, QAMATS)
    return ours != theirs and fold(ours) == fold(theirs)


def words(text: str) -> list[str]:
    """Split on whitespace and maqqef, keeping the pointed forms.

    Anything that is not part of a Hebrew word -- Latin rubrics, verse numbers,
    punctuation standing alone -- survives as its own token and will be compared like
    any other; a token with no Hebrew letters has an empty skeleton, which is what
    makes it align only against another such token.
    """
    return [word for word in _SEPARATOR.split(to_nfkd(text)) if word]


def separators(text: str) -> list[str]:
    """The runs of whitespace and maqqef between the words, one per gap.

    A run of spaces, a newline and a blank line are three different separators: the
    last is a paragraph break, which is a fact about the text, and collapsing them
    would hide a transcription that ran two paragraphs together.
    """
    found = _SEPARATOR.findall(to_nfkd(text).strip())
    return [_classify_separator(run) for run in found]


def _classify_separator(run: str) -> str:
    if MAQQEF in run:
        return MAQQEF
    if run.count("\n") >= 2:
        return "\n\n"
    if "\n" in run:
        return "\n"
    return " "


def _marks(word: str) -> str:
    """The combining marks of one word, in order -- its pointing and nothing else."""
    return "".join(c for c in word if unicodedata.category(c) == "Mn")


@dataclass
class Difference:
    """One place two readings of a page disagree."""

    bucket: str
    ours: str
    theirs: str
    #: Index of the first word involved, in our reading. Enough to find the place.
    at: int
    #: How many marks differ, for a vowel difference; how many words, otherwise.
    size: int = 1
    verdict: str = UNRESOLVED
    note: str = ""

    @property
    def key(self) -> str:
        """A stable handle, so a verdict can be recorded against it."""
        return f"{self.bucket}:{self.at}:{self.ours}|{self.theirs}"


@dataclass
class Comparison:
    """Every difference between one reading of a page and another."""

    page: str = ""
    differences: list[Difference] = field(default_factory=list)
    #: Words in our reading, for a difference count to be read as a proportion.
    word_count: int = 0

    def tally(self) -> dict[str, dict[str, int]]:
        """Counts per bucket, split by verdict, plus a total for each bucket."""
        table = {
            bucket: {verdict: 0 for verdict in VERDICTS} | {"total": 0}
            for bucket in BUCKETS
        }
        for difference in self.differences:
            table[difference.bucket][difference.verdict] += difference.size
            table[difference.bucket]["total"] += difference.size
        return table

    def apply_verdicts(self, verdicts: dict[str, str]) -> list[str]:
        """Record which side the page supported. Returns the keys nothing matched.

        An unmatched verdict is returned rather than ignored: a reading gets edited
        between one run and the next, and a verdict quietly doing nothing is how an
        adjudication gets lost.
        """
        by_key = {difference.key: difference for difference in self.differences}
        for key, verdict in verdicts.items():
            if verdict not in VERDICTS:
                raise ValueError(f"{verdict!r} is not one of {VERDICTS}.")
            if key in by_key:
                by_key[key].verdict = verdict
        return [key for key in verdicts if key not in by_key]

    def qamats_qatan_verdicts(self) -> dict[str, str]:
        """Opt-in Birnbaum policy: print verdict for qamats-qatan-only differences.

        The rule is the one class this comparison settles without going back to the image,
        so applying it by hand on every page is copying, and copying is how a difference
        that only *looks* like the rule gets a `print` it did not earn. This finds them and
        refuses everything else.
        """
        return {
            difference.key: PRINT
            for difference in self.differences
            if difference.bucket == VOWELS
            and is_qamats_qatan_only(difference.ours, difference.theirs)
        }


def _skeleton(word):
    # Preserve Latin words and punctuation exactly. Hebrew points alone are marks;
    # punctuation and English OCR substitutions must be textual differences.
    return "".join(c for c in word if not ("\u0591" <= c <= "\u05c7" and unicodedata.category(c) == "Mn"))


def compare(ours: str, theirs: str, *, page: str = "") -> Comparison:
    """Diff two readings of the same page and classify every difference.

    ``ours`` is the reading taken off the scan; ``theirs`` is the transcription being
    checked against it. The direction matters only for the labels.
    """
    our_words, their_words = words(ours), words(theirs)
    our_skeletons = [_skeleton(word) for word in our_words]
    their_skeletons = [_skeleton(word) for word in their_words]

    comparison = Comparison(page=page, word_count=len(our_words))
    matcher = difflib.SequenceMatcher(None, our_skeletons, their_skeletons, autojunk=False)
    our_separators, their_separators = separators(ours), separators(theirs)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            _compare_pointing(comparison, our_words, their_words, i1, i2, j1, j2)
            _compare_separators(
                comparison, our_words, our_separators, their_separators,
                i1, i2, j1, j2,
            )
            continue
        # The skeletons differ, so this is a different text and not a different
        # pointing of the same one, whatever the vowels do.
        comparison.differences.append(
            Difference(
                bucket=CONSONANTS,
                ours=" ".join(our_words[i1:i2]),
                theirs=" ".join(their_words[j1:j2]),
                at=i1,
                size=max(i2 - i1, j2 - j1),
            )
        )
    return comparison


def _compare_pointing(comparison, our_words, their_words, i1, i2, j1, j2) -> None:
    """Within a run of identical skeletons, whatever differs is pointing."""
    for offset in range(i2 - i1):
        ours, theirs = our_words[i1 + offset], their_words[j1 + offset]
        if ours == theirs:
            continue
        our_marks, their_marks = _marks(ours), _marks(theirs)
        differing = sum(
            1
            for tag, a1, a2, b1, b2 in difflib.SequenceMatcher(
                None, our_marks, their_marks, autojunk=False
            ).get_opcodes()
            if tag != "equal"
            for _ in range(max(a2 - a1, b2 - b1))
        )
        comparison.differences.append(
            Difference(
                bucket=VOWELS,
                ours=ours,
                theirs=theirs,
                at=i1 + offset,
                size=differing or 1,
            )
        )


def _compare_separators(comparison, our_words, ours, theirs, i1, i2, j1, j2) -> None:
    """The gaps inside a matched run, which line up with it word for word.

    A gap is named by the word it follows, since a gap has no other address a person
    can find on the page.
    """
    for offset in range(max(i2 - i1 - 1, 0)):
        our_index, their_index = i1 + offset, j1 + offset
        if our_index >= len(ours) or their_index >= len(theirs):
            continue
        if ours[our_index] == theirs[their_index]:
            continue
        comparison.differences.append(
            Difference(
                bucket=WHITESPACE,
                ours=repr(ours[our_index]),
                theirs=repr(theirs[their_index]),
                at=our_index,
                note=f"after {our_words[our_index]}",
            )
        )


def format_tally(comparison: Comparison) -> str:
    """The counts as a Markdown table, for the accuracy report."""
    table = comparison.tally()
    lines = [
        f"| bucket | total | {PRINT} | {READING} | {UNRESOLVED} |",
        "|---|---:|---:|---:|---:|",
    ]
    for bucket in BUCKETS:
        row = table[bucket]
        lines.append(
            f"| {bucket} | {row['total']} | {row[PRINT]} | "
            f"{row[READING]} | {row[UNRESOLVED]} |"
        )
    lines.append(f"\n{comparison.word_count} words read.")
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Count how far a transcription stands from a reading taken off the scan, "
            "in whitespace, consonants and vowels."
        )
    )
    parser.add_argument("reading", type=Path, help="The reading taken off the page.")
    parser.add_argument("transcription", type=Path, help="The text to check against it.")
    parser.add_argument("--page", default="", help="Printed page number, for the report.")
    parser.add_argument(
        "--verdicts",
        type=Path,
        default=None,
        help="JSON object mapping a difference key to print/reading.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON, not a table.")
    parser.add_argument(
        "--settle-qamats-qatan",
        action="store_true",
        help="Add a print verdict to the --verdicts file for every qamats-qatan-only "
             "difference, then continue. Nothing else is settled this way.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _build_arg_parser().parse_args(argv)
    comparison = compare(
        arguments.reading.read_text(encoding="utf-8"),
        arguments.transcription.read_text(encoding="utf-8"),
        page=arguments.page,
    )
    if arguments.settle_qamats_qatan:
        if not arguments.verdicts:
            raise SystemExit("--settle-qamats-qatan needs --verdicts to write into.")
        settled = comparison.qamats_qatan_verdicts()
        existing = (
            json.loads(arguments.verdicts.read_text(encoding="utf-8"))
            if arguments.verdicts.exists()
            else {}
        )
        added = {k: v for k, v in settled.items() if k not in existing}
        if added:
            arguments.verdicts.write_text(
                json.dumps(existing | added, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(f"qamats qatan: {len(settled)} found, {len(added)} newly recorded")

    if arguments.verdicts:
        unmatched = comparison.apply_verdicts(
            json.loads(arguments.verdicts.read_text(encoding="utf-8"))
        )
        for key in unmatched:
            print(f"warning: no difference matches the verdict {key!r}")

    if arguments.json:
        print(
            json.dumps(
                {
                    "page": comparison.page,
                    "word_count": comparison.word_count,
                    "tally": comparison.tally(),
                    "differences": [
                        {
                            "key": d.key,
                            "bucket": d.bucket,
                            "ours": d.ours,
                            "theirs": d.theirs,
                            "at": d.at,
                            "size": d.size,
                            "verdict": d.verdict,
                        }
                        for d in comparison.differences
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_tally(comparison))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
