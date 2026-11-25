import unittest

from opensiddur.importer.miqra_al_pi_hamasorah.miqra_plus import (
    PlusFormatError,
    PlusToIntermediate,
    _escape_outside_tags,
    _wikitext_basic_markup_to_xml,
    _xml_escape,
    check_plus_file,
    link_target_to_uri,
)


def t(name: str, **params) -> dict:
    """A plus template node; keys "1", "2"... are passed as p1, p2..."""
    node = {"tmpl_name": name}
    if params:
        node["tmpl_params"] = {key[1:] if key[0] == "p" and key[1:].isdigit() else key: value
                               for key, value in params.items()}
    return node


def convert(*nodes, column: str = "E") -> str:
    return PlusToIntermediate().column(list(nodes), column)


class TestLinkTargetToUri(unittest.TestCase):
    def test_empty_target(self):
        self.assertEqual(link_target_to_uri(""), "")
        self.assertEqual(link_target_to_uri("   "), "")

    def test_protocol_relative_url(self):
        self.assertEqual(
            link_target_to_uri("//cdn.example.com/x.pdf"),
            "https://cdn.example.com/x.pdf",
        )

    def test_fragment_preserved(self):
        uri = link_target_to_uri("דף#פרק")
        self.assertIn("#", uri)
        self.assertTrue(uri.startswith("https://he.wikisource.org/wiki/"))


class TestMarkupAndEscape(unittest.TestCase):
    def test_xml_escape(self):
        self.assertEqual(
            _xml_escape('a & b <c> "d" \'e\''),
            "a &amp; b &lt;c&gt; &quot;d&quot; &apos;e&apos;",
        )

    def test_wikitext_bold_italic(self):
        self.assertEqual(
            _wikitext_basic_markup_to_xml("plain '''bold''' ''italic''"),
            'plain <mw:hi rend="bold">bold</mw:hi> <mw:hi rend="italic">italic</mw:hi>',
        )

    def test_wikitext_bold_italic_combined(self):
        self.assertIn(
            'rend="bold-italic"',
            _wikitext_basic_markup_to_xml("'''''both'''''"),
        )

    def test_escape_outside_tags_preserves_miqra_elements(self):
        inner = _escape_outside_tags(
            "plain <miqra:hi rend=\"large\">א</miqra:hi> '''bold'''"
        )
        self.assertIn("<miqra:hi rend=\"large\">", inner)
        self.assertIn("א", inner)
        self.assertIn('rend="bold"', inner)

    def test_italics_in_a_note(self):
        frag = convert(t("נוסח", p1="דבר", p2="וכן ''ל'' שם"))
        self.assertIn('<mw:hi rend="italic">ל</mw:hi>', frag)

    def test_angle_brackets_in_a_note_are_text(self):
        frag = convert(t("נוסח", p1="דבר", p2="<א(ס)=מתג? כן>"))
        self.assertIn("&lt;א(ס)=מתג? כן&gt;", frag)


