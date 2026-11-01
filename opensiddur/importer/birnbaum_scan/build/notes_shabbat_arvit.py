"""Commentary and source notes printed 263–280 (before the home service)."""
from .notes_minchah import note
from .shabbat_arvit import ROOT, URNS
from .common import PRAYER

NOTES = [
 note(URNS['hashkivenu'], ', instead of the weekday ending <tei:foreign xml:lang="he">שומר עמו ישראל</tei:foreign>, is used to express the idea of peace which fills the Jewish home on Friday evening.',lemma='הפורש סכת שלום'),
 note(URNS['veshamru'], 'Exodus 31:16–17.',kind='source',n='1'),
 note(URNS['vaydaber'], 'Leviticus 23:44.',kind='source',n='2'),
 note(URNS['tiqu'], 'Psalm 81:4–5.',kind='source',n='3'),
 note(ROOT+'/amidah', 'is the name of the Sabbath <tei:hi rend="italic">Amidah</tei:hi>, because it contains only seven blessings. The first three and the last three are the same in all forms of the <tei:hi rend="italic">Amidah</tei:hi>, whereas the intermediary blessing varies in all four services of the Sabbath. The thirteen petitions of the weekday <tei:hi rend="italic">Shemoneh Esreh</tei:hi> are eliminated on the ground that no personal requests may be made during Sabbaths and festivals. When one recites these petitions, he is reminded of his failings and troubles, and on the days of rest one ought not to be sad but cheerful.',lemma='תפלת שבע'),
 note(URNS['attah']+'/text', 'appears in the ninth century <tei:hi rend="italic">Siddur</tei:hi> of Amram Gaon and in Maimonides’ text with slight variations.',lemma='אתה קדשת'),
 note(URNS['retzeh']+'/text', ', like the <tei:hi rend="italic">Kiddush</tei:hi>, ends with <tei:foreign xml:lang="he">מקדש השבת</tei:foreign>; on festivals, however, Israel is included in the formula <tei:foreign xml:lang="he">מקדש ישראל והזמנים</tei:foreign>. According to the Talmud (Pesaḥim 117b), Israel is mentioned in the phrase used on festivals because through Israel the festivals are sanctified, since the length of each month is fixed by Jewish authorities who thereby fix the dates of the festivals. The Sabbath, on the other hand, is permanently fixed and depends entirely on God.',lemma='רצה במנוחתנו'),
 note(URNS['vaykhulu'],'Genesis 2:1–3.',kind='source',n='1'),
 note(ROOT+'/after_amidah', ', considered an essential part of the service (Shabbath 119b), is repeated after the <tei:hi rend="italic">Amidah</tei:hi> because the <tei:hi rend="italic">Amidah</tei:hi> of festivals occurring on the Sabbath does not include this passage. Since <tei:foreign xml:lang="he">ויכלו</tei:foreign> has to be recited after the <tei:hi rend="italic">Amidah</tei:hi> when a festival occurs on the Sabbath, it has become the rule for all Sabbaths (Tosafoth, Pesaḥim 106a).',lemma='ויכלו'),
 note(PRAYER+'amidah/magen_avot', 'is termed <tei:foreign xml:lang="he">מעין שבע</tei:foreign> because it contains the substance of the seven blessings of the <tei:hi rend="italic">Amidah</tei:hi>. This abridged form of the <tei:hi rend="italic">Amidah</tei:hi> was originally added in order to prolong the service for the convenience of late-comers. The synagogues were often located outside the precincts of the city (since the rulers did not tolerate Jewish worship within the confines of their municipalities), and it was dangerous to walk home alone at night. By prolonging the Sabbath-eve service, which was far better attended than weekday services, the late-comers were given an opportunity to finish their prayers with the rest of the congregation (Rashi, Shabbath 24b; compare note on <tei:foreign xml:lang="he">במה מדליקין</tei:foreign>, page 251).',lemma='מגן אבות'),
 note(ROOT+'/kiddush', 'recited by the Reader in the synagogue has its origin in the period when strangers were given their Sabbath meal in a room adjoining the Synagogue. Abudarham, writing in Spain early in the fourteenth century, says: “As our predecessors have set up the rule, though for a reason which no longer exists, the rule remains unshaken.”',lemma='קידוש'),
 note(ROOT+'/kiddush/savri', 'is used here in the sense of “Gentlemen, attention!” It is intended to call attention to the blessing which is about to be pronounced over the wine so that those present may answer Amen. According to a midrashic source (Tanḥuma, <tei:hi rend="italic">Pekudé</tei:hi>), this phrase was originally used in the form of a question, namely: “Gentlemen, what is your opinion?” Is it safe to drink of this wine? The response was <tei:foreign xml:lang="he">לחיים</tei:foreign>!',lemma='סברי מרנן'),
]
# The remaining biblical footnotes (262, 266, 274, 278, 280) accompany shared
# passages and are already attached to their targets in earlier apparatus files.
# One source-number differs: p. 262 prints Jeremiah 31:11 rather than p. 196's
# 31:10. Preserve that printed correction at this service's own occurrence.
NOTES.append(note(ROOT+'/blessings_after_shema/emet_seal', 'Jeremiah 31:11.',kind='source',n='4'))

NOTES.append(note(ROOT+'/amidah/meditation', 'Psalms 60:7; 19:15.',kind='source',n='1'))
