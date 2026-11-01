"""Scan-first paired readings, Birnbaum printed 731–752 (IA n755–n776).

The initial readings, corrections and notes are preserved in sourcetexts.
"""

ROWS = [{'key': 'haderekh',
  'page': 731,
  'en_page': 732,
  'he': 'יְהִי רָצוֹן מִלְפָנֶֽיךָ, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, שֶׁתּוֹלִיכֵֽנוּ לְשָׁלוֹם '
        'וְתַצְעִידֵנוּ לְשָׁלוֹם, וְתַגִּיעֵֽנוּ אֶל מְחוֹז חֶפְצֵֽנוּ לְחַיִּים וּלְשִׂמְחָה וּלְשָׁלוֹם. '
        'וְתַצִּילֵֽנוּ מִכַּף כָּל אוֹיֵב וְאוֹרֵב וְאָסוֹן בַּדֶּֽרֶךְ, וְתִתְּנֵֽנוּ לְחֵן וּלְחֶֽסֶד '
        'וּלְרַחֲמִים בְּעֵינֶֽיךָ וּבְעֵינֵי כָל רוֹאֵֽינוּ. וְתִשְׁמַע קוֹל תַּחֲנוּנֵֽינוּ, כִּי אֵל '
        'שׁוֹמֵֽעַ תְּפִלָּה וְתַחֲנוּן אָֽתָּה. בָּרוּךְ אַתָּה, יְיָ, שׁוֹמֵֽעַ תְּפִלָּה.',
  'en': 'May it be thy will, Lord our God and God of our fathers, to lead us on safely and march us safely, '
        'to guide us safely and bring us to our destination in life, happiness and peace. Deliver us from '
        'every lurking enemy and danger on the road. Let us obtain favor, kindness and love from thee and '
        'from all who see us. Hear our supplication, for thou art God who hearest prayer and supplication. '
        'Blessed art thou, O Lord, who hearest prayer.'},
 {'key': 'haderekh_genesis',
  'page': 731,
  'en_page': 732,
  'he': 'וְיַעֲקֹב הָלַךְ לְדַרְכּוֹ, וַיִּפְגְּעוּ בוֹ מַלְאֲכֵי אֱלֹהִים. וַיֹּֽאמֶר יַעֲקֹב כַּאֲשֶׁר '
        'רָאָם, מַחֲנֵה אֱלֹהִים זֶה; וַיִּקְרָא שֵׁם הַמָּקוֹם הַהוּא מַחֲנָֽיִם.',
  'en': 'Jacob went his way and met the angels of God. On seeing them, Jacob said: “This is God’s camp,” and '
        'he called the name of that place Mahanaim.'},
 {'key': 'haderekh_exodus',
  'page': 731,
  'en_page': 732,
  'he': 'הִנֵּה אָנֹכִי שֹׁלֵֽחַ מַלְאָךְ לְפָנֶֽיךָ, לִשְׁמָרְךָ בַּדָּֽרֶךְ, וְלַהֲבִיאֲךָ אֶל הַמָּקוֹם '
        'אֲשֶׁר הֲכִנֹֽתִי.',
  'en': 'I am sending an angel in front of you, to guard you as you go and to guide you to the place I have '
        'prepared.'},
 {'key': 'haderekh_kohanim',
  'page': 731,
  'en_page': 732,
  'he': 'יְבָרֶכְךָ יְיָ וְיִשְׁמְרֶֽךָ. יָאֵר יְיָ פָּנָיו אֵלֶֽיךָ וִיחֻנֶּֽךָּ. יִשָּׂא יְיָ פָּנָיו '
        'אֵלֶֽיךָ וְיָשֵׂם לְךָ שָׁלוֹם.',
  'en': 'May the Lord bless you and protect you; may the Lord countenance you and be gracious to you; may '
        'the Lord favor you and grant you peace.'},
 {'key': 'haderekh_psalm91',
  'page': 731,
  'en_page': 732,
  'he': 'יֹשֵׁב בְּסֵֽתֶר עֶלְיוֹן, בְּצֵל שַׁדַּי יִתְלוֹנָן. אֹמַר לַיְיָ, מַחְסִי וּמְצוּדָתִי, אֱלֹהַי, '
        'אֶבְטַח־בּוֹ. כִּי הוּא יַצִּילְךָ מִפַּח יָקוּשׁ; מִדֶּֽבֶר הַוּוֹת. בְּאֶבְרָתוֹ יָֽסֶךְ לָךְ, '
        'וְתַֽחַת כְּנָפָיו תֶּחְסֶה; צִנָּה וְסֹחֵרָה אֲמִתּוֹ. לֹא תִירָא מִפַּֽחַד לָֽיְלָה, מֵחֵץ יָעוּף '
        'יוֹמָם. מִדֶּֽבֶר בָּאֹֽפֶל יַהֲלֹךְ, מִקֶּֽטֶב יָשׁוּד צָהֳרָֽיִם. יִפֹּל מִצִּדְּךָ אֶֽלֶף, '
        'וּרְבָבָה מִימִינֶֽךָ; אֵלֶֽיךָ לֹא יִגָּשׁ. רַק בְּעֵינֶֽיךָ תַבִּיט, וְשִׁלֻּמַת רְשָׁעִים '
        'תִּרְאֶה. כִּי אַתָּה יְיָ מַחְסִי; עֶלְיוֹן שַֽׂמְתָּ מְעוֹנֶֽךָ. לֹא תְאֻנֶּה אֵלֶֽיךָ רָעָה, '
        'וְנֶֽגַע לֹא יִקְרַב בְּאָהֳלֶֽךָ. כִּי מַלְאָכָיו יְצַוֶּה־לָּךְ, לִשְׁמָרְךָ בְּכָל '
        '{pb:733}דְּרָכֶֽיךָ. עַל כַּפַּֽיִם יִשָּׂאוּנְךָ, פֶּן תִּגֹּף בָּאֶֽבֶן רַגְלֶֽךָ. עַל שַׁחַל '
        'וָפֶֽתֶן תִּדְרֹךְ, תִּרְמֹס כְּפִיר וְתַנִּין. כִּי בִי חָשַׁק וַאֲפַלְּטֵֽהוּ; אֲשַׂגְּבֵהוּ כִּי '
        'יָדַע שְׁמִי. יִקְרָאֵֽנִי וְאֶעֱנֵֽהוּ; עִמּוֹ אָנֹכִי בְצָרָה; אֲחַלְּצֵֽהוּ וַאֲכַבְּדֵֽהוּ. '
        'אֹֽרֶךְ יָמִים אַשְׂבִּיעֵֽהוּ, וְאַרְאֵֽהוּ בִּישׁוּעָתִי.',
  'en': 'He who dwells in the shelter of the Most High abides under the protection of the Almighty. I call '
        'the Lord “My refuge and my fortress, my God in whom I trust.” He saves you from the fowler’s snare '
        'and from the destructive pestilence. With his pinions he covers you, and under his wings you find '
        'refuge; his truth is a shield and armor. Fear not the terror of the night, nor the arrow that flies '
        'by day, nor the pestilence that stalks in darkness, nor the destruction that ravages at noon. '
        'Though a thousand fall at your side, and a myriad at your right hand, it shall not come to you. You '
        'have only to look with your eyes and see how evil men are punished. Thou, O Lord, art my refuge! '
        'When you have made the Most High your shelter, no disaster shall befall you or come near your tent. '
        'For he will give his angels charge over you, to guard you {pb:734}in all your ways. They will bear '
        'you upon their hands, lest you strike your foot against a stone. You shall tread upon the lion and '
        'the asp; you shall trample the young lion and the serpent. “Because he clings to me, I deliver him; '
        'I protect him because he loves me. When he calls upon me, I answer him; I am with him when he is in '
        'trouble; I rescue him and bring him to honor. I enrich him with long life, and let him witness my '
        'deliverance.”'},
 {'key': 'sick_psalm6',
  'page': 733,
  'en_page': 734,
  'he': 'יְיָ, אַל בְּאַפְּךָ תוֹכִיחֵֽנִי, וְאַל בַּחֲמָתְךָ תְיַסְּרֵֽנִי. חָנֵּֽנִי, יְיָ, כִּי אֻמְלַל '
        'אָֽנִי; רְפָאֵֽנִי, יְיָ, כִּי נִבְהֲלוּ עֲצָמָי. וְנַפְשִׁי נִבְהֲלָה מְאֹד; וְאַתָּה יְיָ, עַד '
        'מָתָי. שׁוּבָה, יְיָ, חַלְּצָה נַפְשִׁי; הוֹשִׁיעֵֽנִי לְמַֽעַן חַסְדֶּֽךָ. כִּי אֵין בַּמָּֽוֶת '
        'זִכְרֶֽךָ; בִּשְׁאוֹל מִי יוֹדֶה לָּךְ. יָגַֽעְתִּי בְאַנְחָתִי, אַשְׂחֶה בְכָל לַֽיְלָה מִטָּתִי; '
        'בְּדִמְעָתִי עַרְשִׂי אַמְסֶה. עָשְׁשָׁה מִכַּֽעַס עֵינִי; עָתְקָה בְּכָל צוֹרְרָי. סֽוּרוּ '
        'מִמֶּֽנִּי, כָּל פֹּֽעֲלֵי אָֽוֶן, כִּי שָׁמַע יְיָ קוֹל בִּכְיִי. שָׁמַע יְיָ תְּחִנָּתִי; יְיָ '
        'תְּפִלָּתִי יִקָּח. יֵבֹֽשׁוּ וְיִבָּהֲלוּ מְאֹד כָּל אֹיְבָי; יָשֻֽׁבוּ יֵבֹֽשׁוּ רָֽגַע.',
  'en': 'O Lord, punish me not in thy anger; chastise me not in thy wrath. Have pity on me, O Lord, for I '
        'languish away; heal me, O Lord, for my health is shaken. My soul is severely troubled; and thou, O '
        'Lord, how long? O Lord, deliver my life once again; save me because of thy grace. For in death '
        'there is no thought of thee; in the grave who gives thanks to thee? I am worn out with my groaning; '
        'every night I flood my bed with tears; I cause my couch to melt with my weeping. My eye is dimmed '
        'from grief; it grows old because of all my foes. Depart from me, all you evildoers; for the Lord '
        'has heard the sound of my weeping. The Lord has heard my supplication; the Lord receives my prayer. '
        'All my foes shall be utterly ashamed and terrified; they shall turn back; they shall be suddenly '
        'ashamed.'},
 {'key': 'sick_psalm23',
  'page': 733,
  'en_page': 734,
  'he': 'מִזְמוֹר לְדָוִד. יְיָ רֹעִי, לֹא אֶחְסָר. בִּנְאוֹת דֶּֽשֶׁא יַרְבִּיצֵֽנִי, עַל מֵי מְנֻחוֹת '
        'יְנַהֲלֵֽנִי. נַפְשִׁי יְשׁוֹבֵב, יַנְחֵֽנִי בְמַעְגְּלֵי צֶֽדֶק לְמַֽעַן שְׁמוֹ. גַּם כִּי אֵלֵךְ '
        'בְּגֵיא צַלְמָֽוֶת לֹא אִירָא רָע, כִּי אַתָּה עִמָּדִי; שִׁבְטְךָ וּמִשְׁעַנְתֶּֽךָ, הֵֽמָּה '
        'יְנַחֲמֻֽנִי. תַּעֲרֹךְ לְפָנַי שֻׁלְחָן נֶֽגֶד צֹרְרָי; דִּשַּֽׁנְתָּ בַשֶּֽׁמֶן רֹאשִׁי, כּוֹסִי '
        'רְוָיָה. אַךְ טוֹב וָחֶֽסֶד יִרְדְּפֽוּנִי כָּל יְמֵי חַיָּי; וְשַׁבְתִּי בְּבֵית יְיָ לְאֹֽרֶךְ '
        'יָמִים.',
  'en': 'A psalm of David. The Lord is my shepherd; I am not in want. He makes me lie down in green meadows; '
        'he leads me beside refreshing streams. He restores my life; he guides me by righteous paths for his '
        'own sake. Even though I walk through the darkest valley, I fear no harm; for thou art with me. Thy '
        'rod and thy staff—they comfort me. Thou spreadest a feast for me in the presence of my enemies. '
        'Thou hast perfumed my head with oil; my cup overflows. Only goodness and kindness shall follow me '
        'all the days of my life; I shall dwell in the house of the Lord forever.'},
 {'key': 'sick_refaenu',
  'page': 733,
  'en_page': 734,
  'he': 'רְפָאֵֽנוּ יְיָ וְנֵרָפֵא, הוֹשִׁיעֵֽנוּ וְנִוָּשֵֽׁעָה, כִּי תְהִלָּתֵֽנוּ אָֽתָּה; וְהַעֲלֵה '
        'רְפוּאָה שְׁלֵמָה לְכָל מַכּוֹתֵֽינוּ, כִּי אֵל מֶֽלֶךְ רוֹפֵא נֶאֱמָן וְרַחֲמָן אָֽתָּה. בָּרוּךְ '
        'אַתָּה, יְיָ, רוֹפֵא חוֹלֵי עַמּוֹ יִשְׂרָאֵל.',
  'en': 'Heal us, O Lord, and we shall be healed; save us and we shall be saved; for thou art our praise. '
        'Grant a perfect healing to all our wounds; for thou art a faithful and merciful God, King and '
        'Healer. Blessed art thou, O Lord, who healest the sick among thy people Israel.'},
 {'key': 'tzidduq_1',
  'page': 735,
  'en_page': 736,
  'he': 'הַצּוּר תָּמִים פָּעֳלוֹ, כִּי כָל דְּרָכָיו מִשְׁפָּט; אֵל אֱמוּנָה וְאֵין עָֽוֶל, צַדִּיק '
        'וְיָשָׁר הוּא.',
  'en': 'He is God; what he does is right, for all his ways are just; God of faithfulness and without wrong, '
        'just and right is he.'},
 {'key': 'tzidduq_2',
  'page': 735,
  'en_page': 736,
  'he': 'הַצּוּר תָּמִים בְּכָל פֹּֽעַל, מִי יֹאמַר לוֹ מַה תִּפְעָל; הַשַּׁלִּיט בְּמַֽטָּה וּבְמַֽעַל, '
        'מֵמִית וּמְחַיֶּה, מוֹרִיד שְׁאוֹל וַיָּֽעַל.',
  'en': 'He is God, perfect in every deed; who can say to him: “What art thou doing?” He rules below and '
        'above; he causes death and life; he brings down to the grave and raises up.'},
 {'key': 'tzidduq_3',
  'page': 735,
  'en_page': 736,
  'he': 'הַצּוּר תָּמִים בְּכָל מַעֲשֶׂה, מִי יֹאמַר אֵלָיו מַה תַּעֲשֶׂה; הָאוֹמֵר וְעֹשֶׂה, חֶֽסֶד חִנָּם '
        'לָֽנוּ תַעֲשֶׂה; וּבִזְכוּת הַנֶּעֱקַד כְּשֶׂה, הַקְשִֽׁיבָה וַעֲשֵׂה.',
  'en': 'He is God, perfect in every deed; who can say to him: “What art thou doing?” O thou who decreest '
        'and performest, show us unmerited kindness; for the sake of Isaac who was bound like a lamb, listen '
        'and take action.'},
 {'key': 'tzidduq_4',
  'page': 735,
  'en_page': 736,
  'he': 'צַדִּיק בְּכָל דְּרָכָיו, הַצּוּר תָּמִים, אֶֽרֶךְ אַפַּֽיִם וּמָלֵא רַחֲמִים, חֲמָל־נָא וְחוּס נָא '
        'עַל אָבוֹת וּבָנִים, כִּי לְךָ אָדוֹן הַסְּלִיחוֹת וְהָרַחֲמִים.',
  'en': 'O thou who art righteous in all thy ways, thou who art the perfect God, slow to anger and full of '
        'mercy, have compassion, have pity on parents and children; for thine, O Lord, is forgiveness and '
        'mercy.'},
 {'key': 'tzidduq_5',
  'page': 735,
  'en_page': 736,
  'he': 'צַדִּיק אַתָּה, יְיָ, לְהָמִית וּלְהַחֲיוֹת; אֲשֶׁר בְּיָדְךָ פִּקְדוֹן כָּל רוּחוֹת, חָלִֽילָה '
        'לְךָ זִכְרוֹנֵֽנוּ לִמְחוֹת; וְיִהְיוּ נָא עֵינֶֽיךָ בְּרַחֲמִים עָלֵֽינוּ פְקוּחוֹת, כִּי לְךָ '
        'אָדוֹן הָרַחֲמִים וְהַסְּלִיחוֹת.',
  'en': 'Just art thou, O Lord, in causing death and life; thou in whose hand all living beings are kept, '
        'far be it from thee to blot out our remembrance; let thy eyes be open to us in mercy; for thine, O '
        'Lord, is mercy and forgiveness.'},
 {'key': 'tzidduq_6',
  'page': 735,
  'en_page': 736,
  'he': 'אָדָם אִם בֶּן־שָׁנָה יִחְיֶה, אוֹ אֶֽלֶף שָׁנִים יִחְיֶה, מַה יִתְרוֹן לוֹ; כְּלֹא הָיָה יִהְיֶה; '
        'בָּרוּךְ דַּיַּן הָאֱמֶת, מֵמִית וּמְחַיֶּה.',
  'en': 'Whether one lives a year or a thousand years—what does he gain? He is as though he were '
        'non-existent. Blessed be the true Judge, who causes death and life.'},
 {'key': 'tzidduq_7',
  'page': 735,
  'en_page': 736,
  'he': 'בָּרוּךְ הוּא, כִּי אֱמֶת דִּינוֹ, וּמְשׁוֹטֵט הַכֹּל בְּעֵינוֹ, וּמְשַׁלֵּם לְאָדָם חֶשְׁבּוֹנוֹ '
        'וְדִינוֹ, וְהַכֹּל לִשְׁמוֹ הוֹדָיָה יִתֵּֽנוּ.',
  'en': 'Blessed be he, for his judgment is true; his eye ranges over all, and he punishes and rewards man '
        'according to strict account; all must render acknowledgment to him.'},
 {'key': 'tzidduq_8',
  'page': 737,
  'en_page': 738,
  'he': 'יָדַעְנוּ, יְיָ, כִּי צֶֽדֶק מִשְׁפָּטֶֽךָ, תִּצְדַּק בְּדָבְרֶֽךָ, וְתִזְכֶּה בְּשָׁפְטֶֽךָ, '
        'וְאֵין לְהַרְהֵר אַחַר מִדַּת שָׁפְטֶֽךָ; צַדִּיק אַתָּה, יְיָ, וְיָשָׁר מִשְׁפָּטֶֽךָ.',
  'en': 'We know, O Lord, that thy judgment is just; thou art right when thou speakest, and justified when '
        'thou givest sentence; one must not find fault with thy manner of judging. Thou art righteous, O '
        'Lord, and thy judgment is right.'},
 {'key': 'tzidduq_9',
  'page': 737,
  'en_page': 738,
  'he': 'דַּיַּן אֱמֶת, שׁוֹפֵט צֶֽדֶק וֶאֱמֶת; בָּרוּךְ דַּיַּן הָאֱמֶת, שֶׁכָּל מִשְׁפָּטָיו צֶֽדֶק '
        'וֶאֱמֶת.',
  'en': 'True and righteous Judge, blessed art thou, all whose judgments are righteous and true.'},
 {'key': 'tzidduq_10',
  'page': 737,
  'en_page': 738,
  'he': 'נֶֽפֶשׁ כָּל חַי בְּיָדֶֽךָ, צֶֽדֶק מָלְאָה יְמִינְךָ וְיָדֶֽךָ, רַחֵם עַל פְּלֵיטַת צֹאן יָדֶֽךָ, '
        'וְתֹאמַר לַמַּלְאָךְ הֶֽרֶף יָדֶֽךָ.',
  'en': 'The life of every living being is in thy hand; thy right hand is full of righteousness. Have mercy '
        'on the remnant of thy own flock, and say to the angel: “Stay your hand.”'},
 {'key': 'tzidduq_jeremiah',
  'page': 737,
  'en_page': 738,
  'he': 'גְּדֹל הָעֵצָה וְרַב הָעֲלִילִיָּה, אֲשֶׁר עֵינֶֽיךָ פְקֻחוֹת עַל כָּל דַּרְכֵי בְּנֵי אָדָם, לָתֵת '
        'לְאִישׁ כִּדְרָכָיו וְכִפְרִי מַעֲלָלָיו.',
  'en': 'Thou art great in counsel and mighty in action; thy eyes are open to all the ways of men, to give '
        'to every one according to his conduct and according to the results of his doings.'},
 {'key': 'tzidduq_psalm92',
  'page': 737,
  'en_page': 738,
  'he': 'לְהַגִּיד כִּי יָשָׁר יְיָ; צוּרִי, וְלֹא עַוְלָֽתָה בּוֹ.',
  'en': 'We proclaim that the Lord is just. He is my stronghold, and there is no wrong in him.'},
 {'key': 'tzidduq_job',
  'page': 737,
  'en_page': 738,
  'he': 'יְיָ נָתַן, וַיְיָ לָקָח; יְהִי שֵׁם יְיָ מְבֹרָךְ.',
  'en': 'The Lord gave and the Lord has taken away; blessed be the name of the Lord.'},
 {'key': 'tzidduq_psalm78',
  'page': 737,
  'en_page': 738,
  'he': 'וְהוּא רַחוּם, יְכַפֵּר עָוֹן וְלֹא יַשְׁחִית; וְהִרְבָּה לְהָשִׁיב אַפּוֹ, וְלֹא יָעִיר כָּל '
        'חֲמָתוֹ.',
  'en': 'He being merciful, forgives iniquity and does not destroy; frequently he turns his anger away, and '
        'does not stir up all his wrath.'},
 {'key': 'burial_kaddish_open',
  'page': 737,
  'en_page': 738,
  'he': 'יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ רַבָּא בְּעָלְמָא דְּהוּא עָתִיד לְחַדָּתָא, וּלְאַחֲיָאָה '
        'מֵתַיָּא, וּלְאַסָּקָא יָתְהוֹן לְחַיֵּי עָלְמָא, וּלְמִבְנָא קַרְתָּא דִירוּשְׁלֵם וּלְשַׁכְלָלָא '
        'הֵיכְלֵהּ בְּגַוַּהּ, וּלְמֶעְקַר פֻּלְחָנָא נֻכְרָאָה מִן אַרְעָא, וְלַאֲתָבָא פֻּלְחָנָא '
        'דִּשְׁמַיָּא לְאַתְרֵהּ. וְיִמְלֹךְ קֻדְשָׁא בְּרִיךְ הוּא בְּמַלְכוּתֵהּ וִיקָרֵהּ בְּחַיֵּיכוֹן '
        'וּבְיוֹמֵיכוֹן וּבְחַיֵּי דְכָל בֵּית יִשְׂרָאֵל, בַּעֲגָלָא וּבִזְמַן קָרִיב, וְאִמְרוּ אָמֵן.',
  'en': 'Glorified and sanctified be God’s great name throughout the world which he will renew, reviving the '
        'dead and raising them to life eternal; rebuilding the city of Jerusalem and establishing his shrine '
        'therein; uprooting idolatry from the earth and restoring divine worship to its site. May the Holy '
        'One, blessed be he, reign in his majestic glory in your lifetime and during your days, and within '
        'the life of the entire house of Israel, speedily and soon; and say, Amen.'},
 {'key': 'burial_kaddish_response',
  'page': 739,
  'en_page': 740,
  'he': 'יְהֵא שְׁמֵהּ רַבָּא מְבָרַךְ לְעָלַם וּלְעָלְמֵי עָלְמַיָּא.',
  'en': 'May his great name be blessed forever and to all eternity.'},
 {'key': 'burial_kaddish_praise',
  'page': 739,
  'en_page': 740,
  'he': 'יִתְבָּרַךְ וְיִשְׁתַּבַּח, וְיִתְפָּאַר וְיִתְרוֹמָם, וְיִתְנַשֵּׂא וְיִתְהַדָּר, וְיִתְעַלֶּה '
        'וְיִתְהַלָּל שְׁמֵהּ דְּקֻדְשָׁא, בְּרִיךְ הוּא, לְעֵֽלָּא מִן כָּל בִּרְכָתָא וְשִׁירָתָא, '
        'תֻּשְׁבְּחָתָא וְנֶחֱמָתָא, דַּאֲמִירָן בְּעָלְמָא, וְאִמְרוּ אָמֵן.',
  'en': 'Blessed and praised, glorified and exalted, extolled and honored, adored and lauded be the name of '
        'the Holy One, blessed be he, beyond all the blessings and hymns, praises and consolations that are '
        'ever spoken in the world; and say, Amen.'},
 {'key': 'burial_kaddish_peace',
  'page': 739,
  'en_page': 740,
  'he': 'יְהֵא שְׁלָמָא רַבָּא מִן שְׁמַיָּא, וְחַיִּים, עָלֵֽינוּ וְעַל כָּל יִשְׂרָאֵל, וְאִמְרוּ אָמֵן.',
  'en': 'May there be abundant peace from heaven, and life, for us and for all Israel; and say, Amen.'},
 {'key': 'burial_kaddish_oseh',
  'page': 739,
  'en_page': 740,
  'he': 'עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו, הוּא יַעֲשֶׂה שָׁלוֹם עָלֵֽינוּ וְעַל כָּל יִשְׂרָאֵל, וְאִמְרוּ '
        'אָמֵן.',
  'en': 'He who creates peace in his celestial heights, may he create peace for us and for all Israel; and '
        'say, Amen.'},
 {'key': 'burial_leaving',
  'page': 739,
  'en_page': 740,
  'he': 'בִּלַּע הַמָּוֶת לָנֶֽצַח, וּמָחָה אֲדֹנָי אֱלֹהִים דִּמְעָה מֵעַל כָּל פָּנִים; וְחֶרְפַּת עַמּוֹ '
        'יָסִיר מֵעַל כָּל הָאָֽרֶץ, כִּי יְיָ דִּבֵּר.',
  'en': 'He will destroy death forever; the Lord God will wipe away tears from every face, and will remove '
        'from all the earth all insult against his people; for the Lord has spoken.'},
 {'key': 'chapel_144_3',
  'page': 739,
  'en_page': 740,
  'he': 'יְיָ, מָה אָדָם וַתֵּדָעֵֽהוּ, בֶּן־אֱנוֹשׁ וַתְּחַשְּׁבֵֽהוּ.',
  'en': 'O Lord, what is man that thou shouldst notice him?\n'
        'What is mortal man that thou shouldst consider him?'},
 {'key': 'chapel_144_4',
  'page': 739,
  'en_page': 740,
  'he': 'אָדָם לַהֶֽבֶל דָּמָה, יָמָיו כְּצֵל עוֹבֵר.',
  'en': 'Man is like a breath;\nHis days are like a passing shadow.'},
 {'key': 'chapel_90_6',
  'page': 739,
  'en_page': 740,
  'he': 'בַּבֹּֽקֶר יָצִיץ וְחָלָף, לָעֶֽרֶב יְמוֹלֵל וְיָבֵשׁ.',
  'en': 'He flourishes and grows in the morning;\nHe fades and withers in the evening.'},
 {'key': 'chapel_90_12',
  'page': 739,
  'en_page': 740,
  'he': 'לִמְנוֹת יָמֵֽינוּ כֵּן הוֹדַע, וְנָבִא לְבַב חָכְמָה.',
  'en': 'O teach us how to number our days,\nThat we may attain a heart of wisdom.'},
 {'key': 'chapel_37_37',
  'page': 739,
  'en_page': 740,
  'he': 'שְׁמָר־תָּם וּרְאֵה יָשָׁר, כִּי אַחֲרִית לְאִישׁ שָׁלוֹם.',
  'en': 'Mark the innocent, look upon the upright;\nFor there is a future for the man of peace.'},
 {'key': 'chapel_49_16',
  'page': 739,
  'en_page': 740,
  'he': 'אַךְ אֱלֹהִים יִפְדֶּה נַפְשִׁי מִיַּד שְׁאוֹל, כִּי יִקָּחֵֽנִי סֶֽלָה.',
  'en': 'Surely God will free me from the grave;\nHe will receive me indeed.'},
 {'key': 'chapel_73_26',
  'page': 739,
  'en_page': 740,
  'he': 'כָּלָה שְׁאֵרִי וּלְבָבִי, צוּר לְבָבִי וְחֶלְקִי אֱלֹהִים לְעוֹלָם.',
  'en': 'My flesh and my heart fail,\nYet God is my strength forever.'},
 {'key': 'chapel_ecclesiastes',
  'page': 739,
  'en_page': 740,
  'he': 'וְיָשֹׁב הֶעָפָר עַל הָאָֽרֶץ כְּשֶׁהָיָה, וְהָרֽוּחַ תָּשׁוּב אֶל הָאֱלֹהִים אֲשֶׁר נְתָנָהּ.',
  'en': 'The dust returns to the earth as it was,\nBut the spirit returns to God who gave it.'},
 {'key': 'milah_welcome',
  'page': 741,
  'en_page': 742,
  'he': 'בָּרוּךְ הַבָּא.',
  'en': 'Blessed be he who enters.'},
 {'key': 'milah_ready',
  'page': 741,
  'en_page': 742,
  'he': 'הִנְנִי מוּכָן וּמְזֻמָּן לְקַיֵּם מִצְוַת עֲשֵׂה, שֶׁצִּוָּֽנִי הַבּוֹרֵא יִתְבָּרַךְ, לָמוּל אֶת '
        'בְּנִי, כַּכָּתוּב בַּתּוֹרָה: וּבֶן־שְׁמֹנַת יָמִים יִמּוֹל לָכֶם כָּל זָכָר לְדֹרֹתֵיכֶם.',
  'en': 'I am ready to perform the precept of circumcising my son, as the Creator, blessed be he, has '
        'commanded us in the Torah: “Every male among you, throughout your generations, shall be circumcised '
        'when he is eight days old.”'},
 {'key': 'milah_elijah',
  'page': 741,
  'en_page': 742,
  'he': 'זֶה הַכִּסֵּא שֶׁל אֵלִיָּהוּ זָכוּר לַטּוֹב.',
  'en': 'This is the throne of Elijah, of blessed memory.'},
 {'key': 'milah_verses',
  'page': 741,
  'en_page': 742,
  'he': 'לִישׁוּעָתְךָ קִוִּֽיתִי, יְיָ. שִׂבַּֽרְתִּי לִישׁוּעָתְךָ, יְיָ, וּמִצְוֹתֶֽיךָ עָשִֽׂיתִי. '
        'שִׂבַּֽרְתִּי לִישׁוּעָתְךָ, יְיָ. שָׂשׂ אָנֹכִי עַל אִמְרָתֶֽךָ, כְּמוֹצֵא שָׁלָל רָב. שָׁלוֹם רָב '
        'לְאֹהֲבֵי תוֹרָתֶֽךָ, וְאֵין לָֽמוֹ מִכְשׁוֹל. אַשְׁרֵי תִּבְחַר וּתְקָרֵב, יִשְׁכֹּן חֲצֵרֶֽיךָ—',
  'en': 'O Lord, I hope for thy salvation. I wait for thy deliverance, O Lord, and I do thy bidding. I '
        'delight in thy promise, like one who finds abundant wealth. Abundant peace have they who love thy '
        'Torah, and there is no stumbling for them. Happy is he whom thou choosest to dwell in thy courts, '
        'close to thee.'},
 {'key': 'milah_all',
  'page': 741,
  'en_page': 742,
  'he': 'נִשְׂבְּעָה בְּטוּב בֵּיתֶֽךָ, קְדֹשׁ הֵיכָלֶֽךָ.',
  'en': 'May we fully enjoy the goodness of thy house, thy holy shrine.'},
 {'key': 'milah_blessing',
  'page': 741,
  'en_page': 742,
  'he': 'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֹתָיו וְצִוָּֽנוּ '
        'עַל הַמִּילָה.',
  'en': 'Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, '
        'and commanded us concerning circumcision.'},
 {'key': 'milah_father_blessing',
  'page': 741,
  'en_page': 742,
  'he': 'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֹתָיו וְצִוָּֽנוּ '
        'לְהַכְנִיסוֹ בִּבְרִיתוֹ שֶׁל אַבְרָהָם אָבִֽינוּ.',
  'en': 'Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, '
        'and commanded us to introduce my son into the covenant of Abraham our father.'},
 {'key': 'milah_response',
  'page': 743,
  'en_page': 744,
  'he': 'כְּשֵׁם שֶׁנִּכְנַס לַבְּרִית, כֵּן יִכָּנֵס לְתוֹרָה וּלְחֻפָּה וּלְמַעֲשִׂים טוֹבִים.',
  'en': 'Even as he has been introduced into the covenant, so may he be introduced to the Torah, to the '
        'marriage canopy, and to a life of good deeds.'},
 {'key': 'milah_wine',
  'page': 743,
  'en_page': 744,
  'he': 'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, בּוֹרֵא פְּרִי הַגָּֽפֶן.',
  'en': 'Blessed art thou, Lord our God, King of the universe, who createst the fruit of the vine.'},
 {'key': 'milah_covenant',
  'page': 743,
  'en_page': 744,
  'he': 'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדֵּשׁ יְדִיד מִבֶּֽטֶן, וְחֹק '
        'בִּשְׁאֵרוֹ שָׂם, וְצֶאֱצָאָיו חָתַם בְּאוֹת בְּרִית קֹֽדֶשׁ. עַל כֵּן, בִּשְׂכַר זֹאת, אֵל חַי, '
        'חֶלְקֵֽנוּ צוּרֵֽנוּ, צַוֵּה לְהַצִּיל יְדִידוּת שְׁאֵרֵֽנוּ מִשַּֽׁחַת, לְמַֽעַן בְּרִיתוֹ אֲשֶׁר '
        'שָׂם בִּבְשָׂרֵֽנוּ. בָּרוּךְ אַתָּה, יְיָ, כּוֹרֵת הַבְּרִית.',
  'en': 'Blessed art thou, Lord our God, King of the universe, who didst sanctify beloved Israel from birth, '
        'impressing thy statute in his flesh and marking his descendants with the sign of the holy covenant. '
        'Because of this, for the sake of the covenant thou didst impress in our flesh, O eternal God, our '
        'Stronghold, deliver our dearly beloved from destruction. Blessed art thou, O Lord, Author of the '
        'covenant.'},
 {'key': 'milah_name',
  'page': 743,
  'en_page': 744,
  'he': 'אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, קַיֵּם אֶת הַיֶּֽלֶד הַזֶּה לְאָבִיו וּלְאִמּוֹ, וְיִקָּרֵא '
        'שְׁמוֹ בְּיִשְׂרָאֵל (פלוני בן פלוני). יִשְׂמַח הָאָב בְּיוֹצֵא חֲלָצָיו, וְתָגֵל אִמּוֹ בִּפְרִי '
        'בִטְנָהּ, כַּכָּתוּב: יִשְׂמַח אָבִֽיךָ וְאִמֶּֽךָ, וְתָגֵל יוֹלַדְתֶּֽךָ. וְנֶאֱמַר: וָאֶעֱבֹר '
        'עָלַֽיִךְ וָאֶרְאֵךְ מִתְבּוֹסֶֽסֶת בְּדָמָֽיִךְ, וָאֹֽמַר לָךְ בְּדָמַֽיִךְ חֲיִי; וָאֹֽמַר לָךְ '
        'בְּדָמַֽיִךְ חֲיִי. וְנֶאֱמַר: זָכַר לְעוֹלָם בְּרִיתוֹ, דָּבָר צִוָּה לְאֶֽלֶף דּוֹר. אֲשֶׁר '
        'כָּרַת אֶת אַבְרָהָם, וּשְׁבוּעָתוֹ לְיִשְׂחָק. וַיַּעֲמִידֶֽהָ לְיַעֲקֹב לְחֹק, לְיִשְׂרָאֵל '
        'בְּרִית עוֹלָם. וְנֶאֱמַר: וַיָּֽמָל אַבְרָהָם אֶת יִצְחָק בְּנוֹ בֶּן־שְׁמֹנַת יָמִים, כַּאֲשֶׁר '
        'צִוָּה אֹתוֹ אֱלֹהִים. הוֹדוּ לַיְיָ כִּי טוֹב, כִּי לְעוֹלָם חַסְדּוֹ. זֶה הַקָּטֹן (פלוני) '
        'גָּדוֹל יִהְיֶה. כְּשֵׁם שֶׁנִּכְנַס לַבְּרִית כֵּן יִכָּנֵס לְתוֹרָה וּלְחֻפָּה וּלְמַעֲשִׂים '
        'טוֹבִים.',
  'en': 'Our God and God of our fathers, sustain this child for his father and mother. Let him be called in '
        'Israel . . . son of . . . May both husband and wife rejoice in their offspring, as it is written: '
        '“Let your parents be happy; let your mother thrill with joy.”\n'
        '“I passed by you and saw you weltering in your blood. Live through your blood—I said to you—live '
        'through your blood.”\n'
        '“He remembers his covenant forever, the word which he pledged for a thousand generations, the '
        'covenant he made with Abraham, and his oath to Isaac. He confirmed the same to Jacob as a statute, '
        'to Israel as an everlasting covenant.”\n'
        '“Abraham circumcised his son Isaac when he was eight days old, as God had commanded him.”\n'
        '“Give thanks to the Lord, for he is good; his mercy endures forever.” May this child, named . . ., '
        'become great. Even as he has been introduced into the covenant, so may he be introduced to the '
        'Torah, to the marriage canopy, and to a life of good deeds.'},
 {'key': 'milah_grace_invitation',
  'page': 745,
  'en_page': 746,
  'he': 'רַבּוֹתַי, נְבָרֵךְ.',
  'en': 'Gentlemen, let us say grace.'},
 {'key': 'milah_grace_response',
  'page': 745,
  'en_page': 746,
  'he': 'יְהִי שֵׁם יְיָ מְבֹרָךְ מֵעַתָּה וְעַד עוֹלָם.',
  'en': 'Blessed be the name of the Lord henceforth and forever.'},
 {'key': 'milah_poem_refrain',
  'page': 745,
  'en_page': 746,
  'he': 'נוֹדֶה לְשִׁמְךָ בְּתוֹךְ אֱמוּנָי\nבְּרוּכִים אַתֶּם לַיְיָ.',
  'en': 'We praise his name amidst the faithful;\nMay the Lord’s blessing rest upon you.'},
 {'key': 'milah_poem_1',
  'page': 745,
  'en_page': 746,
  'he': 'בִּרְשׁוּת אֵל אָיוֹם וְנוֹרָא\n'
        'מִשְׂגָּב לְעִתּוֹת בַּצָּרָה\n'
        'אֵל נֶאְזָר בִּגְבוּרָה\n'
        'אַדִּיר בַּמָּרוֹם יְיָ.',
  'en': 'On behalf of the most revered God,\n'
        'Mighty stronghold in times of distress,\n'
        'The God who is girded with power,\n'
        'The Lord majestic in high heaven—'},
 {'key': 'milah_poem_2',
  'page': 745,
  'en_page': 746,
  'he': 'בִּרְשׁוּת הַתּוֹרָה הַקְּדוֹשָׁה\n'
        'טְהוֹרָה הִיא וְגַם פְּרוּשָׁה\n'
        'צִוָּה לָֽנוּ מוֹרָשָׁה\n'
        'מֹשֶׁה עֶֽבֶד יְיָ.',
  'en': 'On behalf of the holy Torah,\n'
        'Which is pure, unmistakably clear,\n'
        'The Torah Moses bequeathed to us,\n'
        'Moses, faithful servant of the Lord—'},
 {'key': 'milah_poem_3',
  'page': 745,
  'en_page': 746,
  'he': 'בִּרְשׁוּת הַכֹּהֲנִים הַלְוִיִּם\n'
        'אֶקְרָא לֵאלֹהֵי הָעִבְרִיִּים\n'
        'אוֹדֶֽנּוּ בְכָל אִיִּים\n'
        'אֲבָרְכָה אֶת יְיָ.',
  'en': 'On behalf of the priests, the Levites,\n'
        'I call to the God of the Hebrews,\n'
        'Singing his praise in all the far lands,\n'
        'Blessing the Eternal at all times.'},
 {'key': 'milah_poem_4',
  'page': 747,
  'en_page': 748,
  'he': 'בִּרְשׁוּת מוֹרַי וְרַבּוֹתַי\n'
        'אֶפְתַּח בְּשִׁיר פִּי וּשְׂפָתַי\n'
        'וְתֹאמַֽרְנָה עַצְמוֹתַי\n'
        'בָּרוּךְ הַבָּא בְּשֵׁם יְיָ.',
  'en': 'On behalf of all those gathered here,\n'
        'I open my lips with a poem,\n'
        'And my entire being does exclaim:\n'
        'Happy he who comes in the Lord’s name.'},
 {'key': 'milah_harachaman_1',
  'page': 747,
  'en_page': 748,
  'he': 'הָרַחֲמָן, הוּא יְבָרֵךְ אֲבִי הַיֶּֽלֶד וְאִמּוֹ\n'
        'וְיִזְכּוּ לְגַדְּלוֹ וּלְחַנְּכוֹ וּלְחַכְּמוֹ;\n'
        'מִיּוֹם הַשְּׁמִינִי וָהָֽלְאָה יֵרָצֶה דָמוֹ\n'
        'וִיהִי יְיָ אֱלֹהָיו עִמּוֹ.',
  'en': 'May God bless this child’s father and mother;\n'
        'May they bring him up and teach him wisdom.\n'
        'Henceforth may his blood win favor for him;\n'
        'May the Lord his God ever be with him.'},
 {'key': 'milah_harachaman_2',
  'page': 747,
  'en_page': 748,
  'he': 'הָרַחֲמָן, הוּא יְבָרֵךְ בַּֽעַל בְּרִית הַמִּילָה\n'
        'אֲשֶׁר שָׂשׂ לַעֲשׂוֹת צֶֽדֶק בְּגִילָה;\n'
        'וִישַׁלֵּם פָּעֳלוֹ וּמַשְׂכֻּרְתּוֹ כְּפוּלָה\n'
        'וְיִתְּנֵֽהוּ לְמַֽעֲלָה לְמָֽעְלָה.',
  'en': 'May God bless the one who served as sandek,\n'
        'And has performed a good deed joyously.\n'
        'May God richly reward his services,\n'
        'And place him ever higher and higher.'},
 {'key': 'milah_harachaman_3',
  'page': 747,
  'en_page': 748,
  'he': 'הָרַחֲמָן, הוּא יְבָרֵךְ רַךְ הַנִּמּוֹל לִשְׁמוֹנָה\n'
        'וְיִהְיוּ יָדָיו וְלִבּוֹ לָאֵל אֱמוּנָה;\n'
        'וְיִזְכֶּה לִרְאוֹת פְּנֵי הַשְּׁכִינָה\n'
        'שָׁלֹשׁ פְּעָמִים בַּשָּׁנָה.',
  'en': 'May God bless this tender child of eight days;\n'
        'May his hands and his heart be firm with God.\n'
        'May he be privileged to make visits\n'
        'To Jerusalem three times every year.'},
 {'key': 'milah_harachaman_4',
  'page': 747,
  'en_page': 748,
  'he': 'הָרַחֲמָן, הוּא יְבָרֵךְ הַמָּל בְּשַׂר הָעָרְלָה\n'
        'וּפָרַע וּמָצַץ דְּמֵי הַמִּילָה;\n'
        'אִישׁ הַיָּרֵא וְרַךְ הַלֵּבָב עֲבוֹדָתוֹ פְּסוּלָה\n'
        'אִם שְׁלָשׁ־אֵֽלֶּה לֹא יַעֲשֶׂה־לָּהּ.',
  'en': 'May God bless him who removed the foreskin,\n'
        'And did fulfill all that had been ordained.\n'
        'One who is faint-hearted must not perform\n'
        'This service which includes three essentials.'},
 {'key': 'milah_harachaman_5',
  'page': 749,
  'en_page': 750,
  'he': 'הָרַחֲמָן, הוּא יִשְׁלַח לָֽנוּ מְשִׁיחוֹ הוֹלֵךְ תָּמִים\n'
        'בִּזְכוּת חַתְנֵי מוּלוֹת דָּמִים;\n'
        'לְבַשֵּׂר בְּשׂוֹרוֹת טוֹבוֹת וְנִחוּמִים\n'
        'לְעַם אֶחָד מְפֻזָּר וּמְפֹרָד בֵּין הָעַמִּים.',
  'en': 'May God send us his faultless Messiah\n'
        'For the sake of our innocent children,\n'
        'To bring good tidings and consolation\n'
        'To a people dispersed among the nations.'},
 {'key': 'milah_harachaman_6',
  'page': 749,
  'en_page': 750,
  'he': 'הָרַחֲמָן, הוּא יִשְׁלַח לָֽנוּ כֹּהֵן צֶֽדֶק אֲשֶׁר לֻקַּח לְעֵילוֹם\n'
        'עַד הוּכַן כִּסְאוֹ כַּשֶּֽׁמֶשׁ וְיַהֲלֹם;\n'
        'וַיָּֽלֶט פָּנָיו בְּאַדַּרְתּוֹ וַיִּגְלֹם\n'
        'בְּרִיתִי הָיְתָה אִתּוֹ הַחַיִּים וְהַשָּׁלוֹם.',
  'en': 'May God send us Elijah the true priest,\n'
        'Concealed till his bright throne be ready,\n'
        'The prophet who wrapped his face in his mantle\n'
        'When God’s covenant was made for life and peace.'},
 {'key': 'pidyon_present',
  'page': 749,
  'en_page': 750,
  'he': 'זֶה בְּנִי בְּכוֹרִי הוּא פֶּֽטֶר רֶֽחֶם לְאִמּוֹ, וְהַקָּדוֹשׁ בָּרוּךְ הוּא צִוָּה לִפְדּוֹתוֹ, '
        'שֶׁנֶּאֱמַר: וּפְדוּיָו מִבֶּן חֹֽדֶשׁ תִּפְדֶּה בְּעֶרְכְּךָ כֶּֽסֶף חֲמֵֽשֶׁת שְׁקָלִים, '
        'בְּשֶֽׁקֶל הַקֹּֽדֶשׁ, עֶשְׂרִים גֵּרָה הוּא. וְנֶאֱמַר: קַדֶּשׁ־לִי כָל בְּכוֹר; פֶּֽטֶר כָּל '
        'רֶֽחֶם בִּבְנֵי יִשְׂרָאֵל, בָּאָדָם וּבַבְּהֵמָה, לִי הוּא.',
  'en': 'This is my first-born son, the first-born of his mother. The Holy One, blessed be he, has commanded '
        'to redeem him, as it is said: “The redemption-price for each first-born son of the age of one month '
        'shall be fixed at five sacred silver shekels at the rate of twenty gerahs.” And it is said: '
        '“Consecrate every first-born to me, whatever is first-born in Israel, of man or beast, since it '
        'belongs to me.”'},
 {'key': 'pidyon_question',
  'page': 751,
  'en_page': 752,
  'he': 'מַאי בָּעִית טְפֵי לִתֵּן לִי, בִּנְךָ בְּכוֹרְךָ שֶׁהוּא פֶּֽטֶר רֶֽחֶם לְאִמּוֹ, אוֹ בָעִית '
        'לִפְדּוֹתוֹ בְּעַד חֲמֵשׁ סְלָעִים, כְּדִמְחֻיַּֽבְתְּ מִדְּאוֹרַיְתָא.',
  'en': 'Do you prefer to give me your first-born son, the first-born of his mother, or would you rather '
        'redeem him for five shekels required by the Torah?'},
 {'key': 'pidyon_answer',
  'page': 751,
  'en_page': 752,
  'he': 'חָפֵץ אֲנִי לִפְדּוֹת אֶת בְּנִי, וְהֵילָךְ דְּמֵי פִדְיוֹנוֹ, כְּדִמְחֻיַּֽבְתִּי מִדְּאוֹרַיְתָא.',
  'en': 'I prefer to redeem my son, and here is his redemption-price required by the Torah.'},
 {'key': 'pidyon_blessing',
  'page': 751,
  'en_page': 752,
  'he': 'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֹתָיו וְצִוָּֽנוּ '
        'עַל פִּדְיוֹן הַבֵּן.',
  'en': 'Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, '
        'and commanded us concerning the redemption of the first-born.'},
 {'key': 'pidyon_shehecheyanu',
  'page': 751,
  'en_page': 752,
  'he': 'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, שֶׁהֶחֱיָֽנוּ וְקִיְּמָֽנוּ וְהִגִּיעָֽנוּ '
        'לַזְּמַן הַזֶּה.',
  'en': 'Blessed art thou, Lord our God, King of the universe, who hast granted us life and sustenance and '
        'permitted us to reach this season.'},
 {'key': 'pidyon_exchange',
  'page': 751,
  'en_page': 752,
  'he': 'זֶה תַּֽחַת זֶה, זֶה חִלּוּף זֶה, זֶה מָחוּל עַל זֶה; וְיִכָּנֵס זֶה הַבֵּן לְחַיִּים, לְתוֹרָה '
        'וּלְיִרְאַת שָׁמָֽיִם. יְהִי רָצוֹן, שֶׁכְּשֵׁם שֶׁנִּכְנַס לְפִדְיוֹן, כֵּן יִכָּנֵס לְתוֹרָה '
        'וּלְחֻפָּה וּלְמַעֲשִׂים טוֹבִים. אָמֵן.',
  'en': 'This instead of that, this in exchange for that, this is given up for that. May this child enjoy a '
        'life of Torah and godliness. Even as he has attained to redemption, so may he attain to the Torah, '
        'to the marriage canopy and to a life of good deeds. Amen.'},
 {'key': 'pidyon_child_blessing',
  'page': 751,
  'en_page': 752,
  'he': 'יְשִׂמְךָ אֱלֹהִים כְּאֶפְרַֽיִם וְכִמְנַשֶּׁה. יְבָרֶכְךָ יְיָ וְיִשְׁמְרֶֽךָ. יָאֵר יְיָ פָּנָיו '
        'אֵלֶֽיךָ וִיחֻנֶּֽךָּ. יִשָּׂא יְיָ פָּנָיו אֵלֶֽיךָ, וְיָשֵׂם לְךָ שָׁלוֹם.',
  'en': 'May God make you like Ephraim and like Manasseh. May the Lord bless you and protect you; may the '
        'Lord countenance you and be gracious to you; may the Lord favor you and grant you peace.'},
 {'key': 'pidyon_closing',
  'page': 751,
  'en_page': 752,
  'he': 'יְיָ שֹׁמְרֶֽךָ, יְיָ צִלְּךָ עַל יַד יְמִינֶֽךָ. כִּי אֹֽרֶךְ יָמִים וּשְׁנוֹת חַיִּים וְשָׁלוֹם '
        'יוֹסִֽיפוּ לָךְ. יְיָ יִשְׁמָרְךָ מִכָּל רָע, יִשְׁמֹר אֶת נַפְשֶֽׁךָ. אָמֵן.',
  'en': 'The Lord guards you; the Lord at your right hand is your shelter. A long and happy life will be '
        'given you. The Lord will guard you from all evil; he will guard your life. Amen.'}]