class TestPlusToIntermediate(unittest.TestCase):
    def test_documented_word_with_a_large_letter(self):
        word = t("מ:אות-מיוחדת-במילה", p1=[t("מ:אות-ג", p1="בְּ"), "רֵאשִׁ֖ית"],
                 p2="בְּרֵאשִׁ֖ית", p3="ב.....", p4="ג", p5="ב/ג")
        frag = convert(t("נוסח", p1=word, p2="note text"))
        self.assertIn('<miqra:variant noteId="miqra-note-1">', frag)
        self.assertIn('<miqra:hi rend="large">בְּ</miqra:hi>רֵאשִׁ֖ית', frag)
        self.assertIn('<miqra:note xml:id="miqra-note-1">note text</miqra:note>', frag)
        # The word's other representations are not rendered.
        self.assertNotIn("ב.....", frag)

    def test_documentation_note_on_a_space_keeps_the_space(self):
        frag = convert("הוּא", t("נוסח", p1=" ", p2="ל=פסקא באמצע פסוק"), "לֹא")
        self.assertIn("<miqra:display> </miqra:display>", frag)

    def test_ketiv_qeri(self):
        frag = convert(t("כו״ק", p1="כתיב", p2="קְרִי"))
        self.assertIn('<miqra:kq order="ketiv-first">', frag)
        self.assertIn("<miqra:ketiv>כתיב</miqra:ketiv>", frag)
        self.assertIn("<miqra:qeri>קְרִי</miqra:qeri>", frag)

    def test_qeri_ketiv(self):
        frag = convert(t("קו״כ", p1="כתיב", p2="קְרִי"))
        self.assertIn('order="qeri-first"', frag)

    def test_special_ketiv_qeri_is_written_first(self):
        frag = convert(t("מ:כו״ק מיוחד", p1="כתיב", p2="קְרִי", סוג="סוג"))
        self.assertIn('<miqra:kq order="ketiv-first">', frag)
        self.assertNotIn("סוג", frag)

    def test_trivial_qere_shows_the_pointed_ketiv(self):
        frag = convert(t("מ:קו״כ-אם-2", p1="הַהִ֖וא", p2="ההוא", p3="הַהִ֖יא", מקורות="ל-קרי", סוג="כתיב הוא קרי היא"))
        # The unpointed ketiv and the pointed qere are alternative forms, not rendered.
        self.assertEqual(frag, convert("הַהִ֖וא"))

    def test_ketiv_only_and_qeri_only(self):
        k = convert(t("כתיב ולא קרי", p1="(אם)־", p2="אם", p3="־"))
        q = convert(t("קרי ולא כתיב", p1="[בָּאִ֖ים]", p2="בָּאִ֖ים"))
        self.assertEqual("<miqra:ketiv-only>אם</miqra:ketiv-only>־", k)
        self.assertEqual("<miqra:qeri-only>בָּאִ֖ים</miqra:qeri-only>", q)

    def test_qeri_only_in_a_note_target_stays_text(self):
        frag = convert(t("נוסח", p1=t("קרי ולא כתיב", p1="[אֵלַ֖י]", p2="אֵלַ֖י"), p2="הערה"))
        self.assertIn("<miqra:qeri-only>אֵלַ֖י</miqra:qeri-only>", frag)
        self.assertNotIn("mw:link", frag)

    def test_parashah_variants(self):
        cases = [
            (t("פפ"), 'type="open"'),
            (t("פפפ"), 'type="open-line"'),
            (t("סס"), 'type="close"'),
            (t("ססס"), 'type="close-inline"'),
            (t("מ:ששש"), 'type="shirah"'),
        ]
        for node, expected in cases:
            with self.subTest(node=node):
                self.assertIn(expected, convert(node))

    def test_parashah_mid_verse_attribute(self):
        frag = convert(t("פפ", p1="פסקא באמצע פסוק"))
        self.assertIn('midVerse="true"', frag)

    def test_verse_label_is_not_rendered(self):
        aliyah = t("מ:עלייה", א="בראשית", ב0="בראשית", ב1="ראשון")
        frag = convert(t("מ:פסוק", p1="בראשית", p2="א", p3="א", סדר="א", עלייה=aliyah), column="D")
        self.assertEqual(frag, "")

    def test_note_link_external(self):
        frag = convert(t("נוסח", p1="א", p2=[t("מ:קישור בהערה", p1="http://www.example.com/doc.pdf", p2="label")]))
        self.assertIn('target="http://www.example.com/doc.pdf"', frag)
        self.assertIn("label", frag)

    def test_internal_note_link_to_wikisource_uri(self):
        frag = convert(t("נוסח", p1="א", p2=[t("מ:קישור פנימי בהערה", p1="ויקיטקסט:מבוא", p2="פרק שני")]))
        self.assertIn('target="https://he.wikisource.org/wiki/', frag)
        self.assertNotIn("ויקיטקסט:מבוא", frag)
        self.assertIn("פרק שני", frag)

    def test_a_double_underscore_is_a_space_in_column_c_only(self):
        # Column C's usual separator, bare or documented; plus has none in columns D and E.
        self.assertEqual(convert("__", column="C"), " ")
        documented = convert(t("נוסח", p1="__", p2="הערה"), column="C")
        self.assertIn("<miqra:display> </miqra:display>", documented)
        self.assertEqual(convert("א__ב", column="E"), "א__ב")

    def test_stress_helpers_show_the_first_parameter_only(self):
        for name, plain, helped in (("מ:דחי", "חַ֭טָּאִים", "חַ֭טָּאִ֭ים"), ("מ:צינור", "בָטַחְתִּי֮", "בָטַ֮חְתִּי֮")):
            with self.subTest(name=name):
                frag = convert(t(name, p1=plain, p2=helped))
                self.assertEqual(frag, plain)

    def test_qamats_shows_the_grammatical_form(self):
        frag = convert(t("מ:קמץ", ד="אׇהֳלֹֽה", ס="אָהֳלֹֽה"))
        self.assertEqual(frag, "אׇהֳלֹֽה")

    def test_silluq_before_meteg_shows_the_word(self):
        self.assertEqual(convert(t("מ:סילוק לפני געיה", p1="מֶֽנְהֽוּ", p2="מֽנהו")), "מֶֽנְהֽוּ")

    def test_poetic_levels(self):
        for level, name in enumerate(("ר0", "ר1", "ר2", "ר3", "ר4")):
            self.assertIn(f'<miqra:poetic level="{level}"/>', convert(t(name)))

    def test_letter_formatting(self):
        frag = convert(t("מ:אות-ק", p1="ק"), t("מ:אות תלויה", p1="ת"), t("מ:נו״ן הפוכה", p1="׆ "))
        self.assertIn('rend="small"', frag)
        self.assertIn('rend="raised"', frag)
        # Plus gives the inverted nun with the space after it.
        self.assertIn("<miqra:inverted-nun>׆ </miqra:inverted-nun>", frag)

    def test_inverted_nun_with_the_earlier_space_code(self):
        # MAM-basics wrote that space as a double underscore until 2026-10-15.
        self.assertEqual(
            convert(t("מ:נו״ן הפוכה", p1="׆__")), "<miqra:inverted-nun>׆ </miqra:inverted-nun>"
        )

    def test_punctuation_and_maqaf(self):
        frag = convert(t("מ:לגרמיה-2"), t("מ:פסק"), t("מ:מקף אפור"))
        self.assertIn('type="legarmeh"', frag)
        self.assertIn('type="paseq"', frag)
        self.assertIn('rend="grey"', frag)

    def test_documentation_note_without_note_text(self):
        self.assertEqual(convert(t("נוסח", p1="טקסט", p2="")), "טקסט")

    def test_scroll_difference_note_marker_after_and_before(self):
        after = convert(t("מ:הערה-2", p1="מִנְּשֹֽׂא", p2="הערה", p3="אאא*"))
        self.assertTrue(after.startswith("מִנְּשֹֽׂא<miqra:anchor"))
        before = convert(t("מ:הערה-2", p1="קַן", p2="הערה", p3="*אאא"))
        self.assertTrue(before.endswith("</miqra:note>קַן"))

    def test_scroll_difference_note_in_a_documentation_note_follows_it(self):
        """MAM's wikitext writes {{נוסח|target|…}}{{מ:הערה|…}}: the documentation note is
        numbered first, and the scroll-difference note's marker follows the documented span."""
        scroll = t("מ:הערה-2", p1="מִנְּשֹֽׂא", p2="בספרי ספרד", p3="אאא*")
        frag = convert(t("נוסח", p1=scroll, p2="תיעוד"))
        self.assertEqual(
            frag,
            '<miqra:variant noteId="miqra-note-1"><miqra:display>מִנְּשֹֽׂא</miqra:display></miqra:variant>'
            '<miqra:note xml:id="miqra-note-1">תיעוד</miqra:note>'
            '<miqra:anchor xml:id="miqra-note-2-ref"/><miqra:note xml:id="miqra-note-2">בספרי ספרד</miqra:note>',
        )

    def test_notes_are_numbered_across_columns(self):
        converter = PlusToIntermediate()
        first = converter.column([t("נוסח", p1="א", p2="1")], "E")
        second = converter.column([t("נוסח", p1="ב", p2="2")], "C")
        self.assertIn("miqra-note-1", first)
        self.assertIn("miqra-note-2", second)

    def test_dual_cantillation(self):
        frag = convert(t("מ:כפול", כפול="ד", א="א", ב="ב"))
        self.assertIn("<miqra:dual-accent>", frag)
        self.assertIn("<miqra:merged>ד</miqra:merged>", frag)
        self.assertIn('<miqra:strand role="א">א</miqra:strand>', frag)
        self.assertIn('<miqra:strand role="ב">ב</miqra:strand>', frag)

    def test_dual_cantillation_numbers_its_notes_merged_text_first(self):
        # Whatever the order of the JSON's keys: כפול, then א, then ב.
        frag = convert(t("מ:כפול", ב=[t("נוסח", p1="ב", p2="3")], א=[t("נוסח", p1="א", p2="2")],
                         כפול=[t("נוסח", p1="ד", p2="1")]))
        for number in ("1", "2", "3"):
            self.assertIn(f'<miqra:note xml:id="miqra-note-{number}">{number}</miqra:note>', frag)

    def test_dual_accent_keeps_apparatus_of_merged_text(self):
        """The manuscript apparatus hangs off the merged doubly-accented reading, so
        ``כפול`` must be an element: in an attribute the note markup would be escaped away."""
        frag = convert(t("מ:כפול", כפול=[t("נוסח", p1="דד", p2="הערת כתבי־היד")], א="א", ב="ב"))
        self.assertIn("<miqra:note", frag)
        self.assertIn("הערת כתבי־היד", frag)
        self.assertNotIn("&lt;miqra:note", frag)

    def test_emphasis_and_doc_part_separator(self):
        frag = convert(t("נוסח", p1="א", p2=[t("מודגש", p1="חשוב"), t("ש")]))
        self.assertIn('<mw:hi rend="bold">חשוב</mw:hi>', frag)
        self.assertIn("<miqra:fn-mark/>", frag)


