"""Birnbaum's English of Adon Olam and Yigdal, read off printed pages 12 and 14.

Both poems are set in two columns on the Hebrew page and as two stacked lines
per verse line on the English one. Birnbaum's own footnote says ten lines and
thirteen lines, and both sides give exactly that, so the structure is not in
dispute between them and only the setting differs. Each `tei:l` holds a whole
line of verse on both sides; splitting on the Hebrew column or on the English
line break would give twice as many and contradict the book about itself.

This side heads both poems and numbers Yigdal's thirteen lines; the Hebrew page
does neither. The numerals are the print's own and are not part of the text, so
they are `@n` on the line rather than words in it, and only on this side.
"""
import functools

from . import common
from .common import POEM

pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

P = POEM

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=P + slug,
                        first=first, last=last, body=body))


def poem(urn, lines, *, indent=8, page_break_before=None):
    """A poem as a `tei:lg` of whole verse lines."""
    pad = " " * indent
    out = []
    for n, line in enumerate(lines):
        numbered = isinstance(line, (list, tuple))
        text = line[1] if numbered else line
        attr = ' n="%s"' % line[0] if numbered else ""
        brk = page_break_before(n) if page_break_before else ""
        out.append("%s    <tei:l%s>%s%s</tei:l>" % (pad, attr, brk, text))
    inner = "\n".join(out)
    return ('%s<tei:div corresp="%s">\n%s  <tei:lg>\n%s\n%s  </tei:lg>\n%s</tei:div>'
            % (pad, urn, pad, inner, pad, pad))


ADON_OLAM = ['He is the eternal Lord who reigned Before any being was created.', 'At the time when all was made by his will, He was at once acknowledged as King.', 'And at the end, when all shall cease to be, The revered God alone shall still be King.', 'He was, he is, and he shall be In glorious eternity.', 'He is One, and there is no other To compare to him, to place beside him.', 'He is without beginning, without end; Power and dominion belong to him.', 'He is my God, my living Redeemer, My stronghold in times of distress.', 'He is my guide and my refuge, My share of bliss the day I call.', 'To him I entrust my spirit When I sleep and when I wake.', 'As long as my soul is with my body The Lord is with me; I am not afraid.']

YIGDAL = [('1', 'Exalted and praised be the living God! He exists; his existence transcends time.'), ('2', 'He is One—there is no oneness like his; He’s unknowable—his Oneness is endless.'), ('3', 'He has no semblance—he is bodiless; Beyond comparison is his holiness.'), ('4', 'He preceded all that was created; The First he is though he never began.'), ('5', 'He is the eternal Lord; every creature Must declare his greatness and his kingship.'), ('6', 'His abundant prophecy he granted To the men of his choice and his glory.'), ('7', "Never has there arisen in Israel A prophet like Moses beholding God's image."), ('8', 'The Torah of truth God gave to his people Through his prophet, his own faithful servant.'), ('9', 'God will never amend, nor ever change His eternal Law for any other law.'), ('10', 'He inspects, he knows all our secret thoughts; He foresees the end of things at their birth.'), ('11', 'He rewards the godly man for his deeds; He repays the evil man for his evil.'), ('12', 'At time’s end he will send our Messiah To save all who wait for his final help.'), ('13', 'God, in his great mercy, will revive the dead; Blessed be his glorious name forever.')]

prayer("poem_adon_olam", 'Adon Olam', "adon_olam", 12, 12,
       poem(P + "adon_olam", ADON_OLAM))

#: Yigdal runs over the page turn: five lines on the first page, eight on the next.
prayer("poem_yigdal", 'Yigdal', "yigdal", 12, 14,
       poem(P + "yigdal", YIGDAL,
            page_break_before=lambda n: pb(14) if n == 5 else ""))
