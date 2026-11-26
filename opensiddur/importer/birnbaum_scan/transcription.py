"""Resolve the Hebrew Wikisource foundation text to the reading *this* book prints.

The Wikisource edition is not a reproduction of the 1949 print: it renders Birnbaum's
English rubrics into Hebrew, adds Eretz Yisrael customs, and corrects the text. Where its
editors knew the print differs from what they set, they said so in a `{{נוסח}}` template
rather than silently choosing -- so the template is the most useful thing in the file, and
stripping it throws away exactly the evidence the comparison is for.

Four conventions are in use, and one of them inverts:

    {{נוסח|X|בירנבוים=Y}}                 X is the default, Y is what Birnbaum prints
    {{נוסח|X|=מסורה|בירנבוים=Y}}           X is the Masorah's, Y is what Birnbaum prints
    {{נוסח|X|=בירנבוים|אחרים=Y}}           *X* is what Birnbaum prints, Y is everyone else
    {{נוסח|X|=בירנבוים ועבו"י|אחרים=Y}}     likewise, X, shared with another edition

So a `בירנבוים=` parameter cannot simply be preferred: where the unnamed attribution
already credits the first positional to Birnbaum, that positional is the reading and
`אחרים=` is the variant to discard.

A `בירנבוים=` value is not always a reading. One in the morning blessings is a sentence
about how he sets two Torah portions, with no word to substitute. A value that does not
look like a short run of pointed Hebrew is treated as a comment: the positional stands,
and the comment is reported so the reading can record it.
"""
import re
from dataclasses import dataclass, field

#: The template, and the attribution that names Birnbaum rather than contrasting with him.
#:
#: Matched by scanning for balanced braces rather than with a regex: a template body can
#: hold a template of its own -- the Kaddish sets
#: `{{נוסח|בְּאַתְרָא [{{ק|בארץ:}} קַדִּישָׁא]|בירנבוים=בְּאַתְרָא}}` -- and a non-greedy
#: `\}\}` closes on the *inner* one, taking half a word as the positional and throwing the
#: `בירנבוים=` reading away. It fails silently, leaving a stray bracket in the slice.
TEMPLATE_OPEN = "{{נוסח|"
BIRNBAUM = "בירנבוים"


def _templates(text: str):
    """Every `{{נוסח|…}}`, as `(start, end, body)`, closing on its own braces."""
    start = text.find(TEMPLATE_OPEN)
    while start != -1:
        depth, i = 0, start
        while i < len(text):
            if text.startswith("{{", i):
                depth += 1
                i += 2
            elif text.startswith("}}", i):
                depth -= 1
                i += 2
                if depth == 0:
                    yield start, i, text[start + len(TEMPLATE_OPEN) : i - 2]
                    break
            else:
                i += 1
        else:  # unclosed; nothing more to find
            return
        start = text.find(TEMPLATE_OPEN, i)

#: A value is a reading if it is short and made of Hebrew letters, points and separators.
READING = re.compile(r"^[֐-׿\u200f\s/\[\]|,.;׳״־-]+$")
MAX_READING_WORDS = 4


@dataclass
class Resolution:
    """The resolved text, and what was set aside to get it."""
    text: str
    comments: list[str] = field(default_factory=list)
    substitutions: list[tuple[str, str]] = field(default_factory=list)
    #: Spans a page transcludes that its foundation page does not define.
    missing: list[tuple[str, str]] = field(default_factory=list)


def _split_params(body: str) -> tuple[str, dict[str, str], str]:
    """A template body into its first positional, its named parameters, and the
    unnamed attribution written as a bare `=value`."""
    parts = body.split("|")
    positional = parts[0].strip()
    named: dict[str, str] = {}
    attribution = ""
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if not key:
            attribution = value
        else:
            named[key] = value
    return positional, named, attribution


def _is_reading(value: str, positional: str = "") -> bool:
    """Whether a parameter is a variant reading or a note about one.

    A variant replaces the text it is given against, so it is about as long. The word
    cap alone is not enough: a four-word Hebrew sentence saying a full stop is missing
    passed it, and was substituted into the middle of a blessing as though the print
    said it.
    """
    if not value or not READING.match(value):
        return False
    if len(value.split()) > MAX_READING_WORDS:
        return False
    if positional and len(value.split()) > len(positional.split()) + 1:
        return False
    return True


def resolve(text: str) -> Resolution:
    """Replace every `{{נוסח}}` with the reading the 1949 print carries."""
    result = Resolution(text="")

    def _one(body: str) -> str:
        positional, named, attribution = _split_params(body)
        # The attribution credits the positional to Birnbaum: it is already the reading.
        if BIRNBAUM in attribution:
            return positional
        value = named.get(BIRNBAUM)
        if value is None:
            return positional
        if not _is_reading(value, positional):
            result.comments.append(value)
            return positional
        if value != positional:
            result.substitutions.append((positional, value))
        return value

    pieces, last = [], 0
    for start, end, body in _templates(text):
        pieces.append(text[last:start])
        pieces.append(_one(body))
        last = end
    pieces.append(text[last:])
    result.text = "".join(pieces)
    return result


