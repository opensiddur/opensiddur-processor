"""Minchah pagination on texts also printed in Shacharit.

Each break names its printing; it is not a new textual correspondence.
"""
from .common import pb

# Name, Hebrew first/last page; the English facing pages are one higher.
RANGES = {
    'ashrei': (157,159), 'amidah_adonai_sefatai': (159,159),
    'amidah_avot': (159,161), 'amidah_gevurot': (161,161),
    'amidah_qedushah': (161,163), 'amidah_qedushat_hashem': (163,163),
    'amidah_binah': (163,163), 'amidah_teshuvah': (163,163),
    'amidah_selichah': (163,163), 'amidah_geullah': (163,163),
    'amidah_aneinu': (163,169),
    'amidah_shalom_hamevarekh': (173,173), 'amidah_shalom_besefer_chayyim': (173,173),
    'amidah_refuah': (163,165), 'amidah_shanim': (165,165),
    'amidah_qibbutz_galuyot': (165,165), 'amidah_mishpat': (165,165),
    'amidah_minim': (165,165), 'amidah_tzaddiqim': (165,165),
    'amidah_yerushalayim': (167,167), 'amidah_david': (167,167),
    'amidah_tefillah': (167,169), 'amidah_avodah': (169,169),
    'yaaleh_veyavo': (169,169), 'amidah_hodaah': (171,173),
    'al_hanissim_chanukah': (171,173), 'al_hanissim_purim': (173,173),
    'amidah_elohai_netzor': (175,175), 'amidah_yehi_ratzon': (175,175),
    'avinu_malkenu': (175,179),
    'tachanun_vayomer': (181,181), 'tachanun_rachum': (181,181),
    'tachanun_psalm6': (181,181), 'tachanun_shomer_yisrael': (181,181),
    'tachanun_shomer_goy_echad': (181,181), 'tachanun_shomer_goy_qadosh': (181,181),
    'tachanun_mitratzeh': (183,183), 'tachanun_vaanachnu': (183,183),
    'conclusion_titqabbal': (183,183), 'conclusion_aleinu': (185,185),
    'conclusion_al_tira': (187,187),
}


def apply(lang, prayers):
    side = int(lang=='en')
    by_name = {p['name']:p for p in prayers}
    # Fail rather than silently dropping a reused passage from the provenance.
    for name, (first,last) in RANGES.items():
        p = by_name[name]
        p['printings'] = (*p.get('printings',()), (first+side,last+side))
    def before(name, anchor, page, section='amidah'):
        p = by_name[name]
        if p['body'].count(anchor)!=1:
            raise ValueError(f'Ambiguous Minchah page {page}: {name} {anchor!r}')
        p['body']=p['body'].replace(anchor,pb(page+side,sigil='1949 chol/minchah/'+section)+anchor,1)
    # Page turns are in the middle of shared paragraphs, independent of URNs.
    before('ashrei', 'סוֹמֵךְ' if not side else 'The Lord upholds',159,'opening')
    before('amidah_avot','אֱלֹהֵי יִצְחָק' if not side else 'of Abraham, God',161)
    before('amidah_qedushah','לְדוֹר וָדוֹר' if not side else 'Through all generations',163)
    before('amidah_refuah','נֶאֱמָן וְרַחֲמָן' if not side else 'Healer.',165)
    before('amidah_yerushalayim','וְלִירוּשָׁלַֽיִם' if not side else 'Return in mercy',167)
    p = by_name['amidah_hodaah']
    p['body'] = p['body'].replace('amidah/hodaah">', 'amidah/hodaah">'+pb(171+side, sigil='1949 chol/minchah/amidah'), 1)
    before('al_hanissim_chanukah','בְּחַצְרוֹת קָדְשֶֽׁךָ' if not side else 'sanctuary,',173)
    before('amidah_aneinu','מִתְּחִנָּתֵֽנוּ' if not side else 'presence from us',169,'amidah/tefillah')
    before('amidah_elohai_netzor','אֱלֹהַי, נְצֹר' if not side else 'My God, guard',175)
    before('avinu_malkenu','כַּלֵּה כָל צַר' if not side else 'rid us of every oppressor',177,'avinu_malkenu')
    before('avinu_malkenu','הָרֵם קֶֽרֶן מְשִׁיחֶֽךָ' if not side else 'raise the strength of thy anointed',179,'avinu_malkenu')
    # Petition ranges must end before the next occasion rubric, including
    # the service-dependent variant in the shared prayer.
    import re
    p=by_name['avinu_malkenu']
    p['body']=re.sub(r'(<tei:milestone unit="petition"[^>]*/>.*?)(</tei:p>)',
        r'\1<tei:milestone unit="petition"/>\2',p['body'],flags=re.S)
    return prayers
