"""New commentary on the Sabbath morning Amidah, printed 352 and 354."""
from .notes_minchah import note
from .shabbat_amidah import URNS, ROOT
NOTES = [
    note(URNS['mimeqomekha'], 'is included in the weekday <tei:hi rend="italic">Kedushah</tei:hi> in the <tei:hi rend="italic">Siddur</tei:hi> of Amram Gaon with some variations: <tei:foreign xml:lang="he">תופיע ותושיענו ... בקרוב בימינו ובחיינו תשכן ...</tei:foreign>',lemma='ממקומך מלכנו'),
    note(URNS['yismach'], 'alludes to the talmudic statement that God said to Moses: “I have a precious gift in my treasure house, called the Sabbath, and I desire to give it to Israel” (Shabbath 10b).',lemma='ישמח משה'),
    note(URNS['yismach'], 'refers to Numbers 12:7 (“Moses my servant, so faithful in all my household”).',lemma='עבד נאמן קראת לו'),
]

# The shared meditation text excludes its old occurrence-level apparatus.
NOTES.append(note(ROOT+'/meditation', 'Psalms 60:7; 19:15.', kind='source', n='1'))
