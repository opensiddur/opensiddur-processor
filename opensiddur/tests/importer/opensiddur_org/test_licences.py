import unittest

from opensiddur.importer.opensiddur_org.licences import (
    DECISIONS_PATH,
    LICENCES,
    load_decisions,
    normalize_licence_url,
)
from opensiddur.importer.opensiddur_org.parse_post import parse_post
from opensiddur.tests.importer.opensiddur_org.support import FIXTURES, make_post


def licence(url: str) -> str:
    return f"<a href='{url}'>a licence</a>" if url else ""


class TestLicenceDecisions(unittest.TestCase):
    def setUp(self) -> None:
        self.decisions = load_decisions(FIXTURES / "licence_decisions.yaml")

    def decide(self, post_data, lang: str):
        post = parse_post(post_data)
        column = next(c for c in post.columns if c.lang == lang)
        return self.decisions.for_column(post, column)

    def test_allowed_licence(self) -> None:
        decision = self.decide(make_post(), "en")
        self.assertEqual((decision.status, decision.licence.id), ("allow", "cc-by-sa-4.0"))

    def test_allowed_with_a_basis(self) -> None:
        decision = self.decide(make_post(licence=licence("https://www.law.cornell.edu/uscode/text/17/105")), "he")
        self.assertEqual(decision.licence.id, "pd-mark-1.0")
        self.assertIn("§105", decision.basis)

    def test_rejected_licence(self) -> None:
        self.assertEqual(self.decide(make_post(licence=licence("https://example.org/not-free")), "he").status, "reject")

    def test_unknown_licence_is_undecided(self) -> None:
        decision = self.decide(make_post(licence=licence("https://example.org/other")), "he")
        self.assertEqual(decision.status, "undecided")

    def test_no_licence_is_undecided(self) -> None:
        decision = self.decide(make_post(licence=""), "he")
        self.assertEqual((decision.status, decision.basis), ("undecided", "no licence"))

    def test_public_domain_source_under_fair_use(self) -> None:
        old = make_post(licence=licence("https://www.law.cornell.edu/uscode/text/17/107"), date_src=("1100-00-00", "1100-00-00"))
        self.assertEqual(self.decide(old, "he").licence.id, "pd-mark-1.0")
        # The translation beside it is not covered.
        self.assertEqual(self.decide(old, "en").status, "undecided")

    def test_modern_source_under_fair_use(self) -> None:
        new = make_post(licence=licence("https://www.law.cornell.edu/uscode/text/17/107"), date_src=("2023-12-10", "2023-12-10"))
        self.assertEqual(self.decide(new, "he").status, "undecided")

    def test_post_decision_for_some_columns(self) -> None:
        post = make_post(501, licence="")
        self.assertEqual(self.decide(post, "he").licence.id, "pd-mark-1.0")
        self.assertEqual(self.decide(post, "en").status, "undecided")

    def test_post_rejection_overrides_the_licence(self) -> None:
        self.assertEqual(self.decide(make_post(502), "he").status, "reject")

    def test_a_rejection_lapses_when_the_post_is_updated(self) -> None:
        fair_use = licence("https://www.law.cornell.edu/uscode/text/17/107")
        self.assertEqual(self.decide(make_post(503, licence=fair_use, last_updated="2026-09-01"), "en").status, "reject")
        # Updated since: decided again, and the fair-use claim is undecided.
        self.assertEqual(self.decide(make_post(503, licence=fair_use, last_updated="2026-10-26"), "en").status, "undecided")

    def test_a_rejection_lapses_when_the_post_is_relicensed(self) -> None:
        decision = self.decide(make_post(503, last_updated="2026-09-01"), "en")
        self.assertEqual((decision.status, decision.licence.id), ("allow", "cc-by-sa-4.0"))

    def test_a_held_column(self) -> None:
        decision = self.decide(make_post(504), "en")
        self.assertEqual((decision.status, decision.basis), ("undecided", "held: Held until the translator licenses it."))
        # The other columns follow the post's licence.
        self.assertEqual(self.decide(make_post(504), "he").status, "allow")


class TestNormalization(unittest.TestCase):
    def test_creative_commons_forms(self) -> None:
        expected = "https://creativecommons.org/licenses/by-sa/4.0/"
        for url in ("http://creativecommons.org/licenses/by-sa/4.0", "https://www.creativecommons.org/licenses/by-sa/4.0/",
                    "https://creativecommons.org/licenses/by-sa/4.0/'"):
            self.assertEqual(normalize_licence_url(url), expected)

    def test_shipped_decisions_name_known_licences(self) -> None:
        decisions = load_decisions(DECISIONS_PATH)
        for entry in list(decisions.licences.values()) + list(decisions.posts.values()):
            if "allow" in entry:
                self.assertIn(entry["allow"], LICENCES)


if __name__ == "__main__":
    unittest.main()
