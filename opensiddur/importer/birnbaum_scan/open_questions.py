"""The open questions, and nothing else.

A page's differences are mostly settled the moment they are looked at, and the settled
ones are noise to whoever has to decide the rest. This collects only what is still open --
across every page read so far -- and writes it as a queue with enough of the surrounding
phrase to decide from, one block per question and a blank `answer:` line under each.

Two states are open, and the distinction is the whole reason this exists:

``unresolved``
    written down, looked at, not settled.
``(absent)``
    no entry in the page's verdict file at all. Indistinguishable, until now, from a page
    nobody had opened -- which is how six of page 7's differences came to be invisible.

Answer a question by writing the form the print actually carries on the `answer:` line, or
by writing `print` or `reading` if that is easier. `apply` turns those into verdicts:
the reading's own form means `print`, the transcription's means `reading`, and anything
else is refused rather than guessed at.
"""
import argparse
import pathlib
import re
import sys

from opensiddur.importer.scan import compare as cmp

from .pages import BOOK_DIRECTORY

READING_DIRECTORY = BOOK_DIRECTORY / "scan_reading"
HEBREW = READING_DIRECTORY / "hebrew"
TRANSCRIPTION = READING_DIRECTORY / "transcription"
VERDICTS = pathlib.Path(__file__).resolve().parents[3] / "specs" / "birnbaum_scan" / "verdicts"

#: How many words either side of the difference to quote. Enough to recognise the phrase.
CONTEXT = 4

#: What each bucket usually turns on, said once here rather than in every block.
WHAT_TO_LOOK_AT = {
    cmp.VOWELS: "a point: crop it at 12x, and ask what the word is before blaming the scan",
    cmp.CONSONANTS: "a letter: the skeleton differs, so this is a different word",
    cmp.WHITESPACE: "spacing or a line break",
}


class Question:
    """One difference nobody has settled, with the phrase it sits in."""

    def __init__(self, page: str, difference: cmp.Difference, context: str, recorded: bool):
        self.page = page
        self.difference = difference
        self.context = context
        #: True when the verdict file says `unresolved`; False when it says nothing at all.
        self.recorded = recorded

    @property
    def key(self) -> str:
        return self.difference.key


def _marks(word: str) -> list[str]:
    """The points on a word, named, in the order they are written."""
    import unicodedata
    return [unicodedata.name(c, "?").replace("HEBREW POINT ", "").replace("HEBREW ", "")
            for c in word if unicodedata.category(c) == "Mn"]


def describe(ours: str, theirs: str) -> str:
    """What actually differs, said in marks rather than left to the eye.

    Two pointed words differing by one meteg look identical in a list, and a reader
    deciding twenty of them should not have to spot the difference twenty times.

    Marks are counted, not merely collected: a qamats swapped for a pataḥ in a word that
    already carries a pataḥ elsewhere is the case that matters most, and a set would
    report only half of it. The skeleton is checked separately, because a difference in
    letters is a different word and should never be reported as a point.
    """
    import unicodedata
    from collections import Counter

    def skeleton(word: str) -> str:
        return "".join(c for c in word if unicodedata.category(c) != "Mn")

    parts = []
    if skeleton(ours) != skeleton(theirs):
        parts.append("the letters differ, not just the points")
    ours_marks, theirs_marks = Counter(_marks(ours)), Counter(_marks(theirs))
    lost = ours_marks - theirs_marks
    gained = theirs_marks - ours_marks
    if lost:
        parts.append(f"reading has {', '.join(sorted(lost.elements()))}")
    if gained:
        parts.append(f"transcription has {', '.join(sorted(gained.elements()))}")
    if not parts:
        parts.append("the same marks in a different order")
    return "; ".join(parts)


def _context(words: list[str], at: int, width: int = CONTEXT) -> str:
    start = max(0, at - width)
    return " ".join(words[start:at + width + 1])


def pages_read(hebrew: pathlib.Path = HEBREW) -> list[str]:
    """Every page with a lifted Hebrew text, in printed order."""
    return sorted((p.stem for p in hebrew.glob("*.txt")), key=lambda n: int(n))


def collect(pages: list[str] | None = None, *, hebrew: pathlib.Path = HEBREW,
            transcription: pathlib.Path = TRANSCRIPTION,
            verdicts: pathlib.Path = VERDICTS) -> list[Question]:
    """Every open question, over every page that has been read."""
    import json
    out: list[Question] = []
    for page in pages or pages_read(hebrew):
        ours_path, theirs_path = hebrew / f"{page}.txt", transcription / f"{page}.txt"
        if not (ours_path.exists() and theirs_path.exists()):
            continue
        ours = ours_path.read_text(encoding="utf-8")
        comparison = cmp.compare(ours, theirs_path.read_text(encoding="utf-8"), page=page)
        recorded: dict[str, str] = {}
        verdict_file = verdicts / f"{page}.json"
        if verdict_file.exists():
            recorded = json.loads(verdict_file.read_text(encoding="utf-8"))
            comparison.apply_verdicts(recorded)
        words = cmp.words(ours)
        for difference in comparison.differences:
            if difference.verdict != cmp.UNRESOLVED:
                continue
            out.append(Question(page, difference,
                                _context(words, difference.at),
                                recorded=difference.key in recorded))
    return out


