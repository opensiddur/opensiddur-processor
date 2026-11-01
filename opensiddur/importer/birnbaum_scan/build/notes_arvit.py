"""Commentary and citations printed with Arvit, pages 189–220."""
from .arvit import ROOT, URNS, ANCHORS
from .notes_minchah import note

NOTES = [
 note(URNS['psalm134']+'/1', 'the evening service, does not correspond to any sacrifice in the Temple since the offering of sacrifices occurred only twice a day, morning and afternoon. Hence in talmudic times and in a greater part of the geonic period the Shemoneh Esreh was omitted from the Ma‘ariv service. To replace the Eighteen Benedictions, eighteen scattered biblical verses, each mentioning the name of God, were introduced at the end of the Ma‘ariv service. This passage, beginning with <tei:foreign xml:lang="he">ברוך ה׳ לעולם</tei:foreign>, was arranged by “the heads of the Babylonian academies” (Maḥzor Vitry, page 78). It is followed by half-Kaddish probably because at one time it marked the end of the evening service, as may be seen from the Siddur of Amram Gaon (ninth century). Maimonides asserts that since the Jews everywhere consented to say the evening prayer regularly, it is equivalent to an obligation (Tefillah 1:6). The controversy in the Talmud as to whether the evening prayer is optional or obligatory refers to the Shemoneh Esreh and not to the Shema, which it is obligatory to recite morning and evening. Since the Ma‘ariv prayer was considered by some talmudic rabbis to be optional, the Shemoneh Esreh is not repeated by the Reader and the Kedushah is not recited.',lemma='תפלת ערבית'),
 note(URNS['opening_verses'],'Psalms 46:8; 84:13; 20:10.',kind='citation',n='1'),
 note(URNS['vehu'],'The verse <tei:foreign xml:lang="he">והוא רחום</tei:foreign>, consisting of thirteen words, was held by some to recall the thirteen attributes of divine mercy (Exodus 34:6–7). “As the evening approaches, man is conscious of having sinned during the day, and thus begins his prayer with this appeal to the divine mercy” (Maḥzor Vitry, page 77).'),
 note(URNS['vehu'],'Psalms 78:38; 20:10.',kind='citation',n='1'),
 note(URNS['emet']+'/opening','Job 9:10; Psalm 66:9.',kind='citation',n='1'),
 note(URNS['emet']+'/mi_khamokhah','Exodus 15:11.',kind='citation',n='2'),
 note(URNS['emet']+'/yimlokh','Exodus 15:18.',kind='citation',n='3'),
 note(URNS['emet']+'/seal','Jeremiah 31:10.',kind='citation',n='4'),
 note(ANCHORS['barukh','psalms/79/13'],'Psalms 89:53; 135:21; 72:18–19; 104:31; 113:2; I Samuel 12:22; I Kings 18:39; Zechariah 14:9; Psalms 33:22; 106:47; 86:9–10; 79:13.',kind='citation',n='1'),
 note(ANCHORS['barukh','job/12/10'],'Job 12:10.',kind='citation',n='2'),
 note(ANCHORS['barukh','psalms/31/6'],'Psalm 31:6.',kind='citation',n='1'),
 note(ROOT+'/amidah','On <tei:foreign xml:lang="he">שמונה עשרה</tei:foreign>, see pages 81–92.'),
 note(ROOT+'/psalm27','On Psalm 27, see pages 147–149.'),
 note(ROOT+'/mourning','On Psalm 49, see pages 149–151.'),
]
# Citations and the two final Psalm 49 comments are already attached to the
# transcluded scripture in notes_conclusion; they must not be duplicated here.
