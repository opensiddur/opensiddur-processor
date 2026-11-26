"""Editorial mapping of Birnbaum's navigational instructions."""
import unittest

from lxml import etree

from opensiddur.importer.birnbaum_scan.build.page_references import dynamic_instructions


class TestDynamicInstructions(unittest.TestCase):
    def note(self, content, project='hasiddur_hashalem-birnbaum-1949-he'):
        return dynamic_instructions('<tei:note xmlns:tei="http://www.tei-c.org/ns/1.0" type="instruction">' + content + '</tei:note>', project)

    def test_facing_hallel_references_use_their_own_edition(self):
        for lang, number in [('he', 565), ('en', 566)]:
            project = 'hasiddur_hashalem-birnbaum-1949-' + lang
            out = self.note(f'Hallel (page {number}) is recited here.', project)
            self.assertIn('hallel/blessing@' + project, out)
            self.assertNotIn(str(number), out)
            self.assertEqual(dynamic_instructions(out, project), out)

    def test_independent_musaf_clauses(self):
        root = etree.fromstring(self.note('Musaf for Rosh Ḥodesh, page 575; for Ḥol ha-Mo‘ed, page 609.'))
        spans = root.findall('{http://www.tei-c.org/ns/1.0}seg')
        self.assertEqual(len(spans), 2)
        self.assertTrue(all(''.join(span.itertext()).startswith('Musaf for') for span in spans))

    def test_range_and_unrelated_tachanun_directions(self):
        root = etree.fromstring(self.note('On Mondays the long Taḥanun is said (pages 105–117). Taḥanun is omitted on Rosh Ḥodesh.'))
        self.assertEqual(len(root.findall('.//{http://www.tei-c.org/ns/1.0}ref')), 2)
        self.assertIn('Taḥanun is omitted on Rosh Ḥodesh.', root[0].tail)

    def test_commentary_bibliographic_pages_are_unchanged(self):
        xml = '<tei:note type="commentary">Maḥzor Vitry (page 214).</tei:note>'
        self.assertEqual(dynamic_instructions(xml, 'hasiddur_hashalem-birnbaum-1949-he'), xml)

    def test_known_misprinted_destination(self):
        out = self.note('Full-Kaddish by the Reader on page 405, where the service is continued.', 'hasiddur_hashalem-birnbaum-1949-en')
        self.assertIn('siddur:shabbat/musaf/kaddish@hasiddur_hashalem-birnbaum-1949-en', out)

    def test_musaf_direction_targets_musaf_despite_printed_page_error(self):
        out = self.note('On festivals, continue with Musaf on page 585.')
        self.assertIn('siddur:regalim/musaf@', out)
        self.assertNotIn('siddur:regalim/amidah@', out)
