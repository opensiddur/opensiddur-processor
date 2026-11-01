"""Commentary and numbered citations on printed pages 103–118."""
from .tachanun import ROOT, URNS


def text(key):
    urn = URNS[key]
    return urn if ':bible:' in urn else urn + '/text'


NOTES = [
    dict(kind='commentary', target=ROOT + '/short', lemma='תחנון', paras=[dict(text=(
        '(“petition”) is recited in a sitting posture known as <tei:foreign xml:lang="he">נפילת אפים</tei:foreign> '
        '(“falling on the face”), which is a modified form of the complete prostration with the face to the ground '
        'practised in the early days of the Talmud (Megillah 22b). This custom originates from Moses, who '
        '“fell down before the Lord” (Deuteronomy 9:18), and Joshua, who “fell on the earth upon his face before '
        'the ark of the Lord” (Joshua 7:6). Hence, <tei:foreign xml:lang="he">נפילת אפים</tei:foreign> '
        'is performed only where there is a <tei:hi rend="italic">Sefer Torah</tei:hi>. It consists of merely '
        'resting the head on the arm. During the morning service, when the <tei:hi rend="italic">tefillin</tei:hi> '
        'are on the left arm, the right arm is used; at the <tei:hi rend="italic">Minḥah</tei:hi> service, however, '
        'the left arm is used. Since the verse <tei:foreign xml:lang="he">ויאמר דוד</tei:foreign> contains the phrase '
        '<tei:foreign xml:lang="he">נפלה נא</tei:foreign> (“let us fall”) it precedes '
        '<tei:foreign xml:lang="he">נפילת אפים</tei:foreign>, the falling posture assumed during the '
        '<tei:hi rend="italic">Taḥanun</tei:hi> prayer.'
    ))]),
    dict(kind='commentary', target=ROOT + '/short', lemma='גד', paras=[dict(text=(
        'was the name of the prophet who offered to David a choice of punishments, coming directly from God '
        'or through the agency of man. David replied that he preferred to be punished by the gracious God '
        'rather than by man.'
    ))]),
    dict(kind='commentary', target=text('vehu'), lemma='והוא רחום', paras=[dict(text=(
        'was composed, according to legend, soon after the destruction of the second Temple. It is suggested, '
        'however, that it was written during the persecutions of the seventh century. It has been said that '
        'whoever can read this long prayer without emotion has lost all feeling for what is great and noble. '
        'The soul of an entire people utters these elegies and supplications, and gives voice to its woe of '
        'a thousand years.'
    ))]),
    dict(kind='commentary', target=ROOT + '/long/nefilah', paras=[dict(text=(
        'On <tei:foreign xml:lang="he">נפילת אפים</tei:foreign>, the posture assumed during the recital of '
        '<tei:hi rend="italic">Taḥanun</tei:hi>, see page 103.'
    ))]),
]

for key, number, citation in (
    ('vayomer', '1', 'II Samuel 24:14.'),
    ('vaanachnu', '1', 'II Chronicles 20:12; Psalms 25:6; 33:22; 79:8; 123:3; Habakkuk 3:2; Psalm 103:14.'),
    ('vehu', '2', 'Psalm 78:38.'),
    ('vehu', '1', 'Psalms 40:12; 106:47; 130:3–4; 103:10; Jeremiah 14:7; Psalms 25:6; 20:2, 10.'),
    ('vehu', '2', 'Daniel 9:15–17.'),
    ('hatteh', '3', 'Daniel 9:18–19.'),
    ('hatteh', '4', 'Isaiah 64:7.'),
    ('hatteh', '5', 'Joel 2:17.'),
    ('hapoteach', '1', 'Deuteronomy 6:4.'),
):
    anchor = {
        ('vehu', 'Psalm 78:38.'): 'vehu_rachum',
        ('vehu', 'Daniel 9:15–17.'): 'veattah',
        ('hatteh', 'Daniel 9:18–19.'): 'hatteh',
        ('hatteh', 'Isaiah 64:7.'): 'veattah',
        ('hatteh', 'Joel 2:17.'): 'chusah',
    }.get((key, citation))
    if key == 'vehu' and number == '1':
        anchor = 'attah'
    target = URNS[key] + '/' + anchor if anchor else text(key)
    NOTES.append(dict(kind='citation', target=target, n=number, paras=[dict(text=citation)]))
