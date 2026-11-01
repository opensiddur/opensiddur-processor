# -*- coding: utf-8 -*-
"""Extract Birnbaum's footnotes from the English transcription and key them to URNs.

The English Wikisource transcription of this scan carries every note as a `<ref>` at the
point the print marks, which is the one thing it is better placed to give than the reading
is: the notes are long English prose, and transcribing eighty-six of them by hand is the
kind of work that went wrong six words at a time in `he_akedah`.

**The transcription is not the print, and for the Hebrew inside a note that matters.** The
English prose it gives is worth taking; the Hebrew it quotes has been silently normalised in
at least two places. Printed 48 sets `על כל דברי שירות ותשבחות דוד` and the transcription
drops `דוד` -- the last word of the phrase, and the point of the comparison, since the note
is about praise contained in *David's* psalms. Printed 84 sets `מחיה מתים` and the
transcription adds a definite article, making the quoted passage name agree with the form the
blessing's own closing uses. Neither is visible from inside the transcription: both read as
perfectly ordinary Hebrew, and only the image says otherwise.

So every Hebrew run a note carries has to be read off the page image, exactly as the liturgy
is, and `TEXT_CORRECTIONS` is where the difference is recorded. English prose can be taken on
the transcription's word; Hebrew cannot.

What it does **not** give is where a note sits on the page. It attaches every `<ref>` to
the English page, and the print sets the commentary under the **Hebrew** page of the
opening — recorded in `readings/english_22_26.md`. So the transcription says *which* notes
a page has and never *where* they are.

Three kinds of note come out, and the print tells them apart by how they are keyed:

- **commentary with a lemma** — `{{he|לעולם יהא|…}}` opens the note, and in the print the
  unpointed Hebrew catchword is the whole key: no mark stands in the text at all.
- **commentary numbered to match its text** — Rabbi Ishmael's `ILLUSTRATIONS`, one worked
  example per rule, numbered `1.` to `13.` to match the rules themselves. The number is
  the key; there is no separate mark and no lemma.
- **a scripture citation** — a bare reference, keyed to a superscript numeral that restarts
  at 1 on every English page.

The target is the canonical URN of the text the anchor falls in, found by matching the
words before the `<ref>` against the authored English prayer bodies. That is why it can be
mechanical: the authored text has already been checked word for word against the reading by
`reverse`, so a match is a match against the print.

What it writes is `build/notes_data.py` -- Python literals, not a data file the package
reads at import time. Nothing importable may read a data file: CI has no submodule, and
`common.SCAN_PAGE` is written out for the same reason.

Run from the repository root:

    uv run python specs/birnbaum_scan/extract_notes.py
"""
import json
import textwrap
import os
import pathlib
import re
import sys

sys.path.insert(0, ".")

#: The sources this reads. Default to the `sourcetexts` submodule, which every checkout
#: has once `git submodule update --init` has run; `$OPENSIDDUR_SOURCETEXTS` points it at
#: a standalone worktree instead. This was an absolute path into one particular worktree,
#: which meant the generator stopped running the moment that worktree was closed out --
#: and a generator that cannot be re-run cannot be corrected.
ST = pathlib.Path(
    os.environ.get("OPENSIDDUR_SOURCETEXTS", pathlib.Path(__file__).resolve().parents[2] / "sourcetexts")
) / "sources/birnbaum_siddur"

REF = re.compile(r"<ref>(.*?)</ref>", re.S)
HE = re.compile(r"\{\{he\|([^|{}]*)(?:\|([^{}]*))?\}\}")
ITALIC = re.compile(r"''([^']+)''")
CENTRED = re.compile(r"\{\{c\|([^{}]*)\}\}")
ILLUSTRATION = re.compile(r"^(\d+)\.\s")

