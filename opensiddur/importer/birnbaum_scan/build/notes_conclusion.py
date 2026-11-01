"""Printed notes on pages 128–152, excluding the Decalogue."""
from .conclusion import PSALMS, SHIR_SHEL_YOM, URNS

def make_notes(anchors):
    """Attach printed notes to the correspondences selected by the passage builder."""
    NOTES = []


    def anchor(key, row):
        return anchors[URNS[key], row]


    def commentary(key, row, lemma, text):
        NOTES.append(dict(kind='commentary', target=anchor(key, row) if row else key,
                          lemma=lemma, paras=[dict(text=text)]))


    commentary('uva_letziyyon', 'uva', 'ובא לציון', 'which consists of biblical passages accompanied by the paraphrase of the Targum, was designed to enable every Jew to have a daily share in the study of the Torah (Rashi, Sotah 49a). On Sabbaths and festivals, when the Torah and the Prophets are read at great length, the recitation of this collection of Scriptural passages is postponed till the afternoon service.')
    commentary('aleinu', 'aleinu', 'עלינו', 'is the proclamation of God as King over a united humanity. An old tradition claims Joshua as its author. Taken from the <tei:hi rend="italic">Musaf</tei:hi> service of <tei:hi rend="italic">Rosh Hashanah</tei:hi>, <tei:hi rend="italic">Alenu</tei:hi> has been used as the closing prayer of the daily services since the thirteenth century. It is reported that it was the death-song of Jewish martyrs in the Middle Ages. <tei:hi rend="italic">Alenu</tei:hi> has been the occasion of repeated attacks on account of the passage: “They bow to vanity and emptiness and pray to a god that cannot save” (<tei:foreign xml:lang="he">שהם משתחוים להבל וריק ומתפללים אל אל לא יושיע</tei:foreign>). Through fear of the official censors, the passage in question has been excluded from the prayer.')
    commentary(SHIR_SHEL_YOM, None, 'שיר של יום', 'the Psalm of the Day, was chanted by the Levites each day during the Temple service (Mishnah Tamid 7:4). According to the Talmud, the daily psalms were intended to recall the incidents of the six days of creation (Rosh Hashanah 31a).')
    commentary(PSALMS+'/sunday/psalm_24/1', None, 'מזמור', 'a poem sung to the accompaniment of musical instruments in the Temple service.')
    commentary(PSALMS+'/sunday/psalm_24/7', None, 'שאו שערים ראשיכם', 'The ancient gates of Zion are poetically commanded to raise their heads, in token of reverence to God whose entrance is an act of condescension. Different parts of this psalm were sung by different choirs of singers at the time when David brought the ark to Mount Zion.')
    commentary('psalm_48', '1', 'בני קרח', 'descendants of Korah, a division of Levites who sang in the Temple.')
    commentary('psalm_48', '6', 'המה ראו', 'they saw the impregnable might of Zion and were terrified.')
    commentary('psalm_48', '8', 'אניות תרשיש', 'the great seagoing vessels that made the long voyage to Tarshish, a seacoast city in Spain (or Carthage).')
    commentary('psalm_48', '9', 'כאשר שמענו כן ראינו', 'that is, history has repeated itself. We have now experienced events similar to those which occurred in the past. This psalm celebrates the escape of Jerusalem from a threatened invasion by the armies of various confederate kings.')
    commentary('psalm_48', '13', 'סובו ציון…', 'that is, after the miraculous deliverance of Zion, its inhabitants can now freely walk around and contemplate the safety of the walls and towers and palaces so lately menaced with destruction.')
    commentary('psalm_82', '1', 'נצב בעדת אל…', 'God takes his stand in the assembly summoned by him, and denounces the wickedness and partiality of judges. He reminds them of their duties, and declares that because they are ignorant and corrupt human society is undermined.')
    commentary('psalm_82', '6', 'אני אמרתי…', 'I appointed you as judges and thus invested you with authority of administering divine justice; however, your high title will not exempt you from punishment. You shall die like common men, and fall like any other prince.')
    commentary('psalm_82', '8', 'קומה', 'The psalmist pleads that God should act as judge over all peoples, since the human judges have failed so miserably.')
    commentary('psalm_94', '1', 'אל נקמות', 'is repeated for emphasis. The psalmist appeals to God to punish the arrogant who contemptuously declare that God is indifferent to the sufferings of his people. He then turns to argue with those who foolishly agree with their oppressors and think that God will not defend them. He who gave others the power to hear and see can surely himself hear and see. God knows the evil thoughts of the wicked, and eventually the righteous will be vindicated when the day of retribution comes. It is unthinkable that God would abandon his people to the ravages of lawless judges and tyrannical rulers.')
    commentary('psalm_81', '1', 'למנצח', 'occurs in the titles of fifty-five psalms, and refers to the use of the psalm in the Temple services. The word means the conductor of the Temple choir, who trained the choir and led the music.')
    commentary('psalm_81', '1', 'על הגתית', 'occurs in the titles of three psalms. According to the Targum, Gittith was a harp used by the Philistines of Gath. Since the Hebrew word <tei:hi rend="italic">gath</tei:hi> means “a winepress,” <tei:hi rend="italic">Gittith</tei:hi> may mean a melody sung at vintage festivals.')
    commentary('psalm_81', '4', 'בחדש', 'is rendered by the Targum and the Talmud: Rosh Ḥodesh Tishri, that is Rosh Hashanah. Metal trumpets, and not a shofar, were used on all other occasions of Rosh Ḥodesh.')
    commentary('psalm_81', '4', 'בכסה ליום חגנו', 'that is, the Sukkoth festival which begins on the fifteenth of Tishri when the moon is full.')
    commentary('psalm_81', '6', 'יהוסף', 'is a synonym for Israel, so called from the favored son of Israel. In Psalm 77:16, Jacob and Joseph are named as the fathers of the entire people of Israel.')
    commentary('psalm_81', '6', 'שפת לא ידעתי…', 'The psalmist represents Israel as quoting the following words of God, heard for the first time after the exodus from Egypt.')
    commentary('psalm_81', '8', 'על מי מריבה', 'refers to Exodus 17:7; Numbers 20:13.')
    commentary('psalm_81', '11', 'הרחב פיך…', 'God will abundantly supply your needs as long as you are faithful to him.')
    commentary('psalm_81', '16', 'משנאי ה׳…', 'God’s enemies are the enemies of his people, and he would compel them to pay homage to Israel. Israel’s national existence and prosperity would know no end.')
    commentary('psalm_93', '1', 'גאות לבש…', 'The psalmist speaks of God’s attributes as a glorious garment wrapped about him. God’s rule reestablishes the moral order of the world. Rashi and others interpret this psalm in connection with the Messianic era.')
    commentary('psalm_93', '3', 'נשאו נהרות…', 'God’s control of the violent forces of nature is used here to represent his power over the mighty enemies of his people.')
    commentary('psalm_93', '5', 'עדותיך…', 'God’s moral laws are firmly established and unchangeable. Zion, his house, shall no longer be desecrated by heathen invaders.')
    commentary('psalm_27', '1', 'ה׳ אורי וישעי', 'The first part of this psalm expresses fearless confidence in the face of hostile armies, while the second part is a prayer of one in deep distress and beset by false accusers.')
    commentary('psalm_27', '2', 'לאכל את בשרי', 'to eat my flesh, like wild beasts of prey.')
    commentary('psalm_27', '4', 'שבתי בבית ה׳', 'that is, living securely under God’s protection and enjoying his hospitality.')
    commentary('psalm_27', '8', 'לך אמר לבי…', 'The psalmist, in his heart, quotes God’s command to the effect that all must seek access to his presence.')
    commentary('psalm_27', '10', 'אבי ואמי עזבוני…', 'Though I am orphaned, friendless and deserted, God will be father to me and protect me.')
    commentary('psalm_27', '13', 'לולא האמנתי…', 'The remainder of the sentence is left to the imagination: “What would my condition be, if I had not believed!”')
    commentary('psalm_49', '2', 'שמעו זאת…', 'The psalmist addresses all the inhabitants of the world and summons them to hear his parable which concerns all humanity.')
    commentary('psalm_49', '4', 'חכמות', 'moral philosophy. The rich man cannot deliver his friends or himself from death, and his prosperity need cause no dismay to those who are less fortunate.')
    commentary('psalm_49', '12', 'קרבם', 'They delude themselves with the thought that their names will be perpetuated in the names of their estates.')
    commentary('psalm_49', '15', 'מות ירעם…', 'death will take control of them; and in the morning, when the dark night of suffering is over, the victims of lawlessness will be triumphant over their fallen oppressors.')
    commentary('psalm_49', '16', 'אך…יפדה נפשי', 'The psalmist is confident that God will deliver him from the premature death of the wicked and will receive him under his divine protection.')

    for key, row, number, citation in (
        ('uva_letziyyon', 'uva', '1', 'Isaiah 59:20–21.'),
        ('uva_letziyyon', 'veattah', '2', 'Psalm 22:4.'),
        ('uva_letziyyon', 'veqara', '3', 'Isaiah 6:3.'),
        ('uva_letziyyon', 'vatissa', '4', 'Ezekiel 3:12.'),
        ('uva_letziyyon', 'targum_qadosh', '*', 'The words in italics are the Targum paraphrase of the preceding verse.'),
        ('uva_letziyyon', 'yimlokh', '1', 'Exodus 15:18.'),
        ('uva_letziyyon', 'avraham', '2', 'I Chronicles 29:18.'),
        ('uva_letziyyon', 'vehu', '3', 'Psalms 78:38; 86:5; 119:142.'),
        ('uva_letziyyon', 'titten', '4', 'Micah 7:20.'),
        ('uva_letziyyon', 'barukh', '5', 'Psalms 68:20; 46:8; 84:13; 20:10.'),
        ('uva_letziyyon', 'lemaan', '6', 'Psalm 30:13.'),
        ('uva_letziyyon', 'barukh_hagever', '7', 'Jeremiah 17:7; Isaiah 26:4; Psalm 9:11.'),
        ('uva_letziyyon', 'chafetz', '8', 'Isaiah 42:21.'),
        ('aleinu', 'veyadata', '1', 'Deuteronomy 4:39.'),
        ('aleinu', 'yimlokh', '1', 'Exodus 15:18.'),
        ('aleinu', 'vehayah', '2', 'Zechariah 14:9.'),
        ('al_tira', 'al_tira', '3', 'Proverbs 3:25; Isaiah 8:10; 46:4.'),
    ):
        NOTES.append(dict(kind='citation', target=anchor(key, row), n=number,
                          paras=[dict(text=citation)]))
    return NOTES
