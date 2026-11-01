"""Commentary read directly from printed 424–436."""
from copy import deepcopy
from .notes_minchah import note
from .shabbat_day_meal import ROOT, URNS, LEIL
from .notes_leil_shabbat import NOTES as OLD_NOTES

NOTES = [
note(ROOT+'/kiddush','the great Kiddush, so called by way of inversion, since it is of later origin and of less importance than the Kiddush recited in the evening.',lemma='קדושא רבא'),
note(URNS['barukh_adonai_yom_yom'],
'was composed by Rabbi Simeon bar Isaac bar Abun, a native of Mayence, who was one of the most important liturgical writers and scholars of the eleventh century. The name of the author (<tei:foreign xml:lang="he">שמעון בר יצחק</tei:foreign>) forms the acrostic of the stanzas, each of which consists of five rhymed verses. The part beginning with <tei:foreign xml:lang="he">ברוך הוא אלהינו</tei:foreign> seems to be a later addition.\n\n'
'The poem bears no reference to the Sabbath, but deals with the persecutions endured by our people in <tei:hi rend="italic">Galuth</tei:hi>. Each stanza ends with a biblical verse as a chorus. The poet utilized the following biblical verses: Psalm 68:20; Isaiah 25:4; 63:9; Exodus 24:10; Psalm 130:7; Isaiah 43:14; Psalm 106:46; I Samuel 12:22; Jeremiah 49:38; Job 33:18; Psalm 148:14; Lamentations 3:32; Daniel 8:8,21; Lamentations 3:23; Jeremiah 60:34; Job 38:6; Lamentations 3:31; Isaiah 63:1; 34:6; Psalm 76:13; Isaiah 27:8; Deuteronomy 4:43; Psalms 31:24; 42:9; Ezekiel 37:9; 17:23; 20:40; 34:14; Deuteronomy 30:3–4; Isaiah 63:7; 43:7; Psalm 117:2; Isaiah 9:5.',lemma='ברוך ה׳ יום יום'),
note(URNS['barukh_adonai_yom_yom']+'/8','refers to a statement in the Talmud (Makkoth 12a) that the guardian angel of Edom will commit three errors in fleeing to Bozrah. He will think that Bozrah is a city of refuge, confusing it with Bezer; he will think that the cities of refuge afford protection to wilful murderers; he will be ignorant of the fact that only human beings may seek refuge in these cities.',lemma='ראותו... אדומי העוצר'),
note(URNS['barukh_el_elyon'],
'is a poem by Rabbi Baruch ben Samuel of Mayence, one of the most eminent German rabbis of the thirteenth century. The stanzas, consisting of four verses each with a cross rhyme and a refrain, bear the acrostic <tei:foreign xml:lang="he">ברוך חזק</tei:foreign>. Each of the seven stanzas, including the refrain, has a total of sixty syllables. The refrain <tei:foreign xml:lang="he">הבן עם הבת</tei:foreign> is an allusion to the fourth commandment: “You shall not do any work, neither you, nor your son, nor your daughter...” <tei:foreign xml:lang="he">מנחה על מחבת</tei:foreign>, the offering baked on a griddle, is ordained in Leviticus 2:5. The expression <tei:foreign xml:lang="he">עד אנה תוגיון נפש</tei:foreign> is borrowed from Job 19:2.\n\n'
'The biblical verses utilized in this poem are: Genesis 14:20; I Kings 8:56; Lamentations 3:47; Jeremiah 30:17; Job 19:2 (Stanza I). Psalm 68:5; Ecclesiastes 12:9; I Samuel 20:29 (Stanza II). Isaiah 30:18; I Kings 8:12; Deuteronomy 1:7; Malachi 3:20, or Genesis 32:32 (Stanza III). Isaiah 56:6; Genesis 32:19 (Stanza IV). Psalm 119:1; Isaiah 26:4; 11:2 (Stanza V). Numbers 6:7; Proverbs 29:17; Exodus 29:29 (Stanza VI). Exodus 35:2; Ezekiel 44:30; Exodus 35:3; 20:10 (Stanza VII).',lemma='ברוך אל עליון'),
note(URNS['barukh_el_elyon']+'/3','the twofold reward for Sabbath observance, is in keeping with the opening words of the fourth commandment, <tei:foreign xml:lang="he">זכור</tei:foreign> and <tei:foreign xml:lang="he">שמור</tei:foreign>, in Exodus 20:8 and Deuteronomy 5:12, respectively.',lemma='תשלומי כפל'),
note(URNS['yom_zeh_mekhubbad'],'is by an unidentified poet, Rabbi Israel, whose name appears in the acrostic, which adds <tei:foreign xml:lang="he">הגר</tei:foreign> (“the proselyte”) in the last stanza. Each verse contains six syllables. The biblical verses utilized in this poem are: Isaiah 58:13; Genesis 2:3; Exodus 20:9–11; 12:2; 16:23; Nehemiah 8:10; Deuteronomy 4:4; Genesis 28:20; Proverbs 30:8; Deuteronomy 8:9–10; 7:14; 15:6; Psalms 19:2; 33:5; Isaiah 66:2; Deuteronomy 32:4.',lemma='יום זה מכובד'),
note(URNS['yom_zeh_mekhubbad']+'/3','is based on the talmudic statement that the best food should be prepared for the Sabbath, for “he who delights in the Sabbath is granted his heart’s desires” (Shabbath 118a-b). The emphasis on the Sabbath as a day of eating and drinking was meant, according to some, to counteract the ascetic tendencies of the Essenes.',lemma='אכל משמנים...'),
]
# These notes are reprinted with the hymns. Their occurrence wrappers keep the
# local wording; the identical note on Tzur's opening refrain is inherited.
for key in ('yah_ribbon','tzur_mishello'):
    entry=deepcopy(next(n for n in OLD_NOTES if n['target']==LEIL[key]))
    entry['target']=ROOT+'/'+key
    if key=='yah_ribbon':
        entry['paras'][0]['text']=entry['paras'][0]['text'].replace('popular songbook among','popular songbook of').replace('several languages and','several languages, and')
    NOTES.append(entry)
