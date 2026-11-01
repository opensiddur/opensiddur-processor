# -*- coding: utf-8 -*-
"""Birnbaum's English for Mah Tovu and the tallith order, from printed pages 4 and 6.

Same URNs as the Hebrew, which is what aligns them. The one place the two sides are
shaped differently is Mah Tovu, and that difference is the reason the parting is named:
the Hebrew page sets the whole catena as one paragraph and this page sets it as two, so
each side keeps its own paragraphing and the two halves carry the URNs that pair them.

See `he_tallith` for the argument. Here it means two ``tei:p`` where the Hebrew has two
milestone ranges inside one; both sides use the same milestone units.
"""
import functools

from .common import PRAYER
from . import common

pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

U = PRAYER

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug,
                        first=first, last=last, body=body))


def d(urn, *paras, indent=8):
    pad = " " * indent
    inner = "\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\n{inner}\n{pad}</tei:div>'


prayer("birkhot_mah_tovu", "Mah Tovu", "mah_tovu", 4, 4, "\n".join([
    f'        <tei:div corresp="{U}mah_tovu">',
    f'          <tei:p><tei:milestone unit="prayer-part" corresp="{U}mah_tovu/mah_tovu"/>How goodly are your tents, '
    'O Jacob, your habitations, O Israel!<tei:milestone unit="prayer-part"/></tei:p>',
    f'          <tei:p><tei:milestone unit="prayer-part" corresp="{U}mah_tovu/varani"/>By thy abundant grace I enter thy '
    'house; I worship before thy holy shrine with reverence. O Lord, I love thy abode, '
    'the place where thy glory dwells. I will worship and bow down; I will bend the knee '
    'before the Lord my Maker. I offer my prayer to thee, O Lord, at a time of grace. '
    'O God, in thy abundant kindness, answer me with thy saving truth.<tei:milestone unit="prayer-part"/></tei:p>',
    '        </tei:div>']))

prayer("tallith_barkhi_nafshi", "Bless the Lord, O my soul", "tallith/barkhi_nafshi",
       4, 4,
       d(U + "tallith/barkhi_nafshi",
         "Bless the Lord, O my soul! Lord my God, thou art very great; thou art robed in "
         "glory and majesty. Thou wrappest thyself in light as in a garment; thou "
         "spreadest the heavens like a curtain."))

prayer("tallith_hineni_mitattef", "I am enwrapping myself", "tallith/hineni_mitattef",
       4, 4,
       d(U + "tallith/hineni_mitattef",
         "I am enwrapping myself in the fringed garment in order to fulfill the command "
         "of my Creator, as it is written in the Torah: “They shall make fringes for "
         "themselves on the corners of their garments throughout their generations.” "
         "Even as I cover myself with the tallith in this world, so may my soul deserve "
         "to be robed in a beautiful garment in the world to come, in Paradise. Amen."))

prayer("tallith_lehitattef", "Blessing over the tallith", "tallith/lehitattef", 6, 6,
       d(U + "tallith/lehitattef",
         f"{pb(6)}Blessed art thou, Lord our God, King of the universe, who hast "
         "sanctified us with thy commandments, and commanded us to enwrap ourselves in "
         "the fringed garment."))

prayer("tallith_mah_yaqar", "How precious is thy kindness", "tallith/mah_yaqar", 6, 6,
       d(U + "tallith/mah_yaqar",
         "How precious is thy kindness, O God! The children of men take refuge in the "
         "shadow of thy wings. They have their fill of the choice food of thy house, and "
         "thou givest them drink of thy stream of delights. For with thee is the "
         "fountain of life; by thy light do we see light. Continue thy kindness to those "
         "who know thee, and thy righteousness to the upright in heart."))

prayer("tallith_yehi_ratzon", "May it be thy will", "tallith/yehi_ratzon", 6, 6,
       d(U + "tallith/yehi_ratzon",
         "May it be thy will, Lord our God and God of our fathers, that my observance of "
         "this precept of tsitsith be considered as if I fulfilled it with all its "
         "particulars, details and implications, together with the six hundred and "
         "thirteen precepts that are related to it. Amen."))
