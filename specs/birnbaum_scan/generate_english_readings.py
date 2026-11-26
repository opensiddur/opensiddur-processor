"""Write `scan_reading/english/{page}.txt` from the English Wikisource transcription.

The English pages have something the Hebrew pages do not: a page-by-page transcription of
**this same scan**, at quality 4. That is not corroboration -- both are the same witness --
but it does mean the English reading is made by *correcting* a transcription rather than by
setting type from nothing, and the corrections are the part worth recording.

So this script derives the file and applies :data:`CORRECTIONS`, each of which was settled
on the image and is recorded in `readings/english_*.md`. Everything else is the
transcription's, which is the honest description: we read the English pages to find what
the transcription gets wrong, and it gets very little wrong.

What is stripped: `<ref>` (the apparatus, which is not the page's running text), and
`<noinclude>` (running heads). **Headings and citations are stripped too**, because
`hebrew/{page}.txt` excludes them and the two sides of `reverse` have to hold the same kind
of thing -- the same rule the transcription slice follows. They are read into
`readings/english_*.md` instead, and the script prints every one it drops so that nothing
goes missing quietly.

Run from the repository root:

    uv run python specs/birnbaum_scan/generate_english_readings.py

The point of the file is that `reverse` can then check the English column as it checks the
Hebrew one -- which is what would have caught `Psalm 36:8-11` standing where the print sets
an en dash.
"""
import pathlib
import re

ST = pathlib.Path("/home/efeins/src/opensiddur-repos/sourcetexts/feat_birnbaum-birchot-hashachar/sources/birnbaum_siddur")
OUT = ST / "scan_reading" / "english"

#: Whole passages the transcription **omits**, supplied from the image. Distinct from a
#: correction because nothing is there to correct: printed 16's last blessing is simply not
#: in the transcription, and the Hebrew Wikisource text does not have the facing
#: `שֶׁלֹּא עָשַֽׂנִי גּוֹי` either. Two derived witnesses missing the same thing is exactly
#: the failure that no comparison between them can see.
SUPPLIED: dict[int, tuple[tuple[str, str], ...]] = {
    16: ((
        "between day and night.",
        "between day and night.\n\nBlessed art thou, Lord our God, King of the universe, "
        "who hast not made me a heathen.",
    ),),
}

#: Settled on the image, page by page. Each is quoted in `readings/english_*.md`.
CORRECTIONS: dict[int, tuple[tuple[str, str], ...]] = {
    24: ((" what thou hast, promised us ", " what thou hast promised us "),),
    26: (("deal Kindly with us", "deal kindly with us"),),
    30: (("It is also said; Aaron shall burn", 'It is also said: “Aaron shall burn'),),
}

#: Places the transcription centres that the print does not. Printed 26 sets the Shema verse
#: and Barukh Shem as **ordinary indented paragraphs**, at the same indent as the body --
#: only the facing Hebrew page centres them. The `{{c|…}}` is the transcriber's reading of
#: the layout, so it is undone here before the centred lines are set aside as headings.
#: Column headings that the table flattening turns into ordinary paragraphs. They are
#: rubrics -- `Men say:` and `Women say:` over the two gendered blessings on printed 18 --
#: so they belong in `readings/` with the other rubrics and not in the running text.
RUBRICS: dict[int, tuple[str, ...]] = {
    18: ("Men say:", "Women say:"),
}

UNCENTRE: dict[int, tuple[str, ...]] = {
    26: (
        "Hear, O Israel, the Lord is our God, the Lord is One.",
        "Blessed be the name of his glorious majesty forever and ever.",
    ),
}

#: The transcription sets a hyphen in every verse range on every page; the print sets an
#: en dash on both sides of the book. Systematic, so it is a rule and not a list.
RANGE = re.compile(r"(\d+):(\d+)-(\d+)")

#: What the last `strip` call set aside, so the caller can print it.
DROPPED: list[str] = []


