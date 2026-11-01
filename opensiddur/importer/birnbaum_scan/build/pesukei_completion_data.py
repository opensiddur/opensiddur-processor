"""Direct readings of printed 57–70 (IA n81–n94), Ashrei through Yishtabach.

Markers retain page turns, printed line breaks and Reader instructions.
The Hebrew-only repetition of Psalm 150:6 has an empty English counterpart.
"""

PASSAGES = {'ashrei_prefix': [('psalms/84/5',
                    'אַשְׁרֵי יוֹשְׁבֵי בֵיתֶֽךָ; עוֹד יְהַלְלֽוּךָ סֶּֽלָה.',
                    'Happy are those who dwell in thy house; they are ever praising thee.'),
                   ('psalms/144/15',
                    'אַשְׁרֵי הָעָם שֶׁכָּֽכָה לּוֹ; אַשְׁרֵי הָעָם שֶׁיְיָ אֱלֹהָיו.',
                    'Happy the people that is so situated; happy the people whose God is the '
                    'Lord.')],
 'psalm_145': [('psalms/145/1',
                'תְּהִלָּה לְדָוִד{lb}אֲרוֹמִמְךָ, אֱלֹהַי הַמֶּֽלֶךְ, וַאֲבָרְכָה שִׁמְךָ '
                'לְעוֹלָם וָעֶד.',
                'A hymn of praise by David.{lb}I extol thee, my God the King,{lb}And bless thy '
                'name forever and ever.'),
               ('psalms/145/2',
                'בְּכָל יוֹם אֲבָרְכֶֽךָּ, וַאֲהַלְלָה שִׁמְךָ לְעוֹלָם וָעֶד.',
                'Every day I bless thee,{lb}And praise thy name forever and ever.'),
               ('psalms/145/3',
                'גָּדוֹל יְיָ וּמְהֻלָּל מְאֹד, וְלִגְדֻלָּתוֹ אֵין חֵֽקֶר.',
                'Great is the Lord and most worthy of praise;{lb}His greatness is unsearchable.'),
               ('psalms/145/4',
                'דּוֹר לְדוֹר יְשַׁבַּח מַעֲשֶֽׂיךָ, וּגְבוּרֹתֶֽיךָ יַגִּֽידוּ.',
                'One generation to another praises thy works;{lb}They recount thy mighty acts.'),
               ('psalms/145/5',
                '{pb:59}הֲדַר כְּבוֹד הוֹדֶֽךָ, וְדִבְרֵי נִפְלְאֹתֶֽיךָ אָשִֽׂיחָה.',
                '{pb:60}On the splendor of thy glorious majesty{lb}And on thy wondrous deeds I '
                'meditate.'),
               ('psalms/145/6',
                'וֶעֱזוּז נוֹרְאֹתֶֽיךָ יֹאמֵֽרוּ, וּגְדֻלָּתְךָ אֲסַפְּרֶֽנָּה.',
                'They speak of thy awe-inspiring might,{lb}And I tell of thy greatness.'),
               ('psalms/145/7',
                'זֵֽכֶר רַב טוּבְךָ יַבִּֽיעוּ, וְצִדְקָתְךָ יְרַנֵּֽנוּ.',
                'They spread the fame of thy great goodness,{lb}And sing of thy righteousness.'),
               ('psalms/145/8',
                'חַנּוּן וְרַחוּם יְיָ, אֶֽרֶךְ אַפַּֽיִם וּגְדָל־חָֽסֶד.',
                'Gracious and merciful is the Lord,{lb}Slow to anger and of great kindness.'),
               ('psalms/145/9',
                'טוֹב יְיָ לַכֹּל, וְרַחֲמָיו עַל כָּל מַעֲשָֽׂיו.',
                'The Lord is good to all,{lb}And his mercy is over all his works.'),
               ('psalms/145/10',
                'יוֹדֽוּךָ יְיָ כָּל מַעֲשֶֽׂיךָ, וַחֲסִידֶֽיךָ יְבָרְכֽוּכָה.',
                'All thy works praise thee, O Lord,{lb}And thy faithful followers bless thee.'),
               ('psalms/145/11',
                'כְּבוֹד מַלְכוּתְךָ יֹאמֵֽרוּ, וּגְבוּרָתְךָ יְדַבֵּֽרוּ.',
                'They speak of thy glorious kingdom,{lb}And talk of thy might,'),
               ('psalms/145/12',
                'לְהוֹדִֽיעַ לִבְנֵי הָאָדָם גְּבוּרֹתָיו, וּכְבוֹד הֲדַר מַלְכוּתוֹ.',
                'To let men know thy mighty deeds,{lb}And the glorious splendor of thy kingdom.'),
               ('psalms/145/13',
                'מַלְכוּתְךָ מַלְכוּת כָּל עֹלָמִים, וּמֶמְשַׁלְתְּךָ בְּכָל דּוֹר וָדֹר.',
                'Thy kingdom is a kingdom of all ages,{lb}And thy dominion is for all '
                'generations.'),
               ('psalms/145/14',
                'סוֹמֵךְ יְיָ לְכָל הַנֹּפְלִים, וְזוֹקֵף לְכָל הַכְּפוּפִים.',
                'The Lord upholds all who fall,{lb}And raises all who are bowed down.'),
               ('psalms/145/15',
                'עֵינֵי כֹל אֵלֶֽיךָ יְשַׂבֵּרוּ, וְאַתָּה נוֹתֵן לָהֶם אֶת אָכְלָם בְּעִתּוֹ.',
                'The eyes of all look hopefully to thee,{lb}And thou givest them their food in due '
                'season.'),
               ('psalms/145/16',
                'פּוֹתֵֽחַ אֶת יָדֶֽךָ, וּמַשְׂבִּֽיעַ לְכָל חַי רָצוֹן.',
                'Thou openest thy hand,{lb}And satisfiest every living thing with favor.'),
               ('psalms/145/17',
                'צַדִּיק יְיָ בְּכָל דְּרָכָיו, וְחָסִיד בְּכָל מַעֲשָׂיו.',
                'The Lord is righteous in all his ways,{lb}And gracious in all his deeds.'),
               ('psalms/145/18',
                'קָרוֹב יְיָ לְכָל קֹרְאָיו, לְכֹל אֲשֶׁר יִקְרָאֻֽהוּ בֶאֱמֶת.',
                'The Lord is near to all who call upon him,{lb}To all who call upon him '
                'sincerely.'),
               ('psalms/145/19',
                'רְצוֹן יְרֵאָיו יַעֲשֶׂה, וְאֶת שַׁוְעָתָם יִשְׁמַע וְיוֹשִׁיעֵם.',
                'He fulfills the desire of those who revere him;{lb}He hears their cry and saves '
                'them.'),
               ('psalms/145/20',
                'שׁוֹמֵר יְיָ אֶת כָּל אֹהֲבָיו, וְאֵת כָּל הָרְשָׁעִים יַשְׁמִיד.',
                'The Lord preserves all who love him,{lb}But all the wicked he destroys.'),
               ('psalms/145/21',
                'תְּהִלַּת יְיָ יְדַבֶּר־פִּי; וִיבָרֵךְ כָּל בָּשָׂר שֵׁם קָדְשׁוֹ לְעוֹלָם '
                'וָעֶד.',
                'My mouth speaks the praise of the Lord;{lb}Let all creatures bless his holy name '
                'forever and ever.')],
 'ashrei_suffix': [('psalms/115/18',
                    '{reader}וַאֲנַֽחְנוּ נְבָרֵךְ יָהּ מֵעַתָּה וְעַד עוֹלָם; הַלְלוּיָהּ.',
                    'We will bless the Lord henceforth and forever.{lb}Praise the Lord!')],
 'psalm_146': [('psalms/146/1',
                'הַלְלוּיָהּ; הַלְלִי נַפְשִׁי אֶת יְיָ.',
                'Praise the Lord! Praise the Lord, O my soul!'),
               ('psalms/146/2',
                'אֲהַלְלָה יְיָ בְּחַיָּי, אֲזַמְּרָה לֵאלֹהַי בְּעוֹדִי.',
                'I will praise the Lord as long as I live; I will sing to my God as long as I '
                'exist.'),
               ('psalms/146/3',
                'אַל תִּבְטְחוּ בִנְדִיבִים, בְּבֶן־אָדָם שֶׁאֵין לוֹ תְשׁוּעָה.',
                'Put no trust in princes, in mortal man who can give no help.'),
               ('psalms/146/4',
                'תֵּצֵא רוּחוֹ יָשֻׁב לְאַדְמָתוֹ; בַּיּוֹם הַהוּא אָבְדוּ עֶשְׁתֹּנֹתָיו.',
                'When his breath goes, he returns to the dust, and on that very day his '
                '{pb:62}designs perish.'),
               ('psalms/146/5',
                '{pb:61}אַשְׁרֵי שֶׁאֵל יַעֲקֹב בְּעֶזְרוֹ, שִׂבְרוֹ עַל יְיָ אֱלֹהָיו.',
                'Happy is he who has the God of Jacob as his help, whose hope rests upon the Lord '
                'his God,'),
               ('psalms/146/6',
                'עֹשֶׂה שָׁמַֽיִם וָאָֽרֶץ, אֶת הַיָּם, וְאֶת כָּל אֲשֶׁר בָּם; הַשֹּׁמֵר אֱמֶת '
                'לְעוֹלָם.',
                'Maker of heaven and earth and sea and all that is therein; who keeps faith '
                'forever,'),
               ('psalms/146/7',
                'עֹשֶׂה מִשְׁפָּט לָעֲשׁוּקִים, נֹתֵן לֶֽחֶם לָרְעֵבִים; יְיָ מַתִּיר אֲסוּרִים.',
                'renders justice to the oppressed, and feeds those who are hungry. The Lord sets '
                'the captives free.'),
               ('psalms/146/8',
                'יְיָ פֹּקֵֽחַ עִוְרִים, יְיָ זֹקֵף כְּפוּפִים, יְיָ אֹהֵב צַדִּיקִים.',
                'The Lord opens the eyes of the blind, raises those who are bowed down, and loves '
                'the righteous.'),
               ('psalms/146/9',
                'יְיָ שֹׁמֵר אֶת גֵּרִים; יָתוֹם וְאַלְמָנָה יְעוֹדֵד, וְדֶֽרֶךְ רְשָׁעִים '
                'יְעַוֵּת.',
                'The Lord protects the strangers, and upholds the fatherless and the widow; but '
                'the way of the wicked he thwarts.'),
               ('psalms/146/10',
                '{reader}יִמְלֹךְ יְיָ לְעוֹלָם, אֱלֹהַֽיִךְ צִיּוֹן לְדֹר וָדֹר; הַלְלוּיָהּ.',
                'The Lord shall reign forever; your God, O Zion, for all generations. Praise the '
                'Lord!')],
 'psalm_147': [('psalms/147/1',
                'הַלְלוּיָהּ; כִּי טוֹב זַמְּרָה אֱלֹהֵֽינוּ, כִּי נָעִים, נָאוָה תְהִלָּה.',
                'Praise the Lord! It is good to sing to our God, it is pleasant; praise is '
                'comely.'),
               ('psalms/147/2',
                'בּוֹנֵה יְרוּשָׁלַֽיִם יְיָ; נִדְחֵי יִשְׂרָאֵל יְכַנֵּס.',
                'The Lord rebuilds Jerusalem; he gathers together the dispersed people of Israel.'),
               ('psalms/147/3',
                'הָרֹפֵא לִשְׁבֽוּרֵי לֵב, וּמְחַבֵּשׁ לְעַצְּבוֹתָם.',
                'He heals the broken-hearted, and binds up their wounds.'),
               ('psalms/147/4',
                'מוֹנֶה מִסְפָּר לַכּוֹכָבִים, לְכֻלָּם שֵׁמוֹת יִקְרָא.',
                'He counts the number of the stars, and gives a name to each.'),
               ('psalms/147/5',
                'גָּדוֹל אֲדוֹנֵֽינוּ וְרַב כֹּֽחַ, לִתְבוּנָתוֹ אֵין מִסְפָּר.',
                'Great is our Lord and abundant in power; his wisdom is infinite.'),
               ('psalms/147/6',
                'מְעוֹדֵד עֲנָוִים יְיָ, מַשְׁפִּיל רְשָׁעִים עֲדֵי אָֽרֶץ.',
                'The Lord raises the humble; he casts the wicked down to the ground.'),
               ('psalms/147/7',
                'עֱנוּ לַייָ בְּתוֹדָה, זַמְּרוּ לֵאלֹהֵֽינוּ בְכִנּוֹר.',
                'Sing thanks to the Lord; make melody upon the harp to our God,'),
               ('psalms/147/8',
                'הַמְכַסֶּה שָׁמַֽיִם בְּעָבִים, הַמֵּכִין לָאָֽרֶץ מָטָר, הַמַּצְמִֽיחַ הָרִים '
                'חָצִיר.',
                'who covers the sky with clouds, provides rain for the earth, and causes grass to '
                'grow upon the hills.'),
               ('psalms/147/9',
                'נוֹתֵן לִבְהֵמָה לַחְמָהּ, לִבְנֵי עֹרֵב אֲשֶׁר יִקְרָֽאוּ.',
                'He gives food to the cattle and to the crying young ravens.'),
               ('psalms/147/10',
                'לֹא בִגְבוּרַת הַסּוּס יֶחְפָּץ, לֹא בְשׁוֹקֵי הָאִישׁ יִרְצֶה.',
                'He cares not for [those who rely on] the strength of the horse; he delights not '
                'in [those who rely on] a warrior’s legs.'),
               ('psalms/147/11',
                'רוֹצֶה יְיָ אֶת יְרֵאָיו, אֶת הַמְיַחֲלִים לְחַסְדּוֹ.',
                'The Lord is pleased with those who revere him, those who yearn for his kindness.'),
               ('psalms/147/12',
                'שַׁבְּחִי, יְרוּשָׁלַֽיִם, אֶת יְיָ; הַלְלִי אֱלֹהַֽיִךְ, צִיּוֹן.',
                'Praise the Lord, O Jerusalem! Praise your God, O Zion!'),
               ('psalms/147/13',
                'כִּי חִזַּק בְּרִיחֵי שְׁעָרָֽיִךְ, בֵּרַךְ בָּנַֽיִךְ בְּקִרְבֵּךְ.',
                'He has indeed fortified your gates; he has blessed your children within.'),
               ('psalms/147/14',
                'הַשָּׂם גְּבוּלֵךְ שָׁלוֹם, חֵֽלֶב חִטִּים יַשְׂבִּיעֵךְ.',
                'He establishes peace within your territory, and fills you with the finest of '
                'wheat.'),
               ('psalms/147/15',
                'הַשֹּׁלֵֽחַ אִמְרָתוֹ אָֽרֶץ; עַד מְהֵרָה יָרוּץ דְּבָרוֹ.',
                'He sends forth his command to the earth; his word runs very swiftly.'),
               ('psalms/147/16',
                'הַנֹּתֵן שֶֽׁלֶג כַּצָּֽמֶר; כְּפוֹר כָּאֵֽפֶר יְפַזֵּר.',
                'He gives snow like wool; he scatters hoarfrost like ashes.'),
               ('psalms/147/17',
                'מַשְׁלִיךְ קַרְחוֹ כְפִתִּים; לִפְנֵי קָרָתוֹ מִי יַעֲמֹד.',
                'He casts forth his ice like crumbs; who can stand before his cold?'),
               ('psalms/147/18',
                'יִשְׁלַח דְּבָרוֹ וְיַמְסֵם; יַשֵּׁב רוּחוֹ, יִזְּלוּ מָֽיִם.',
                'He sends forth his word and melts them; he causes his wind to blow, and the '
                'waters flow.'),
               ('psalms/147/19',
                'מַגִּיד דְּבָרָיו לְיַעֲקֹב, חֻקָּיו וּמִשְׁפָּטָיו לְיִשְׂרָאֵל.',
                'He declares his word to Jacob, his statutes and ordinances to Israel.'),
               ('psalms/147/20',
                '{reader}לֹא עָֽשָׂה כֵן לְכָל גּוֹי, וּמִשְׁפָּטִים בַּל יְדָעוּם; הַלְלוּיָהּ.',
                'He has not dealt so with heathen nations; his ordinances they do not know. Praise '
                'the Lord!')],
 'psalm_148': [('psalms/148/1',
                'הַלְלוּיָהּ; הַלְלוּ אֶת יְיָ מִן הַשָּׁמַֽיִם, הַלְלֽוּהוּ בַּמְּרוֹמִים.',
                'Praise the Lord! Praise the Lord from the heavens; praise him in the heights.'),
               ('psalms/148/2',
                'הַלְלֽוּהוּ כָּל מַלְאָכָיו, הַלְלֽוּהוּ כָּל צְבָאָיו.',
                'Praise him, all his angels; praise him, all his hosts.'),
               ('psalms/148/3',
                'הַלְלֽוּהוּ שֶֽׁמֶשׁ {pb:63}וְיָרֵֽחַ, הַלְלֽוּהוּ כָּל כּֽוֹכְבֵי אוֹר.',
                '{pb:64}Praise him, sun and moon; praise him, all you stars of light.'),
               ('psalms/148/4',
                'הַלְלֽוּהוּ שְׁמֵי הַשָּׁמָֽיִם, וְהַמַּֽיִם אֲשֶׁר מֵעַל הַשָּׁמָֽיִם.',
                'Praise him, highest heavens and waters that are above the heavens.'),
               ('psalms/148/5',
                'יְהַלְלוּ אֶת שֵׁם יְיָ, כִּי הוּא צִוָּה וְנִבְרָֽאוּ.',
                'Let them praise the name of the Lord; for he commanded and they were created.'),
               ('psalms/148/6',
                'וַיַּעֲמִידֵם לָעַד לְעוֹלָם, חָק־נָתַן וְלֹא יַעֲבוֹר.',
                'He fixed them fast forever and ever; he gave a law which none transgresses.'),
               ('psalms/148/7',
                'הַלְלוּ אֶת יְיָ מִן הָאָרֶץ, תַּנִּינִים וְכָל תְּהֹמוֹת.',
                'Praise the Lord from the earth, you sea-monsters and all depths;'),
               ('psalms/148/8',
                'אֵשׁ וּבָרָד, שֶֽׁלֶג וְקִיטוֹר, רֽוּחַ סְעָרָה עֹשָׂה דְבָרוֹ.',
                'fire and hail, snow and vapor, stormy wind, fulfilling his word;'),
               ('psalms/148/9',
                'הֶהָרִים וְכָל גְּבָעוֹת, עֵץ פְּרִי וְכָל אֲרָזִים,',
                'mountains and all hills, fruit-trees and all cedars;'),
               ('psalms/148/10',
                'הַחַיָּה וְכָל בְּהֵמָה, רֶֽמֶשׂ וְצִפּוֹר כָּנָף.',
                'wild animals and all cattle, crawling things and winged fowl;'),
               ('psalms/148/11',
                'מַלְכֵי אֶֽרֶץ וְכָל לְאֻמִּים, שָׂרִים וְכָל שֹֽׁפְטֵי אָֽרֶץ.',
                'kings of the earth and all nations, princes and all earthly rulers;'),
               ('psalms/148/12',
                'בַּחוּרִים וְגַם בְּתוּלוֹת, זְקֵנִים עִם נְעָרִים.',
                'young men and maidens, old men and children;'),
               ('psalms/148/13',
                'יְהַלְלוּ אֶת שֵׁם יְיָ, כִּי נִשְׂגָּב שְׁמוֹ לְבַדּוֹ; הוֹדוֹ עַל אֶֽרֶץ '
                'וְשָׁמָֽיִם.',
                'let them praise the name of the Lord, for his name alone is exalted; his majesty '
                'is above earth and heaven.'),
               ('psalms/148/14',
                '{reader}וַיָּֽרֶם קֶֽרֶן לְעַמּוֹ, תְּהִלָּה לְכָל חֲסִידָיו, לִבְנֵי יִשְׂרָאֵל '
                'עַם קְרֹבוֹ; הַלְלוּיָהּ.',
                'He has raised the honor of his people, the glory of his faithful followers, the '
                'children of Israel, the people near to him. Praise the Lord!')],
 'psalm_149': [('psalms/149/1',
                'הַלְלוּיָהּ; שִׁירוּ לַייָ שִׁיר חָדָשׁ, תְּהִלָּתוֹ בִּקְהַל חֲסִידִים.',
                'Praise the Lord! Sing a new song to the Lord; praise him in the assembly of the '
                'faithful.'),
               ('psalms/149/2',
                'יִשְׂמַח יִשְׂרָאֵל בְּעֹשָׂיו, בְּנֵי צִיּוֹן יָגִֽילוּ בְמַלְכָּם.',
                'Let Israel rejoice in his Maker; let the children of Zion exult in their King.'),
               ('psalms/149/3',
                'יְהַלְלוּ שְׁמוֹ בְמָחוֹל, בְּתֹף וְכִנּוֹר יְזַמְּרוּ לוֹ.',
                'Let them praise his name with dancing; let them make music to him with drum and '
                'harp.'),
               ('psalms/149/4',
                'כִּי רוֹצֶה יְיָ בְּעַמּוֹ, יְפָאֵר עֲנָוִים בִּישׁוּעָה.',
                'For the Lord is pleased with his people; he adorns the meek with triumph.'),
               ('psalms/149/5',
                'יַעְלְזוּ חֲסִידִים בְּכָבוֹד, יְרַנְּנוּ עַל מִשְׁכְּבוֹתָם.',
                'Let the faithful exult in glory; let them sing upon their beds.'),
               ('psalms/149/6',
                'רוֹמְמוֹת אֵל בִּגְרוֹנָם, וְחֶֽרֶב פִּיפִיּוֹת בְּיָדָם.',
                'Let the praises of God be in their mouth, and a double-edged sword in their '
                'hand,'),
               ('psalms/149/7',
                'לַעֲשׂוֹת נְקָמָה בַּגּוֹיִם, תּוֹכֵחוֹת בַּלְאֻמִּים.',
                'to execute vengeance upon the nations, punishment upon the peoples;'),
               ('psalms/149/8',
                '{reader}לֶאְסֹר מַלְכֵיהֶם בְּזִקִּים, וְנִכְבְּדֵיהֶם בְּכַבְלֵי בַרְזֶל.',
                'to bind their kings with chains, and their nobles with fetters of iron;'),
               ('psalms/149/9',
                'לַעֲשׂוֹת בָּהֶם מִשְׁפָּט כָּתוּב; הָדָר הוּא לְכָל חֲסִידָיו; הַלְלוּיָהּ.',
                'to execute upon them the written judgment. He is the glory of all his faithful. '
                'Praise the Lord!')],
 'psalm_150': [('psalms/150/1',
                'הַלְלוּיָהּ; הַלְלוּ אֵל בְּקָדְשׁוֹ, הַלְלֽוּהוּ בִּרְקִֽיעַ עֻזּוֹ.',
                'Praise the Lord! Praise God in his sanctuary; praise him in his glorious heaven.'),
               ('psalms/150/2',
                'הַלְלֽוּהוּ בִגְבוּרֹתָיו, הַלְלֽוּהוּ כְּרֹב גֻּדְלוֹ.',
                'Praise him for his mighty deeds; praise him for his abundant greatness.'),
               ('psalms/150/3',
                'הַלְלֽוּהוּ בְּתֵֽקַע שׁוֹפָר, הַלְלֽוּהוּ בְּנֵֽבֶל וְכִנּוֹר.',
                'Praise him with the blast of the horn; praise him with the harp and the lyre.'),
               ('psalms/150/4',
                'הַלְלֽוּהוּ בְּתֹף וּמָחוֹל, הַלְלֽוּהוּ בְּמִנִּים וְעֻגָב.',
                'Praise him with the drum and dance; praise him with strings and flute.'),
               ('psalms/150/5',
                '{pb:65}הַלְלֽוּהוּ בְּצִלְצְלֵי שָֽׁמַע, הַלְלֽוּהוּ בְּצִלְצְלֵי תְרוּעָה.',
                'Praise him with re{pb:66}sounding cymbals; praise him with clanging cymbals.'),
               ('psalms/150/6',
                '{reader}כֹּל הַנְּשָׁמָה תְּהַלֵּל יָהּ; הַלְלוּיָהּ.',
                'Let everything that has breath praise the Lord. Praise the Lord!')],
 'psalm_150_repeat': [('psalms/150/6', 'כֹּל הַנְּשָׁמָה תְּהַלֵּל יָהּ; הַלְלוּיָהּ.', '')],
 'barukh_adonai': [('psalms/89/53',
                    'בָּרוּךְ יְיָ לְעוֹלָם, אָמֵן וְאָמֵן.',
                    'Blessed be the Lord forever. Amen, Amen.'),
                   ('psalms/135/21',
                    'בָּרוּךְ יְיָ מִצִּיּוֹן, שֹׁכֵן יְרוּשָׁלָֽיִם; הַלְלוּיָהּ.',
                    'Blessed out of Zion be the Lord who dwells in Jerusalem. Praise the Lord!'),
                   ('psalms/72/18',
                    'בָּרוּךְ יְיָ אֱלֹהִים, אֱלֹהֵי יִשְׂרָאֵל, עֹשֵׂה נִפְלָאוֹת לְבַדּוֹ.',
                    'Blessed be the Lord God, the God of Israel, who alone works wonders;'),
                   ('psalms/72/19',
                    '{reader}וּבָרוּךְ שֵׁם כְּבוֹדוֹ לְעוֹלָם; וְיִמָּלֵא כְבוֹדוֹ אֶת־כָּל '
                    'הָאָֽרֶץ, אָמֵן וְאָמֵן.',
                    'blessed be his glorious name forever. May the whole earth be filled with his '
                    'glory. Amen, Amen.')],
 'vayevarekh_david': [('chronicles_1/29/10',
                       'וַיְבָרֶךְ דָּוִיד אֶת יְיָ לְעֵינֵי כָּל הַקָּהָל, וַיֹּֽאמֶר דָּוִיד: '
                       'בָּרוּךְ אַתָּה יְיָ, אֱלֹהֵי יִשְׂרָאֵל אָבִינוּ, מֵעוֹלָם וְעַד עוֹלָם.',
                       'David blessed the Lord before all the assembly, and David said: Blessed '
                       'art thou, O Lord God of Israel our father, forever and ever.'),
                      ('chronicles_1/29/11',
                       'לְךָ יְיָ הַגְּדֻלָּה וְהַגְּבוּרָה וְהַתִּפְאֶֽרֶת וְהַנֵּֽצַח וְהַהוֹד, '
                       'כִּי כֹל בַּשָּׁמַֽיִם וּבָאָֽרֶץ; לְךָ יְיָ הַמַּמְלָכָה, '
                       'וְהַמִּתְנַשֵּׂא לְכֹל לְרֹאשׁ.',
                       'Thine, O Lord, is the greatness and the power, the glory and the victory '
                       'and the majesty, for all that is in heaven and on earth is thine; thine, O '
                       'Lord, is the kingdom, and thou art supreme over all.'),
                      ('chronicles_1/29/12',
                       'וְהָעֹֽשֶׁר וְהַכָּבוֹד מִלְּפָנֶֽיךָ, וְאַתָּה מוֹשֵׁל בַּכֹּל, '
                       'וּבְיָדְךָ כֹּֽחַ וּגְבוּרָה, וּבְיָדְךָ לְגַדֵּל וּלְחַזֵּק לַכֹּל.',
                       'Riches and honor come from thee; thou rulest over all; in thy hand are '
                       'power and might, and it is in thy power to make all great and strong.'),
                      ('chronicles_1/29/13',
                       'וְעַתָּה אֱלֹהֵֽינוּ, מוֹדִים אֲנַֽחְנוּ לָךְ, וּמְהַלְלִים לְשֵׁם '
                       'תִּפְאַרְתֶּֽךָ.',
                       'Hence, our God, we ever thank thee and praise thy glorious name.')],
 'attah_hu': [('nehemiah/9/6',
              'אַתָּה הוּא יְיָ לְבַדֶּֽךָ, אַתָּה עָשִֽׂיתָ אֶת הַשָּׁמַֽיִם, שְׁמֵי הַשָּׁמַֽיִם '
              'וְכָל צְבָאָם, הָאָֽרֶץ וְכָל אֲשֶׁר עָלֶֽיהָ, הַיַּמִּים וְכָל אֲשֶׁר בָּהֶם, '
              'וְאַתָּה מְחַיֶּה אֶת כֻּלָּם, וּצְבָא הַשָּׁמַֽיִם לְךָ מִשְׁתַּחֲוִים.',
              'Thou art the Lord, thou alone. Thou hast made the heavens and the heaven of heavens '
              'with all their host, the earth and all the things upon it, the seas and all that is '
              'in them, and thou preservest them all; the host of the heavens worships thee.'),
             ('nehemiah/9/7',
              '{reader}אַתָּה הוּא יְיָ הָאֱלֹהִים, אֲשֶׁר בָּחַרְתָּ בְּאַבְרָם וְהוֹצֵאתוֹ '
              'מֵאוּר כַּשְׂדִּים וְשַֽׂמְתָּ שְּׁמוֹ אַבְרָהָם.',
              'Thou art the Lord God, who didst choose Abram, and didst bring him out of Ur of the '
              'Chaldeans, and gavest him the name of Abraham.'),
             ('nehemiah/9/8',
              'וּמָצָֽאתָ אֶת לְבָבוֹ נֶאֱמָן לְפָנֶֽיךָ—{lb}וְכָרוֹת עִמּוֹ הַבְּרִית לָתֵת אֶת '
              'אֶֽרֶץ הַכְּנַעֲנִי, הַחִתִּי, הָאֱמֹרִי, וְהַפְּרִזִּי וְהַיְבוּסִי '
              'וְהַגִּרְגָּשִׁי, לָתֵת לְזַרְעוֹ; וַתָּֽקֶם אֶת דְּבָרֶֽיךָ, כִּי צַדִּיק אָֽתָּה.',
              'Thou didst find his heart faithful before thee, and didst make a covenant with him '
              'to give the land of the Canaanite, the Hittite, the Amorite, the Perizzite, the '
              'Jebusite, and the Girgashite—to give it to his descendants, and hast fulfilled thy '
              'words, for thou art righteous.'),
             ('nehemiah/9/9',
              'וַתֵּֽרֶא אֶת עֳנִי אֲבֹתֵֽינוּ בְּמִצְרָֽיִם, וְאֶת זַעֲקָתָם שָׁמַֽעְתָּ עַל '
              'יַם סוּף.',
              'Thou didst see the distress of our fathers in Egypt and hear their cry by the Red '
              'Sea;'),
             ('nehemiah/9/10',
              'וַתִּתֵּן אֹתֹת וּמֹפְתִים בְּפַרְעֹה וּבְכָל עֲבָדָיו {pb:67}וּבְכָל עַם אַרְצוֹ, '
              'כִּי יָדַֽעְתָּ כִּי הֵזִֽידוּ עֲלֵיהֶם; וַתַּֽעַשׂ לְךָ שֵׁם כְּהַיּוֹם הַזֶּה.',
              'thou didst show signs and wonders on Pharaoh and all his servants and all the '
              'people of his {pb:68}land, for thou knewest that they dealt viciously against them; '
              'and so hast thou made a name for thyself to this day.'),
             ('nehemiah/9/11',
              '{reader}וְהַיָּם בָּקַֽעְתָּ לִפְנֵיהֶם, וַיַּֽעַבְרוּ בְתוֹךְ הַיָּם בַּיַּבָּשָׁה; '
              'וְאֶת רֹדְפֵיהֶם הִשְׁלַֽכְתָּ בִמְצוֹלֹת, כְּמוֹ אֶֽבֶן בְּמַֽיִם עַזִּים.',
              'The sea thou didst divide before them, so that they went through the middle of the '
              'sea on dry ground; and their pursuers thou didst cast into the depths, like a stone '
              'into the mighty waters.')],
 'vayyosha': [('exodus/14/30',
              'וַיּֽוֹשַׁע יְיָ בַּיּוֹם הַהוּא אֶת יִשְׂרָאֵל מִיַּד מִצְרָֽיִם; וַיַּרְא '
              'יִשְׂרָאֵל אֶת מִצְרַֽיִם מֵת עַל שְׂפַת הַיָּם.',
              'Thus did the Lord save Israel that day from the power of the Egyptians; and Israel '
              'saw the Egyptians dead on the seashore.'),
             ('exodus/14/31',
              '{reader}וַיַּרְא יִשְׂרָאֵל אֶת הַיָּד הַגְּדֹלָה אֲשֶׁר עָשָׂה יְיָ בְּמִצְרַֽיִם, '
              'וַיִּירְאוּ הָעָם אֶת יְיָ, וַיַּאֲמִֽינוּ בַּייָ וּבְמֹשֶׁה עַבְדּוֹ.',
              'Israel saw the mighty act which the Lord had performed against the Egyptians, and '
              'the people revered the Lord; they believed in the Lord and in his servant Moses.')],
 'az_yashir': [('exodus/15/1',
                'אָז יָשִׁיר מֹשֶׁה וּבְנֵי יִשְׂרָאֵל אֶת הַשִּׁירָה הַזֹּאת לַייָ, וַיֹּאמְרוּ '
                'לֵאמֹר: אָשִֽׁירָה לַייָ כִּי גָאֹה גָּאָה, סוּס וְרֹכְבוֹ רָמָה בַיָּם.',
                'Then Moses and the children of Israel sang this song to the Lord; they said: I '
                'will sing to the Lord, for he has completely triumphed; the horse and its rider '
                'he has hurled into the sea.'),
               ('exodus/15/2',
                'עָזִּי וְזִמְרָת יָהּ, וַיְהִי לִי לִישׁוּעָה; זֶה אֵלִי וְאַנְוֵֽהוּ, אֱלֹהֵי '
                'אָבִי וַאֲרֹמְמֶֽנְהוּ.',
                'The Lord is my strength and song, for he has come to my aid. This is my God, and '
                'I will glorify him; my father’s God, and I will extol him.'),
               ('exodus/15/3',
                'יְיָ אִישׁ מִלְחָמָה, יְיָ שְׁמוֹ.',
                'The Lord is a warrior—Lord is his name.'),
               ('exodus/15/4',
                'מַרְכְּבֹת פַּרְעֹה וְחֵילוֹ יָרָה בַיָּם, וּמִבְחַר שָׁלִשָׁיו טֻבְּעוּ בְיַם '
                'סוּף.',
                'Pharaoh’s chariots and his army he has cast into the sea, and his picked captains '
                'are engulfed in the Red Sea.'),
               ('exodus/15/5',
                'תְּהֹמֹת יְכַסְיֻֽמוּ: יָרְדוּ בִמְצוֹלֹת כְּמוֹ אָֽבֶן.',
                'The depths cover them; they went down into the depths like a stone.'),
               ('exodus/15/6',
                'יְמִינְךָ יְיָ נֶאְדָּרִי בַּכֹּֽחַ, יְמִינְךָ יְיָ תִּרְעַץ אוֹיֵב.',
                'Thy right hand, O Lord, glorious in power, thy right hand, O Lord, crushes the '
                'enemy.'),
               ('exodus/15/7',
                'וּבְרֹב גְּאוֹנְךָ תַּהֲרֹס קָמֶֽיךָ; תְּשַׁלַּח חֲרֹנְךָ, יֹאכְלֵֽמוֹ כַּקַּשׁ.',
                'By thy great majesty thou destroyest thy opponents. Thou sendest forth thy '
                'wrath—it consumes them like stubble.'),
               ('exodus/15/8',
                'וּבְרֽוּחַ אַפֶּֽיךָ נֶעֶרְמוּ מַֽיִם, נִצְּבוּ כְמוֹ נֵד נֹזְלִים; קָפְאוּ '
                'תְהֹמֹת בְּלֶב־יָם.',
                'By the blast of thy nostrils the waters piled up—the floods stood upright like a '
                'wall; the depths were congealed in the heart of the sea.'),
               ('exodus/15/9',
                'אָמַר אוֹיֵב: אֶרְדֹּף אַשִּׂיג, אֲחַלֵּק שָׁלָל, תִּמְלָאֵֽמוֹ נַפְשִׁי, אָרִיק '
                'חַרְבִּי, תּוֹרִישֵֽׁמוֹ יָדִי.',
                'The enemy said: “I will pursue them, I will overtake them, I will divide the '
                'spoil, my lust shall be glutted with them; I will draw my sword, my hand shall '
                'destroy them.”'),
               ('exodus/15/10',
                'נָשַֽׁפְתָּ בְרוּחֲךָ, כִּסָּֽמוֹ יָם; צָלְלוּ כַּעוֹפֶֽרֶת בְּמַֽיִם אַדִּירִים.',
                'Thou didst blow with thy wind—the sea covered them; they sank like lead in the '
                'mighty waters.'),
               ('exodus/15/11',
                'מִי כָמֹֽכָה בָּאֵלִם, יְיָ; מִי כָּמֹֽכָה, נֶאְדָּר בַּקֹּֽדֶשׁ, נוֹרָא '
                'תְהִלֹּת, עֹֽשֵׂה פֶֽלֶא.',
                'Who is the like of thee among the mighty, O Lord? Who is like thee, glorious in '
                'holiness, awe-inspiring in renown, doing marvels?'),
               ('exodus/15/12',
                'נָטִֽיתָ יְמִינְךָ, תִּבְלָעֵֽמוֹ אָֽרֶץ.',
                'Thou didst stretch out thy right hand—the earth swallowed them.'),
               ('exodus/15/13',
                'נָחִֽיתָ בְחַסְדְּךָ עַם־זוּ גָּאָֽלְתָּ; נֵהַֽלְתָּ בְעָזְּךָ אֶל נְוֵה '
                'קָדְשֶֽׁךָ.',
                'In thy grace thou hast led the people whom thou hast redeemed; by thy power thou '
                'hast guided them to thy holy habitation.'),
               ('exodus/15/14',
                'שָׁמְעוּ עַמִּים, יִרְגָּזוּן; חִיל אָחַז יֹשְׁבֵי פְּלָֽשֶׁת.',
                'The peoples have heard of it and trembled; pangs have seized the inhabitants of '
                'Philistia.'),
               ('exodus/15/15',
                'אָז נִבְהֲלוּ אַלּוּפֵי {pb:69}אֱדוֹם; אֵילֵי מוֹאָב יֹאחֲזֵֽמוֹ רָֽעַד; נָמֹֽגוּ '
                'כֹּל יֹשְׁבֵי כְנָֽעַן.',
                'Then were the chieftains of Edom in agony; {pb:70}trembling seized the lords of '
                'Moab; all the inhabitants of Canaan melted away.'),
               ('exodus/15/16',
                'תִּפֹּל עֲלֵיהֶם אֵימָֽתָה וָפַֽחַד; בִּגְדֹל זְרוֹעֲךָ יִדְּמוּ כָּאָֽבֶן; עַד '
                'יַעֲבֹר עַמְּךָ יְיָ, עַד יַעֲבֹר עַם־זוּ קָנִֽיתָ.',
                'Terror and dread fell on them. Under the great sweep of thy arm they are as still '
                'as a stone; till thy people pass over, O Lord, till the people thou hast acquired '
                'pass over.'),
               ('exodus/15/17',
                'תְּבִאֵֽמוֹ וְתִטָּעֵֽמוֹ בְּהַר נַחֲלָתְךָ, מָכוֹן לְשִׁבְתְּךָ פָּעַֽלְתָּ, '
                'יְיָ; מִקְדָּשׁ, אֲדֹנָי, כּוֹנְנוּ יָדֶֽיךָ.',
                'Thou wilt bring them in and plant them in the highlands of thy own, the place '
                'which thou, O Lord, hast made for thy dwelling, the sanctuary, O Lord, which thy '
                'hands have established.'),
               ('exodus/15/18',
                'יְיָ יִמְלֹךְ לְעֹלָם וָעֶד.',
                'The Lord shall reign forever and ever.')],
 'adonai_yimlokh_repeat': [('exodus/15/18',
                            'יְיָ יִמְלֹךְ לְעוֹלָם וָעֶד.',
                            'The Lord shall reign forever and ever.')],
 'ki_ladonai': [('psalms/22/29',
                 'כִּי לַייָ הַמְּלוּכָה, וּמוֹשֵׁל בַּגּוֹיִם.',
                 'For sovereignty is the Lord’s, and he governs the nations.'),
                ('obadiah/1/21',
                 '{reader}וְעָלוּ מוֹשִׁיעִים בְּהַר צִיּוֹן לִשְׁפֹּט אֶת הַר עֵשָׂו, וְהָיְתָה '
                 'לַייָ הַמְּלוּכָה.',
                 'Deliverers shall go up to Mount Zion to rule the hill country of Esau, and '
                 'dominion shall be the Lord’s.'),
                ('zechariah/14/9',
                 'וְהָיָה יְיָ לְמֶֽלֶךְ עַל כָּל הָאָֽרֶץ; בַּיּוֹם הַהוּא יִהְיֶה יְיָ אֶחָד '
                 'וּשְׁמוֹ אֶחָד.',
                 'The Lord shall be King over all the earth; on that day shall the Lord be One and '
                 'his name One.')],
 'yishtabbach': [('prayer:yishtabbach',
                 'יִשְׁתַּבַּח שִׁמְךָ לָעַד, מַלְכֵּֽנוּ, הָאֵל הַמֶּֽלֶךְ הַגָּדוֹל '
                 'וְהַקָּדוֹשׁ, בַּשָּׁמַֽיִם וּבָאָֽרֶץ. כִּי לְךָ נָאֶה, יְיָ אֱלֹהֵֽינוּ '
                 'וֵאלֹהֵי אֲבוֹתֵֽינוּ, שִׁיר וּשְׁבָחָה, הַלֵּל וְזִמְרָה, עֹז וּמֶמְשָׁלָה, '
                 'נֶֽצַח, גְּדֻלָּה וּגְבוּרָה, תְּהִלָּה וְתִפְאֶֽרֶת, קְדֻשָּׁה וּמַלְכוּת, '
                 '{reader}בְּרָכוֹת וְהוֹדָאוֹת, מֵעַתָּה וְעַד עוֹלָם. בָּרוּךְ אַתָּה, יְיָ, אֵל '
                 'מֶֽלֶךְ גָּדוֹל בַּתִּשְׁבָּחוֹת, אֵל הַהוֹדָאוֹת, אֲדוֹן הַנִּפְלָאוֹת, '
                 'הַבּוֹחֵר בְּשִׁירֵי זִמְרָה, מֶֽלֶךְ, אֵל, חֵי הָעוֹלָמִים.',
                 'Praised be thy name forever, our King, great and holy God and King, in heaven '
                 'and on earth; for to thee, Lord our God and God of our fathers, pertain song and '
                 'praise, hymn and psalm, power and dominion, victory, greatness and might, renown '
                 'and glory, holiness and kingship, blessings and thanks, henceforth and forever. '
                 'Blessed art thou, O Lord, most exalted God and King, Lord of wonders, who art '
                 'pleased with hymns, thou God and King, the life of the universe.')]}