#: A scripture citation is a reference and nothing else: a book, a chapter, a verse, and at
#: most a few of them separated by semicolons. Everything longer is commentary.
#:
#: Classifying by "does it open with `{{he|`" is not enough -- printed 6's note on the
#: tefillin heading opens `The תפילין, known as …` and is plainly commentary. Length and
#: shape tell them apart, and the boundary is not close: the longest citation in the book is
#: nine words and the shortest commentary is twenty-eight.
#: A reference: a book name and its numbers. A citation is a run of them, because one note
#: often gives several -- `Numbers 24:5; Psalms 5:8; 26:8; 95:6; 69:14.` is one citation on
#: printed 4, and `Deuteronomy 6:4-9; 11:13-21; Exodus 13:1-10; 11-16.` is one on printed 6.
#:
#: A first version anchored the book name at the start only, so both of those came through
#: as commentary. The readings caught it: they record three citations on printed 4 and two
#: on printed 6, and the extraction was finding two and one.
REFERENCE = r"(?:I{1,3}\s+)?[A-Z][A-Za-z']*(?:\s+[A-Z][A-Za-z']*)*[\s\d:;,.\u2013-]+"
CITATION = re.compile(rf"^[\s'\"]*(?:{REFERENCE})+$")


def _is_citation(body: str) -> bool:
    plain = " ".join(re.sub(r"'{2,}", "", body).split())
    return bool(CITATION.match(plain)) and len(plain.split()) <= 12


def _tei(text: str):
    """Wikitext to the paragraphs of block content a note carries.

    A note is **not** a paragraph of inline prose. Printed 41's runs to a sub-heading, a
    numbered list and a reference to another page of the book; several others carry a
    `<br>` that is a paragraph break in the print. So this returns a list of
    `{"rend": …, "text": …}` and the emitter wraps each in its own `tei:p`.

    A centred line inside a note -- `ILLUSTRATIONS`, `THE KADDISH` -- is a sub-heading, but
    `tei:head` must be a direct child of `tei:div` and a note is not one. It is a
    `tei:p[@rend]` instead, which says the same thing about the typography and is valid.
    """
    text = text.replace("<br />", "<br>").replace("<br/>", "<br>")
    out = []
    for chunk in text.split("<br>"):
        for piece, rend in _split_centred(chunk):
            piece = HE.sub(
                lambda m: f'<tei:foreign xml:lang="he">{m.group(1)}</tei:foreign>', piece)
            piece = ITALIC.sub(r'<tei:hi rend="italic">\1</tei:hi>', piece)
            piece = RANGE.sub("\u2013", piece)
            piece = " ".join(piece.split())
            if piece:
                out.append({"rend": rend, "text": piece})
    return out


def _split_centred(chunk: str):
    """A chunk into (text, rend) runs, the `{{c|…}}` ones centred and on their own."""
    pos = 0
    for m in CENTRED.finditer(chunk):
        yield chunk[pos:m.start()], None
        yield m.group(1), "centred"
        pos = m.end()
    yield chunk[pos:], None


def _lemma(body: str):
    """A note opening with `{{he|…}}` is lemma-keyed; the lemma is the Hebrew."""
    m = HE.match(body.lstrip())
    if not m:
        return None, body
    return m.group(1), body[body.index("}}", body.index("{{he|")) + 2:]


def _fold(text: str) -> str:
    """Quote and dash characters differ between the transcription and the authored text."""
    for a, b in (("\u201c", '"'), ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'"),
                 ("\u2014", "-"), ("\u2013", "-")):
        text = text.replace(a, b)
    return text


def anchors(printed: int):
    raw = (ST / "en" / "text" / f"{printed + 25:03d}.txt").read_text(encoding="utf-8")
    for was, now in TEXT_CORRECTIONS.items():
        raw = raw.replace(was, now)
    for m in REF.finditer(raw):
        before = raw[:m.start()]
        before = REF.sub("", before)
        before = re.sub(r"<[^>]*>", " ", before)
        before = re.sub(r"\{\{[^{}]*\}\}", " ", before)
        # A template whose closing braces are *after* the ref -- `{{c|“The Lord shall
        # reign forever and ever."<ref>…</ref>}}` -- leaves `{{c|` in the window, and the
        # last-N-words match then never finds the passage.
        before = re.sub(r"\{\{[^{}|]*\|", " ", before)
        before = re.sub(r"'{2,}", "", before)
        yield " ".join(before.split())[-120:], m.group(1)