class TestClosedDispatch(unittest.TestCase):
    def test_unknown_template_raises(self):
        with self.assertRaises(PlusFormatError):
            convert(t("גלגל"))

    def test_parameter_outside_the_schema_raises(self):
        with self.assertRaises(PlusFormatError):
            convert(t("כו״ק", p1="כתיב", p2="קְרִי", p3="עוד"))

    def test_note_in_an_unrendered_alternative_raises(self):
        with self.assertRaises(PlusFormatError):
            convert(t("מ:דחי", p1="א", p2=t("נוסח", p1="א", p2="הערה")))

    def test_unparsed_wikitext_in_text_raises(self):
        with self.assertRaises(PlusFormatError):
            convert("{{פפ}}")

    def test_aliyah_outside_a_verse_label_raises(self):
        with self.assertRaises(PlusFormatError):
            convert(t("מ:עלייה", א="בראשית", ב0="בראשית"))

    def test_note_in_a_trivial_qere_alternative_raises(self):
        note = t("נוסח", p1="א", p2="הערה")
        for key in ("p2", "p3"):
            params = {"p1": "א", "p2": "א", "p3": "א", key: note}
            with self.subTest(key=key), self.assertRaises(PlusFormatError):
                convert(t("מ:קו״כ-אם-2", **params))

    def test_verse_label_outside_column_d_raises(self):
        label = t("מ:פסוק", p1="בראשית", p2="א", p3="א")
        self.assertEqual(convert(label, column="D"), "")
        for column in ("C", "E"):
            with self.subTest(column=column), self.assertRaises(PlusFormatError):
                convert(label, column=column)

    def test_placed_template_in_an_unrendered_alternative_raises(self):
        for placed in (t("מ:פסוק", p1="בראשית", p2="א", p3="א"), t("מ:עלייה", א="בראשית", ב0="בראשית"),
                       t("מ:סיום בטוב", p1="סיום")):
            with self.subTest(placed=placed["tmpl_name"]), self.assertRaises(PlusFormatError):
                convert(t("מ:דחי", p1="א", p2=["א", placed]))


