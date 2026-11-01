"""All commentary and citations before Ashrei on printed 119–128."""
from .torah import ROOT, URNS, BIBLE, anchor
from .torah_data import PASSAGES

NOTES = [
    dict(kind='commentary', target=ROOT, lemma='קריאת התורה', paras=[dict(text=(
        'on Mondays and Thursdays was instituted by Ezra, according to tradition, in order not to let three days go by without the instruction of the Torah. Originally, the persons called to the Torah read the passages apportioned to them. This custom was abandoned in order not to embarrass those who lacked proper training.'
    ))]),
    dict(kind='commentary', target=URNS['berikh_shemeh'] + '/berikh', lemma='בריך שמיה', paras=[dict(text=(
        'is taken from the <tei:hi rend="italic">Zohar</tei:hi>, the fundamental book of <tei:hi rend="italic">Kabbalah</tei:hi>, which was first made known in the thirteenth century and ascribed to Rabbi Simeon ben Yoḥai of the second century. The <tei:hi rend="italic">Zohar</tei:hi> introduces this inspiring and uplifting prayer as follows: “When the Torah is taken out to be read before the congregation, the heavenly gates of mercy are opened and the divine love is aroused; therefore one should recite: <tei:foreign xml:lang="he">בריך הוא</tei:foreign> . . .” The term <tei:foreign xml:lang="he">בר אלהין</tei:foreign> (“angel”) is found in Daniel 3:25.'
    ))]),
    dict(kind='commentary', target=URNS['hagomel'] + '/blessing', lemma='ברכת הגומל', paras=[dict(text=(
        ', known as “gomel benshen,” is derived from Berakhoth 54b, where it is said that four classes of men should offer thanks: 1) those who have made a voyage by sea, 2) or a journey through the desert, 3) or have recovered from a severe illness, 4) or have been released from prison.'
    ))]),
]

# Keep the edition's printed references, including its Numbers 10:35–36
# reference at the opening, even though only verse 35 occurs there.
for key, row, number, citation in (
    ('vayehi_binsoa', 'vayehi', '1', 'Numbers 10:35–36.'),
    ('vayehi_binsoa', 'ki_mitziyyon', '2', 'Isaiah 2:3.'),
    ('gaddelu', 'gaddelu', '1', 'Psalm 34:4.'),
    ('lekha_adonai', 'lekha', '2', 'I Chronicles 29:11.'),
    ('lekha_adonai', 'romemu_hadom', '3', 'Psalm 99:5, 9.'),
    ('vetiggaleh', 'torat', '4', 'Psalms 19:8–9; 29:11; 18:31.'),
    ('veattem', 'veattem', '5', 'Deuteronomy 4:4.'),
    ('vezot_hatorah', 'vezot', '1', 'Deuteronomy 4:44; Numbers 9:23.'),
    ('vezot_hatorah', 'etz', '2', 'Proverbs 3:18, 17, 16; Isaiah 42:21.'),
    ('yehalelu', 'reader', '1', 'Psalm 148:13–14.'),
    ('uvnucho', 'uvnucho', '2', 'Numbers 10:36; Psalm 132:8–10; Proverbs 4:2; 3:18, 17; Lamentations 5:21.'),
):
    source = next(r[1] for r in PASSAGES[key]['rows'] if r[0] == row)
    NOTES.append(dict(kind='citation', target=anchor(key, row, source), n=number,
                      paras=[dict(text=citation)]))
