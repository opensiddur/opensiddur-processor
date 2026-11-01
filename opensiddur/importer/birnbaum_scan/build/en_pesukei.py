# -*- coding: utf-8 -*-
"""Weekday opening and verses of praise, printed 50–58, ending before Ashrei.
The new biblical passages are built by pesukei_passages; the preceding opening
remains separate from the wrapper that begins at Hareni mezamen.
"""
import functools
from . import common
from .common import PRAYER
from .he_prayers import d
pb = functools.partial(common.pb, sigil=common.SIGIL_PESUKEI)
U = PRAYER
PRAYERS = []

def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug,
                        first=first, last=last, body=body))

prayer('mizmor_shir_chanukat_habayit', 'A psalm, a song', 'mizmor_shir_chanukat_habayit', 50, 50,
    "\n".join([f'<tei:div corresp="{U}mizmor_shir_chanukat_habayit">',
        '<tei:head xml:lang="en">Psalm 30</tei:head>',
        '<tei:div corresp="urn:x-opensiddur:text:bible:psalms/30">',
        d(U + "mizmor_shir_chanukat_habayit/aromimkha", f'{pb(50)}' + 'A psalm, a song for the dedication of the house; by David.',
          (
            'I extol thee, O Lord, for thou hast lifted me, and hast not let my foes '
            'rejoice over me. Lord my God, I cried to thee, and thou didst heal me. O '
            'Lord, thou hast lifted me up from the grave; thou hast let me live, that I '
            'should not go down to the pit. Sing to the Lord, you who are godly, and give'
            ' thanks to his holy name. For his anger only lasts a moment, but his favor '
            'lasts a lifetime; weeping may lodge with us at evening, but in the morning '
            'there are shouts of joy. I thought in my security I never would be shaken. O'
            ' Lord, by thy favor thou hadst established my mountain as a stronghold; but '
            'when thy favor was withdrawn, I was dismayed. To thee, O Lord, I called; I '
            'appealed to my God: “What profit would my blood be, if I went down to the '
            'grave? Will the dust praise thee? Will it declare thy faithfulness? Hear, O '
            'Lord, and be gracious to me; Lord, be thou my helper.” Thou hast changed my '
            'mourning into dancing; thou hast put off my sackcloth and girded me with '
            'joy;')),
        d(U + "mizmor_shir_chanukat_habayit/lemaan", 'so that my soul may praise thee, and not be silent. Lord my God, I will thank thee forever.'),
        "</tei:div></tei:div>"]))

prayer('kaddish_yatom', 'Mourners’ Kaddish', 'kaddish/yatom', 50, 52,
    "\n".join([f'<tei:div corresp="{U}kaddish/yatom">',
      f'<j:transclude type="external" target="{U}kaddish/yitgaddal"/>',
      f'<j:transclude type="external" target="{U}kaddish/yehe_shemeh"/>',
      f'<j:transclude type="external" target="{U}kaddish/yitbarakh"/>',
      d(U + "kaddish/yatom/yehe_shelama",
      f'{pb(52)}' + 'May there be abundant peace from heaven, and life, for us and for all Israel; and say, Amen.'),
      d(U + "kaddish/yatom/oseh_shalom", 'He who creates peace in his celestial heights, may he create peace for us and for all Israel; and say, Amen.'),
      "</tei:div>"]))

# An explicit empty corresponding position, not an invented English translation.
# Without it the sequence alignment pairs the next English prayer with Hareni.
prayer('hareini_mezammen', 'Hareni mezamen (not translated in the print)',
       'hareini_mezammen', 52, 52,
       f'<tei:div corresp="{U}hareini_mezammen"><!-- No English text printed. --></tei:div>')

prayer('barukh_sheamar', 'Blessed be he who spoke', 'pesuqei_dezimrah/barukh_sheamar', 52, 52,
    "\n".join([f'<tei:div corresp="{U}pesuqei_dezimrah/barukh_sheamar">',
        d(U + "pesuqei_dezimrah/barukh_sheamar/barukh", (
            'Blessed be he who spoke, and the world came into being; blessed be he. '
            'Blessed be he who created the universe. Blessed be he who says and performs.'
            ' Blessed be he who decrees and fulfills. Blessed be he who has mercy on the '
            'world. Blessed be he who has mercy on all creatures. Blessed be he who '
            'grants a fair reward to those who revere him. Blessed be he who lives '
            'forever and exists eternally. Blessed be he who redeems and saves; blessed '
            'be his name. Blessed art thou, Lord our God, King of the universe, O God, '
            'merciful Father, who art praised by the mouth of thy people, lauded and '
            'glorified by the tongue of thy faithful servants. With the songs of thy '
            'servant David will we praise thee, Lord our God; with his hymns and psalms '
            'will we exalt, extol and glorify thee. We will call upon thy name and '
            'proclaim thee King, our King, our God.')),
        d(U + "pesuqei_dezimrah/barukh_sheamar/yachid", (
            'Thou who art One, the life of the universe, O King, praised and glorified be'
            ' thy great name forever and ever. Blessed art thou, O Lord, King extolled '
            'with hymns of praise.')),
        "</tei:div>"]))

# Continuing the scan through the paragraph before Ashrei.
from .pesukei_passages import prayers
PRAYERS += prayers("en")

from .pesukei_completion import prayers as completion_prayers
PRAYERS += completion_prayers("en")
