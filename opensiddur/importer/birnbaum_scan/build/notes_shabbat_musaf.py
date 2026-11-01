"""Commentary read on printed 391–422; Kiddush's note is outside this unit."""
from .notes_minchah import note
from .shabbat_musaf import ROOT, URNS, TIKANTA, EIN, ANIM, TAMID, TANA, BIBLE
NOTES = [
 note(ROOT+'/amidah','the prayer added after <tei:hi rend="italic">Shaḥarith</tei:hi>, corresponds to the additional sacrifices on Sabbaths and festive days over and above the regular daily <tei:hi rend="italic">tamid</tei:hi> offered in the Temple.',lemma='מוסף'),
 # The Ki Shem commentary and its Deuteronomy citation are inherited from Minchah.
 note(URNS['naaritz'],'equals <tei:foreign xml:lang="he">שיח סוד</tei:foreign>; compare <tei:foreign xml:lang="he">שיח סוד שרפי קודש</tei:foreign> in the Sephardic <tei:hi rend="italic">Siddur</tei:hi>. <tei:foreign xml:lang="he">נעריצך כשיח סוד</tei:foreign> is based on <tei:foreign xml:lang="he">אל נערץ בסוד קדושים</tei:foreign> (Psalm 89:8) where the meaning is: “God is revered in the council of the holy ones.”',lemma='סוד שיח'),
 note(ROOT+'/amidah/qedushah/shema','and the concluding words of the <tei:hi rend="italic">Shema</tei:hi> were inserted here in the fifth century, when special government officials were posted in the synagogues to prevent the congregational proclamation of God’s Oneness. Toward the end of the service, when the spies had left, the <tei:hi rend="italic">Shema</tei:hi> was thus recited in an abridged form.',lemma='שמע ישראל'),
 note(ROOT+'/amidah/qedushah/shema','Deuteronomy 6:4.',kind='source',n='3'),
 note(URNS['ani'],'Numbers 15:41.',kind='source',n='4'),
 note(TIKANTA,'the first twenty-two words of which run in a reversed alphabetic acrostic, is found in Maḥzor Vitry and was known to Amram Gaon (ninth century). The passage begins with <tei:foreign xml:lang="he">ת</tei:foreign>, the last letter of the alphabet, and ends with <tei:foreign xml:lang="he">א</tei:foreign>, the first letter.',lemma='תכנת שבת'),
 note(BIBLE+'numbers/28/9','Numbers 28:9–10.',kind='source',n='1'),
 note(BIBLE+'numbers/28/11','Numbers 28:11.',kind='source',n='1'),
 note(ROOT+'/amidah/meditation','Psalms 60:7; 19:15.',kind='source',n='2'),
 note(ROOT+'/kaddish','is said between <tei:hi rend="italic">Rosh Hashanah</tei:hi> and <tei:hi rend="italic">Yom Kippur</tei:hi>; otherwise only <tei:foreign xml:lang="he">לעילא</tei:foreign> is said. In some rituals <tei:foreign xml:lang="he">לעילא</tei:foreign> is repeated throughout the year. <tei:foreign xml:lang="he">לעילא לעילא</tei:foreign> is the Targum’s rendering of <tei:foreign xml:lang="he">מעלה מעלה</tei:foreign> (Deuteronomy 28:43).',lemma='לעילא לעילא'),
 note(ROOT+'/kaddish','(“consolations”), occurring in the Kaddish as a synonym of praise, probably refers to prophetic works such as the Book of Isaiah, called Books of Consolation, which contain hymns of praise as well as Messianic prophecies.',lemma='נחמתא'),
 note(ROOT+'/qavveh','Psalm 27:14; I Samuel 2:2; Psalm 18:32.',kind='source',n='2'),
 note(EIN,'forms the acrostic <tei:foreign xml:lang="he">אמן, ברוך אתה</tei:foreign>. Each of the three letters of <tei:foreign xml:lang="he">אמן</tei:foreign> is repeated four times, totalling twelve. Rashi, in his <tei:hi rend="italic">Siddur</tei:hi>, points out that <tei:foreign xml:lang="he">אין כאלהינו</tei:foreign> is recited on Sabbaths and festivals, when the <tei:hi rend="italic">Amidah</tei:hi> prayer is limited to seven benedictions instead of the nineteen benedictions contained in the regular <tei:hi rend="italic">Shemoneh Esreh</tei:hi>, in order to bring the blessings to a total of nineteen. <tei:hi rend="italic">En Kelohenu</tei:hi> was composed during the period of the Geonim.',lemma='אין כאלהינו'),
 note(TAMID+'/shabbat','“the great Sabbath,” a symbolic description of the world to come, a foretaste of which is offered by the weekly Sabbath.',lemma='יום שכולו שבת'),
 note(TANA,'a midrashic collection of mysterious authorship, consists of two parts: <tei:hi rend="italic">Seder Eliyyahu Rabba</tei:hi> (thirty-one chapters) and <tei:hi rend="italic">Seder Eliyyahu Zuta</tei:hi> (twenty-five chapters). According to the Talmud (Kethubboth 106a), Elijah frequently visited Rabbi Anan (third century) and taught him <tei:hi rend="italic">Seder Eliyyahu</tei:hi>. This work, which has been named “the jewel of aggadic literature,” repeatedly emphasizes the importance of diligence in the study of the Torah.',lemma='תנא דבי אליהו'),
 note(TANA,'Habakkuk 3:6.',kind='source',n='8'),
 note(ROOT+'/study/elazar/al_tiqra','introduces a play on words, and is not intended as an emendation of the biblical text.',lemma='אל תקרא'),
 note(ANIM,'is attributed to Rabbi Judah of Regensburg (<tei:foreign xml:lang="he">ר׳ יהודה החסיד</tei:foreign>), who was a philosopher and poet, saint and mystic. He died in 1217. Each stanza in this poem contains sixteen syllables.',lemma='אנעים זמירות'),
 note(ANIM+'/beyad','has been mistranslated: “in the mystic utterance of thy servants.” However, the poet uses <tei:foreign xml:lang="he">בסוד עבדיך</tei:foreign> in the sense of <tei:foreign xml:lang="he">בסוד קדושים</tei:foreign> (Psalm 89:8) which is rendered “in the council of the holy ones.” See page 393.',lemma='בסוד עבדיך'),
 note(ANIM+'/dimmu','that is, the human intellect cannot conceive the essence of God, but only his acts.',lemma='לפי מעשיך'),
 note(ANIM+'/vayyechezu','alludes to Daniel 7:9; Song of Songs 5:11; Exodus 15:3; Deuteronomy 33:7; Psalm 98:1; Isaiah 26:19; 28:5; Song of Songs 5:2, 11.',lemma='ויחזו בך…'),
 note(ANIM+'/ketem','the plate on Aaron’s forehead, upon which was engraved: “Holy to the Lord” (Exodus 28:36).',lemma='על מצח'),
 note(ANIM+'/lechen','hymns of praise.',lemma='עטרה'),
 note(ANIM+'/neveh','Jerusalem.',lemma='נוה הצדק'),
 note(ANIM+'/peero','the <tei:hi rend="italic">tefillin</tei:hi> containing the words <tei:foreign xml:lang="he">ה׳ אחד</tei:foreign>, “the Lord is One”. <tei:foreign xml:lang="he">פארי עליו</tei:foreign> God’s <tei:hi rend="italic">tefillin</tei:hi> containing the words <tei:foreign xml:lang="he">מי כעמך… גוי אחד</tei:foreign>.',lemma='פארו עלי'),
 note(ANIM+'/segullato','Isaiah 62:3; 46:3; 43:4; Song of Songs 5:10; Isaiah 63:1–3.',lemma='צבי תפארת…'),
 note(ANIM+'/qesher','refers to the talmudic statement that Moses saw God’s <tei:hi rend="italic">tefillin</tei:hi>.',lemma='קשר תפלין'),
 note(ANIM+'/rosh','alludes to <tei:foreign xml:lang="he">בראשית ברא אלהים</tei:foreign>, the first three words of the Torah, whose final letters spell <tei:foreign xml:lang="he">אמת</tei:foreign>.',lemma='ראש דברך אמת'),
 note(ROOT+'/anim_end','I Chronicles 29:11; Psalm 106:2.',kind='source',n='1'),
 # The earlier Psalm 27 printing already supplies both comments, except this sentence.
 note(ROOT+'/psalm27','The word <tei:foreign xml:lang="he">לולא</tei:foreign> is marked with dots in the Massoretic text.'),
]
for number,(key,psalm) in enumerate(zip(('sunday','monday','tuesday','wednesday','thursday','friday','shabbat'),(24,48,82,94,81,93,92)),1):
    NOTES.append(note(TAMID+'/'+key,f'Psalm {psalm}.',kind='source',n=str(number)))
