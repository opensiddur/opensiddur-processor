"""Tachanun and El Erekh Appayim: scan-collated readings, printed 103–118.

{pb:N} is a physical page break; {p} a paragraph; {reader} the printed rubric.
The Hebrew foundation transcription was collated against the scan, retaining
Birnbaum readings rather than Wikisource’s subsequent changes.
"""

PASSAGES = {'vayomer': {'he': 'וַיֹּֽאמֶר דָּוִד אֶל גָּד: צַר לִי מְאֹד; נִפְּלָה נָּא בְיַד יְיָ, כִּי רַבִּים '
                   'רַחֲמָיו, וּבְיַד אָדָם אַל אֶפֹּֽלָה.',
             'en': 'And David said to Gad: “I am deeply distressed; let us fall into the hand of the Lord, '
                   'for his mercy is great, but let me not fall into the hand of man.”',
             'first': 103,
             'last': 113},
 'rachum': {'he': 'רַחוּם וְחַנּוּן, חָטָֽאתִי לְפָנֶֽיךָ; יְיָ מָלֵא רַחֲמִים, רַחֵם עָלַי וְקַבֵּל '
                  'תַּחֲנוּנָי.',
            'en': 'Merciful and gracious God, I have sinned before thee; O Lord, who art full of compassion, '
                  'have mercy on me and accept my supplications.',
            'first': 103,
            'last': 113},
 'shomer_yisrael': {'he': 'שׁוֹמֵר יִשְׂרָאֵל, שְׁמוֹר שְׁאֵרִית יִשְׂרָאֵל, וְאַל יֹאבַד יִשְׂרָאֵל, '
                          'הָאוֹמְרִים שְׁמַע יִשְׂרָאֵל.',
                    'en': 'Guardian of Israel, preserve the remnant of Israel; let not Israel perish, who '
                          'say: “Hear, O Israel.”',
                    'first': 103,
                    'last': 115},
 'shomer_goy_echad': {'he': 'שׁוֹמֵר גּוֹי אֶחָד, שְׁמוֹר שְׁאֵרִית עַם אֶחָד, וְאַל יֹאבַד גּוֹי אֶחָד, '
                            'הַמְיַחֲדִים שִׁמְךָ, יְיָ אֱלֹהֵֽינוּ, יְיָ אֶחָד.',
                      'en': 'Guardian of a unique people, preserve the remnant of a unique people; let not a '
                            'unique people perish, who proclaim thy Oneness, saying: “The Lord is our God, '
                            'the Lord is One.”',
                      'first': 105,
                      'last': 115},
 'shomer_goy_qadosh': {'he': 'שׁוֹמֵר גּוֹי קָדוֹשׁ, שְׁמוֹר שְׁאֵרִית עַם קָדוֹשׁ, וְאַל יֹאבַד גּוֹי '
                             'קָדוֹשׁ, הַמְשַׁלְּשִׁים בְּשָׁלֹשׁ קְדֻשּׁוֹת לְקָדוֹשׁ.',
                       'en': 'Guardian of a holy people, preserve the remnant of a holy people; let not a '
                             'holy people perish, who repeat the threefold sanctification to the Holy One.',
                       'first': 105,
                       'last': 117},
 'mitratzeh': {'he': 'מִתְרַצֶּה בְּרַחֲמִים וּמִתְפַּיֵּס בְּתַחֲנוּנִים, הִתְרַצֵּה וְהִתְפַּיֵּס לְדוֹר '
                     'עָנִי, כִּי אֵין עוֹזֵר. אָבִֽינוּ מַלְכֵּֽנוּ, חָנֵּֽנוּ וַעֲנֵֽנוּ, כִּי אֵין '
                     'בָּֽנוּ מַעֲשִׂים; עֲשֵׂה עִמָּֽנוּ צְדָקָה וָחֶֽסֶד וְהוֹשִׁיעֵֽנוּ.',
               'en': 'O thou who art reconciled by prayers and conciliated by supplications, be thou '
                     'reconciled and conciliated to an afflicted generation, for there is none to '
                     'help.{p}Our Father, our King, be gracious to us and answer us, for we have no merits; '
                     'deal charitably and kindly with us and save us.',
               'first': 105,
               'last': 117},
 'vaanachnu': {'first': 105,
               'last': 117,
               'chunks': [{'anchor': 'vaanachnu',
                           'source': 'chronicles_2/20/12',
                           'he': 'וַאֲנַֽחְנוּ לֹא נֵדַע מַה נַּעֲשֶׂה, כִּי עָלֶֽיךָ עֵינֵֽינוּ. ',
                           'en': 'We know not what to do, but our eyes are upon thee. '},
                          {'anchor': 'zekhor',
                           'source': 'psalms/25/6',
                           'he': 'זְכֹר רַחֲמֶיךָ יְיָ, וַחֲסָדֶֽיךָ, כִּי מֵעוֹלָם הֵֽמָּה. ',
                           'en': 'Remember thy mercy and thy kindness, O Lord, for they are eternal. '},
                          {'anchor': 'yehi',
                           'source': 'psalms/33/22',
                           'he': 'יְהִי חַסְדְּךָ יְיָ עָלֵֽינוּ, כַּאֲשֶׁר יִחַֽלְנוּ לָךְ. ',
                           'en': 'May thy kindness rest on us, O Lord, as our hope rests on thee. '},
                          {'anchor': 'al_tizkor',
                           'source': 'psalms/79/8',
                           'he': 'אַל תִּזְכָּר־לָֽנוּ עֲוֹנוֹת רִאשֹׁנִים; מַהֵר יְקַדְּמֽוּנוּ רַחֲמֶֽיךָ, '
                                 'כִּי דַלּֽוֹנוּ מְאֹד. ',
                           'en': 'O mind not our former iniquities; may thy compassion hasten to our aid, '
                                 'for we are brought very low. '},
                          {'anchor': 'chonnenu',
                           'source': 'psalms/123/3',
                           'he': 'חָנֵּֽנוּ יְיָ חָנֵּֽנוּ, כִּי רַב שָׂבַֽעְנוּ בוּז. ',
                           'en': 'Take pity on us, O Lord, take pity on us, for we are exceedingly sated '
                                 'with contempt. '},
                          {'anchor': 'berogez',
                           'source': 'habakkuk/3/2',
                           'he': 'בְּרֹֽגֶז רַחֵם תִּזְכּוֹר. ',
                           'en': 'When in wrath, remember to be merciful. '},
                          {'anchor': 'ki_hu',
                           'source': 'psalms/103/14',
                           'he': 'כִּי הוּא יָדַע יִצְרֵֽנוּ, זָכוּר כִּי עָפָר אֲנָֽחְנוּ. {reader} ',
                           'en': 'He knows what we are made of, remembering that we are but dust. '},
                          {'anchor': 'ozrenu',
                           'source': 'psalms/79/9',
                           'he': 'עָזְרֵֽנוּ, אֱלֹהֵי יִשְׁעֵֽנוּ, עַל דְּבַר כְּבוֹד שְׁמֶֽךָ, '
                                 'וְהַצִּילֵֽנוּ וְכַפֵּר עַל חַטֹּאתֵֽינוּ לְמַֽעַן שְׁמֶֽךָ.',
                           'en': 'Help us, our saving God, for the sake of thy glorious name; rescue us and '
                                 'pardon our sins for thy name’s sake.'}]},
 'vehu': {'first': 105,
          'last': 107,
          'chunks': [{'anchor': 'vehu_rachum',
                      'source': 'psalms/78/38',
                      'he': 'וְהוּא רַחוּם, יְכַפֵּר עָוֹן וְלֹא יַשְׁחִית; וְהִרְבָּה לְהָשִׁיב אַפּוֹ, '
                            'וְלֹא יָעִיר כָּל חֲמָתוֹ. ',
                      'en': 'He, being merciful, forgives iniquity, and does not destroy; frequently he '
                            'turns his anger away, and does not stir up all his wrath.{p}'},
                     {'anchor': 'attah',
                      'source': 'psalms/40/12',
                      'he': 'אַתָּה יְיָ לֹא תִכְלָא רַחֲמֶֽיךָ מִמֶּֽנּוּ; חַסְדְּךָ וַאֲמִתְּךָ תָּמִיד '
                            'יִצְּרֽוּנוּ. ',
                      'en': 'Thou, O Lord, wilt not hold back thy mercy from us; thy kindness and thy truth '
                            'will always protect us. '},
                     {'anchor': 'hoshienu',
                      'source': 'psalms/106/47',
                      'he': 'הוֹשִׁיעֵנוּ, יְיָ אֱלֹהֵֽינוּ, וְקַבְּצֵֽנוּ מִן הַגּוֹיִם לְהוֹדוֹת לְשֵׁם '
                            'קָדְשֶֽׁךָ, לְהִשְׁתַּבֵּחַ בִּתְהִלָּתֶֽךָ. ',
                      'en': 'Save us, Lord our God, and gather us from among the nations, that we may give '
                            'thanks to thy holy name, that we may glory in thy praise. '},
                     {'anchor': 'im_avonot',
                      'source': 'psalms/130/3',
                      'he': 'אִם עֲוֹנוֹת תִּשְׁמָר־יָהּ, אֲדֹנָי, מִי יַעֲמֹד. ',
                      'en': 'If thou, O Lord, shouldst record iniquities—O Lord, who could live on? '},
                     {'anchor': 'ki_immekha',
                      'source': 'psalms/130/4',
                      'he': 'כִּי עִמְּךָ הַסְּלִיחָה, לְמַֽעַן תִּוָּרֵא. ',
                      'en': 'But with thee there is forgiveness, that thou mayest be revered. '},
                     {'anchor': 'lo_khataenu',
                      'source': 'psalms/103/10',
                      'he': 'לֹא כַחֲטָאֵֽינוּ תַּעֲשֶׂה לָּנוּ, וְלֹא כַעֲוֹנוֹתֵֽינוּ תִּגְמוֹל '
                            'עָלֵֽינוּ. ',
                      'en': 'Deal not with us according to our sins; requite us not according to our '
                            'iniquities. '},
                     {'anchor': 'im_avonenu',
                      'source': 'jeremiah/14/7',
                      'he': 'אִם עֲוֹנֵֽינוּ {pb:107}עָֽנוּ בָֽנוּ, יְיָ, עֲשֵׂה לְמַֽעַן שְׁמֶֽךָ. ',
                      'en': 'If our sins, O Lord, testify against us, act for {pb:108}thy name’s sake. '},
                     {'anchor': 'zekhor',
                      'source': 'psalms/25/6',
                      'he': 'זְכֹר רַחֲמֶֽיךָ יְיָ, וַחֲסָדֶֽיךָ, כִּי מֵעוֹלָם הֵֽמָּה. ',
                      'en': 'Remember, O Lord, thy mercy and thy kindness, for they are eternal. '},
                     {'anchor': 'yaanenu',
                      'source': 'psalms/20/2',
                      'he': 'יַעֲנֵֽנוּ יְיָ בְּיוֹם צָרָה, יְשַׂגְּבֵֽנוּ שֵׁם אֱלֹהֵי יַעֲקֹב. ',
                      'en': 'May the Lord answer us on the day of trouble; may the name of the God of Jacob '
                            'protect us. '},
                     {'anchor': 'adonai_hoshiah',
                      'source': 'psalms/20/10',
                      'he': 'יְיָ, הוֹשִׁיעָה; הַמֶּֽלֶךְ יַעֲנֵֽנוּ בְיוֹם קָרְאֵֽנוּ. ',
                      'en': 'O Lord, save us; may the King answer us when we call.{p}'},
                     {'anchor': 'avinu',
                      'source': None,
                      'he': 'אָבִֽינוּ מַלְכֵּֽנוּ, חָנֵּֽנוּ וַעֲנֵֽנוּ, כִּי אֵין בָּֽנוּ מַעֲשִׂים; '
                            'צְדָקָה עֲשֵׂה עִמָּֽנוּ לְמַֽעַן שְׁמֶךָ. אֲדוֹנֵֽינוּ אֱלֹהֵֽינוּ, שְׁמַע '
                            'קוֹל תַּחֲנוּנֵֽינוּ, וּזְכָר־לָנוּ אֶת בְּרִית אֲבוֹתֵֽינוּ, וְהוֹשִׁיעֵֽנוּ '
                            'לְמַֽעַן שְׁמֶךָ. ',
                      'en': 'Our Father, our King, take pity on us and answer us, for we have no merits; '
                            'deal charitably with us for thy name’s sake. Our Lord God, hear our '
                            'supplications; remember in our favor the covenant of our fathers, and save us '
                            'for thy name’s sake. '},
                     {'anchor': 'veattah',
                      'source': 'daniel/9/15',
                      'he': 'וְעַתָּה אֲדֹנָי אֱלֹהֵֽינוּ, אֲשֶׁר הוֹצֵֽאתָ אֶת עַמְּךָ מֵאֶֽרֶץ מִצְרַֽיִם '
                            'בְּיָד חֲזָקָה וַתַּֽעַשׂ לְךָ שֵׁם כַּיּוֹם הַזֶּה, חָטָֽאנוּ רָשָֽׁעְנוּ. ',
                      'en': 'And now, Lord our God, who hast brought thy people out of the land of Egypt '
                            'with a mighty hand, and hast made for thyself a name unto this day, we have '
                            'sinned, we have acted wickedly. '},
                     {'anchor': 'adonai',
                      'source': 'daniel/9/16',
                      'he': 'אֲדֹנָי, כְּכָל צִדְקוֹתֶֽךָ יָֽשָׁב־נָא אַפְּךָ וַחֲמָתְךָ מֵעִירְךָ '
                            'יְרוּשָׁלַֽיִם, הַר קָדְשֶֽׁךָ; כִּי בַחֲטָאֵֽינוּ וּבַעֲוֹנוֹת אֲבוֹתֵֽינוּ, '
                            'יְרוּשָׁלַֽיִם וְעַמְּךָ לְחֶרְפָּה לְכָל סְבִיבוֹתֵֽינוּ. ',
                      'en': 'O Lord, in accordance with all thy righteous deeds, pray let thy anger and thy '
                            'fury turn from Jerusalem thy city, thy holy mountain; for through our sins, and '
                            'through the iniquities of our fathers, Jerusalem and thy people are held in '
                            'disgrace by all who surround us. '},
                     {'anchor': 'veattah_shema',
                      'source': 'daniel/9/17',
                      'he': 'וְעַתָּה שְׁמַע, אֱלֹהֵֽינוּ, אֶל תְּפִלַּת עַבְדְּךָ וְאֶל תַּחֲנוּנָיו, '
                            'וְהָאֵר פָּנֶֽיךָ עַל מִקְדָּשְׁךָ הַשָּׁמֵם, לְמַֽעַן אֲדֹנָי.',
                      'en': 'And now, our God, listen to thy servant’s prayer and supplications, and let thy '
                            'favor shine upon thy desolate sanctuary for thy own sake, O Lord.'}]},
 'hatteh': {'first': 107,
           'last': 109,
           'chunks': [{'anchor': 'hatteh',
                       'source': 'daniel/9/18',
                       'he': 'הַטֵּה אֱלֹהַי אָזְנְךָ וּשְׁמָע; פְּקַח עֵינֶֽיךָ וּרְאֵה שׁוֹמְמוֹתֵֽינוּ, '
                             'וְהָעִיר אֲשֶׁר נִקְרָא שִׁמְךָ עָלֶֽיהָ; כִּי לֹא עַל צִדְקוֹתֵֽינוּ '
                             'אֲנַֽחְנוּ מַפִּילִים תַּחֲנוּנֵֽינוּ לְפָנֶֽיךָ, כִּי עַל רַחֲמֶֽיךָ '
                             'הָרַבִּים. ',
                       'en': 'Bend thy ear, my God, and hear; open thy eyes and see our ruins, and the city '
                             'which is called by thy name. Indeed, it is not because of our own '
                             'righteousness that we plead before thee, but because of thy great mercy. '},
                      {'anchor': 'adonai_shemaah',
                       'source': 'daniel/9/19',
                       'he': 'אֲדֹנָי, שְׁמָֽעָה; אֲדֹנָי, סְלָֽחָה; אֲדֹנָי, הַקְשִֽׁיבָה וַעֲשֵׂה, אַל '
                             'תְּאַחַר, לְמַעַנְךָ אֱלֹהַי, כִּי שִׁמְךָ נִקְרָא עַל עִירְךָ וְעַל '
                             'עַמֶּֽךָ. ',
                       'en': 'O Lord, hear; O Lord, forgive; O Lord, listen and take action, do not delay, '
                             'for thy own sake, my God; for thy city and thy people are called by thy '
                             'name. '},
                      {'anchor': 'avinu',
                       'source': None,
                       'he': 'אָבִֽינוּ הָאָב הָרַחֲמָן, הַרְאֵֽנוּ אוֹת לְטוֹבָה וְקַבֵּץ נְפוּצוֹתֵֽינוּ '
                             'מֵאַרְבַּע כַּנְפוֹת הָאָרֶץ; יַכִּירוּ וְיֵדְעוּ כָּל הַגּוֹיִם כִּי אַתָּה '
                             'יְיָ אֱלֹהֵֽינוּ. ',
                       'en': 'Our Father, merciful Father, show us a sign for happiness, and gather our '
                             'dispersed from the four corners of the earth; let all the nations realize and '
                             'know that thou art the Lord our God. '},
                      {'anchor': 'veattah',
                       'source': 'isaiah/64/7',
                       'he': 'וְעַתָּה יְיָ, אָבִֽינוּ אָֽתָּה; אֲנַֽחְנוּ הַחֹֽמֶר וְאַתָּה יוֹצְרֵֽנוּ, '
                             'וּמַעֲשֵׂה יָדְךָ כֻּלָּֽנוּ. ',
                       'en': 'And now, O Lord, thou art our Father; we are the clay, and thou art our '
                             'potter; all of us are the work of thy hands. '},
                      {'anchor': 'hoshienu',
                       'source': None,
                       'he': 'הוֹשִׁיעֵֽנוּ לְמַֽעַן שְׁמֶֽךָ, צוּרֵֽנוּ, מַלְכֵּֽנוּ וְגוֹאֲלֵֽנוּ. ',
                       'en': 'Save us for thy name’s sake, our Stronghold, our King, our Redeemer. '},
                      {'anchor': 'chusah',
                       'source': 'joel/2/17',
                       'he': 'חֽוּסָה יְיָ עַל עַמֶּֽךָ, וְאַל תִּתֵּן נַחֲלָתְךָ לְחֶרְפָּה לִמְשָׁל־בָּם '
                             'גּוֹיִם; לָֽמָּה יֹאמְרוּ בָעַמִּים אַיֵּה אֱלֹהֵיהֶם. ',
                       'en': 'Spare thy people, O Lord, and let not thy heritage be an object of contempt, a '
                             'byword among nations. Why should it be said among the peoples: “Where is their '
                             'God?” '},
                      {'anchor': 'yadanu',
                       'source': None,
                       'he': 'יָדַֽעְנוּ כִּי חָטָֽאנוּ, וְאֵין מִי יַעֲמֹד בַּעֲדֵֽנוּ; שִׁמְךָ הַגָּדוֹל '
                             'יַעֲמָד־לָֽנוּ בְּעֵת צָרָה. יָדַֽעְנוּ כִּי אֵין בָּֽנוּ מַעֲשִׂים; צְדָקָה '
                             'עֲשֵׂה עִמָּֽנוּ לְמַֽעַן שְׁמֶֽךָ. כְּרַחֵם אָב עַל בָּנִים, כֵּן תְּרַחֵם '
                             '{pb:109}יְיָ עָלֵֽינוּ, וְהוֹשִׁיעֵֽנוּ לְמַֽעַן שְׁמֶךָ. חֲמוֹל עַל עַמֶּֽךָ, '
                             'רַחֵם עַל נַחֲלָתֶֽךָ, חֽוּסָה נָּא כְּרֹב רַחֲמֶֽיךָ, חָנֵּֽנוּ וַעֲנֵֽנוּ, '
                             'כִּי לְךָ יְיָ הַצְּדָקָה, עֹשֵׂה נִפְלָאוֹת בְּכָל עֵת.',
                       'en': 'We know that we have sinned, and there is none to stand up for us, so let thy '
                             'great name protect us in time of trouble; we know that we have no merits, so '
                             'deal with us charitably for thy name’s sake. As a father has compassion on his '
                             'children, so, O Lord, have compassion on us, and save us for thy '
                             '{pb:110}name’s sake. Have compassion on thy people; have mercy on thy '
                             'heritage; spare us in thy great mercy; take pity on us and answer us, for '
                             'righteousness is thine, O Lord, who doest wonders at all times.'}]},
 'habbet_na': {'he': 'הַבֶּט־נָא, רַחֶם־נָא עַל עַמְּךָ מְהֵרָה לְמַֽעַן שְׁמֶךָ. בְּרַחֲמֶֽיךָ הָרַבִּים, '
                    'יְיָ אֱלֹהֵֽינוּ, חוּס וְרַחֵם וְהוֹשִֽׁיעָה צֹאן מַרְעִיתֶֽךָ, וְאַל יִמְשָׁל־בָּֽנוּ '
                    'קֶֽצֶף, כִּי לְךָ עֵינֵֽינוּ תְלוּיוֹת; הוֹשִׁיעֵֽנוּ לְמַֽעַן שְׁמֶֽךָ. רַחֵם '
                    'עָלֵֽינוּ לְמַֽעַן בְּרִיתֶֽךָ; הַבִּֽיטָה וַעֲנֵֽנוּ בְּעֵת צָרָה, כִּי לְךָ יְיָ '
                    'הַיְשׁוּעָה, בְּךָ תוֹחַלְתֵּֽנוּ, אֱלֽוֹהַּ סְלִיחוֹת. אָֽנָּא, סְלַח נָא, אֵל טוֹב '
                    'וְסַלָּח, כִּי אֵל מֶֽלֶךְ חַנּוּן וְרַחוּם אַתָּה.',
              'en': 'O look down and speedily have mercy on thy people for the sake of thy name; in thy '
                    'great compassion, Lord our God, mercifully spare and save thy own flock; let no wrath '
                    'prevail against us, for our eyes are lifted to thee; save us for thy name’s sake. Have '
                    'mercy on us for the sake of thy covenant; look down and answer us in time of distress, '
                    'for salvation is thine, O Lord; our hope rests with thee, God of forgiveness. O '
                    'forgive, beneficent and forgiving God, for thou art a gracious and merciful God and '
                    'King.',
              'first': 109,
              'last': 109},
 'anna_melekh': {'he': 'אָֽנָּא, מֶֽלֶךְ חַנּוּן וְרַחוּם, זְכוֹר וְהַבֵּט לִבְרִית בֵּין הַבְּתָרִים, '
                      'וְתֵרָאֶה לְפָנֶֽיךָ עֲקֵדַת יָחִיד לְמַֽעַן יִשְׂרָאֵל. אָבִֽינוּ מַלְכֵּֽנוּ, '
                      'חָנֵּֽנוּ וַעֲנֵֽנוּ, כִּי שִׁמְךָ הַגָּדוֹל נִקְרָא עָלֵֽינוּ; עֹשֵׂה נִפְלָאוֹת '
                      'בְּכָל עֵת, עֲשֵׂה עִמָּֽנוּ כְּחַסְדֶּֽךָ; חַנּוּן וְרַחוּם, הַבִּֽיטָה וַעֲנֵֽנוּ '
                      'בְּעֵת צָרָה, כִּי לְךָ יְיָ הַיְשׁוּעָה. אָבִֽינוּ מַלְכֵּֽנוּ, מַחֲסֵֽנוּ, אַל '
                      'תַּֽעַשׂ עִמָּֽנוּ כְּרֹֽעַ מַעֲלָלֵֽינוּ. זְכֹר רַחֲמֶֽיךָ יְיָ, וַחֲסָדֶֽיךָ, '
                      'וּכְרֹב טוּבְךָ הוֹשִׁיעֵֽנוּ, וַחֲמָל־נָא עָלֵֽינוּ, כִּי אֵין לָֽנוּ אֱלֽוֹהַּ '
                      'אַחֵר מִבַּלְעָדֶֽיךָ. צוּרֵֽנוּ, אַל תַּעַזְבֵֽנוּ; יְיָ אֱלֹהֵֽינוּ, אַל תִּרְחַק '
                      'מִמֶּֽנּוּ; כִּי נַפְשֵֽׁנוּ קְצָרָה מֵחֶֽרֶב וּמִשְּׁבִי, וּמִדֶּֽבֶר וּמִמַּגֵּפָה, '
                      'וּמִכָּל צָרָה וְיָגוֹן. הַצִּילֵֽנוּ, כִּי לְךָ קִוִּֽינוּ, וְאַל תַּכְלִימֵֽנוּ, '
                      'יְיָ אֱלֹהֵֽינוּ; וְהָאֵר פָּנֶֽיךָ בָּֽנוּ, וּזְכָר־לָֽנוּ אֶת בְּרִית אֲבוֹתֵֽינוּ, '
                      'וְהוֹשִׁיעֵֽנוּ לְמַֽעַן שְׁמֶֽךָ. רְאֵה בְצָרוֹתֵֽינוּ, וּשְׁמַע קוֹל '
                      'תְּפִלָּתֵֽנוּ, כִּי אַתָּה שׁוֹמֵֽעַ תְּפִלַּת כָּל פֶּה.',
                'en': 'O gracious and merciful King, remember thy covenant with Abraham; let the attempted '
                      'sacrifice of his only son appear before thee for Israel’s sake. Our Father, our King, '
                      'be gracious to us and answer us, for we bear thy great name; thou who doest wonders '
                      'at all times, deal with us according to thy kindness. Thou who art gracious and '
                      'merciful, look down and answer us in time of distress, for salvation is thine, O '
                      'Lord. Our Father, our King, our Refuge, deal not with us according to our evil deeds; '
                      'remember, O Lord, thy mercy and thy kindness; save us, in thy great goodness, and '
                      'have compassion on us, for we have no other God besides thee. Our Rock, forsake us '
                      'not; Lord our God, be not far from us; for we are exhausted from war and captivity, '
                      'pestilence and plague, and from every trouble and sorrow. Rescue us, for thou art our '
                      'hope; put us not to shame, Lord our God; let thy favor shine upon us; remember the '
                      'covenant of our fathers, and save us for thy name’s sake. Look at our troubles, and '
                      'hear the voice of our prayer, for thou hearest the prayer of every mouth.',
                'first': 109,
                'last': 109},
 'el_rachum': {'he': 'אֵל רַחוּם וְחַנּוּן, רַחֵם עָלֵֽינוּ וְעַל כָּל מַעֲשֶֽׂיךָ, כִּי אֵין כָּמֽוֹךָ, '
                     'יְיָ אֱלֹהֵֽינוּ. אָֽנָּא, שָׂא נָא פְשָׁעֵֽינוּ, אָבִינוּ מַלְכֵּֽנוּ, צוּרֵֽנוּ '
                     'וְגוֹאֲלֵֽנוּ, אֵל חַי וְקַיָּם, הַחֲסִין כֹּֽחַ, חָסִיד וָטוֹב עַל כָּל מַעֲשֶֽׂיךָ, '
                     'כִּי אַתָּה הוּא יְיָ אֱלֹהֵֽינוּ. אֵל אֶֽרֶךְ אַפַּֽיִם וּמָלֵא רַחֲמִים, עֲשֵׂה '
                     'עִמָּֽנוּ {pb:111}כְּרֹב רַחֲמֶֽיךָ, וְהוֹשִׁיעֵֽנוּ לְמַֽעַן שְׁמֶֽךָ. שְׁמַע '
                     'מַלְכֵּֽנוּ תְּפִלָּתֵֽנוּ, וּמִיַּד אוֹיְבֵֽינוּ הַצִּילֵֽנוּ; שְׁמַע מַלְכֵּֽנוּ '
                     'וּתְפִלָּתֵֽנוּ, וּמִכָּל צָרָה וְיָגוֹן הַצִּילֵֽנוּ. אָבִֽינוּ מַלְכֵּֽנוּ אַתָּה, '
                     'וְשִׁמְךָ עָלֵֽינוּ נִקְרָא, אַל תַּנִּיחֵֽנוּ. אַל תַּעַזְבֵֽנוּ אָבִֽינוּ, וְאַל '
                     'תִּטְּשֵֽׁנוּ בּוֹרְאֵֽנוּ, וְאַל תִּשְׁכָּחֵֽנוּ יוֹצְרֵֽנוּ, כִּי אֵל מֶֽלֶךְ '
                     'חַנּוּן וְרַחוּם אָֽתָּה.',
               'en': 'Merciful and gracious God, have compassion on us and on all that thou hast made, for '
                     'there is none like thee, Lord our God. O forgive our transgressions, our Father, our '
                     'King, our Rock and Redeemer, thou everlasting and almighty God, who art kind and good '
                     'to all that thou hast made; truly, thou art the Lord our God. O God, who art slow to '
                     'anger and full of compassion, deal with us {pb:112}in thy great mercy, and save us for '
                     'the sake of thy name. Hear our prayer, O our King, and deliver us from the hand of our '
                     'enemies; hear our prayer, O our King, and save us from all trouble and sorrow. Thou '
                     'art our Father, our King, and we bear thy name, desert us not. Forsake us not, our '
                     'Father; abandon us not, our Creator; forget us not, our Maker; for thou art a gracious '
                     'and merciful God and King.',
               'first': 109,
               'last': 111},
 'ein_kamokha': {'he': 'אֵין כָּמֽוֹךָ חַנּוּן וְרַחוּם, יְיָ אֱלֹהֵֽינוּ; אֵין כָּמֽוֹךָ אֵל אֶֽרֶךְ '
                       'אַפַּֽיִם וְרַב חֶֽסֶד וֶאֶמֶת. הוֹשִׁיעֵֽנוּ בְּרַחֲמֶֽיךָ הָרַבִּים; מֵרַֽעַשׁ '
                       'וּמֵרֹֽגֶז הַצִּילֵֽנוּ. זְכוֹר לַעֲבָדֶֽיךָ, לְאַבְרָהָם לְיִצְחָק וּלְיַעֲקֹב; אַל '
                       'תֵּֽפֶן אֶל קָשְׁיֵֽנוּ וְאֶל רִשְׁעֵֽנוּ וְאֶל חַטָּאתֵֽנוּ. שׁוּב מֵחֲרוֹן '
                       'אַפֶּֽךָ, וְהִנָּחֵם עַל הָרָעָה לְעַמֶּֽךָ, וְהָסֵר מִמֶּֽנּוּ מַכַּת הַמָּֽוֶת, '
                       'כִּי רַחוּם אָֽתָּה; כִּי כָךְ דַּרְכֶּֽךָ, עֹֽשֶׂה חֶֽסֶד חִנָּם בְּכָל דוֹר '
                       'וָדוֹר. חֽוּסָה יְיָ עַל עַמֶּֽךָ, וְהַצִּילֵֽנוּ מִזַּעְמֶֽךָ; וְהָסֵר מִמֶּֽנּוּ '
                       'מַכַּת הַמַּגֵּפָה וּגְזֵרָה קָשָׁה, כִּי אַתָּה שׁוֹמֵר יִשְׂרָאֵל. לְךָ אֲדֹנָי '
                       'הַצְּדָקָה, וְלָֽנוּ בֹּֽשֶׁת הַפָּנִים. מַה נִּתְאוֹנֵן, מַה נֹּאמַר, מַה '
                       'נְּדַבֵּר, וּמַה נִּצְטַדָּק. נַחְפְּשָׂה דְרָכֵֽינוּ וְנַחְקֹֽרָה וְנָשֽׁוּבָה '
                       'אֵלֶֽיךָ, כִּי יְמִינְךָ פְשׁוּטָה לְקַבֵּל שָׁבִים. אָנָּא, יְיָ, הוֹשִֽׁיעָה נָּא; '
                       'אָנָּא, יְיָ, הַצְלִיחָה נָא. אָנָּא, יְיָ, עֲנֵֽנוּ בְיוֹם קָרְאֵֽנוּ. לְךָ יְיָ '
                       'חִכִּֽינוּ, לְךָ יְיָ קִוִּֽינוּ, לְךָ יְיָ נְיַחֵל, אַל תֶּחֱשֶׁה וּתְעַנֵּֽנוּ, '
                       'כִּי נָאֲמוּ גוֹיִם אָבְדָה תִקְוָתָם. לְךָ תִּכְרַע כָּל בֶּֽרֶךְ וְכָל קוֹמָה לְךָ '
                       'לְבַד תִּשְׁתַּחֲוֶה.',
                 'en': 'There is none gracious and merciful like thee, Lord our God; there is none like '
                       'thee, a God slow to anger and rich in kindness and truth. Save us in thy great '
                       'mercy; deliver us from storm and rage. Remember thy servants Abraham, Isaac and '
                       'Jacob; consider not our stubbornness, our wickedness and sinfulness. Turn from thy '
                       'fierce anger, and change thy mind about doing evil to thy people. Remove from us the '
                       'scourge of death, for thou art merciful, for such is thy way—showing undeserved '
                       'kindness in every generation. Spare thy people, O Lord, and deliver us from thy '
                       'wrath; remove from us the scourge of plague and cruel persecution, for thou art the '
                       'guardian of Israel. Righteousness is thine, O Lord, and confusion is ours. How can '
                       'we complain? What can we say? What can we urge? How can we justify ourselves? Let us '
                       'search and examine our ways and return to thee, for thy right hand is stretched out '
                       'to receive those who repent.{p}O Lord, save us; O Lord, make us prosper; O Lord, '
                       'answer us when we call. For thee, O Lord, we wait; for thee, O Lord, we hope; in '
                       'thee, O Lord, we trust; afflict us not by thy silence, for the nations say: “Their '
                       'hope is lost.” To thee alone everyone shall bend the knee and bow down.',
                 'first': 111,
                 'last': 111},
 'hapoteach': {'he': 'הַפּוֹתֵחַ יָד בִּתְשׁוּבָה לְקַבֵּל פּוֹשְׁעִים וְחַטָּאִים, נִבְהֲלָה נַפְשֵֽׁנוּ '
                     'מֵרֹב עִצְּבוֹנֵֽנוּ, אַל תִּשְׁכָּחֵֽנוּ נֶֽצַח; קֽוּמָה וְהוֹשִׁיעֵֽנוּ, כִּי '
                     'חָסִֽינוּ בָךְ. אָבִֽינוּ מַלְכֵּֽנוּ, אִם אֵין בָּֽנוּ צְדָקָה וּמַעֲשִׂים טוֹבִים, '
                     'זְכָר־לָֽנוּ אֶת־בְּרִית אֲבוֹתֵֽינוּ וְעֵדוּתֵֽנוּ בְּכָל יוֹם יְיָ אֶחָד. הַבִּֽיטָה '
                     'בְעָנְיֵֽנוּ, כִּי רַבּֽוּ מַכְאוֹבֵֽינוּ וְצָרוֹת לְבָבֵֽנוּ. חֽוּסָה יְיָ עָלֵֽינוּ '
                     'בְּאֶֽרֶץ שִׁבְיֵֽנוּ, וְאַל תִּשְׁפּוֹךְ חֲרוֹנְךָ עָלֵֽינוּ, כִּי אֲנַֽחְנוּ עַמְּךָ '
                     'בְּנֵי בְרִיתֶֽךָ. {pb:113}אֵל, הַבִּֽיטָה, דַּל כְּבוֹדֵֽנוּ בַּגּוֹיִם; '
                     'וְשִׁקְּצֽוּנוּ כְּטֻמְאַת הַנִּדָּה. עַד מָתַי עֻזְּךָ בַּשְׁבִי, וְתִפְאַרְתְּךָ '
                     'בְּיַד צָר. עוֹרְרָה גְבוּרָתְךָ וְקִנְאָתְךָ עַל אוֹיְבֶֽיךָ; הֵם יֵבֽוֹשׁוּ '
                     'וְיֵחַֽתּוּ מִגְּבוּרָתָם, וְאַל יִמְעֲטוּ לְפָנֶֽיךָ תְּלָאוֹתֵֽינוּ. מַהֵר '
                     'יְקַדְּמֽוּנוּ רַחֲמֶֽיךָ בְּיוֹם צָרָתֵֽנוּ; וְאִם לֹא לְמַעֲנֵֽנוּ, לְמַעַנְךָ '
                     'פְעַל, וְאַל תַּשְׁחִית זֵֽכֶר שְׁאֵרִיתֵֽנוּ. {reader} וְחֹן אֹם הַמְיַחֲדִים שִׁמְךָ '
                     'פַּעֲמַֽיִם בְּכָל יוֹם תָּמִיד בְּאַהֲבָה, וְאוֹמְרִים: שְׁמַע יִשְׂרָאֵל, יְיָ '
                     'אֱלֹהֵֽינוּ, יְיָ אֶחָֽד.',
               'en': 'O thou who openest thy hand to receive [repentant] transgressors and sinners—our soul '
                     'is crushed by our great sorrow—forget us not forever; arise and save us, for we trust '
                     'in thee. Our Father, our King, though we be without righteousness and good deeds, '
                     'remember in our favor the covenant of our fathers and our daily testimony: “The Lord '
                     'is One.” Look at our plight, for our pangs and miseries of heart are numerous. Have '
                     'pity on us, O Lord, in the land of our captivity; pour not out thy anger on us, for we '
                     'are thy people, thy people of the covenant. O God, look! {pb:114}Our glory has waned '
                     'among the nations; they utterly detest us. How long shall thy glory remain in '
                     'captivity, and thy splendor in the hand of the foe? Arouse thy might and thy zeal '
                     'against thy enemies, that they may be put to shame and crushed despite their power; '
                     'let not our sufferings seem trivial to thee. May thy compassion hasten to our aid in '
                     'the day of our trouble; if not for our sake, act for thy own sake, and destroy not our '
                     'mere remnant. Be gracious to a people, who fervently proclaim thy Oneness twice a day, '
                     'saying: “Hear, O Israel, the Lord is our God, the Lord is One.”',
               'first': 111,
               'last': 113},
 'adonai_elohei': {'he': 'יְיָ אֱלֹהֵי יִשְׂרָאֵל, שׁוּב מֵחֲרוֹן אַפֶּֽךָ, וְהִנָּחֵם עַל הָרָעָה '
                         'לְעַמֶּֽךָ.',
                   'en': 'Lord God of Israel, turn from thy fierce anger, and change thy mind about doing '
                         'evil to thy people.',
                   'first': 113,
                   'last': 115},
 'habbet_mishamayim': {'he': 'הַבֵּט מִשָּׁמַֽיִם וּרְאֵה, כִּי הָיִֽינוּ לַֽעַג וָקֶֽלֶס בַּגּוֹיִם, '
                            'נֶחְשַֽׁבְנוּ כְּצֹאן לָטֶֽבַח יוּבָל, לַהֲרוֹג וּלְאַבֵּד וּלְמַכָּה '
                            'וּלְחֶרְפָּה.',
                      'en': 'Look down from heaven and see how we have become an object of contempt and '
                            'derision among the nations; we are counted as sheep led to the slaughter, to be '
                            'slain and destroyed, or be beaten and disgraced.',
                      'first': 113,
                      'last': 113},
 'uvekhol': {'he': 'וּבְכָל זֹאת שִׁמְךָ לֹא שָׁכָֽחְנוּ; נָא אַל תִּשְׁכָּחֵֽנוּ.',
             'en': 'Yet, despite all this, we have not forgotten thy name; O forget us not.',
             'first': 115,
             'last': 115},
 'zarim': {'he': 'זָרִים אוֹמְרִים אֵין תּוֹחֶֽלֶת וְתִקְוָה; חֹן אֹם לְשִׁמְךָ מְקַוֶּה. טָהוֹר, '
                 'יְשׁוּעָתֵֽנוּ קָרְבָה; יָגַֽעְנוּ וְלֹא הֽוּנַח לָֽנוּ. רַחֲמֶֽיךָ יִכְבְּשׁוּ אֶת '
                 'כַּעַסְךָ מֵעָלֵֽינוּ.',
           'en': 'Strangers say to us: “There is no hope for you.” Be gracious to a people that yearns for '
                 'thy name. Pure One, hasten our salvation; we are worn out, and no rest is granted us. May '
                 'thy mercy hold back thy anger from us.',
           'first': 115,
           'last': 115},
 'anna_shuv': {'he': 'אָנָּא, שׁוּב מֵחֲרוֹנֶֽךָ, וְרַחֵם סְגֻלָּה אֲשֶׁר בָּחָֽרְתָּ.',
              'en': 'O turn from thy wrath, and have pity on the people thou hast chosen.',
              'first': 115,
              'last': 115},
 'chusah': {'he': 'חֽוּסָה יְיָ עָלֵֽינוּ בְּרַחֲמֶֽיךָ, וְאַל תִּתְּנֵֽנוּ בִּידֵי אַכְזָרִים; לָֽמָּה '
                  'יֹאמְרוּ הַגּוֹיִם אַיֵּה נָא אֱלֹהֵיהֶם. לְמַעַנְךָ עֲשֵׂה עִמָּֽנוּ חֶֽסֶד, וְאַל '
                  'תְּאַחַר.',
            'en': 'Spare us, O Lord, in thy mercy, and deliver us not into the hands of the cruel '
                  'oppressors. Why should the nations say: “Where is their God?” For thy own sake, deal '
                  'kindly with us, and delay not.',
            'first': 115,
            'last': 115},
 'qolenu': {'he': 'קוֹלֵֽנוּ תִשְׁמַע וְתָחֹן, וְאַל תִּטְּשֵֽׁנוּ בְּיַד אוֹיְבֵֽינוּ לִמְחוֹת אֶת '
                  'שְׁמֵֽנוּ. זְכוֹר אֲשֶׁר נִשְׁבַּֽעְתָּ לַאֲבוֹתֵֽינוּ: כְּכוֹכְבֵי הַשָּׁמַֽיִם אַרְבֶּה '
                  'אֶת זַרְעֲכֶם; וְעַתָּה נִשְׁאַֽרְנוּ מְעַט מֵהַרְבֵּה.',
            'en': 'Hear our voice and have pity; leave us not in the power of our enemies to blot out our '
                  'name. Remember that thou hast sworn to our fathers: “I will make your descendants as '
                  'numerous as the stars in the sky”; and now, we are left but a few out of many.',
            'first': 115,
            'last': 115},
 'ozrenu': {'he': 'עָזְרֵֽנוּ, אֱלֹהֵי יִשְׁעֵֽנוּ, עַל דְּבַר כְּבוֹד שְׁמֶֽךָ, וְהַצִּילֵֽנוּ וְכַפֵּר עַל '
                  'חַטֹּאתֵֽינוּ לְמַֽעַן שְׁמֶֽךָ.',
            'en': 'Help us, our saving God, for the sake of thy glorious name; rescue us, and pardon our '
                  'sins for thy name’s sake.',
            'first': 115,
            'last': 115},
 'el_erekh_appayim': {'he': 'אֵל אֶֽרֶךְ אַפַּֽיִם וְרַב חֶֽסֶד וֶאֱמֶת, אַל בְּאַפְּךָ תוֹכִיחֵֽנוּ. חֽוּסָה '
                           'יְיָ עַל עַמֶּֽךָ, וְהוֹשִׁיעֵֽנוּ מִכָּל רָע. חָטָֽאנוּ לָךְ, אָדוֹן; סְלַח נָא '
                           'כְּרֹב רַחֲמֶֽיךָ, אֵל.',
                     'en': 'O God who art slow to anger and abounding in kindness and truth, hide not thy '
                           'face from us. Have pity on thy people, O Lord, and save us from all evil. We '
                           'have sinned against thee, O Lord; forgive us, O God, in thy great mercy.',
                     'first': 117,
                     'last': 117},
 'psalm6': {'first': 103,
            'last': 113,
            'verses': [('2',
                        'יְיָ אַל בְּאַפְּךָ תוֹכִיחֵֽנִי, וְאַל בַּחֲמָתְךָ תְיַסְּרֵֽנִי.',
                        'O Lord, punish me not in thy anger; chastise me not in thy wrath.'),
                       ('3',
                        'חָנֵּֽנִי, יְיָ, כִּי אֻמְלַל אָֽנִי; רְפָאֵֽנִי, יְיָ, כִּי נִבְהֲלוּ עֲצָמָי.',
                        'Have pity on me, O Lord, for I languish away; heal me, O Lord, for my health is '
                        'shaken.'),
                       ('4',
                        'וְנַפְשִׁי נִבְהֲלָה מְאֹד; וְאַתָּה יְיָ, עַד מָתָי.',
                        'My soul is severely troubled; and thou, O Lord, how long?'),
                       ('5',
                        'שׁוּבָה, יְיָ, חַלְּצָה נַפְשִׁי; הוֹשִׁיעֵֽנִי לְמַֽעַן חַסְדֶּֽךָ.',
                        'O Lord, deliver my life once again; save me because of thy grace.'),
                       ('6',
                        'כִּי אֵין בַּמָּֽוֶת זִכְרֶֽךָ; בִּשְׁאוֹל מִי יֽוֹדֶה לָּךְ.',
                        'For in death there is no thought of thee; in the grave who gives thanks to thee?'),
                       ('7',
                        'יָגַֽעְתִּי בְאַנְחָתִי, אַשְׂחֶה בְכָל לַֽיְלָה מִטָּתִי; בְּדִמְעָתִי עַרְשִׂי '
                        'אַמְסֶה.',
                        'I am worn out with my groaning; every night I flood my bed with tears; I cause my '
                        'couch to melt with my weeping.'),
                       ('8',
                        'עָשְׁשָׁה מִכַּֽעַס עֵינִי; עָתְקָה בְּכָל צוֹרְרָי.',
                        'My eye is dimmed from grief; it grows old because of all my foes.'),
                       ('9',
                        'סֽוּרוּ מִמֶּֽנִּי, כָּל פֹּֽעֲלֵי אָֽוֶן, כִּי שָׁמַע יְיָ קוֹל בִּכְיִי.',
                        'Depart from me, all you evildoers, for the Lord has heard the sound of my weeping.'),
                       ('10',
                        'שָׁמַע יְיָ תְּחִנָּתִי; יְיָ תְּפִלָּתִי יִקָּח.',
                        'The Lord has heard my supplication; the Lord receives my prayer.'),
                       ('11',
                        'יֵבֹֽשׁוּ וְיִבָּהֲלוּ מְאֹד כָּל אֹיְבָי; יָשֻֽׁבוּ יֵבֹֽשׁוּ רָֽגַע.',
                        'All my foes shall be utterly ashamed and terrified; they shall turn back; they '
                        'shall be suddenly ashamed.')]}}
