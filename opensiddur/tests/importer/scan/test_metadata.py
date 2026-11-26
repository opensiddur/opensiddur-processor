"""Machine metadata is evidence to verify, not an authoritative page label."""
import unittest

from opensiddur.importer.scan.metadata import derive_pages


class MetadataTests(unittest.TestCase):
    def test_sorts_scan_identity_and_keeps_duplicate_labels_and_unknowns(self):
        xml=b'<book><pageData><page leafNum="2"/><page leafNum="0"/><page leafNum="1"/></pageData></book>'
        corrections={
            '0':{'evidence':'image-a','printed_page':'14','printed_label':'xiv','language':'he','facing_leaf':1},
            '1':{'evidence':'image-b','printed_page':'14','language':'en','facing_leaf':0}}
        result=derive_pages('synthetic-item',xml,{'pages':[{'leafNum':0,'pageNumber':'1'}]},corrections)
        self.assertEqual(result['identifier'],'synthetic-item')
        pages=result['pages']
        self.assertEqual([p['scan_page'] for p in pages],[1,2,3])
        self.assertEqual([p['printed_page'] for p in pages],['14','14',None])
        self.assertEqual([p['facing_scan_page'] for p in pages],[2,1,None])
        self.assertEqual(pages[0]['machine_page_candidate'],'1')
        self.assertEqual(pages[0]['printed_label'],'xiv')
        self.assertIn('synthetic-item',pages[2]['facs'])
        self.assertIn('/n2_',pages[2]['facs'])
        self.assertIsNone(pages[2]['language'])

    def test_rejects_missing_leaf_evidence_and_nonreciprocal_pair(self):
        xml=b'<book><pageData><page leafNum="0"/></pageData></book>'
        for corrections in [{'1':{'evidence':'image'}},{'0':{'printed_page':'1'}},
                            {'0':{'evidence':'image','facing_leaf':1}}]:
            with self.subTest(corrections=corrections),self.assertRaises(ValueError):
                derive_pages('synthetic-item',xml,{'pages':[]},corrections)
