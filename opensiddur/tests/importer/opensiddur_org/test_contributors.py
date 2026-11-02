import json
import unittest

from opensiddur.importer.opensiddur_org.contributors import (
    Credit,
    Contributors,
    candidate_line,
    post_credits,
    registered_contributors,
    role_key,
    unregistered,
)
from opensiddur.importer.opensiddur_org.parse_post import parse_post
from opensiddur.tests.importer.opensiddur_org.support import (
    FIXTURES,
    NEW_PERSON,
    POET,
    PRINT_TRANSLATOR,
    TRANSCRIBER,
    TRANSLATOR,
    UNKNOWN_TRANSLATOR,
    make_post,
)


class TestContributors(unittest.TestCase):
    def setUp(self) -> None:
        self.contributors = Contributors.load(FIXTURES / "contributors_by_id.json")

    def credits(self, coauthors):
        return post_credits(parse_post(make_post(coauthors=coauthors)), self.contributors)

    def test_role_users_are_one_person(self) -> None:
        self.assertEqual(self.contributors.person_slug("rivka-translator-translation"), "rivka-translator")
        self.assertEqual(self.contributors.person_slug("rivka-translator-transcription"), "rivka-translator")

    def test_role_keys(self) -> None:
        self.assertEqual(role_key("translation")[0], "trl")
        self.assertEqual(role_key("transcription & naqdanut")[0], "trc")
        self.assertIsNone(role_key("Charleston, South Carolina"))

    def test_digital_text_credits(self) -> None:
        credits = self.credits([TRANSLATOR, TRANSCRIBER, POET])
        self.assertEqual([(c.key, c.slug) for c in credits.responsibilities],
                         [("trl", "rivka-translator"), ("trc", "rivka-translator")])
        self.assertEqual(credits.responsibilities[0].urn,
                         "urn:x-opensiddur:contributor:opensiddur.org/rivka-translator")
        self.assertEqual(credits.authors, ("Yehudah Poet",))

    def test_credits_follow_the_column(self) -> None:
        credits = self.credits([TRANSLATOR, TRANSCRIBER])
        self.assertEqual([c.key for c in credits.for_column_role("translation")], ["trl"])
        self.assertEqual([c.key for c in credits.for_column_role("source")], ["trc"])

    def test_printed_source_translator_has_no_urn(self) -> None:
        credits = self.credits([PRINT_TRANSLATOR, POET])
        self.assertEqual(credits.responsibilities, ())
        self.assertEqual([c.name for c in credits.source_responsibilities], ["Old Print Translator"])

    def test_placeholder_is_credited_with_nothing(self) -> None:
        credits = self.credits([UNKNOWN_TRANSLATOR])
        self.assertEqual((credits.responsibilities, credits.source_responsibilities), ((), ()))

    def test_unregistered_people_are_reported_once(self) -> None:
        registered = registered_contributors(FIXTURES)
        self.assertEqual(registered, {"urn:x-opensiddur:contributor:opensiddur.org/rivka-translator"})
        credits = self.credits([TRANSLATOR, TRANSCRIBER, NEW_PERSON])
        missing = unregistered(credits, registered)
        self.assertEqual([c.slug for c in missing], ["new-person-transcription"])
        self.assertEqual(json.loads(candidate_line(missing[0]))["label_en"], "New Person")



class TestCandidateLines(unittest.TestCase):
    def test_directional_marks_are_dropped_from_the_label(self) -> None:
        line = candidate_line(Credit(key="trc", resp="Transcribed by", name="أحمد\u200e", slug="achmed"))
        self.assertEqual(json.loads(line)["label_en"], "أحمد")


class TestPlaceholderAuthor(unittest.TestCase):
    def test_unknown_is_not_an_author(self) -> None:
        contributors = Contributors.load(FIXTURES / "contributors_by_id.json")
        unknown = {"name": "Unknown", "profile_link": "https://opensiddur.org/profile/unknown"}
        credits = post_credits(parse_post(make_post(coauthors=[unknown, POET])), contributors)
        self.assertEqual(credits.authors, ("Yehudah Poet",))


if __name__ == "__main__":
    unittest.main()