class TestGoodEnding(unittest.TestCase):
    """good_ending_plus is checked, not rendered: null, or a נוסח documenting a מ:סיום בטוב."""

    def _good_ending(self, **changes) -> dict:
        ending = {
            "last_chapnver": ["66", "24"],
            "wikitext_element": t("נוסח", p1=t("מ:סיום בטוב", p1="סיום טוב"), p2="הערה"),
        }
        ending.update(changes)
        return ending

    def test_null_and_the_plus_shape_pass(self):
        converter = PlusToIntermediate()
        converter.check_good_ending(None, "isaiah")
        converter.check_good_ending(self._good_ending(), "isaiah")

    def test_other_shapes_raise(self):
        cases = {
            "an extra key": self._good_ending(extra=1),
            "no verse": {"wikitext_element": self._good_ending()["wikitext_element"]},
            "a verse that is not two numbers": self._good_ending(last_chapnver=["66"]),
            "a bare good ending": self._good_ending(wikitext_element=t("מ:סיום בטוב", p1="סיום")),
            "another documented template": self._good_ending(
                wikitext_element=t("נוסח", p1=t("מ:קמץ", ד="א", ס="א"), p2="הערה")),
            "a note in the note": self._good_ending(
                wikitext_element=t("נוסח", p1=t("מ:סיום בטוב", p1="סיום"), p2=[t("נוסח", p1="א", p2="ב")])),
        }
        for case, ending in cases.items():
            with self.subTest(case=case), self.assertRaises(PlusFormatError):
                PlusToIntermediate().check_good_ending(ending, "isaiah")


