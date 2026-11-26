"""Synthetic occasion boundaries and filenames for Shabbat/festival Arvit."""
import unittest
from unittest.mock import patch

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN, PROJECT_HE
from opensiddur.importer.birnbaum_scan.build.shabbat_arvit import (
    REGALIM,
    SHABBAT_AMIDAH,
    declaration,
    prayers,
    units,
)

from .test_tachanun_conditions import evaluate, fragment


class TestShabbatArvit(unittest.TestCase):
    def test_sabbath_amidah_is_replaced_on_festival(self):
        for shabbat,festival in ((True,False),(True,True),(False,True),(False,False)):
            values={('opensiddur:holiday-aggregate','shabbat'):shabbat,
                    ('opensiddur:holiday-aggregate','yom-tov'):festival}
            self.assertEqual(evaluate(SHABBAT_AMIDAH,values),
                             TriState.TRUE if shabbat and not festival else TriState.FALSE)
        self.assertEqual(evaluate(SHABBAT_AMIDAH,{}),TriState.UNDEFINED)

    def test_festival_verse_includes_atzeret_but_not_intermediate_days(self):
        holidays=('pesah','shavuot','sukkot','shmini-atzeret')
        for day in holidays:
            for yt in (True,False):
                values={('opensiddur:holiday',h):1 if h==day else 0 for h in holidays}
                values['opensiddur:holiday-aggregate','yom-tov']=yt
                self.assertEqual(evaluate(REGALIM,values),TriState.TRUE if yt else TriState.FALSE)

    def test_evening_declaration_does_not_override_calendar(self):
        root=fragment(declaration())
        ns={'t':'http://www.tei-c.org/ns/1.0'}
        self.assertFalse(root.xpath('.//t:fs[@type="opensiddur:holiday-aggregate"]',namespaces=ns))
        self.assertEqual(root.xpath('.//t:f[@name="repetition"]/t:binary/@value',namespaces=ns),['false'])
        self.assertEqual(root.xpath('.//t:f[@name="maariv"]/t:binary/@value',namespaces=ns),['true'])

    def test_prayer_filenames_cannot_overwrite_service_callers(self):
        # The bodies are synthetic: this checks the writer's naming contract,
        # independently of the evolving transcription or shared prayer corpus.
        with patch('opensiddur.importer.birnbaum_scan.build.shabbat_arvit.amidah',return_value='<tei:p>Synthetic Amidah.</tei:p>'):
            for lang,project in (('he',PROJECT_HE),('en',PROJECT_EN)):
                shared={'arvit_emet':{'body':'<tei:p><tei:milestone unit="prayer-part" corresp="urn:x-opensiddur:text:prayer:emet_veemunah/seal"/>Synthetic seal.<tei:milestone unit="prayer-part"/></tei:p>'}}
                files=prayers(lang,[])+list(units(project,shared))
                names=[f['name'] for f in files]
                self.assertEqual(len(names),len(set(names)))