#: Notes the transcription attaches where the words before them are not the words they
#: annotate: a note on a **section heading**, whose key is the heading and not a phrase in
#: any passage, and a note whose `<ref>` follows the opening words of the passage it is
#: about rather than preceding them. Both are read off the page, not guessed.
BY_LEMMA = {
    "ציצית": "urn:x-opensiddur:text:prayer:tallith/lehitattef",
    "אדון עולם": "urn:x-opensiddur:text:poem:adon_olam",
    "יגדל": "urn:x-opensiddur:text:poem:yigdal",
    "קדיש דרבנן": "urn:x-opensiddur:text:prayer:kaddish/derabbanan/yitgaddal",
    "עושה שלום": "urn:x-opensiddur:text:prayer:kaddish/derabbanan/oseh_shalom",
    "שמונה עשרה": "urn:x-opensiddur:text:prayer:amidah/adonai_sefatai",
    "קדושה": "urn:x-opensiddur:text:prayer:amidah/qedushah",
    "רצה": "urn:x-opensiddur:text:prayer:amidah/avodah",
}


#: Commentary with no catchword, keyed by the opening of the note itself. Printed 6 sets a
#: note on the section heading `PUTTING ON THE TEFILLIN`; it has no lemma because the
#: heading is the key, and it takes the first text under that heading -- the nearest
#: canonical URN, which is the rule for every note in this apparatus.
BY_OPENING = {
    "The <tei:foreign": "urn:x-opensiddur:text:prayer:tefillin/hineni_mekhavven",
}

#: The transcription sets a **hyphen** in every numeric range; the print sets an **en dash**.
#: Not only verse ranges: printed 6's foot has `13:1–10; 11–16.`, where the second range has
#: no chapter at all, and `Rabbi Isaiah Horowitz (1555–1630)` in the note above it. So the
#: rule is any number, dash, number -- checked at 7x on that page.
RANGE = re.compile(r"(?<=\d)-(?=\d)")

#: Set as printed, and **not** a transcription error, so that nobody tidies it later: the
#: second citation on printed 34 reads `Psalms 46:8; 84:13: 20:10; 32:7.` with a colon where
#: every other separator in the same note is a semicolon. Checked at 7x on the page's own
#: foot. His slip, faithfully transcribed.
PRINTS_ITS_OWN_SLIP = "''Psalms'' 46:8; 84:13: 20:10; 32:7."

#: How many numbered citations each English page carries, where the page's foot has been
#: read. An independent record: these come from `readings/english_*.md` and the images, and
#: the extraction derives its own count from the transcription. Two witnesses that were made
#: separately, so a disagreement is a finding.
#:
#: It has already been one. A first version of `CITATION` anchored the book name at the
#: start of the note, so `Numbers 24:5; Psalms 5:8; …` and `Deuteronomy 6:4-9; …; Exodus
#: 13:1-10; …` came through as commentary -- printed 4 counted two where the page prints
#: three, and printed 6 counted one where it prints two.
EXPECTED_CITATIONS = {4: 3, 6: 2, 8: 2, 10: 0, 24: 1, 26: 1, 28: 0, 34: 4, 48: 0}

#: Errors in the notes' own text, settled on the image.
TEXT_CORRECTIONS = {
    # Printed 4's first citation, at 7x: `Numbers 24:5; Psalms 5:8` -- semicolon, as it is
    # between every other pair of references in the same note. The transcription sets a
    # colon.
    "''Numbers'' 24:5: ''Psalms'' 5:8": "''Numbers'' 24:5; ''Psalms'' 5:8",
    # Printed 28's note, at 7x. The transcription drops a letter and sets a backtick.
    "wll forgive": "will forgive",
    # He transliterates ayin with a turned comma: `Ta\u2018anith`, plain on printed 84's
    # foot. The transcription sets a backtick and drops the first `a`.
    "Ta`nith 27b": "Ta\u2018anith 27b",
    # Printed 85's foot, at 8x: `God is to be made in public service only.` The
    # transcription drops both `i`s. Found by ranking the notes against the Archive's OCR
    # -- this one scored 74% where the median is 95%.
    "kingship of God s to be made n public service only":
        "kingship of God is to be made in public service only",
    # Printed 48's foot, at 4x: the expression ends `ותשבחות דוד`. The transcription drops
    # `דוד`. It is the phrase from Nishmath, and the last word is the point of the
    # comparison -- the note is about praise contained in *David's* psalms.
    "על כל דברי שירות ותשבחות": "על כל דברי שירות ותשבחות דוד",
    # Printed 84's foot, at 4.5x: `מחיה מתים`, no article. The transcription adds a `ה`,
    # normalising the quotation to the form the blessing's closing uses. Birnbaum is
    # naming the passage, and he sets it as printed.
    "אתה גבור... מחיה המתים": "אתה גבור... מחיה מתים",
}

