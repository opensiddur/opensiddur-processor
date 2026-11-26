"""Seasonal Half Kaddish selection must reach the shared Asher module."""
import tempfile
import unicodedata
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.asher_selichot.first_day import opening


class HalfKaddishTests(unittest.TestCase):
    def test_ten_days_doubles_and_ordinary_days_keep_one_leela(self):
        data=dict(start_scan='s6',next_scan='s8',next_label='3',heading='Service',
                  rubrics=[],kaddish_rubrics=[],prelude=['א','ב'],psalm=['ג']*21,
                  verse_9_continuation='ד',postlude='ה',kaddish_preface=['ו','ז'],
                  kaddish=['יִתְגַּדַּל׃','יְהֵא שְׁמֵהּ׃ יִתְבָּרַךְ לְעֵלָּא מִן כָּל בִּרְכָתָא׃'])
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);project=base/'test_project';project.mkdir()
            (project/'opening.xml').write_bytes(etree.tostring(opening('he','test_project',data)))
            for ten_days,count in [(False,1),(True,2)]:
                with self.subTest(ten_days=ten_days):
                    reset_linear_data();get_linear_data().xml_cache.base_path=base
                    CompilerProcessor.load_init_settings(get_linear_data(),yaml_to_declaration_entries(
                        {'opensiddur:holiday-aggregate':{'aseret-ymei-tshuva':ten_days}}))
                    tree=CompilerProcessor('test_project','opening.xml').process()
                    words=''.join(c for c in unicodedata.normalize('NFD',''.join(tree.itertext())) if 'א'<=c<='ת')
                    self.assertEqual(words.count('לעלא'),count)
                    self.assertIn('לעלאלעלאמןכל' if ten_days else 'לעלאמןכל',words)
        reset_linear_data()

    def test_compiled_check_rejects_missing_doubled_word(self):
        from opensiddur.importer.asher_selichot.first_day import verify_half_kaddish
        ns='http://jewishliturgy.org/ns/processing'
        service=etree.Element('service')
        passage=etree.SubElement(service,'{'+ns+'}transclude',target='urn:x-opensiddur:text:prayer:kaddish/chatzi')
        primary=etree.SubElement(passage,'{'+ns+'}parallelItem',role='primary')
        primary.text='לְעֵלָּא מִן כָּל בִּרְכָתָא'
        verify_half_kaddish(service,False)
        with self.assertRaisesRegex(ValueError,'seasonal reading'):
            verify_half_kaddish(service,True)
        primary.text='לְעֵלָּא לְעֵלָּא מִן כָּל בִּרְכָתָא'
        verify_half_kaddish(service,True)
        with self.assertRaisesRegex(ValueError,'seasonal reading'):
            verify_half_kaddish(service,False)