def strip_markup(text: str) -> str:
    """What is left after the variants are resolved: plain pointed Hebrew.

    `compare` tokenises whatever it is given and would count a stray brace as a word, so
    nothing may survive here but the text and its separators.
    """
    # Removed markup leaves a space, never nothing. A `<קטע סוף=.../>` between two words
    # is a boundary, and deleting it outright joins them into one token -- which `compare`
    # then reports as two consonantal differences, and the misalignment cascades through
    # everything after it. One missing space produced twenty-five phantom differences on
    # printed page 11 before this was found.
    text = re.sub(r"\{\{#קטע:[^}]*\}\}", " ", text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"'{2,}", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def section(page_text: str, name: str) -> str | None:
    """One named `<קטע>` span out of a foundation page.

    Spans nest: `אתה הוא עד שלא נברא הכל` wraps `... א` and `... ב`, with the reader's
    rubric between them. Closing on the first `<קטע סוף=` of any name would end the outer
    span at the inner one's close -- half the passage, with the missing half showing up in
    `compare` as a word-count gap and a wall of consonantal differences rather than as a
    slice error. Close only on the end tag that names this span.
    """
    m = re.search(
        r"<קטע התחלה=" + re.escape(name) + r"/>(.*?)<קטע סוף=" + re.escape(name) + r"/>",
        page_text,
        re.S,
    )
    return m.group(1) if m else None


#: A printed page transcludes foundation spans: `{{#קטע:<path>/<page>|<span>}}`.
TRANSCLUSION = re.compile(r"\{\{#קטע:[^|}]*?/([^/|}]+)\|([^|}]+)\}\}")

#: Span names say what a span is, and three kinds are not the print's Hebrew words.
#:
#: `הוראה` is a rubric: the edition renders Birnbaum's *English* rubrics into Hebrew, so
#: there is nothing on his Hebrew page to compare one against.
#:
#: `כותרת` is a heading and `מקור` a scripture citation, and he prints **both** in the
#: Hebrew column -- the korbanot pages set `שמות ל, יז-כא` over the passage in small type,
#: and the Akedah on printed page 19 carries `בראשית כב, א-יט` the same way. They are left
#: out all the same, because a heading and a citation are read off the image into
#: `readings/` and never into `hebrew/`: including them on the transcription side alone
#: would report every one of them as a word the reading had dropped.
#:
#: Both sides of the comparison must hold the same kind of thing or the tally is noise.
SKIP_PREFIXES = ("כותרת ", "הוראה ", "מקור ")
SKIP_SUFFIXES = (" מקור", " מקורות")


#: Spans a printed page transcludes under a name its foundation page no longer defines.
#:
#: The page files and the foundation pages were snapshotted at different revisions, so a
#: span renamed or a typo fixed on one side reads here as a missing span. Both are recorded
#: rather than guessed: the first is a rename, the second a typo corrected in the
#: foundation page and left standing in the page that transcludes it.
RENAMED_SPANS = {
    ("קידוש והבדלה וסעודות שבת ויום טוב", "ברכת המבדיל בין קודש לקודש"):
        "ברכת המבדיל בין קודש לקודש הכל",
    ("קריאת התורה", "ואתם הדבקים"): "ואתם הדבקים מילים",
    ("ברכות השחר וקרבנות", "הוראה לתפילה פני שמתעטפים בטלית"): (
        "הוראה לתפילה לפני שמתעטפים בטלית"
    ),
}


def is_prayer_span(name: str) -> bool:
    """Whether a span name promises the print's own Hebrew words."""
    return not (name.startswith(SKIP_PREFIXES) or name.endswith(SKIP_SUFFIXES))


#: What the printed page does *not* transclude into the work.
#:
#: The page wrapper `{{סידור בירנבוים תפילה|` opens inside one `<noinclude>` and closes
#: inside another, so removing these regions is also what leaves the rest of the page with
#: balanced braces to evaluate.
NOINCLUDE = re.compile(r"<noinclude>.*?</noinclude>", re.S)

#: MediaWiki's list and indent markup, which is only markup at the start of a line.
LIST_MARKER = re.compile(r"^[:*#;]+")

#: Layout templates that wrap text which is part of the work: centring and two heading
#: sizes. Everything else -- the running head, the interwiki link, the "paragraph continues"
#: marker, and the rubric and citation wrappers -- is the edition's furniture and goes.
KEEP_WRAPPERS = ("מרכז", "ג", "גג")

#: An innermost template: one holding no braces of its own.
INNERMOST = re.compile(r"\{\{([^{}|]*)(?:\|([^{}]*))?\}\}")


def _evaluate_templates(text: str) -> str:
    """Collapse templates from the inside out, keeping what the work itself sets."""
    def _one(match: re.Match) -> str:
        name, body = match.group(1).strip(), match.group(2) or ""
        if name == "ש":  # an explicit line break
            return "\n"
        return body if name in KEEP_WRAPPERS else " "

    previous = None
    while previous != text:
        previous, text = text, INNERMOST.sub(_one, text)
    return text


def page_slice(page_text: str, load) -> Resolution:
    """Render one printed page of the edition from the foundation spans it transcludes.

    `load(foundation_page_name)` returns that foundation page's wikitext.

    The page is rendered rather than having its spans concatenated, because the text
    *between* two transclusions is part of the reading: printed page 1 joins five spans
    into one paragraph with `. ` between them, and a slicer that concatenated them would
    manufacture four paragraph breaks and lose four sentence-final periods -- reported
    afterwards as whitespace and vowel differences that are the slicer's own doing.
    """
    result = Resolution(text="")

    def _substitute(match: re.Match) -> str:
        foundation, name = match.group(1), match.group(2)
        if not is_prayer_span(name):
            return " "
        page = load(foundation)
        span = section(page, name)
        if span is None:
            renamed = RENAMED_SPANS.get((foundation, name))
            if renamed is not None:
                span = section(page, renamed)
        if span is None:
            # The page file and the foundation page were snapshotted at different
            # revisions, so a span was renamed or a typo in the name was fixed on one side
            # only. Record the gap; a slice with a hole in it is not a slice, and the
            # caller must not quietly write one.
            result.missing.append((foundation, name))
            return " "
        resolved = resolve(span)
        result.comments.extend(resolved.comments)
        result.substitutions.extend(resolved.substitutions)
        return resolved.text

    text = NOINCLUDE.sub(" ", page_text)
    text = TRANSCLUSION.sub(_substitute, text)
    text = _evaluate_templates(text)
    text = strip_markup(text)
    # `strip_markup` flattens runs of spaces but leaves the page's own line structure, so
    # the paragraphing the edition sets survives to be compared.
    #
    # A `:`, `*`, `#` or `;` opening a line is MediaWiki's list and indent markup, not text.
    # Rabbi Ishmael's thirteen rules are set as an indented list, and left in place the
    # marker rides on the first token of every rule -- `:א)` against `א)` -- so `compare`
    # reports thirteen differences that are the slicer's own punctuation.
    paragraphs = [
        " ".join(LIST_MARKER.sub("", line).split()) for line in text.split("\n")
    ]
    result.text = "\n".join(p for p in paragraphs).strip()
    result.text = re.sub(r"\n{3,}", "\n\n", result.text)
    return result


def _cli(argv: list[str] | None = None) -> int:
    """Write `transcription/{printed}.txt` for each printed page named.

    Doing this by hand is how printed page 19 lost a span and printed page 25 nearly lost
    one: the slice is a judgement about which foundation spans a page sets, and the page
    file already records that judgement. Read it from there.
    """
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description=_cli.__doc__)
    parser.add_argument("pages", type=int, nargs="+", help="Printed page numbers.")
    parser.add_argument(
        "--sourcetexts",
        type=Path,
        default=Path("sourcetexts"),
        help="Root of the sourcetexts checkout holding this book.",
    )
    parser.add_argument(
        "--scan-offset", type=int, default=25, help="scan leaf = printed page + this."
    )
    parser.add_argument("--stdout", action="store_true", help="Print instead of writing.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Write the slice even though a span it transcludes could not be found.",
    )
    args = parser.parse_args(argv)

    book = args.sourcetexts / "sources" / "birnbaum_siddur"
    foundation = book / "source" / "text" / "אשכנז" / "דפי יסוד"
    out_dir = book / "scan_reading" / "transcription"

    def load(name: str) -> str:
        return (foundation / f"{name}.txt").read_text(encoding="utf-8")

    status = 0
    for printed in args.pages:
        page_file = book / "text" / f"{printed + args.scan_offset:03d}.txt"
        sliced = page_slice(page_file.read_text(encoding="utf-8"), load)
        def report(message: str, printed=printed) -> None:
            print(f"{printed}: {message}", file=sys.stderr)

        for comment in sliced.comments:
            report(f"comment: {comment}")
        for was, now in sliced.substitutions:
            report(f"reads {now} where the edition sets {was}")
        for foundation_name, name in sliced.missing:
            report(f"MISSING SPAN {name!r} in {foundation_name!r}")
        if sliced.missing and not (args.stdout or args.allow_missing):
            status = 1
            report("not written -- the slice has a hole in it")
            continue
        if args.stdout:
            print(sliced.text)
        else:
            (out_dir / f"{printed}.txt").write_text(sliced.text + "\n", encoding="utf-8")
            report(f"{len(sliced.text.split())} words -> {out_dir}/{printed}.txt")
    return status


if __name__ == "__main__":
    raise SystemExit(_cli())