RUBRICS = {'tzidduq_he': 'Burial service held on days when Taḥanan (page 103) is recited',
 'tzidduq_en': 'Burial service held on days when Taḥanan (page 104) is recited',
 'burial_kaddish': 'Recited after the burial',
 'leaving': 'On leaving the burial ground all wash their hands and say:',
 'chapel_he': 'Add Psalm 23 (page 733).',
 'chapel_en': 'Add Psalm 23 (page 734).',
 'milah_welcome': 'When the child is brought for circumcision, the guests rise and say:',
 'milah_father': 'The father of the child:',
 'milah_seat': 'The Mohel, placing the child upon the sandek’s knees:',
 'all': 'All:',
 'mohel_before': 'The Mohel, before operating:',
 'father_after': 'The father, after the circumcision:',
 'mohel': 'The Mohel:',
 'leader': 'Leader:',
 'company': 'Company, then Leader:',
 'grace_he': 'Grace is continued on page 759.',
 'grace_en': 'Grace is continued on page 760.',
 'insert_he': 'The following is inserted after בעיני אלהים ואדם (page 767).',
 'insert_en': 'The following is inserted after “God and men” (page 768).',
 'pidyon': 'Performed on the thirty-first day after birth. Should the child’s father be a kohen or a Levite, '
           'or the mother the daughter of a kohen or Levite, they are exempt from this duty. If the '
           'thirty-first day falls on a Sabbath or a major festival, the Pidyon ha-Ben is postponed until '
           'the following day.',
 'present': 'Presenting the child to the kohen, the father says:',
 'kohen': 'Kohen:',
 'father': 'Father:',
 'exchange': 'Holding the redemption-money over the child’s head, the kohen says:',
 'hand': 'Placing his hand on the child’s head:'}

