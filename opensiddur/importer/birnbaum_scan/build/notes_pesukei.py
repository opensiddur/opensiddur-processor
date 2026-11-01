"""Commentary read from printed pages 49–70, through Half Kaddish."""
from .common import PRAYER

PESUKEI_NOTES = [
    dict(kind="commentary", target=PRAYER + "mizmor_shir_chanukat_habayit/aromimkha",
         lemma="מזמור שיר", paras=[dict(text=(
             "is a hymn of gratitude for recovery from a grave sickness. The psalmist "
             "relates that trouble came to him when he thought that he could be "
             "independent of God’s aid. In his distress he pleaded that his life might "
             "be spared, and his prayer was answered. He is determined to spend the "
             "rest of his life in thanksgiving."))]),
    dict(kind="commentary", target=PRAYER + "pesuqei_dezimrah/barukh_sheamar/barukh",
         lemma="ברוך שאמר", paras=[dict(text=(
             "is composed of eighty-seven words, a number suggesting the numerical "
             'value of <tei:foreign xml:lang="he">פז</tei:foreign> (“refined gold”). '
             'This hymn introduces the biblical selections entitled '
             '<tei:foreign xml:lang="he">פסוקי דזמרה</tei:foreign> (“verses of praise”). '
             'It is included in the ninth century <tei:hi rend="italic">Siddur</tei:hi> '
             "of Amram Gaon."))]),
]

from .common import SIDDUR
from .pesukei_passages import BIBLE, ROOT

PESUKEI_NOTES += [
    dict(kind="commentary", target=ROOT + "hodu", lemma="הודו", paras=[dict(text=(
        "is the hymn which David sang when the ark was brought to Jerusalem. "
        "The first fifteen verses of Psalm 105 are almost identical with the first half of this passage."))]),
    dict(kind="commentary", target=ROOT + "romemu", paras=[dict(text=(
        'The passage beginning with <tei:foreign xml:lang="he">רוממו</tei:foreign> '
        'is composed of a variety of biblical verses.'))]),
    dict(kind="commentary", target=ROOT + "hoshiah_et_ammekha", paras=[dict(text=(
        '<tei:hi rend="italic">Psalms</tei:hi> 99:5, 9; 78:38; 40:12; 25:6; 68:35–36; '
        '94:1–2; 3:9; 46:8; 84:13; 20:10; 28:9; 33:20–22; 85:8; 44:27; 81:11; 144:15; 13:6.'))]),
    dict(kind="commentary", target=BIBLE + "psalms/100", lemma="מזמור לתודה", paras=[dict(text=(
        'was recited in the Temple on weekdays when thank-offerings were presented. '
        'The psalmist invites the whole world to join Israel in the worship of God '
        'and to acknowledge him as the merciful Father of all mankind.'))]),
    dict(kind="commentary", target=ROOT + "yehi_khevod", lemma="יהי כבוד . . .", paras=[dict(text=(
        'that is, may the glory of the Lord, the universe, remain forever; may God '
        'always be pleased with his creation and preserve it.'))]),
    dict(kind="commentary", target=ROOT + "yehi_khevod", paras=[dict(text=(
        '<tei:hi rend="italic">Psalms</tei:hi> 104:31; 113:2–4; 135:13; 103:19; '
        '<tei:hi rend="italic">I Chronicles</tei:hi> 16:31; '
        '<tei:hi rend="italic">Psalms</tei:hi> 10:16; 33:10; '
        '<tei:hi rend="italic">Proverbs</tei:hi> 19:21; '
        '<tei:hi rend="italic">Psalms</tei:hi> 33:11, 9; 132:13; 135:4; 94:14; 78:38; 20:10.'))]),
]

