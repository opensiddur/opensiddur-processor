# -*- coding: utf-8 -*-
"""Birnbaum's English for the Torah blessings and Birkhoth ha-Shaḥar, pages 14 to 20.

Same URNs as the Hebrew, which is what aligns them.

**One blessing here is not in any transcription of this page.** Printed 16 ends with the
blessing beginning *who hast not made me…*, and both the en.wikisource text and the
Internet Archive OCR stop one blessing earlier. It was read off the page image instead --
see `readings/english_14_20.md`. Two derived witnesses agreeing with each other and with
neither the page nor each other's gaps is exactly why the page is the evidence here.

**The English runs two passages together where the Hebrew parts them.** Printed 20 sets the
tail of the Yehi Ratzon and the blessing that follows it as one paragraph; printed 19 sets
two. As with Mah Tovu on pages 3 and 4, each side keeps the paragraphing the print gives
it and the parting is named on both, so the columns pair instead of drifting.
"""
import functools

from .common import PRAYER
from . import common

pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

U = PRAYER

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug,
                        first=first, last=last, body=body))


def d(urn, *paras, indent=8):
    pad = " " * indent
    inner = "\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\n{inner}\n{pad}</tei:div>'


prayer('asher_yatzar', 'Asher Yatzar', 'asher_yatzar', 14, 14,
       d(U + 'asher_yatzar', 'Blessed art thou, Lord our God, King of the universe, who hast formed man in wisdom, and created in him a system of veins and arteries. It is well known before thy glorious throne that if but one of these be opened, or if one of those be closed, it would be impossible to exist in thy presence. Blessed art thou, O Lord, who healest all creatures and doest wonders.'))

prayer('birkhot_hatorah_laasoq', 'Birkhot Hatorah Laasok', 'birkhot_hatorah/laasoq', 14, 14,
       d(U + 'birkhot_hatorah/laasoq', 'Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, and commanded us to study the Torah.'))

prayer('birkhot_hatorah_vehaarev', 'Birkhot Hatorah Vehaarev', 'birkhot_hatorah/vehaarev', 14, 14,
       d(U + 'birkhot_hatorah/vehaarev', 'Lord our God, make the words of thy Torah pleasant in our mouth and in the mouth of thy people, the house of Israel, so that we and our descendants and the descendants of thy people, the house of Israel, may all know thy name and study the Torah for its own sake. Blessed art thou, O Lord, who teachest the Torah to thy people Israel.'))

prayer('birkhot_hatorah_asher_bachar', 'Birkhot Hatorah Asher Bachar', 'birkhot_hatorah/asher_bachar', 14, 14,
       d(U + 'birkhot_hatorah/asher_bachar', 'Blessed art thou, Lord our God, King of the universe, who hast chosen us from all peoples and given us thy Torah. Blessed art thou, O Lord, Giver of the Torah.'))

prayer('birkat_kohanim', 'Birkat Kohanim', 'birkat_kohanim', 16, 16,
       d(U + 'birkat_kohanim', pb(16) + 'May the Lord bless you and protect you; may the Lord countenance you and be gracious to you; may the Lord favor you and grant you peace.'))

prayer('ellu_devarim', 'Elu Devarim', 'ellu_devarim', 16, 16,
       d(U + 'ellu_devarim', 'These are the things for which no limit is prescribed: the corner of the field, the first-fruits, the pilgrimage offerings, the practice of kindness, and the study of the Torah. These are the things of which a man enjoys the fruits in this world, while the principal remains for him in the hereafter, namely: honoring father and mother, practice of kindness, early attendance at the schoolhouse morning and evening, hospitality to strangers, visiting the sick, dowering the bride, attending the dead to the grave, devotion in prayer, and making peace between fellow men; but the study of the Torah excels them all.'))

prayer('elohai_neshamah', 'Elohai Neshamah', 'elohai_neshamah', 16, 16,
       d(U + 'elohai_neshamah', 'My God, the soul which thou hast placed within me is pure. Thou hast created it; thou hast formed it; thou hast breathed it into me. Thou preservest it within me; thou wilt take it from me, and restore it to me in the hereafter. So long as the soul is within me, I offer thanks before thee, Lord my God and God of my fathers, Master of all creatures, Lord of all souls. Blessed art thou, O Lord, who restorest the souls to the dead.'))

prayer('birkhot_lasekhvi', 'Lasekhvi', 'birkhot_hashachar/lasekhvi', 16, 16,
       d(U + 'birkhot_hashachar/lasekhvi', 'Blessed art thou, Lord our God, King of the universe, who hast given the cock intelligence to distinguish between day and night.'))

prayer('birkhot_shelo_asani_goy', 'Shelo Asani Goy', 'birkhot_hashachar/shelo_asani_goy', 16, 16,
       d(U + 'birkhot_hashachar/shelo_asani_goy', 'Blessed art thou, Lord our God, King of the universe, who hast not made me a heathen.'))

prayer('birkhot_shelo_asani_aved', 'Shelo Asani Aved', 'birkhot_hashachar/shelo_asani_aved', 18, 18,
       d(U + 'birkhot_hashachar/shelo_asani_aved', pb(18) + 'Blessed art thou, Lord our God, King of the universe, who hast not made me a slave.'))

prayer('birkhot_shelo_asani_ishah', 'Shelo Asani Ishah', 'birkhot_hashachar/shelo_asani_ishah', 18, 18,
       d(U + 'birkhot_hashachar/shelo_asani_ishah', 'Blessed art thou, Lord our God, King of the universe, who hast not made me a woman.'))

