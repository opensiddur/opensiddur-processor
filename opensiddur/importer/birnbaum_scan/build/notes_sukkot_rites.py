"""All printed notes,675–708, with cross-page continuations joined once."""
from .sukkot_rites import URNS, USHPIZIN, LULAV, HOSHANOT, GESHEM, HAKAFOT
from .sukkot_rites_data import NOTES as READINGS
from .notes_motzaei_shabbat import xml

TARGETS = {'אושפיזין':USHPIZIN,'נטילת לולב':LULAV,'הושענות':HOSHANOT,'processions':HOSHANOT,
 'למען אמתך':'hoshanot_hoshana_a','אבן שתיה':'hoshanot_hoshana_b','אם אני חומה':'hoshanot_hoshana_c',
 'אדון המושיע':'hoshanot_hoshia_start','אדם ובהמה':'hoshanot_adam','אדמה מארר':'hoshanot_adamah',
 'למען איתן':'hoshanot_lemaan_eitan','אערוך שועי':'hoshanot_eerokh_start','אל למושעות':'hoshanot_el_lemoshaot',
 'אני והו':'hoshanot_ani_vaho_1','כהושעת אלים':'hoshanot_kehosha_start','אם נצורה כבבת':'hoshanot_om_netzurah_start',
 'כהושעת אדם':'hoshanot_kehosha_adam_start','תתננו לשם':'hoshanot_tittenenu_start','אנא אזון':'hoshanot_anna_azon_1',
 'תעינו כשה':'hoshanot_el_na_1','למען תמים':'hoshanot_lemaan_tamim','תענה אמונים':'hoshanot_taaneh_emunim_first',
 'אז כעיני עבדים':'hoshanot_az_einei_first','קול מבשר':'hoshanot_qol_mevasser_response','אמץ ישעך':'hoshanot_qol_mevasser_first',
 'הושענא רבה':HOSHANOT+'/rabbah','יהי רצון':'hoshanot_yehi_ratzon_aravah','תפלת גשם':GESHEM,
 'אף ברי':'geshem_af_beri','זכור אב':'geshem_abraham_begin','משיב הרוח':'geshem_wind','שמחת תורה':HAKAFOT}
CITATIONS={'1':'attah_horeta','2':'leoseh','3':'ein_kamokha','4':'yehi_khevod','5':'yehi_shem','6':'yehi_immanu','7':'veimru','8':'strength','9':'vayehi','10':'qumah','11':'veamar','12':'malkhut','13':'zion'}
NOTES=[]
for r in READINGS:
    if r['kind']=='citation':
        key='lulav_lulav_intent' if r['page']==678 else 'haqqafot_'+CITATIONS[r['key']]
    else:key=TARGETS[r['key']]
    NOTES.append(dict(target=URNS.get(key,key),kind='source' if r['kind']=='citation' else 'commentary',lemma='',n='',paras=[dict(text=xml(r['text']))]))
