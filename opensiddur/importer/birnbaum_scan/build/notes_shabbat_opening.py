"""Commentary and citation read from printed pages 221–236."""
from .common import PRAYER
from .notes_minchah import note

SONG = 'urn:x-opensiddur:text:bible:song_of_songs'

def song(ref, lemma, text):
    return note(SONG+'/'+ref, text, lemma=lemma)

NOTES = [
 note(PRAYER+'hadlaqat_ner_shabbat',
    'the blessing pronounced at the lighting of the Sabbath light, is not cited in the Talmud but is found in the ninth century <tei:hi rend="italic">Siddur</tei:hi> of Amram Gaon. The custom of lighting two lights is in keeping with the two terms “Remember” and “Observe” which introduce the Sabbath Commandment in Exodus 20:8 and Deuteronomy 5:12, respectively. The lights are symbolical of the cheerfulness and serenity which distinguish the holy days.', lemma='ברכת הנר'),
 note(PRAYER+'birkat_horim',
    'the blessing of children by their parents on all important occasions, notably on the eve of Sabbaths and festivals, is one of the most beautiful customs. The <tei:hi rend="italic">Brantspiegel</tei:hi>, a treatise on morals published in 1602, mentions this in the following terms: “Before the children can walk they should be carried on Sabbaths and festivals to the father and mother to be blessed; after they are able to walk they shall go of their own accord with bowed body and shall incline their heads and receive the blessing.” This custom has linked the generations together in mutual loyalty and affection.', lemma='ברכת הורים'),
 note(PRAYER+'birkat_horim', 'Numbers 6:24–26.', kind='citation', n='1'),
 note(SONG+'/1/1',
    'is recited every Friday evening because of the religious idealism attached to it by tradition. The poem has been accepted throughout the ages as an allegory of the relations between God and his people. Some nineteen centuries ago, Rabbi Akiba declared: “All the <tei:hi rend="italic">Kethubim</tei:hi> are holy, but the Song of Songs is the holiest of all.” According to the paraphrase of the Targum, the poem portrays the history of Israel till the times of the Messiah. It has been regarded also as a representation of the affection of Israel for the Sabbath. The author of the poem <tei:foreign xml:lang="he">לכה דודי</tei:foreign>, “one of the finest pieces of religious poetry in existence,” used the theme of the Sabbath bride and borrowed the title of his famous hymn from the Song of Songs (7:12). Although its meaning has been extended by various methods of interpretation, one cannot miss the beauty of the poem in its literal interpretation. Its author takes us along with him into the open air, to the vineyards, the villages, the mountains. He awakens us at daybreak to catch the scent of the forest trees, to gather the apples and the pomegranates. His verse is fragrant with the breath of spring.', lemma='שיר השירים'),
 song('1/5','קדר','a tribe of nomads who wandered in the Arabian desert.'),
 song('1/6','כרמי שלי','that is, my personal beauty. The phrase is often used in the sense of neglecting one’s family while being engrossed in public duties.'),
 song('1/9','לסוסתי','The point of comparison is the rich ornamentation of the bride.'),
 song('1/17','רהיטנו','our rafters, panelled ceilings. The cedar trees and fir trees form the roof over their heads as they sit in the green grass.'),
 song('2/1','חבצלת השרון','She modestly compares herself to the wild flowers of Sharon.'),
 song('2/7','צבאות, אילות','are symbolic of shyness and timidity as well as of beauty.'),
 song('2/7','עד שתחפץ','that is, it should be allowed to awake of itself. A true love is spontaneous.'),
 song('2/15','אחזו לנו שועלים','is a couplet of a vineyard song which she sings in response to his request to let him hear her voice.'),
 song('2/17','ונסו הצללים','the shadows of rocks and trees disappear when the sun sets.'),
 song('3/1','על משכבי . . .','is a dream she narrates to her friends.'),
 song('3/6','תמרות עשן','the pillars of smoke are caused by the burning of incense.'),
 song('4/1','שערך . . .','The bride’s dark hair, hanging down in tresses over her shoulders, is compared to a herd of black goats couching on the slopes of the hill.'),
 song('4/2','מתאימות','symmetrical, running accurately in pairs, the upper teeth corresponding to the lower.'),
 song('4/3','כפלח הרמון','like the rounded form and ruddy color of a pomegranate.'),
 song('4/4','בנוי לתלפיות','is an allusion to the bride’s necklace. On shields used as adornments on the outside of towers, see Ezekiel 27:10–11.'),
 song('4/8','אתי מלבנון . . .','is a warning to flee from Lebanon being full of dangers.'),
 song('4/8','תשורי מ . . .','depart; compare <tei:foreign xml:lang="he">ותשורי</tei:foreign> (Isaiah 57:9) “you journeyed.”'),
 song('4/9','אחותי','is used here in the sense of “my own.”'),
 song('4/11','נפת','honey that drips from the honeycomb. The reference is to loving words.'),
 song('4/16','צפון, תימן','The north wind clears the air in Palestine; the south wind warms and ripens. The east and west winds are stormy.'),
 song('5/8','מה','is here used in the sense of “not.” Compare below <tei:foreign xml:lang="he">מה תעירו ומה תעוררו את האהבה</tei:foreign> (8:4); <tei:foreign xml:lang="he">מה לנו חלק בדוד ולא נחלה בבן־ישי</tei:foreign> (I Kings 12:16).'),
 song('5/14','ידיו . . .','his fingers are delicately rounded, and his nails are as transparent as topaz. <tei:foreign xml:lang="he">ספירים</tei:foreign> the bright blue veins showing through the lighter skin.'),
 song('6/4','תרצה','(“delight”) was an ancient city famed for its attractiveness. It is mentioned in Joshua 12:24; I Kings 14:17.'),
 song('7/1','מה תחזו בשולמית','are the words of the Shulammite, who asks why they would stare at her as at a public spectacle.'),
 song('7/3','בטנך','“your body,” like <tei:foreign xml:lang="he">נפשי ובטני</tei:foreign> (“my soul and my body”) in Psalm 31:10.'),
 song('7/5','צוארך כמגדל השן','white, straight and slender.'),
 song('7/5','ברכות בחשבון','refers to the soft shimmer of her eyes.'),
 song('7/5','אפך כמגדל הלבנון','straight and symmetrical. The tower of Lebanon was probably some watch-tower in the direction of Damascus.'),
 song('7/6','כרמל','an emblem of stateliness and beauty. The point of comparison is a head proudly held.'),
 song('8/5','מי זאת עולה . . .','She points out incidents and places that are memorable to both of them.'),
 song('8/6','חותם','signet ring, engraved with the owner’s name or some design. The seal, affixed as signature to letters and documents, was worn on the finger or was strung on a cord and hung around the neck. She wishes to be united in the closest way with her beloved.'),
 song('8/6','שלהבתיה','a flame of supernatural, stupendous power.'),
 song('8/8','אחות לנו קטנה','was the speech of her brothers in the past, when she was still too young to marry. She recalls having heard them say that they would reward her modesty with adornments and provide strong protection in the case of any sign of moral weakness.'),
 song('8/9','אם חומה היא . . .','that is, if she preserves her innocence, we will reward her.'),
 song('8/11','כרם היה','that is, his possession is prized more than Solomon’s highly-cultivated vineyard with all its rich revenues.'),
 song('8/14','ברח דודי','is a repetition of her song in 2:17. Allegorically, it is a prayer addressed to God: Mayest thou hasten to reappear on Mount Moriah.'),
]