prayer('birkhot_sheasani_kirtzono', 'Sheasani Kirtzono', 'birkhot_hashachar/sheasani_kirtzono', 18, 18,
       d(U + 'birkhot_hashachar/sheasani_kirtzono', 'Blessed art thou, Lord our God, King of the universe, who hast made me according to thy will.'))

prayer('birkhot_poqeach_ivrim', 'Pokeach Ivrim', 'birkhot_hashachar/poqeach_ivrim', 18, 18,
       d(U + 'birkhot_hashachar/poqeach_ivrim', 'Blessed art thou, Lord our God, King of the universe, who openest the eyes of the blind.'))

prayer('birkhot_malbish_arummim', 'Malbish Arumim', 'birkhot_hashachar/malbish_arummim', 18, 18,
       d(U + 'birkhot_hashachar/malbish_arummim', 'Blessed art thou, Lord our God, King of the universe, who clothest the naked.'))

prayer('birkhot_mattir_asurim', 'Matir Asurim', 'birkhot_hashachar/mattir_asurim', 18, 18,
       d(U + 'birkhot_hashachar/mattir_asurim', 'Blessed art thou, Lord our God, King of the universe, who settest the captives free.'))

prayer('birkhot_zoqef_kefufim', 'Zokef Kefufim', 'birkhot_hashachar/zoqef_kefufim', 18, 18,
       d(U + 'birkhot_hashachar/zoqef_kefufim', 'Blessed art thou, Lord our God, King of the universe, who raisest up those who are bowed down.'))

prayer('birkhot_roqa_haaretz', 'Roka Haaretz', 'birkhot_hashachar/roqa_haaretz', 18, 18,
       d(U + 'birkhot_hashachar/roqa_haaretz', 'Blessed art thou, Lord our God, King of the universe, who spreadest forth the earth above the waters.'))

prayer('birkhot_sheasah_li', 'Sheasah Li', 'birkhot_hashachar/sheasah_li', 18, 18,
       d(U + 'birkhot_hashachar/sheasah_li', 'Blessed art thou, Lord our God, King of the universe, who hast provided for all my needs.'))

prayer('birkhot_hamekhin', 'Hamekhin', 'birkhot_hashachar/hamekhin', 18, 18,
       d(U + 'birkhot_hashachar/hamekhin', 'Blessed art thou, Lord our God, King of the universe, who guidest the steps of man.'))

prayer('birkhot_ozer_yisrael', 'Ozer Yisrael', 'birkhot_hashachar/ozer_yisrael', 18, 18,
       d(U + 'birkhot_hashachar/ozer_yisrael', 'Blessed art thou, Lord our God, King of the universe, who girdest Israel with might.'))

prayer('birkhot_oter_yisrael', 'Oter Yisrael', 'birkhot_hashachar/oter_yisrael', 18, 18,
       d(U + 'birkhot_hashachar/oter_yisrael', 'Blessed art thou, Lord our God, King of the universe, who crownest Israel with glory.'))

prayer('birkhot_hanoten_layaef', 'Hanoten Layaef', 'birkhot_hashachar/hanoten_layaef', 18, 18,
       d(U + 'birkhot_hashachar/hanoten_layaef', 'Blessed art thou, Lord our God, King of the universe, who givest strength to the weary.'))

prayer('birkhot_hamaavir_shenah', 'Hamaavir Shenah', 'birkhot_hashachar/hamaavir_shenah', 18, 18,
       d(U + 'birkhot_hashachar/hamaavir_shenah', 'Blessed art thou, Lord our God, King of the universe, who removest sleep from my eyes and slumber from my eyelids.'))

prayer('birkhot_shetargilenu', 'Shetargilenu', 'birkhot_hashachar/shetargilenu', 18, 20,
       d(U + 'birkhot_hashachar/shetargilenu',
         'May it be thy will, Lord our God and God of our fathers, to make us familiar with thy Torah, and to cause us to adhere to thy precepts. Lead us not into sin, transgression, iniquity, temptation, or disgrace; let not the evil impulse have power over us; keep us far from an evil man and a bad companion; make us cling to'
         + " " + pb(20) + " "
         + 'the good impulse and to good deeds, and bend our will to submit to thee.'))

prayer('birkhot_gomel_chasadim', 'Gomel Chasadim', 'birkhot_hashachar/gomel_chasadim', 20, 20,
       d(U + 'birkhot_hashachar/gomel_chasadim', 'Grant us today, and every day, grace, favor and mercy, both in thy sight and in the sight of all men, and bestow loving-kindness on us. Blessed art thou, O Lord, who bestowest loving kindness on thy people Israel.'))

prayer('birkhot_shetatzileni', 'Shetatzileni', 'birkhot_hashachar/shetatzileni', 20, 20,
       d(U + 'birkhot_hashachar/shetatzileni', 'May it be thy will, Lord my God and God of my fathers, to deliver me today, and every day, from impudent men and from insolence; from an evil man, a bad companion, and a bad neighbor; from an evil occurrence and from the destructive adversary; from an oppressive lawsuit and from a hard opponent, be he a man of the covenant or not.'))

prayer('birkhot_zokhrenu', 'Zochreinu', 'birkhot_hashachar/zokhrenu', 20, 20,
       d(U + 'birkhot_hashachar/zokhrenu', 'Our God and God of our fathers, remember us favorably, and visit us with mercy and salvation from the eternal high heavens. Remember in our favor, Lord our God, the love of our ancestors Abraham, Isaac and Israel thy servants. Remember the covenant, the kindness, and the oath which thou didst swear to our father Abraham on Mount Moriah, and the binding of Isaac his son on the altar, as it is written in thy Torah:'))
