"""Birnbaum's own footnotes, as a standoff apparatus.

The print carries two apparatuses, and they are different things:

*Commentary* sits at the foot of the Hebrew page, keyed by a Hebrew catchword set in
bold, and is set across the opening -- a note begun under a Hebrew page finishes under
the facing English one. Birnbaum describes the keying himself in his introduction: each
note begins with a Hebrew catchword so that a reader can find the explanation he seeks.

*Scripture citations* are numbered, keyed to superscript numerals, and are printed on the
English pages only -- again his own statement, and confirmed by every page read so far.

Both are `tei:note` in one `tei:standOff`, told apart by `@type`. A commentary note
carries the catchword in `tei:label`; a citation carries the printed numeral in `@n`.

Two decisions worth stating, because neither is obvious:

**The apparatus is realised in the English project only.** The commentary is English
prose about Hebrew words, like Birnbaum's introduction, and the same reasoning applies:
English-only material is realised on the English side and the Hebrew reaches it by
resolution rather than by duplication. What is given up is that the commentary begins
physically under the Hebrew page in the print and will not in the rendered PDF.

**A note carries no URN of its own.** `urn:x-opensiddur:notes:` exists for swapping one
edition's apparatus for another's, and there is exactly one Birnbaum apparatus. A note is
not a text: it is addressed by what it annotates, and `@target` says that already.

The printed numeral in `@n` is evidence, not an instruction to the renderer. Birnbaum
restarts at 1 on every page; a PDF repaginates, so the renderer draws its own series.

**A third keying turns up in Rabbi Ishmael's rules.** Under printed 41 the commentary block
carries a centred sub-heading, `ILLUSTRATIONS`, and then a numbered list of worked examples
running 1 to 13 -- one per rule, numbered to match the rules themselves. There is no mark in
the text and no catchword: the *number* is the key. Those are `commentary` with an `@n` and
no `tei:label`.

**A note carries block content.** Printed 41's is the largest in the book: prose, a
sub-heading, a numbered list with lettered sub-items, and a reference to another page. Any
assumption that a note is a paragraph of inline prose is contradicted by that one page.
"""
#: What the apparatus is attached to, per unit. `target` is a `@corresp` URN that the
#: text already carries -- never an `#id`, which `refdb` resolves only inside one file.
#:
#: The notes themselves are in `notes_data`, generated from the English transcription and
#: keyed to URNs by matching against the authored text -- see
#: `specs/birnbaum_scan/extract_notes.py`. They were written out by hand here while there
#: was one of them; there are eighty-four.
from .common import AGG, SERVICE, feature
from .notes_data import AMIDAH_NOTES, BIRCHOT_NOTES, YELADIM_NOTES  # noqa: F401

# This essay concerns the nineteen-blessing weekday Amidah. Its opening is
# shared by the Sabbath, festival and Rosh Hodesh Musaf Amidahs too.
WEEKDAY_AMIDAH_NOTE = '<j:none>' + feature(AGG, 'shabbat') + feature(AGG, 'yom-tov') + feature(SERVICE, 'musaf') + '</j:none>'
def amidah_note(entry):
    if entry.get('lemma') == 'שמונה עשרה':
        return dict(entry, condition=WEEKDAY_AMIDAH_NOTE)
    if entry.get('lemma') == 'מודים דרבנן':
        # The ordinal applies only to the nineteen-blessing Amidah.
        ordinal = ('<j:conditional xml:id="modim_eighteenth">' + WEEKDAY_AMIDAH_NOTE
                   + '</j:conditional>eighteenth <j:endConditional target="#modim_eighteenth"/>')
        return dict(entry, paras=[dict(para, text=para['text'].replace('eighteenth ', ordinal))
                                  for para in entry['paras']])
    return entry


AMIDAH_NOTES = [amidah_note(entry) for entry in AMIDAH_NOTES]


def note(entry: dict, *, indent: int = 4) -> str:
    """One `tei:note` in the apparatus, as the block content a note actually carries."""
    pad = " " * indent
    attrs = [f'type="{entry["kind"]}"']
    if entry.get("n"):
        attrs.append(f'n="{entry["n"]}"')
    attrs.append(f'target="{entry["target"]}"')
    out = [f'{pad}<tei:note {" ".join(attrs)}>']
    if entry.get("condition"):
        out.append(f'{pad}  <j:condition>{entry["condition"]}</j:condition>')
    paras = entry["paras"]
    for index, para in enumerate(paras):
        rend = f' rend="{para["rend"]}"' if para.get("rend") else ""
        label = ""
        if index == 0 and entry.get("lemma"):
            # No space before the punctuation that follows a catchword: the print sets
            # `רבי ישמעאל בן אלישע, a contemporary of Rabbi Akiba`, comma tight.
            gap = "" if para["text"][:1] in ",.;:?!" else " "
            label = f'<tei:label xml:lang="he">{entry["lemma"]}</tei:label>{gap}'
        out.append(f'{pad}  <tei:p{rend}>{label}{para["text"]}</tei:p>')
    out.append(f"{pad}</tei:note>")
    return "\n".join(out)


def standoff(entries: list[dict], *, indent: int = 4) -> str:
    """The body of one apparatus file."""
    return "\n".join(note(e, indent=indent) for e in entries)