def render(questions: list[Question]) -> str:
    """The queue, as a page someone can answer in place."""
    if not questions:
        return ("# Open questions\n\nNone. Every difference on every page read so far has "
                "a verdict.\n")
    lines = ["# Open questions", ""]
    lines.append(f"{len(questions)} unsettled, over "
                 f"{len({q.page for q in questions})} page(s). Everything already decided "
                 "is left out on purpose.")
    lines.append("")
    lines.append("Write the form the print carries on the `answer:` line -- or `print` to "
                 "keep the reading, `reading` to take the transcription. Then:")
    lines.append("")
    lines.append("    python -m opensiddur.importer.birnbaum_scan.open_questions "
                 "--apply specs/birnbaum_scan/OPEN_QUESTIONS.md")
    lines.append("")
    by_page: dict[str, list[Question]] = {}
    for q in questions:
        by_page.setdefault(q.page, []).append(q)
    for page, group in by_page.items():
        lines.append(f"## Printed page {page}")
        lines.append("")
        for n, q in enumerate(group, start=1):
            d = q.difference
            lines.append(f"### {page}.{n}  ({d.bucket})")
            lines.append("")
            lines.append(f"    context        … {q.context} …")
            lines.append(f"    reading        {d.ours}")
            lines.append(f"    transcription  {d.theirs}")
            lines.append("")
            lines.append(f"    differs by     {describe(d.ours, d.theirs)}")
            lines.append("")
            lines.append(f"What to look at: {WHAT_TO_LOOK_AT.get(d.bucket, d.bucket)}.")
            if not q.recorded:
                lines.append("")
                lines.append("*No entry in the verdict file — this one was never written "
                             "down, only left out.*")
            lines.append("")
            lines.append(f"    key: {q.key}")
            lines.append("    answer:")
            lines.append("")
    return "\n".join(lines) + "\n"


ANSWER = re.compile(r"^\s*key:\s*(?P<key>.+?)\s*\n\s*answer:\s*(?P<answer>.*?)\s*$",
                    re.M)


def parse_answers(text: str) -> dict[str, str]:
    """The answered blocks of a queue, as key -> what was written."""
    return {m.group("key"): m.group("answer")
            for m in ANSWER.finditer(text) if m.group("answer")}


def verdict_for(key: str, answer: str) -> str:
    """What an answer means, refusing anything it cannot mean.

    A key is `bucket:at:ours|theirs`, so the two readings are in the key itself and an
    answer can be checked against them rather than trusted.
    """
    def unquote(value: str) -> str:
        """A whitespace candidate is shown quoted, because a bare space is invisible.
        Accept it either way rather than making someone type the quotes back."""
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == "'":
            return value[1:-1]
        return value

    answer = answer.strip()
    if answer in cmp.VERDICTS:
        return answer
    _, _, forms = key.split(":", 2)
    ours, _, theirs = forms.partition("|")
    if answer == ours or unquote(answer) == unquote(ours):
        return cmp.PRINT
    if answer == theirs or unquote(answer) == unquote(theirs):
        return cmp.READING
    raise ValueError(
        f"answer {answer!r} is neither reading ({ours!r}) nor transcription ({theirs!r}) "
        f"nor one of {cmp.VERDICTS}")


def apply(text: str, *, verdicts: pathlib.Path = VERDICTS,
          hebrew: pathlib.Path = HEBREW,
          transcription: pathlib.Path = TRANSCRIPTION) -> dict[str, int]:
    """Write answered questions into the verdict files they belong to."""
    import json
    answers = parse_answers(text)
    questions = {q.key: q for q in collect(hebrew=hebrew, transcription=transcription,
                                           verdicts=verdicts)}
    written: dict[str, int] = {}
    by_page: dict[str, dict[str, str]] = {}
    for key, answer in answers.items():
        question = questions.get(key)
        if question is None:
            raise ValueError(f"no open question has the key {key!r}")
        by_page.setdefault(question.page, {})[key] = verdict_for(key, answer)
    for page, decided in by_page.items():
        path = verdicts / f"{page}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        existing.update(decided)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        written[page] = len(decided)
    return written


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", metavar="QUEUE",
                        help="read answers from a filled-in queue and record them")
    parser.add_argument("-o", "--output", metavar="PATH",
                        help="write the queue here instead of standard output")
    parser.add_argument("--reading-directory", metavar="PATH",
                        help="where scan_reading/ lives. Defaults to the sourcetexts "
                             "submodule, which is pinned to a release and so is stale "
                             "while a reading is being worked on; point this at the "
                             "sourcetexts worktree instead.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    hebrew, transcription = HEBREW, TRANSCRIPTION
    if args.reading_directory:
        root = pathlib.Path(args.reading_directory)
        hebrew, transcription = root / "hebrew", root / "transcription"
    if args.apply:
        written = apply(pathlib.Path(args.apply).read_text(encoding="utf-8"),
                        hebrew=hebrew, transcription=transcription)
        if not written:
            print("no answers found")
            return 0
        for page, count in sorted(written.items(), key=lambda kv: int(kv[0])):
            print(f"page {page}: {count} recorded")
        return 0
    text = render(collect(hebrew=hebrew, transcription=transcription))
    if args.output:
        pathlib.Path(args.output).write_text(text, encoding="utf-8")
        print(f"{args.output} written")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
