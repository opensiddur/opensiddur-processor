"""Calendar selection, bounded references, and complete bilingual poems."""
import unittest

from lxml import etree as E

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import omer_akdamut as o
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN

from .test_tachanun_conditions import NS, evaluate, fragment


class TestOmerAkdamut(unittest.TestCase):
    def test_counting_selects_exactly_one_of_all_49_days(self):
        body=next(u['body'] for u in o.units(o.PROJECT_HE) if u['name']=='omer_counting')
        nodes=fragment(body).xpath('.//j:conditional',namespaces=NS)
        self.assertEqual(len(nodes),49)
        for day in range(51):
            selected=[]
            for i,node in enumerate(nodes,1):
                expr=node.find('tei:fs',NS)
                result=evaluate(E.tostring(expr,encoding='unicode'),{('opensiddur:holiday','omer'):day})
                if result==TriState.TRUE:selected.append(i)
            self.assertEqual(selected,[day] if 1<=day<=49 else [])
        for node in nodes:
            self.assertEqual(evaluate(E.tostring(node.find('tei:fs',NS),encoding='unicode'),{}),TriState.UNDEFINED)
    def test_occasion_gates_belong_to_callers(self):
        units={u['urn']:u['body'] for u in o.units(o.PROJECT_HE)}
        self.assertNotIn('j:conditional',units[o.OMER])
        self.assertNotIn('j:conditional',units[o.AKDAMUT_URN])
        for day in (0,1,49,50):
            self.assertEqual(evaluate(o.SEASON,{('opensiddur:holiday','omer'):day}),TriState.TRUE if 1<=day<=49 else TriState.FALSE)
        for day in (0,1,2):
            self.assertEqual(evaluate(o.holiday('shavuot'),{('opensiddur:holiday','shavuot'):day}),TriState.TRUE if day==1 else TriState.FALSE)
    def test_poem_complete_aligned_and_bounded(self):
        for project in (o.PROJECT_HE,PROJECT_EN):
            body=next(u['body'] for u in o.units(project) if u['urn']==o.AKDAMUT_URN)
            doc=fragment(body)
            self.assertEqual(len(doc.xpath('.//tei:l',namespaces=NS)),90)
            starts=doc.xpath('.//tei:milestone[@corresp]',namespaces=NS)
            self.assertEqual([n.get('corresp') for n in starts],[o.AKDAMUT_URN+'/'+str(i) for i in range(1,46)])
            self.assertEqual(len(doc.xpath('.//tei:milestone[not(@corresp)]',namespaces=NS)),45)
        # Double alphabet plus author's name and closing petition: a consonant-level
        # independent completeness check, not just an expected element count.
        initial=''.join(line[0] for row in o.AKDAMUT for line in row['he'].splitlines())
        self.assertEqual(initial[:44],''.join(c*2 for c in 'אבגדהוזחטיכלמנסעפצקרשת'))
        self.assertEqual(initial[44:],'מאירביררבייצחקיגדלבתורהובמעשיםטוביםאמןוחזקואמץ'.translate(str.maketrans('ךםןףץ','כמנפצ')))
    def test_biblical_sources_and_logical_holam(self):
        prayers={p['urn']:fragment(p['body']) for p in o.prayers('he')}
        psalm=prayers[o.URNS['psalm_67']]
        self.assertEqual(psalm.xpath('.//tei:seg/@source',namespaces=NS),[o.BIBLE+'psalms/67/'+str(i) for i in range(1,9)])
        for key in ('preparation','ribbono'):
            self.assertEqual(prayers[o.URNS[key]].xpath('.//tei:seg/@source',namespaces=NS),[o.BIBLE+'leviticus/23/15',o.BIBLE+'leviticus/23/16'])
        self.assertIn('מֹשֶׁה',next(r['he'] for r in o.ROWS if r['key']=='ribbono'))