NOTES = [{'key': 'haderekh',
  'page': 731,
  'text': 'תפלת הדרך is quoted in the Talmud (Berakhoth 29b).',
  'kind': 'commentary'},
 {'key': 'haderekh_kohanim',
  'page': 732,
  'text': 'Genesis 32:2–3; Exodus 23:20; Numbers 6:24–26.',
  'kind': 'source'},
 {'key': 'sick_psalm6', 'page': 734, 'text': 'Psalm 6.', 'kind': 'source'},
 {'key': 'tzidduq',
  'page': 735,
  'text': 'צדוק הדין, the submission to the justice of the divine judgment, is mentioned in the Talmud '
          '(Abodah Zarah 18a) in connection with the martyrdom of Rabbi Ḥanina ben Teradyon and his family. '
          'Before the execution was carried out by the Romans, Rabbi Ḥanina quoted the biblical verse הצור '
          'תמים פעלו, כי כל דרכיו משפט; his wife continued it: אל אמונה ואין עול, צדיק וישר הוא (Deuteronomy '
          '32:4); and the daughter quoted: גדול העצה ורב העליליה... (Jeremiah 32:19). These passages were '
          'later embodied in the rhymed verses of tsidduk ha-din, the burial service.',
  'kind': 'commentary'},
 {'key': 'tzidduq_1', 'page': 736, 'text': 'Deuteronomy 32:4.', 'kind': 'source'},
 {'key': 'burial_kaddish',
  'page': 737,
  'text': 'קדיש ל(את)חדתא refers to the restoration of the Holy Land. The Sephardic Jews recite this Kaddish '
          'on the fast of Tish‘ah b’Av. Maimonides quotes it as the Kaddish d’Rabbanan, to be recited at the '
          'conclusion of a talmudic discourse; compare Sofrim 19:12.',
  'kind': 'commentary'},
 {'key': 'tzidduq_jeremiah', 'page': 738, 'text': 'Jeremiah 32:19.', 'kind': 'source'},
 {'key': 'tzidduq_psalm92', 'page': 738, 'text': 'Psalm 92:16.', 'kind': 'source'},
 {'key': 'tzidduq_job', 'page': 738, 'text': 'Job 1:21.', 'kind': 'source'},
 {'key': 'tzidduq_psalm78', 'page': 738, 'text': 'Psalm 78:38.', 'kind': 'source'},
 {'key': 'burial_leaving', 'page': 740, 'text': 'Isaiah 25:8.', 'kind': 'source'},
 {'key': 'chapel',
  'page': 740,
  'text': 'Psalms 144:3–4; 90:6,12; 37:37; 49:16; 73:26; Ecclesiastes 12:7.',
  'kind': 'source'},
 {'key': 'milah_welcome',
  'page': 741,
  'text': 'ברוך הבא, the greeting extended to the infant, is at the same time a welcome to Elijah, the '
          '“angel of the covenant” and protector of children, who is said to be the invisible participant at '
          'circumcisions. The word הבא is said to be composed of the initials of הנה בא אליהו and to allude '
          'to the eight-days-old boy to be circumcised (הבא numerically equals eight).',
  'kind': 'commentary'},
 {'key': 'milah_elijah',
  'page': 742,
  'text': 'כסא של אליהו, the special chair reserved for Elijah, is left in position for three days because '
          'the first three days after circumcision are a dangerous period for the child.',
  'kind': 'commentary'},
 {'key': 'milah_ready', 'page': 742, 'text': 'Genesis 17:12.', 'kind': 'source'},
 {'key': 'milah_all', 'page': 742, 'text': 'Genesis 49:18; Psalms 119:162–166; 65:5.', 'kind': 'source'},
 {'key': 'milah_response',
  'page': 743,
  'text': 'כשם שנכנס לברית and the passages which follow are quoted in the Talmud (Shabbath 137b).',
  'kind': 'commentary'},
 {'key': 'milah_elijah',
  'page': 743,
  'text': 'סנדק has been identified with the Greek term “synteknos” denoting literally “with the child.” The '
          'sandek, whose privilege it is to hold the child on his knees during the operation, became known '
          'in medieval times as Gottvater, G’vater (Kwater). At a later period, the title “Kwater” was '
          'conferred upon the person handing the infant to the Mohel.',
  'kind': 'commentary'},
 {'key': 'milah_name',
  'page': 744,
  'text': 'Proverbs 23:25; Ezekiel 16:6; Psalm 105:8–10; Genesis 21:4; Psalm 118:1.',
  'kind': 'source'},
 {'key': 'milah_poem',
  'page': 745,
  'text': 'ברשות, the poetical introduction to grace, dates from the thirteenth century. It is the '
          'composition of an anonymous author.',
  'kind': 'commentary'},
 {'key': 'milah_harachaman',
  'page': 747,
  'text': 'הרחמן, inserted at the closing of grace, is a poem by Rabbi Abraham ben Isaac ha-Kohen who lived '
          'in Germany (eleventh century).',
  'kind': 'commentary'},
 {'key': 'milah_harachaman_4',
  'page': 748,
  'text': 'ידיו אמונה and שלש פעמים בשנה are phrases borrowed from Exodus 17:12; 23:17. איש הירא ורך הלבב is '
          'taken from Deuteronomy 20:8, and אם שלש־אלה לא יעשה לה from Exodus 21:11. חתני מולות דמים is '
          'based upon the expression חתן דמים למולות (Exodus 4:26).',
  'kind': 'commentary'},
 {'key': 'milah_harachaman_6',
  'page': 749,
  'text': 'לקח לעילום refers to Elijah’s translation to heaven (II Kings 2:1–12). The word לעילום (=לעולם) '
          'occurs only once in the Bible (II Chronicles 33:7). The poet chose this word for a double '
          'connotation: eternity and concealment.',
  'kind': 'commentary'},
 {'key': 'milah_harachaman_6',
  'page': 749,
  'text': 'וילט פניו באדרתו ויגלם is a combination of two biblical verses concerning Elijah (I Kings 19:13; '
          'II Kings 2:8).',
  'kind': 'commentary'},
 {'key': 'pidyon',
  'page': 749,
  'text': 'פדיון הבן, the redemption of the first-born son (of the mother), is based on Exodus 13:13 and '
          'Numbers 18:16. Originally, the first-born sons belonged to the service of God. Later, instead of '
          'the first-born of all the tribes, the Levites were chosen for service in connection with the '
          'sanctuary. In return for this, every first-born Israelite was to be redeemed by paying five '
          'shekels to a kohen, descendant of Levi. The two blessings recited by the father are found in '
          'Pesaḥim 121b.',
  'kind': 'commentary'},
 {'key': 'pidyon_present',
  'page': 750,
  'text': 'שקל הקדש may have received its name from the fact that the standard weight of the silver shekel '
          '(=סלע in post-biblical Hebrew) was kept in the Temple. Tradition has it that the sacred shekel '
          'had twice the value of a common shekel.',
  'kind': 'commentary'},
 {'key': 'pidyon_present', 'page': 750, 'text': 'Numbers 18:16; Exodus 13:2.', 'kind': 'source'},
 {'key': 'pidyon_question',
  'page': 751,
  'text': 'מאי בעית טפי, the question in Aramaic asked by the kohen, is quoted by Abudarham in Hebrew: '
          'אֵיזֶה תִרְצֶה יוֹתֵר, בִּנְךָ בְּכוֹרְךָ זֶה אוֹ חֲמֵשׁ סְלָעִים שֶׁנִּתְחַיַּבְתָּ לִפְדּוֹתוֹ.',
  'kind': 'commentary'},
 {'key': 'pidyon',
  'page': 752,
  'text': 'With the Spanish and Portuguese Jews it is customary that the kohen officiating at a '
          'Pidyon-ha-Ben begins by directing several questions to the mother of the child in order to '
          'determine that the child is indeed her first-born; thereupon he makes the following declaration: '
          'זה הבן בכור הוא, והקדוש ברוך הוא צוה לפדותו . . .',
  'kind': 'commentary'},
 {'key': 'pidyon_child_blessing', 'page': 752, 'text': 'Genesis 48:20; Numbers 6:24–26.', 'kind': 'source'},
 {'key': 'pidyon_closing', 'page': 752, 'text': 'Psalm 121:5; Proverbs 3:2; Psalm 121:7.', 'kind': 'source'}]
