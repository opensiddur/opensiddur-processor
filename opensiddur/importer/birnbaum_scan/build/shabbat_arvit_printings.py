"""Repeat-printing provenance and exact page turns for printed 257–284."""
from .common import pb

RANGES = {
 'barekhu':(257,257),'arvit_maariv':(257,257),'arvit_ahavat':(257,257),
 'shema':(257,261),'arvit_emet':(261,261),'arvit_hashkivenu':(261,263),
 'amidah_adonai_sefatai':(265,265),'amidah_avot':(265,265),
 'amidah_gevurot':(265,265),'amidah_qedushat_hashem':(267,267),
 'amidah_avodah':(267,269),'yaaleh_veyavo':(267,269),'amidah_hodaah':(269,271),
 'al_hanissim_chanukah':(269,271),'amidah_shalom_rav':(271,271),
 'amidah_shalom_hamevarekh':(271,271),'amidah_shalom_besefer_chayyim':(271,271),
 'amidah_elohai_netzor':(271,273),'amidah_yehi_ratzon':(273,273),
 'conclusion_titqabbal':(275,275),'conclusion_aleinu':(277,279),
 'conclusion_al_tira':(279,279),'conclusion_psalm_27':(281,281),'poem_adon_olam':(281,283),
}


def apply(lang,prayers):
    side=int(lang=='en'); by_name={p['name']:p for p in prayers}
    for name,(first,last) in RANGES.items():
        p=by_name[name];p['printings']=(*p.get('printings',()),(first+side,last+side))
    for name in ('kaddish_derabbanan_yitgaddal','kaddish_derabbanan_yehe_shemeh','kaddish_derabbanan_yitbarakh','kaddish_yatom'):
        p=by_name[name]
        pages=(275,279) if name=='kaddish_yatom' else (263,275,279)
        p['printings']=(*p.get('printings',()),*((n+side,n+side) for n in pages))
    def before(name,he,en,page):
        p=by_name[name];anchor=(he,en)[side]
        if p['body'].count(anchor)!=1:raise ValueError(f'Ambiguous Shabbat Arvit page {page}: {name}: {anchor!r}')
        p['body']=p['body'].replace(anchor,pb(page+side,sigil='1949 shabbat/arvit')+anchor,1)
    before('shema','לְבָבֶֽךָ.', 'teach them diligently',259)
    before('shema','אֲנִי יְיָ אֱלֹהֵיכֶם, אֲשֶׁר','am the Lord your God who',261)
    before('arvit_hashkivenu','תַּסְתִּירֵֽנוּ','for thou art our protecting',263)
    before('amidah_qedushat_hashem','אַתָּה קָדוֹשׁ','Thou art holy',267)
    before('yaaleh_veyavo','וְזִכְרוֹן כָּל עַמְּךָ','ascend and come',269)
    before('al_hanissim_chanukah','וּלְךָ עָשִֽׂיתָ','of the students of thy Torah',271)
    before('amidah_elohai_netzor','יְדִידֶֽיךָ','and answer me.',273)
    before('conclusion_aleinu','אֵלֶֽיךָ כָּל רִשְׁעֵי','thy name, and all the wicked',279)
    before('poem_adon_olam','וְהוּא אֵלִי','He is my God',283)
    return prayers
