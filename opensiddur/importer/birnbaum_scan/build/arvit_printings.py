"""Pagination and provenance for Arvit's shared readings (printed 191–220)."""
from .common import pb

RANGES = {
 'barekhu':(191,191), 'shema':(193,195),
 'amidah_adonai_sefatai':(199,199), 'amidah_avot':(199,201),
 'amidah_gevurot':(201,201), 'amidah_qedushat_hashem':(201,201), 'amidah_binah':(201,201),
 'amidah_teshuvah':(203,203), 'amidah_selichah':(203,203), 'amidah_geullah':(203,203),
 'amidah_refuah':(203,203), 'amidah_shanim':(203,203), 'amidah_qibbutz_galuyot':(203,203),
 'amidah_mishpat':(203,203), 'amidah_minim':(205,205), 'amidah_tzaddiqim':(205,205),
 'amidah_yerushalayim':(205,205), 'amidah_david':(205,205), 'amidah_tefillah':(205,205),
 'amidah_avodah':(205,207), 'yaaleh_veyavo':(205,207), 'amidah_hodaah':(207,209),
 'al_hanissim_chanukah':(207,209), 'al_hanissim_purim':(209,209),
 'amidah_shalom_rav':(209,209), 'amidah_shalom_hamevarekh':(209,209),
 'amidah_shalom_besefer_chayyim':(209,211), 'amidah_elohai_netzor':(211,211),
 'amidah_yehi_ratzon':(211,211), 'conclusion_titqabbal':(213,213),
 'conclusion_aleinu':(213,215), 'conclusion_al_tira':(215,215),
 'conclusion_psalm_27':(215,217), 'conclusion_psalm_49':(217,219),
}


def apply(lang, prayers):
    side=int(lang=='en')
    by_name={p['name']:p for p in prayers}
    for name,(first,last) in RANGES.items():
        p=by_name[name]
        p['printings']=(*p.get('printings',()),(first+side,last+side))
    # Kaddish has several distinct occurrences in this service.
    for name, ranges in {
        'kaddish_derabbanan_yitgaddal':((189,189),(199,199),(211,211),(215,215),(219,219)),
        'kaddish_derabbanan_yehe_shemeh':((189,189),(199,199),(211,211),(215,215),(219,219)),
        'kaddish_derabbanan_yitbarakh':((189,189),(199,199),(211,211),(215,215),(219,219)),
        'kaddish_yatom':((213,213),(215,215),(217,217),(219,219)),
    }.items():
        p=by_name[name]
        p['printings']=(*p.get('printings',()),*((a+side,b+side) for a,b in ranges))
    def before(name,he,en,page,section='amidah'):
        p=by_name[name]; anchor=(he,en)[side]
        if p['body'].count(anchor)!=1:
            raise ValueError(f'Ambiguous Arvit page {page}: {name} {anchor!r}')
        p['body']=p['body'].replace(anchor,pb(page+side,sigil='1949 chol/arvit/'+section)+anchor,1)
    before('shema','אֲלֵהֶם','Israel and tell them',195,'shema')
    before('amidah_avot','מֶֽלֶךְ עוֹזֵר','O King, Supporter',201)
    before('amidah_teshuvah','הֲשִׁיבֵֽנוּ','Restore us, our Father',203)
    before('amidah_minim','וְלַמַּלְשִׁינִים','May the slanderers',205)
    before('yaaleh_veyavo','וְזִכְרוֹן מָשִֽׁיחַ','Jerusalem thy holy city',207)
    before('al_hanissim_chanukah','טְהוֹרִים.','into the hands of the righteous',209)
    before('amidah_shalom_besefer_chayyim','לְפָנֶֽיךָ, אֲנַֽחְנוּ','for a happy life and for peace',211)
    before('conclusion_aleinu','לְעוֹלָם וָעֶד.', '“The Lord shall be King forever',215,'conclusion')
    before('conclusion_psalm_27','עָלַי מִלְחָמָה','war should arise against me',217,'psalms')
    before('conclusion_psalm_49','אֲדָמוֹת.','generations; they name',219,'psalms')
    return prayers
