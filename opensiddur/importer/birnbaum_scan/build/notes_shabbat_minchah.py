"""Commentary read from printed 439–476, including the winter Psalms."""
from .notes_minchah import note
from .shabbat_minchah import ROOT, ATAH, BIBLE

NOTES = [
 note(ROOT+'/uva_letziyyon','is postponed till Minḥah on Sabbaths and festivals. The reason is explained on page 131.',lemma='ובא לציון'),
 note(ROOT+'/opening_kaddish','is said between Rosh Hashanah and Yom Kippur.',lemma='לעילא לעילא'),
 note(ATAH,'is based on Zechariah 14:9; I Chronicles 17:21. The <tei:hi rend="italic">Siddur</tei:hi> of Amram Gaon records the following variant in use during the ninth century: <tei:foreign xml:lang="he">הנח לנו ה׳ אלהינו כי אתה אבינו... ואל תהי צרה ויגון ביום מנוחתנו, מנוחת אהבה ונדבה, מנוחת אמת ואמונה</tei:foreign>.',lemma='אתה אחד ... בארץ'),
 note(ATAH,'According to midrashic literature the patriarchs observed the Sabbath and fulfilled all the commands that were revealed later. The children of Abraham and of Isaac are not mentioned because Ishmael and Esau are not credited with the observance of the Sabbath.',lemma='יעקב ובניו ינוחו'),
 note(ROOT+'/amidah/modim','is based on Psalms 79:13 and 55:18, namely: <tei:foreign xml:lang="he">נודה לך לעולם, לדור ודור נספר תהלתך</tei:foreign> and <tei:foreign xml:lang="he">ערב ובקר וצהרים אשיחה</tei:foreign>.',lemma='מודים'),
 note(ROOT+'/amidah/modim_derabbanan','is a composite of variants suggested by several rabbis of the Talmud (Sotah 40a).',lemma='מודים דרבנן'),
 note(ROOT+'/amidah/chanukah','the leader of the Maccabean revolt against the Syrians, was the father of Simon who became High Priest in 141 before the common era. Hence, it is suggested that the epithet <tei:foreign xml:lang="he">כהן גדול</tei:foreign> refers to that fact. According to Sofrim 20:8, <tei:foreign xml:lang="he">מתתיהו</tei:foreign> and <tei:foreign xml:lang="he">חשמונאי</tei:foreign> were two different persons. There the reading is: <tei:foreign xml:lang="he">בימי מתתיהו... וחשמונאי ובניו</tei:foreign>.',lemma='מתתיהו'),
 note(ROOT+'/tzidqatekha','is regarded as a form of <tei:foreign xml:lang="he">צדוק הדין</tei:foreign> said on the occasion of a death. According to tradition, Moses died on Sabbath afternoon. These three verses, containing the words <tei:foreign xml:lang="he">ה׳ אלהים אמת</tei:foreign>, are arranged in a reverse order in the Sephardic <tei:hi rend="italic">Siddur</tei:hi>. <tei:foreign xml:lang="he">צדקתך צדק</tei:foreign> is presumably a substitute for the <tei:hi rend="italic">Taḥanun</tei:hi> of the <tei:hi rend="italic">Minḥah</tei:hi> for weekdays.',lemma='צדקתך צדק'),
 note(BIBLE+'psalms/104','(Psalm 104) is closely similar to the story of creation in Genesis. The psalmist celebrates God’s glory as seen in the forces of nature. It has been declared that it is worthwhile studying the Hebrew language for ten years in order to read Psalm 104 in the original.',lemma='ברכי נפשי'),
 note(BIBLE+'psalms/120','the title prefixed to the following fifteen psalms, is now generally understood to mean a psalm sung by the pilgrims as they went up to Jerusalem to celebrate the three pilgrim festivals in the center of national and religious life.',lemma='שיר המעלות'),
]
PSALM_COMMENTS = {
120:'Psalm 120 is directed against slanderers. They are doomed to severe punishment. They shall be pierced with sharp arrows and burned with the hot charcoal of the broom bush. <tei:foreign xml:lang="he">משך</tei:foreign> and <tei:foreign xml:lang="he">קדר</tei:foreign>, wild tribes, symbolize barbarian enemies.',
121:'Psalm 121 is a perfect expression of trust in God, and has been on the lips of countless people when they felt the need of help beyond that which mortals can offer.',
122:'Psalm 122 is a pilgrim’s recollection of a visit to Jerusalem and the many sacred memories associated with that magnificent city.',
123:'Psalm 123 begins in the singular and continues in the plural. It is a hymn of faith composed in a time of distress, contemptuous scorn and mockery.',
124:'Psalm 124 commemorates an escape from some imminent danger.',
125:'Psalm 125 expresses the unshakable confidence of Israel in God, and the assurance that the evildoers shall perish.',
126:'Psalm 126 is a song of those who have been redeemed from exile, and a hopeful prayer for those who have not yet returned. <tei:foreign xml:lang="he">כאפיקים בנגב</tei:foreign> like the hill streams of the Negev, dry in summer but becoming suddenly swollen torrents in the rains of the autumn.',
127:'Psalm 127 is a warning against over-anxiety in any work. Man’s labor is in vain without God’s help. A numerous family is one of God’s special blessings; it secures for the parents influence and respect.',
128:'Psalm 128 contains a picture of an ideal homelife. The welfare of the state depends upon virtuous family life.',
129:'Psalm 129 is a song of deliverance and the overthrow of the wicked. On the flat roofs of oriental houses grass often springs up in the rainy season but quickly withers, yielding nothing useful. So the enemies of Zion shall be destroyed before their malicious schemes can mature.',
130:'Psalm 130 is an expression of remorse for sin and a plea for forgiveness. Since God reveals himself as a forgiving God, Israel can hope and trust.',
131:'Psalm 131 is a song of child-like humility. As the child that has gone through the troublesome process of weaning can lie happily in its mother’s arms, so the psalmist’s soul has found contentment and happiness through the discipline of humility.',
132:'Psalm 132 contains the prayer that David’s efforts in establishing a sanctuary in Jerusalem should be well remembered and rewarded by God.',
133:'Psalm 133 describes the blessing of unity and brotherly love. <tei:foreign xml:lang="he">כשמן הטוב</tei:foreign> as the fragrant oil with which Aaron was anointed diffused its fragrance all around, so the spirit of amity and mutual friendship is spread throughout the environment.',
134:'Psalm 134 is a night-salutation addressed to the priests and Levites in the Temple, and their reply.',
}
for n,text in PSALM_COMMENTS.items():
 NOTES.append(note(BIBLE+f'psalms/{n}' if n!=134 else ROOT+'/psalms/134',text))
NOTES += [note(ROOT+'/vaani_tefillati','Psalm 69:14.',kind='citation',n='1'),
 note(ROOT+'/tzidqatekha','Psalms 119:142; 71:19; 36:7.',kind='citation',n='3')]

NOTES += [
 note(ROOT+'/torah/vezot_hatorah','Deuteronomy 4:44; Numbers 9:23.',kind='citation',n='1'),
 note(ROOT+'/torah/vezot_hatorah/adonai_chafetz','Proverbs 3:18, 17, 16; Isaiah 42:21.',kind='citation',n='2'),
 note(ROOT+'/torah/uvnucho','Numbers 10:36; Psalm 132:8–10; Proverbs 4:2; 3:18, 17; Lamentations 5:21.',kind='citation',n='1'),
]
