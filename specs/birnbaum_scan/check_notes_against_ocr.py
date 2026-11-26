"""Corroborate every extracted note against the Internet Archive's own OCR of the scan.

The notes are lifted from the English Wikisource transcription, which is a second reading of
the *same images* and so not an independent witness. The Archive's OCR is a third reading of
those images, made by a different process that has never seen the transcription. It is poor
at Hebrew -- `LICENSE.md` §3 says so -- but the notes are English prose, and for English it
is good enough to answer one question: **are these words on the page at all?**

That is what this asks. For each note it takes the long English words and reports what
fraction of them appear in the OCR of the opening the note sits on. A note whose words are
mostly present is corroborated by a witness that could not have copied the transcription; a
note whose words are largely absent is where to point a pair of eyes.

It does not adjudicate. OCR mangles a word here and there, so a single miss means nothing;
what the score is for is ranking fifty notes on sixteen unread page feet so the reading goes
where it is worth going.

A note is not always on the leaf its `<ref>` is attached to: the commentary sits under the
**Hebrew** page of an opening, and the OCR's own pagination runs a leaf out of step in
places -- printed 88's note on `גרי הצדק` turns up in the OCR of scan 115. So a window of
five leaves is searched, not one.

**Citations are skipped.** A citation is a book name and some numbers; the only long word in
it is the book name, set in italic, and the OCR mangles italic. Scoring them measures the
OCR's handling of italic type and nothing about the note, and it drowned the informative
rows the first time this was run.

    uv run python specs/birnbaum_scan/check_notes_against_ocr.py

## What it found

57 commentary notes, **median corroboration 95%**, two below 75%. Both were read on the
page, and they came out differently:

- Printed 84's note on `קדושה` scored 74%. The transcription reads `kingship of God s to be
  made n public service only`; printed 85's foot, where the note finishes, reads `is` and
  `in`. A real error, now corrected. Note that the score did not *find* the dropped letters
  -- `is` and `in` are shorter than the word threshold -- it found the note worth reading.
- Printed 86's note on `אתה חונן` scored 27%, and the transcription is **right**. The page
  itself carries a damaged glyph, `wh.ch` for `which`, and the OCR of that opening is poor.
  A false alarm, which is what a ranking is allowed to produce.

That is the useful shape of this check: it does not adjudicate, it says where to look. Fifty
of the eighty-six notes sit on page feet that were not read during this pass, and this put
two of them in front of a pair of eyes instead of sixteen page images.
"""
import importlib.util
import pathlib
import re

ST = pathlib.Path("/home/efeins/src/opensiddur-repos/sourcetexts/feat_birnbaum-birchot-hashachar/sources/birnbaum_siddur")
SCAN_OFFSET = 25

#: Long enough that a match is not a coincidence, and short enough to leave plenty to match.
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]{4,}")


def ocr(printed: int) -> str:
    """The OCR of both pages of the opening this printed page belongs to."""
    text = []
    for page in range(printed - 2, printed + 3):
        path = ST / "ia" / "ocr" / f"{page + SCAN_OFFSET:03d}.txt"
        if path.exists():
            text.append(path.read_text(encoding="utf-8", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(text)).lower()


def main() -> int:
    spec = importlib.util.spec_from_file_location(
        "ex", "specs/birnbaum_scan/extract_notes.py")
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)

    rows = []
    for printed in list(range(2, 49, 2)) + list(range(82, 99, 2)):
        page_ocr = ocr(printed)
        if not page_ocr.strip():
            continue
        for _anchor, body in ex.anchors(printed):
            if ex._is_citation(body):
                continue
            words = [w.lower() for w in WORD.findall(re.sub(r"\{\{[^{}]*\}\}", " ", body))]
            if len(words) < 5:
                continue
            found = sum(1 for w in words if w in page_ocr)
            rows.append((found / len(words), printed, len(words), found,
                         " ".join(body.split())[:60]))

    rows.sort()
    weak = [r for r in rows if r[0] < 0.75]
    print(f"{len(rows)} notes checked against the Archive's OCR")
    print(f"median corroboration: "
          f"{sorted(r[0] for r in rows)[len(rows)//2]:.0%}")
    print(f"{len(weak)} below 75%:")
    for score, printed, total, found, text in weak:
        print(f"   p{printed:3d}  {score:5.0%}  ({found}/{total})  {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
