import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.opensiddur_org.parse_post import parse_post
from opensiddur.importer.opensiddur_org.urns import (
    PostUrns,
    load_post_urns,
    mint,
    registry_lines,
    save_post_urns,
)
from opensiddur.tests.importer.opensiddur_org.support import make_post

PREFIX = "urn:x-opensiddur:text:"
#: A spelling list of the tests' own, so that these do not change with the real one.
VARIANTS = {"tsur": "tzur", "chanukkah": "chanukah"}
POET = {"name": "Yehudah Poet", "profile_link": "https://opensiddur.org/profile/yehudah-poet"}


def post(title: str, *, slug: str = "a-slug-the-urn-does-not-use", tags=None, post_id: int = 7):
    return parse_post(make_post(post_id, title=title, slug=slug, tags=tags, coauthors=[POET]))


class TestMinting(unittest.TestCase):
    def test_named_from_the_title_and_author_not_the_slug(self) -> None:
        record = mint(post("A Prayer for Rain, by Yehudah Poet"), set(), VARIANTS)
        self.assertEqual(record.urn, f"{PREFIX}prayer:a_prayer_for_rain_poet")

    def test_respelled_by_the_spelling_list(self) -> None:
        record = mint(post("מעוז צור | Maoz Tsur for Ḥanukkah"), set(), VARIANTS)
        self.assertEqual(record.urn, f"{PREFIX}prayer:maoz_tzur_for_chanukah_poet")

    def test_a_hebrew_only_title_is_named_from_the_slug(self) -> None:
        record = mint(post("שירה", slug="shirah-by-someone"), set(), VARIANTS)
        self.assertEqual(record.urn, f"{PREFIX}prayer:shirah_poet")

    def test_the_author_is_respelled_too(self) -> None:
        tsur = {"name": "Yaaqov ibn Tsur", "profile_link": "https://opensiddur.org/profile/yaaqov-ibn-tsur"}
        p = parse_post(make_post(7, title="A Piyyut", coauthors=[tsur]))
        self.assertEqual(mint(p, set(), VARIANTS).urn, f"{PREFIX}prayer:a_piyyut_tzur")

    def test_an_author_credited_only_by_the_title(self) -> None:
        unknown = {"name": "Unknown", "profile_link": "https://opensiddur.org/profile/unknown"}
        p = parse_post(make_post(7, title="A Stanza, by Rabbi Yirmiyah of Würzburg", coauthors=[unknown]))
        self.assertEqual(mint(p, set(), VARIANTS).urn, f"{PREFIX}prayer:a_stanza_yirmiyah")

    def test_no_author_at_all(self) -> None:
        p = parse_post(make_post(7, title="A Song", coauthors=[]))
        self.assertEqual(mint(p, set(), VARIANTS).urn, f"{PREFIX}prayer:a_song")

    def test_poem_from_tags(self) -> None:
        self.assertIn(":poem:", mint(post("A Song", tags=["פיוטים piyyuṭim"]), set(), VARIANTS).urn)

    def test_a_taken_name_gets_the_post_id(self) -> None:
        taken = {f"{PREFIX}prayer:kaddish_poet"}
        self.assertEqual(mint(post("Kaddish"), taken, VARIANTS).urn, f"{PREFIX}prayer:kaddish_poet_7")


class TestRecords(unittest.TestCase):
    def test_new_rows(self) -> None:
        record = PostUrns(1, "new", "urn:x-opensiddur:text:prayer:p")
        self.assertEqual(record.row_urn(3), "urn:x-opensiddur:text:prayer:p/3")

    def test_new_post_with_existing_parts(self) -> None:
        record = PostUrns(1, "new", "urn:x-opensiddur:text:prayer:p", {2: "urn:x-opensiddur:text:prayer:shehecheyanu"})
        self.assertEqual(record.row_urn(2), "urn:x-opensiddur:text:prayer:shehecheyanu")
        self.assertEqual(record.row_urn(1), "urn:x-opensiddur:text:prayer:p/1")
        lines = registry_lines(record, [1, 2, 3], label_en="P")
        self.assertEqual([line["urn"] for line in lines], [
            "urn:x-opensiddur:text:prayer:p", "urn:x-opensiddur:text:prayer:p/1", "urn:x-opensiddur:text:prayer:p/3"])

    def test_existing_rows(self) -> None:
        record = PostUrns(1, "existing", "urn:x-opensiddur:text:poem:maoz_tzur",
                          {1: "urn:x-opensiddur:text:poem:maoz_tzur/1", 2: None})
        self.assertEqual(record.row_urn(1), "urn:x-opensiddur:text:poem:maoz_tzur/1")
        self.assertIsNone(record.row_urn(2))
        self.assertEqual(registry_lines(record, [1, 2], label_en="x"), [])

    def test_registry_labels(self) -> None:
        lines = registry_lines(PostUrns(1, "new", "urn:x-opensiddur:text:prayer:p"), [1], label_en="P", label_he="פ")
        self.assertEqual((lines[0]["label_en"], lines[0]["label_he"]), ("P", "פ"))
        self.assertEqual(lines[1]["parent"], "urn:x-opensiddur:text:prayer:p")

    def test_tables(self) -> None:
        psalm = PostUrns(1, "existing", "urn:x-opensiddur:text:bible:psalms/67")
        record = PostUrns(1, "new", "urn:x-opensiddur:text:prayer:p", tables={1: psalm})
        self.assertIs(record.table(1, 1), record)
        self.assertIs(record.table(1, 2), psalm)
        self.assertEqual(record.table(2, 2).urn, "urn:x-opensiddur:text:prayer:p/2")
        lines = registry_lines(record.table(2, 2), [1], label_en="P / 2", parent=record.urn)
        self.assertEqual(lines[0]["parent"], record.urn)

    def test_round_trip(self) -> None:
        records = {
            3: PostUrns(3, "new", "urn:x-opensiddur:text:prayer:d",
                        tables={2: PostUrns(3, "existing", "urn:x-opensiddur:text:bible:psalms/67", {1: None},
                                            spans={1: "urn:x-opensiddur:text:bible:psalms/67/2-8"})}),
            2: PostUrns(2, "existing", "urn:x-opensiddur:text:poem:a", {1: "urn:x-opensiddur:text:poem:a/1", 2: None},
                        spans={2: ""}),
            1: PostUrns(1, "new", "urn:x-opensiddur:text:prayer:b", {3: "urn:x-opensiddur:text:prayer:c"}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "post_urns.jsonl"
            save_post_urns(records, path)
            self.assertEqual(load_post_urns(path), records)
            # Sorted by post ID, so the file is stable.
            self.assertTrue(path.read_text().startswith('{"post_id": 1,'))


if __name__ == "__main__":
    unittest.main()
