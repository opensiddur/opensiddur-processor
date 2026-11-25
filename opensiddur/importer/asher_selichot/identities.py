"""Source-independent identities and matching filenames for reusable texts.

Reading IDs describe evidence units; they are not the identities of the prayers.
Use established registry names where present, otherwise the distinctive incipit.
The edition belongs only in the publication URN's @project suffix.
"""

BASE = 'urn:x-opensiddur:text:'


def project_name(lang):
    """The project of Asher's book in ``lang`` (specs/NAMING_SCHEME.md): it prints its own name
    in Latin letters, Selichoth."""
    return f'selichoth-asher-1912-{lang}'

#: URNs the readings name that are now another text's (see TEXTS): the build writes the new one.
RENAMED_URNS = {
    BASE + 'prayer:el_erekh_apayim': BASE + 'prayer:el_erekh_appayim_attah',
    BASE + 'prayer:vayaavor/selichot_preliminary': BASE + 'prayer:vayaavor',
}

# reading ID: (filename stem, canonical text identity)
TEXTS = {
    'invocation': ('lekha_adonai_hatsedaqah', 'prayer:lekha_adonai_hatsedaqah'),
    'scriptural_adoration': ('shomea_tefillah', 'prayer:shomea_tefillah'),
    'forgive_our_father': ('selah_lanu_avinu', 'prayer:selah_lanu_avinu'),
    'eikh_niftah': ('eikh_niftah_peh', 'poem:eikh_niftah_peh'),
    'mercy_invocation': ('ki_al_rahamekha', 'prayer:ki_al_rahamekha'),
    # Not Tachanun's אֵל אֶרֶךְ אַפַּיִם וְרַב חֶסֶד (prayer:el_erekh_appayim): another text.
    'el_erekh_apayim': ('el_erekh_appayim_attah', 'prayer:el_erekh_appayim_attah'),
    # Vayaavor and the Thirteen Attributes it introduces, printed in full on p. 11 (build.py).
    'vayaavor_before_selihot': ('vayaavor', 'prayer:vayaavor'),
    'morning_scriptural_petitions': ('adonai_boqer_tishma_qoli', 'prayer:adonai_boqer_tishma_qoli'),
    'selah_na': ('selah_na', 'prayer:selah_na'),
    'daniel_petition': ('hateh_elohai_oznekha', 'prayer:hateh_elohai_oznekha'),
    'ein_mi_yiqra': ('ein_mi_yiqra_betsedeq', 'poem:ein_mi_yiqra_betsedeq'),
    'miqveh_yisrael': ('miqveh_yisrael', 'prayer:miqveh_yisrael'),
    'im_avoneinu': ('im_avoneinu_rabu_lehagdil', 'poem:im_avoneinu_rabu_lehagdil'),
    'tavo_lefanekha_prayer': ('tavo_lefanekha_tefillatenu', 'prayer:tavo_lefanekha_tefillatenu'),
    'tavo_lefanekha_selihah': ('tavo_lefanekha_shavat_hinnun', 'poem:tavo_lefanekha_shavat_hinnun'),
    'zekhor_mercies': ('zekhor_rahamekha', 'prayer:zekhor_rahamekha'),
    'zekhor_covenant': ('zekhor_lanu_berit_rishonim', 'prayer:zekhor_lanu_berit_rishonim'),
    'shema_qolenu': ('shema_qolenu', 'prayer:shema_qolenu'),
    'amarenu_haazinah': ('amarenu_haazinah', 'prayer:amarenu_haazinah'),
    'confession_introduction': ('viduy_introduction', 'prayer:viduy/introduction'),
    'ashamnu': ('ashamnu', 'prayer:ashamnu'),
    'ashamnu_mikol': ('ashamnu_mikol_am', 'poem:ashamnu_mikol_am'),
    'leenenu': ('leenenu_ashuqu_amalenu', 'poem:leenenu_ashuqu_amalenu'),
    'meshihe_tsidqekha': ('meshiah_tsidqekha', 'prayer:meshiah_tsidqekha'),
    'el_rahum': ('el_rahum_shimkha', 'poem:el_rahum_shimkha'),
    'anenu': ('anenu', 'prayer:anenu'),
    'mi_sheanah': ('mi_sheanah', 'prayer:mi_sheanah'),
    'rahmana': ('rahmana', 'prayer:rahmana'),
    'vayomer_david': ('vayomer_david', 'prayer:vayomer_david'),
    'rahum_vehanun': ('rahum_vehanun', 'prayer:rahum_vehanun'),
    'psalm_6': ('psalm_6', 'bible:psalms/6'),
    'mahi_umasi': ('mahi_umasi', 'prayer:mahi_umasi'),
    'makhnise_rahamim': ('makhnise_rahamim', 'poem:makhnise_rahamim'),
    'maran_captive': ('maran_divishmaya_captive', 'poem:maran_divishmaya/captive'),
    'maran_slave': ('maran_divishmaya_slave', 'poem:maran_divishmaya/slave'),
    'shomer_yisrael': ('shomer_yisrael', 'prayer:tachanun/shomer_yisrael'),
    'shomer_ehad': ('shomer_goy_echad', 'prayer:tachanun/shomer_goy_echad'),
    'shomer_qadosh': ('shomer_goy_kadosh', 'prayer:tachanun/shomer_goy_kadosh'),
    'mitratseh': ('mitratseh_berahamim', 'prayer:mitratseh_berahamim'),
    'avinu_malkenu': ('avinu_malkenu_chonenu', 'prayer:avinu_malkenu/chonenu'),
    'vaanahnu_lo_neda': ('vaanahnu_lo_neda', 'prayer:vaanahnu_lo_neda'),
}


def text_urn(reading_id):
    return BASE + TEXTS[reading_id][1]