# Commentary and numbered references on printed 57–70.
PESUKEI_NOTES += [
    dict(kind='commentary', target=PRAYER+'ashrei', lemma='אשרי', paras=[dict(text=(
        'The first two verses, which are taken from Psalms 84:5 and 144:15 and prefixed to Psalm 145, '
        'contain the word <tei:foreign xml:lang="he">אשרי</tei:foreign> three times. '
        '<tei:hi rend="italic">Ashre</tei:hi> is recited twice in the morning service and once in the evening service. '
        'The Talmud asserts that “whoever recites this psalm three times a day is assured of his share '
        'in the world to come” (Berakhoth 4b). This noble hymn of praise, calling upon all mankind '
        'to glorify God’s greatness, celebrates his providential care for all his creation. It is an '
        'acrostic psalm, the successive lines beginning with the letters of the Hebrew alphabet taken '
        'in order. However, the letter <tei:hi rend="italic">nun</tei:hi> is missing. The alphabetic '
        'arrangement is probably intended as an aid to memory.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/84/5', paras=[dict(text='<tei:hi rend="italic">Psalms</tei:hi> 84:5; 144:15.')]),
    dict(kind='commentary', target=BIBLE+'psalms/115/18', lemma='ואנחנו נברך', paras=[dict(text=(
        'is added from Psalm 115:18 so that <tei:foreign xml:lang="he">אשרי</tei:foreign>, '
        'like the five subsequent psalms, may end with <tei:hi rend="italic">Halleluyah</tei:hi>.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/115/18', paras=[dict(text='<tei:hi rend="italic">Psalm</tei:hi> 115:18.')]),
    dict(kind='commentary', target=BIBLE+'psalms/147/9', lemma='לבני עורב', paras=[dict(text=(
        'that is, God sends food to the abandoned young birds that are unable to provide for themselves. '
        'The raven turns its young out of the nest at an early period.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/148/4', lemma='המים . . . מעל השמים', paras=[dict(text=(
        'According to Genesis 1:6–7, there are waters above the heavens.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/149/1', lemma='שיר חדש', paras=[dict(text=(
        'a new song, in acknowledgment of a fresh act of deliverance by God which merits a new song of thanksgiving.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/149/4', lemma='יפאר ענוים', paras=[dict(text=(
        'God restores the dignity and honor to those who have been humiliated and degraded.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/149/5', lemma='ירננו על משכבותם', paras=[dict(text=(
        'that is, they can lie down in peace, their foes having been defeated.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/149/6', lemma='רוממות–חרב . . .', paras=[dict(text=(
        'The Maccabean warriors were described as “fighting with their hands and praying with their hearts.”'))]),
    dict(kind='commentary', target=BIBLE+'psalms/150/3', paras=[dict(text=(
        'According to Josephus, the <tei:foreign xml:lang="he">נבל</tei:foreign> had twelve strings '
        'and the <tei:foreign xml:lang="he">כנור</tei:foreign> ten.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/150/4', lemma='מחול', paras=[dict(text=(
        'The dance was an important part of religious ceremonies. “David danced before the Lord with '
        'all his might” (II Samuel 6:14). <tei:foreign xml:lang="he">עוגב</tei:foreign> was a wind '
        'instrument, a flute, which was called <tei:foreign xml:lang="he">אבוב</tei:foreign> '
        'in the period of the second Temple.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/150/5', lemma='צלצלי שמע', paras=[dict(text=(
        'cymbals of soft sound, castanets or metal discs fixed to two fingers of the hand. '
        '<tei:foreign xml:lang="he">צלצלי תרועה</tei:foreign> cymbals of loud sound, constructed of copper.'))]),
    dict(kind='commentary', target=BIBLE+'psalms/150/6', lemma='כל הנשמה', paras=[dict(text=(
        'is repeated because this verse marks the end of the Book of Psalms.'))]),
    dict(kind='commentary', target=ROOT+'barukh_adonai', paras=[dict(text='<tei:hi rend="italic">Psalms</tei:hi> 89:53; 135:21; 72:18–19.')]),
    dict(kind='commentary', target=BIBLE+'nehemiah/9/8', lemma='וכרות', paras=[dict(text=(
        'is recited responsively on the occasion of a <tei:hi rend="italic">Brith Milah</tei:hi>; '
        'hence it has been arranged as a new paragraph. <tei:foreign xml:lang="he">וכרות</tei:foreign> '
        'is part of the preceding verse.'))]),
    dict(kind='commentary', target=ROOT+'az_yashir', lemma="ה׳ ימלוך", paras=[dict(text=(
        'is said twice to mark the end of <tei:foreign xml:lang="he">שירת הים</tei:foreign> (Abudarham).'))]),
    dict(kind='commentary', target=ROOT+'ki_ladonai', paras=[dict(text=(
        '<tei:hi rend="italic">Psalm</tei:hi> 22:29; <tei:hi rend="italic">Obadiah</tei:hi> 1:21; '
        '<tei:hi rend="italic">Zechariah</tei:hi> 14:9.'))]),
    dict(kind='commentary', target=PRAYER+'yishtabbach', lemma='ישתבח', paras=[dict(text=(
        'and <tei:foreign xml:lang="he">ברוך שאמר</tei:foreign> form the prologue and the epilogue '
        'to <tei:hi rend="italic">Pesuke d’Zimrah</tei:hi>. It has been suggested that the name of '
        'the author of <tei:hi rend="italic">Yishtabaḥ</tei:hi> was Solomon, since the initial letters '
        'of the words <tei:foreign xml:lang="he">שמך לעד מלכנו האל</tei:foreign> form the acrostic '
        '<tei:foreign xml:lang="he">שלמה</tei:foreign>. According to some, the fifteen synonyms of '
        'praise correspond to the fifteen psalms known as <tei:foreign xml:lang="he">שיר המעלות</tei:foreign>.'))]),
]
