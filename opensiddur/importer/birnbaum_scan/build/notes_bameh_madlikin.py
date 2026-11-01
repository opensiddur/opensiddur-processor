"""Commentary and source footnotes read from printed 251–256."""
from .notes_minchah import note
from .bameh_madlikin import MISHNAH, TALMUD

NOTES = [
 note(MISHNAH, 'was inserted during the geonic period. Various reasons are given for the recital of this chapter from the Mishnah, which deals with the oils and wicks appropriate for the Sabbath lights. Rashi in his <tei:hi rend="italic">Siddur</tei:hi> (page 243) says that this chapter is recited <tei:hi rend="italic">after</tei:hi> the Sabbath eve service so as to enable the late-comers to complete their prayers and leave the synagogue together with the rest of the congregation. Accordingly, this chapter is omitted on festival occasions when late-coming is not likely to happen. Rabbi Isaiah Horowitz and Rabbi Jacob Emden, in their respective editions of the <tei:hi rend="italic">Siddur</tei:hi>, are of the opinion that <tei:hi rend="italic">Bammeh Madlikin</tei:hi> is to be recited before <tei:hi rend="italic">Kabbalath Shabbath</tei:hi>.', lemma='במה מדליקין'),
 note(MISHNAH+'/1', 'and the other unfamiliar terms are discussed and explained in the <tei:hi rend="italic">Gemara</tei:hi> (Shabbath 20b).', lemma='לכש, חסן, כלך'),
 note(MISHNAH+'/1', 'oil of consecrated <tei:hi rend="italic">terumah</tei:hi> that has been defiled. It is called “oil for burning” because of one’s duty to burn and destroy defiled <tei:hi rend="italic">terumah</tei:hi>. <tei:foreign xml:lang="he">שמן שרפה</tei:foreign> must not be used for the Sabbath lights, for fear that one may tilt the lamp to accelerate the burning of the oil.', lemma='שמן שרפה'),
 note(MISHNAH+'/3', 'is classed among trees in Joshua 2:6 (<tei:foreign xml:lang="he">פשתי העץ</tei:foreign>). It contracts ritual uncleanness, though the other materials originating from trees do not.', lemma='פשתן'),
 note(MISHNAH+'/4', 'for fear that one may draw oil from the eggshell and thus cause the light to go out sooner. The same rule applies even to a shell made of clay, though the oil it contains becomes loathsome and useless as food.', lemma='לא יקוב...'),
 note(MISHNAH+'/5', 'refers to idolators, like the Persians, who permitted no lights to burn on certain nights except in their temples (Rashi).', lemma='גוים'),
 note(MISHNAH+'/5', '(“he is not culpable”) implies that it is actually forbidden.', lemma='פטור'),
 note(MISHNAH+'/7', ', which renders permissible the carrying of objects on the Sabbath from one household to another, consists of food placed in a room accessible to all inhabitants of a court or a town. Since each of the householders contributes his share to it, the <tei:hi rend="italic">eruv</tei:hi> (“mixture”) symbolically turns all of them into one household.', lemma='עירוב'),
 note(MISHNAH+'/7', ', the act of purifying utensils from their defilement, renders them fit for use; hence it is forbidden work on Friday at twilight.', lemma='טבילת כלים'),
 note(MISHNAH+'/7', ', produce concerning which there is a doubt as to whether the rules relating to the priestly and Levitical dues were strictly observed, may be tithed at twilight, because the probability is that the tithes have already been set apart, so that this tithing does not really make it fit for use.', lemma='דמאי'),
 note(TALMUD+'/al_tiqra', 'is not intended to indicate a variant in the text. <tei:foreign xml:lang="he">בניך–בוניך</tei:foreign> is a mere play on words, designed to attract the attention to the great significance of peace.', lemma='אל תקרא'),
 note(TALMUD+'/isaiah_54_13', '<tei:hi rend="italic">Isaiah</tei:hi> 54:13.', kind='source', n='1'),
 note(TALMUD+'/psalms_29_11', '<tei:hi rend="italic">Psalms</tei:hi> 119:165; 122:7–9; 29:11.', kind='source', n='1'),
]

# One commentary occurrence per target, retaining each printed paragraph and lemma.
_grouped = {}
for entry in NOTES:
    key = (entry['target'], entry['kind'])
    if key not in _grouped:
        _grouped[key] = dict(entry, lemma='', paras=[])
    for para in entry['paras']:
        prefix = ('<tei:label xml:lang="he">'+entry['lemma']+'</tei:label> ') if entry['lemma'] else ''
        _grouped[key]['paras'].append(dict(text=prefix+para['text']))
NOTES = list(_grouped.values())
