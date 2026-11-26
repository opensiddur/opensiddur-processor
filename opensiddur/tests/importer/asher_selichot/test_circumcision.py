"""Distinct short refrains must select their own printed full verses."""
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot import penitential_days as service
from opensiddur.importer.asher_selichot.build import TEI


class CircumcisionTests(unittest.TestCase):
    def test_each_refrain_has_its_own_expansion(self):
        f={'he':dict(scan='s408',printed_page='203',text='א · והשב ושוב'),'notes':{'he':[]}}
        r=dict(fragments=[f],stanzas=[dict(fragments=[f])],refrain_cues={'he':'והשב|ושוב'},refrain={'he':''},refrain_expansions={'he':{'והשב':'וְהָשֵׁב שְׁבוּת','ושוב':'וְשׁוּב בְּרַחֲמִים'}})
        root=etree.Element('{'+TEI+'}body');service.pizmon(root,r,'he','urn:example')
        self.assertEqual([n.text for n in root.findall('.//{'+TEI+'}abbr')],['והשב','ושוב'])
        self.assertEqual([n.text for n in root.findall('.//{'+TEI+'}expan')],['וְהָשֵׁב שְׁבוּת','וְשׁוּב בְּרַחֲמִים'])

    def test_unresolved_marker_survives_normalization_as_superscript(self):
        from opensiddur.importer.scan.authoring import normalized_xml
        f={'en':dict(scan='s409',printed_page='203',text='The flesh?¹ No note follows.'),'notes':{'en':[]}}
        r=dict(fragments=[f],stanzas=[dict(fragments=[f])],refrain_cues={'en':'(?!)'},refrain={'en':''},literal_superscript_markers=['¹'])
        root=etree.Element('{'+TEI+'}body');service.pizmon(root,r,'en','urn:example')
        result=etree.fromstring(normalized_xml(root).encode())
        hi=result.find('.//{'+TEI+'}hi')
        self.assertEqual(hi.get('rend'),'superscript');self.assertEqual(hi.text,'1')
        self.assertEqual(hi.tail,' No note follows. ')

    def test_final_book_order_places_circumcision_after_monthly_service(self):
        from unittest.mock import patch

        from opensiddur.importer.asher_selichot.first_day import entry
        with patch('opensiddur.importer.asher_selichot.first_day.titles'):
            root=entry('he','example',{},book=True,remaining_services=tuple(d for d in service.SERVICES if d in service.FAST_SERVICES or d=='circumcision'))
        targets=[n.get('target')for n in root.findall('.//{'+service.J+'}transclude')]
        self.assertLess(targets.index('urn:x-opensiddur:text:siddur:selichot/yom_kippur_katan'),targets.index('urn:x-opensiddur:text:siddur:selichot/circumcision'))