def _drop(text: str) -> str:
    text = " ".join(re.sub(r"'{2,}", "", text).split())
    if text:
        DROPPED.append(text)
    return "\n\n"


def _table(text: str) -> str:
    """Flatten a wiki table into paragraphs, keeping the cells and dropping the scaffolding.

    Printed 18 sets the two gendered blessings in side-by-side columns and the transcription
    renders that as a table. Left alone, `{|`, `|width=48%` and `|-` come through as words,
    and the column headings `Men say:` / `Women say:` -- which are rubrics -- come through as
    text. Cells are kept in source order, which on this page is men then women, and that is
    the order the print reads in: the men's column is on the right of the *Hebrew* page and
    the English page mirrors the placement.
    """
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("{|", "|}", "|-", "!")):
            continue
        if stripped.startswith("|"):
            # `|width=48% align=center| Men say:` -- the cell content follows the last `|`
            # that carries attributes; a bare `|` opens a cell with no attributes.
            cell = stripped[1:]
            if "|" in cell:
                cell = cell.split("|", 1)[1]
            if cell.strip():
                out.append("")
                out.append(cell.strip())
            continue
        out.append(line)
    return "\n".join(out)


_NOINCLUDE = re.compile(r"<noinclude>.*?</noinclude>", re.S)
_REF = re.compile(r"<ref>.*?</ref>", re.S)
_BR = re.compile(r"<br\s*/?>")


def strip(text: str) -> str:
    text = _NOINCLUDE.sub(" ", text)
    text = _table(text)
    text = _REF.sub("", text)          # the apparatus is not the page's running text
    text = _BR.sub("\n\n", text)       # the transcription's `<br>` is a paragraph break
    # A `{{c|…}}` line is a heading or a citation -- read into `readings/`, not here.
    for _ in range(4):
        text = re.sub(r"\{\{(?:c|sc)\|([^{}]*)\}\}", lambda m: _drop(m[1]), text)
    text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    text = re.sub(r"'{2,}", "", text)  # wiki italics
    text = re.sub(r"<[^>]+>", " ", text)
    # A `:`, `*`, `#` or `;` opening a line is MediaWiki's indent and list markup. Left in
    # it rides on the first word of every verse line -- `:He` against `He` -- exactly as it
    # did in the Hebrew slice until `transcription.LIST_MARKER` was added.
    text = re.sub(r"^[:*#;]+", "", text, flags=re.M)
    paragraphs = [" ".join(p.split()) for p in text.split("\n\n")]
    return "\n\n".join(p for p in paragraphs if p)


def page(printed: int) -> str:
    DROPPED.clear()
    raw = (ST / "en" / "text" / f"{printed + 25:03d}.txt").read_text(encoding="utf-8")
    for phrase in UNCENTRE.get(printed, ()):
        wrapped = "{{c|" + phrase + "}}"
        if wrapped not in raw:
            raise SystemExit(f"page {printed}: not centred any more: {phrase!r}")
        raw = raw.replace(wrapped, phrase)
    text = strip(raw)
    for rubric in RUBRICS.get(printed, ()):
        if rubric not in text:
            raise SystemExit(f"page {printed}: rubric not found: {rubric!r}")
        text = text.replace(rubric, "", 1)
        DROPPED.append(rubric)
    for was, now in SUPPLIED.get(printed, ()) + CORRECTIONS.get(printed, ()):
        if was not in text:
            raise SystemExit(f"page {printed}: correction no longer applies: {was!r}")
        text = text.replace(was, now)
    return RANGE.sub(lambda m: f"{m[1]}:{m[2]}–{m[3]}", text)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for printed in range(4, 49, 2):
        text = page(printed)
        (OUT / f"{printed}.txt").write_text(text + "\n", encoding="utf-8")
        print(f"{printed}: {len(text.split())} words"
              + ("; set aside: " + " | ".join(DROPPED) if DROPPED else ""))
