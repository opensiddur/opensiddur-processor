"""The Hebrew of Adon Olam and Yigdal, read off printed pages 11 and 13.

Both poems are set in two columns on the Hebrew page and as two stacked lines
per verse line on the English one. Birnbaum's own footnote says ten lines and
thirteen lines, and both sides give exactly that, so the structure is not in
dispute between them and only the setting differs. Each `tei:l` holds a whole
line of verse on both sides; splitting on the Hebrew column or on the English
line break would give twice as many and contradict the book about itself.

Neither poem is headed on the Hebrew page: they begin directly, the first word
doing the work. The facing English page heads them both, which is the sharpest
form of the asymmetry in this unit -- a heading on one side and none on the other.
"""
import functools

from . import common
from .common import POEM

pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

P = POEM

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=P + slug,
                        first=first, last=last, body=body))


def poem(urn, lines, *, indent=8, page_break_before=None):
    """A poem as a `tei:lg` of whole verse lines."""
    pad = " " * indent
    out = []
    for n, line in enumerate(lines):
        numbered = isinstance(line, (list, tuple))
        text = line[1] if numbered else line
        attr = ' n="%s"' % line[0] if numbered else ""
        brk = page_break_before(n) if page_break_before else ""
        out.append("%s    <tei:l%s>%s%s</tei:l>" % (pad, attr, brk, text))
    inner = "\n".join(out)
    return ('%s<tei:div corresp="%s">\n%s  <tei:lg>\n%s\n%s  </tei:lg>\n%s</tei:div>'
            % (pad, urn, pad, inner, pad, pad))


ADON_OLAM = ['אֲדוֹן עוֹלָם אֲשֶׁר מָלַךְ בְּטֶֽרֶם כָּל יְצִיר נִבְרָא.', 'לְעֵת נַעֲשָׂה בְחֶפְצוֹ כֹּל אֲזַי מֶֽלֶךְ שְׁמוֹ נִקְרָא.', 'וְאַחֲרֵי כִּכְלוֹת הַכֹּל לְבַדּוֹ יִמְלוֹךְ נוֹרָא.', 'וְהוּא הָיָה וְהוּא הֹוֶה וְהוּא יִהְיֶה בְּתִפְאָרָה.', 'וְהוּא אֶחָד וְאֵין שֵׁנִי לְהַמְשִׁיל לוֹ לְהַחְבִּֽירָה.', 'בְּלִי רֵאשִׁית בְּלִי תַכְלִית וְלוֹ הָעֹז וְהַמִּשְׂרָה.', 'וְהוּא אֵלִי וְחַי גֹּאֲלִי וְצוּר חֶבְלִי בְּעֵת צָרָה.', 'וְהוּא נִסִּי וּמָנוֹס לִי מְנָת כּוֹסִי בְּיוֹם אֶקְרָא.', 'בְּיָדוֹ אַפְקִיד רוּחִי בְּעֵת אִישַׁן וְאָעִֽירָה.', 'וְעִם רוּחִי גְּוִיָּתִי יְיָ לִי וְלֹא אִירָא.']

YIGDAL = ['יִגְדַּל אֱלֹהִים חַי וְיִשְׁתַּבַּח נִמְצָא וְאֵין עֵת אֶל מְצִיאוּתוֹ.', 'אֶחָד וְאֵין יָחִיד כְּיִחוּדוֹ נֶעְלָם וְגַם אֵין סוֹף לְאַחְדוּתוֹ.', 'אֵין לוֹ דְּמוּת הַגּוּף וְאֵינוֹ גוּף לֹא נַעֲרוֹךְ אֵלָיו קְדֻשָּׁתוֹ.', 'קַדְמוֹן לְכָל דָּבָר אֲשֶׁר נִבְרָא רִאשׁוֹן וְאֵין רֵאשִׁית לְרֵאשִׁיתוֹ.', 'הִנּוֹ אֲדוֹן עוֹלָם וְכָל נוֹצָר יוֹרֶה גְדֻלָּתוֹ וּמַלְכוּתוֹ.', 'שֶֽׁפַע נְבוּאָתוֹ נְתָנוֹ אֶל אַנְשֵׁי סְגֻלָּתוֹ וְתִפְאַרְתּוֹ.', 'לֹא קָם בְּיִשְׂרָאֵל כְּמֹשֶׁה עוֹד נָבִיא וּמַבִּיט אֶת תְּמוּנָתוֹ.', 'תּוֹרַת אֱמֶת נָתַן לְעַמּוֹ אֵל עַל יַד נְבִיאוֹ נֶאֱמַן בֵּיתוֹ.', 'לֹא יַחֲלִיף הָאֵל וְלֹא יָמִיר דָּתוֹ לְעוֹלָמִים לְזוּלָתוֹ.', 'צוֹפֶה וְיוֹדֵֽעַ סְתָרֵֽינוּ מַבִּיט לְסוֹף דָּבָר בְּקַדְמָתוֹ.', 'גּוֹמֵל לְאִישׁ חֶֽסֶד כְּמִפְעָלוֹ נוֹתֵן לְרָשָׁע רָע כְּרִשְׁעָתוֹ.', 'יִשְׁלַח לְקֵץ יָמִין מְשִׁיחֵֽנוּ לִפְדּוֹת מְחַכֵּי קֵץ יְשׁוּעָתוֹ.', 'מֵתִים יְחַיֶּה אֵל בְּרֹב חַסְדּוֹ בָּרוּךְ עֲדֵי עַד שֵׁם תְּהִלָּתוֹ.']

prayer("poem_adon_olam", 'אֲדוֹן עוֹלָם', "adon_olam", 11, 11,
       poem(P + "adon_olam", ADON_OLAM))

#: Yigdal runs over the page turn: five lines on the first page, eight on the next.
prayer("poem_yigdal", 'יִגְדַּל', "yigdal", 11, 13,
       poem(P + "yigdal", YIGDAL,
            page_break_before=lambda n: pb(13) if n == 5 else ""))