#: Lemmas the transcription gets wrong, settled on the image. The catchword is quoted from
#: the text, so a wrong one is as much a misreading as a wrong word would be.
LEMMA_CORRECTIONS = {
    # Printed 1's foot, at 8x: the catchword ends at `לנו`. The transcription adds `משה`.
    "תורה צוה לנו משה": "תורה צוה לנו",
}

#: Lemmas the print spells **plene** where the pointed text is defective: an unpointed
#: catchword has to be readable without points, so `עֹשֶׂה` is quoted as `עושה` and
#: `נְצֹר` as `נצור`. Confirmed on printed 48's own foot. Not a transcription error, and
#: not something to normalise -- the catchword is set as printed.
#:
#: Checked mechanically: every other lemma's consonantal skeleton is found in the skeleton
#: of the text it annotates. 37 of 47 are, and the ten that are not are these three plus
#: seven that name a prayer or a person rather than quoting it.
PLENE_LEMMAS = ("עושה שלום", "אלהי נצור", "ברכה המשולשת")

#: Lemmas that **name** what the note is about instead of quoting it: a section heading,
#: a prayer's traditional name, or a person.
NAMING_LEMMAS = ("ציצית", "רבי ישמעאל בן אלישע", "קדיש דרבנן", "שמונה עשרה", "קדושה",
                 "יעלה ויבוא", "מודים דרבנן")

#: Notes on text these projects do not hold, and why. They are **not** dropped silently:
#: the count has to add up, and a note quietly missing is indistinguishable from a note
#: never read.
OUTSIDE = {
    "Exodus</tei:hi> 15:11": "Mi Khamokha, in the Ge'ulah blessing of the Shema",
    "Exodus</tei:hi> 15:18": "Adonai Yimlokh, in the Ge'ulah blessing of the Shema",
}


def main():
    from opensiddur.importer.birnbaum_scan.build import build_en

    # A note keys to the **nearest** canonical URN, so a `tei:seg` inside a prayer beats
    # the prayer: printed 1's note is about `תורה צוה לנו`, which is one seg of the
    # children's composite and not the whole of it.
    SEG = re.compile(r'<tei:seg corresp="([^"]+)">(.*?)</tei:seg>', re.S)
    bodies = []
    for p in build_en.PRAYERS:
        for m in SEG.finditer(p["body"]):
            bodies.append((m.group(1),
                           _fold(" ".join(re.sub(r"<[^>]+>", " ", m.group(2)).split())),
                           p["first"], p["last"]))
        bodies.append((p["urn"],
                       _fold(" ".join(re.sub(r"<[^>]+>", " ", p["body"]).split())),
                       p["first"], p["last"]))

    out, unmatched = [], 0
    for printed in list(range(2, 49, 2)) + list(range(82, 99, 2)):
        citation_n = 0
        for anchor, body in anchors(printed):
            tail = _fold(anchor).split()
            target = None
            for take in (10, 7, 5, 3):
                needle = " ".join(tail[-take:])
                hits = [u for u, t, _f, _l in bodies if needle in t]
                if len(hits) == 1:
                    target = hits[0]
                    break
                if len(hits) > 1:
                    # Several matched because a seg and the prayer holding it both do:
                    # take the seg, which is the nearer URN.
                    nested = [u for u in hits
                              if all(u == v or u.startswith(v + "/") for v in hits)]
                    if len(nested) == 1:
                        target = nested[0]
                        break
                    # The same words in two places: the one printed on this page wins.
                    # `days of old and as in former years` closes both the korbanot's
                    # ve-arvah and the Yehi Ratzon after Rabbi Ishmael's rules.
                    here = [u for u, t, f, l in bodies
                            if needle in t and f <= printed <= l]
                    if len(here) == 1:
                        target = here[0]
                        break
            lemma, rest = _lemma(body)
            lemma = LEMMA_CORRECTIONS.get(lemma, lemma)
            illustration = ILLUSTRATION.match(body.strip())
            if not lemma and not illustration and not _is_citation(body):
                # Commentary that does not open with its Hebrew -- printed 6's note on the
                # tefillin heading, for one. It has no catchword to key on, so it is keyed
                # like a heading note, by what it is about.
                lemma = None
            if lemma:
                kind, n = "commentary", None
                text = _tei(rest)
            elif illustration:
                kind, n = "commentary", illustration.group(1)
                text = _tei(body.strip()[illustration.end():])
            elif _is_citation(body):
                citation_n += 1
                kind, n = "citation", str(citation_n)
                text = _tei(body)
            else:
                kind, n = "commentary", None
                text = _tei(body)
            if target is None and lemma in BY_LEMMA:
                target = BY_LEMMA[lemma]
            flat = " ".join(p["text"] for p in text)
            if target is None:
                for opening, urn in BY_OPENING.items():
                    if flat.startswith(opening):
                        target = urn
                        break
            outside = next((why for frag, why in OUTSIDE.items() if frag in flat), None)
            if target is None and outside is None:
                unmatched += 1
            out.append(dict(page=printed, kind=kind, n=n, lemma=lemma,
                            target=target, text=text, outside=outside,
                            anchor=" ".join(tail[-8:])))
    _write_module(out)
    for page, expected in sorted(EXPECTED_CITATIONS.items()):
        got = sum(1 for n in out if n["page"] == page and n["kind"] == "citation")
        if got != expected:
            raise SystemExit(
                f"printed {page}: the reading records {expected} numbered citation(s) and "
                f"the transcription yields {got}")
    outside = sum(1 for n in out if n["outside"])
    print(f"# {len(out)} notes, {outside} on text these projects do not hold, "
          f"{unmatched} without a target", file=sys.stderr)