class TestPlusFileKeys(unittest.TestCase):
    HEADER = {"book24_name": "ספר ישעיהו", "sub_book_names": None, "chapter_counts": {}}
    BOOK39 = {"book24_name": "ספר ישעיהו", "sub_book_name": None, "good_ending_plus": None, "chapters": {}}

    def test_the_plus_keys_pass(self):
        check_plus_file({"header": self.HEADER, "book39s": [self.BOOK39]}, "C1-Isaiah.json")
        # MAM-basics' headers have had a consumer_notice since 2026-09-16.
        header = {**self.HEADER, "consumer_notice": {}}
        check_plus_file({"header": header, "book39s": [self.BOOK39]}, "C1-Isaiah.json")

    def test_other_keys_raise(self):
        cases = {
            "an extra file key": {"header": self.HEADER, "book39s": [self.BOOK39], "x": 1},
            "a header without its chapter counts": {
                "header": {k: v for k, v in self.HEADER.items() if k != "chapter_counts"},
                "book39s": [self.BOOK39]},
            "an extra header key": {"header": {**self.HEADER, "x": 1}, "book39s": [self.BOOK39]},
            "a book39 without its good ending": {
                "header": self.HEADER,
                "book39s": [{k: v for k, v in self.BOOK39.items() if k != "good_ending_plus"}]},
            "an extra book39 key": {"header": self.HEADER, "book39s": [{**self.BOOK39, "x": 1}]},
        }
        for case, data in cases.items():
            with self.subTest(case=case), self.assertRaises(PlusFormatError):
                check_plus_file(data, "C1-Isaiah.json")


if __name__ == "__main__":
    unittest.main()