UNITS = (
    ("YELADIM_NOTES", lambda u: u.endswith(("torah_tzivvah", "torah_tzivvah/morashah"))
     or "/yeladim" in u),
    ("AMIDAH_NOTES", lambda u: ":prayer:amidah" in u),
    ("BIRCHOT_NOTES", lambda u: True),
)


def _write_module(notes):
    """Birnbaum's notes as Python literals, one list per unit."""
    buckets = {name: [] for name, _ in UNITS}
    dropped = []
    for n in notes:
        if n["outside"]:
            dropped.append(n)
            continue
        for name, belongs in UNITS:
            if belongs(n["target"]):
                buckets[name].append(n)
                break

    lines = ['# -*- coding: utf-8 -*-',
             '"""Birnbaum\'s eighty-six footnotes, keyed to the texts they annotate.',
             '',
             'Generated by `specs/birnbaum_scan/extract_notes.py`; see its docstring for how the',
             'notes are read, how they are told apart and how each one\'s target is found.',
             '',
             'Two notes are not here, and the number is what says so: printed 82 carries notes on',
             'Mi Khamokha and Adonai Yimlokh, which are in the Ge\'ulah blessing of the Shema and',
             'are not in these projects yet. 86 read, 84 encoded.',
             '"""',
             '']
    for name, _ in UNITS:
        lines.append(f"{name} = [")
        for n in buckets[name]:
            lines.append("    dict(")
            lines.append(f'        kind="{n["kind"]}",')
            if n["n"]:
                lines.append(f'        n="{n["n"]}",')
            lines.append(f'        target="{n["target"]}",')
            if n["lemma"]:
                lines.append(f'        lemma="{n["lemma"]}",')
            lines.append("        paras=[")
            for para in n["text"]:
                body = para["text"].replace("\\", "\\\\").replace('"', '\\"')
                wrapped = textwrap.wrap(body, width=80) or [""]
                rend = f'rend="{para["rend"]}", ' if para["rend"] else ""
                lines.append(f"            dict({rend}text=(")
                for w in wrapped:
                    tail = " " if w is not wrapped[-1] else ""
                    lines.append(f'                "{w}{tail}"')
                lines.append("            )),")
            lines.append("        ],")
            lines.append("    ),")
        lines.append("]")
        lines.append("")
    out = pathlib.Path("opensiddur/importer/birnbaum_scan/build/notes_data.py")
    out.write_text("\n".join(lines), encoding="utf-8")
    for name, _ in UNITS:
        print(f"# {name}: {len(buckets[name])}", file=sys.stderr)
    print(f"# dropped (outside these projects): {len(dropped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
