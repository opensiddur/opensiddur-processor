import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from opensiddur.importer.birnbaum_siddur import wikisource
from opensiddur.importer.birnbaum_siddur.wikisource import download_book, main
from opensiddur.importer.util import wikisource_book
from opensiddur.importer.util.pages import (
    birnbaum_siddur_credits_directory,
    birnbaum_siddur_data_directory,
    birnbaum_siddur_text_directory,
)
from opensiddur.importer.util.wikisource import RevisionInfo, WikisourceError

# Page numbers chosen so the zero-padding width is the real one (three digits).
FIRST, LAST = 1, 815
TITLES = {
    FIRST: f"{wikisource.WIKI_NAMESPACE}:{wikisource.BOOK_NAME}/{FIRST}",
    LAST: f"{wikisource.WIKI_NAMESPACE}:{wikisource.BOOK_NAME}/{LAST}",
}

ROOT = wikisource.SOURCE_ROOT
FOUNDATION = f"{ROOT}/אשכנז/דפי יסוד/קדיש"
REDIRECT_PAGE = f"{ROOT}/אשכנז/הלל"
EXTERNAL = "עשרת הדברות/ניקוד"

# The scan page names a section that the foundation page defines, which is the
# relationship structure.json exists to record.
SECTION = "כותרת חצי קדיש"
SCAN_WIKITEXT = f"{{{{#קטע:{FOUNDATION}|{SECTION}}}}}"
SOURCE_WIKITEXT = {
    ROOT: "index page",
    FOUNDATION: f"<קטע התחלה={SECTION}/>text<קטע סוף={SECTION}/>",
    REDIRECT_PAGE: f"#הפניה [[{FOUNDATION}]]",
    EXTERNAL: "<קטע התחלה=דברות/>text<קטע סוף=דברות/>",
}


class BirnbaumDownloadTestCase(unittest.TestCase):
    """Fixture wiring the downloader to a temporary sourcetexts tree and a fake wiki."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self.text_dir = birnbaum_siddur_text_directory(self.root)
        self.credits_dir = birnbaum_siddur_credits_directory(self.root)
        self.manifest_file = birnbaum_siddur_data_directory(self.root) / "manifest.json"

        # Latest revision id per title, as the wiki would report it.
        self.revids = {TITLES[FIRST]: 111, TITLES[LAST]: 222}
        self.contributors = {TITLES[FIRST]: ["Dovi"], TITLES[LAST]: ["Dovi", "Nahum"]}

        self.content_requests = []
        self.contributor_requests = []
        self.closure_calls = []

        # The source layer: revision ids keyed by title, same shape as the scan layer.
        self.source_revids = {t: 500 for t in SOURCE_WIKITEXT}

        # The scan-page half of the download lives in util.wikisource_book, so its calls
        # are looked up there; the source-page half is still this module's own.
        scan_patcher = patch.multiple(
            wikisource_book,
            list_book_pages=MagicMock(return_value=dict(TITLES)),
            fetch_revisions=MagicMock(side_effect=self.fake_fetch_revisions),
            fetch_contributors=MagicMock(side_effect=self.fake_fetch_contributors),
        )
        source_patcher = patch.multiple(
            wikisource,
            fetch_contributors=MagicMock(side_effect=self.fake_fetch_contributors),
            list_pages_with_prefix=MagicMock(
                return_value=[FOUNDATION, REDIRECT_PAGE]
            ),
            download_closure=MagicMock(side_effect=self.fake_download_closure),
        )
        for patcher in (scan_patcher, source_patcher):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_fetch_revisions(self, wiki, titles, *, include_content, **kwargs):
        titles = list(titles)
        if include_content:
            self.content_requests.append(titles)
        return {
            title: RevisionInfo(
                revid=self.revids[title],
                timestamp="2022-02-07T05:35:00Z",
                content=SCAN_WIKITEXT if include_content else None,
            )
            for title in titles
        }

    def fake_fetch_contributors(self, wiki, titles, **kwargs):
        titles = list(titles)
        self.contributor_requests.append(titles)
        return {title: self.contributors.get(title, ["Dovi"]) for title in titles}

    def fake_download_closure(self, wiki, roots, *, include, **kwargs):
        """Stand in for the real walker, returning a fixed small source tree.

        Records `include` so tests can assert what the real walker would follow
        without re-implementing traversal here.
        """
        self.closure_calls.append((list(roots), include))
        return {
            title: RevisionInfo(
                revid=self.source_revids[title],
                timestamp="2022-02-07T05:35:00Z",
                content=text,
            )
            for title, text in SOURCE_WIKITEXT.items()
        }

    def run_download(self, **kwargs):
        return download_book(
            "example@opensiddur.org",
            self.root,
            wiki=MagicMock(server=wikisource.SERVER),
            **kwargs,
        )

    def seed_page(self, page_num, key, revid, text="existing", credits="Dovi"):
        """Write a page to disk and record it in the manifest as already current."""
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.credits_dir.mkdir(parents=True, exist_ok=True)
        (self.text_dir / f"{key}.txt").write_text(text, encoding="utf-8")
        (self.credits_dir / f"{key}.txt").write_text(credits, encoding="utf-8")
        manifest = {
            "source": wikisource.SERVER,
            "book_name": wikisource.BOOK_NAME,
            "namespace": wikisource.WIKI_NAMESPACE,
            "downloaded_at": "2022-02-07T05:35:00Z",
            "pages": {key: {"revid": revid, "timestamp": "2022-02-07T05:35:00Z"}},
        }
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    def read_manifest(self):
        return json.loads(self.manifest_file.read_text(encoding="utf-8"))

    def read_structure(self):
        path = wikisource.birnbaum_siddur_data_directory(self.root) / "structure.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def seed_everything_current(self):
        """Put both layers on disk and in the manifest, exactly as a finished run would."""
        self.seed_page(FIRST, "001", revid=self.revids[TITLES[FIRST]])
        (self.text_dir / "815.txt").write_text(SCAN_WIKITEXT, encoding="utf-8")
        (self.credits_dir / "815.txt").write_text("Dovi", encoding="utf-8")

        source_pages = {}
        for title, text in SOURCE_WIKITEXT.items():
            text_path, credits_path = wikisource.source_page_paths(title, self.root)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            credits_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding="utf-8")
            credits_path.write_text("Dovi", encoding="utf-8")
            source_pages[title] = {"revid": self.source_revids[title]}

        manifest = self.read_manifest()
        manifest["pages"]["815"] = {"revid": self.revids[TITLES[LAST]]}
        manifest["source_pages"] = source_pages
        self.manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        wikisource.save_structure(wikisource.build_structure(self.root), self.root)


class TestFirstRun(BirnbaumDownloadTestCase):
    def test_downloads_every_page_when_there_is_no_manifest(self):
        self.run_download()

        self.assertEqual(sorted(self.content_requests[0]), sorted(TITLES.values()))

    def test_writes_text_and_credits_with_three_digit_names(self):
        self.run_download()

        self.assertEqual(
            sorted(p.name for p in self.text_dir.iterdir()), ["001.txt", "815.txt"]
        )
        self.assertEqual(
            (self.text_dir / "815.txt").read_text(encoding="utf-8"), SCAN_WIKITEXT
        )

    def test_writes_contributors_one_per_line(self):
        self.run_download()

        self.assertEqual(
            (self.credits_dir / "815.txt").read_text(encoding="utf-8"), "Dovi\nNahum"
        )

    def test_records_every_page_in_the_manifest(self):
        self.run_download()

        manifest = self.read_manifest()
        self.assertEqual(manifest["pages"]["001"]["revid"], 111)
        self.assertEqual(manifest["pages"]["815"]["revid"], 222)
        self.assertEqual(manifest["book_name"], wikisource.BOOK_NAME)

    def test_refuses_a_book_with_no_transcribed_pages(self):
        wikisource_book.list_book_pages.return_value = {}

        with self.assertRaises(WikisourceError):
            self.run_download()


class TestIncrementalUpdate(BirnbaumDownloadTestCase):
    def test_skips_pages_whose_revision_is_unchanged(self):
        self.seed_page(FIRST, "001", revid=111)
        self.revids[TITLES[LAST]] = 999  # page 815 has moved on

        self.run_download()

        # The source phase makes its own requests; assert on the scan phase's.
        self.assertEqual(self.content_requests, [[TITLES[LAST]]])
        self.assertEqual(self.contributor_requests[0], [TITLES[LAST]])

    def test_leaves_an_unchanged_page_untouched_on_disk(self):
        self.seed_page(FIRST, "001", revid=111, text="existing", credits="Dovi")
        self.revids[TITLES[LAST]] = 999

        self.run_download()

        self.assertEqual((self.text_dir / "001.txt").read_text(encoding="utf-8"), "existing")

    def test_keeps_the_old_entry_and_records_the_new_one(self):
        self.seed_page(FIRST, "001", revid=111)
        self.revids[TITLES[LAST]] = 999

        self.run_download()

        pages = self.read_manifest()["pages"]
        self.assertEqual(pages["001"]["revid"], 111)
        self.assertEqual(pages["815"]["revid"], 999)

    def test_downloads_nothing_when_the_whole_book_is_current(self):
        self.seed_everything_current()

        self.run_download()

        self.assertEqual(self.content_requests, [])
        self.assertEqual(self.contributor_requests, [])

    def test_a_no_op_rerun_leaves_every_file_untouched(self):
        # The property that makes re-running cheap enough to do routinely: an
        # unchanged run must not even rewrite the manifest, or it shows up as a diff.
        self.seed_everything_current()
        before = {
            p: p.stat().st_mtime_ns
            for p in wikisource.birnbaum_siddur_data_directory(self.root).rglob("*")
            if p.is_file()
        }

        self.run_download()

        after = {
            p: p.stat().st_mtime_ns
            for p in wikisource.birnbaum_siddur_data_directory(self.root).rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)

    def test_refetches_when_a_file_has_gone_missing(self):
        # A manifest entry is not proof the files survived.
        self.seed_page(FIRST, "001", revid=111)
        (self.credits_dir / "001.txt").unlink()
        self.revids[TITLES[LAST]] = 222

        self.run_download()

        self.assertIn(TITLES[FIRST], self.content_requests[0])

    def test_starts_over_when_the_manifest_is_corrupt(self):
        self.seed_page(FIRST, "001", revid=111)
        self.manifest_file.write_text("{not json", encoding="utf-8")

        self.run_download()

        self.assertEqual(sorted(self.content_requests[0]), sorted(TITLES.values()))


class TestForce(BirnbaumDownloadTestCase):
    def test_refetches_everything_regardless_of_the_manifest(self):
        self.seed_page(FIRST, "001", revid=111)

        self.run_download(force=True)

        self.assertEqual(sorted(self.content_requests[0]), sorted(TITLES.values()))


class TestDryRun(BirnbaumDownloadTestCase):
    def test_writes_nothing(self):
        self.run_download(dry_run=True)

        self.assertFalse(self.text_dir.exists())
        self.assertFalse(self.manifest_file.exists())

    def test_does_not_fetch_content(self):
        self.run_download(dry_run=True)

        self.assertEqual(self.content_requests, [])


class TestSourceLayout(BirnbaumDownloadTestCase):
    def test_subtree_pages_mirror_the_title_hierarchy(self):
        self.run_download()

        expected = (
            wikisource.birnbaum_siddur_source_text_directory(self.root)
            / "אשכנז"
            / "דפי יסוד"
            / "קדיש.txt"
        )
        self.assertTrue(expected.is_file())
        self.assertEqual(expected.read_text(encoding="utf-8"), SOURCE_WIKITEXT[FOUNDATION])

    def test_credits_mirror_the_text_tree(self):
        self.run_download()

        self.assertTrue(
            (
                wikisource.birnbaum_siddur_source_credits_directory(self.root)
                / "אשכנז" / "דפי יסוד" / "קדיש.txt"
            ).is_file()
        )

    def test_the_root_page_becomes_index(self):
        self.run_download()

        self.assertTrue(
            (wikisource.birnbaum_siddur_source_text_directory(self.root) / "index.txt").is_file()
        )

    def test_pages_outside_the_subtree_go_in_the_external_tree(self):
        self.run_download()

        expected = (
            wikisource.birnbaum_siddur_external_text_directory(self.root)
            / "עשרת הדברות" / "ניקוד.txt"
        )
        self.assertTrue(expected.is_file())

    def test_redirects_are_kept_and_recorded(self):
        # Roughly half the real subtree is redirects carrying alternate service
        # names, so they are organization rather than noise.
        self.run_download()

        entry = self.read_manifest()["source_pages"][REDIRECT_PAGE]
        self.assertEqual(entry["redirect_target"], FOUNDATION)
        self.assertIsNone(self.read_manifest()["source_pages"][FOUNDATION]["redirect_target"])


class TestClosureBoundary(BirnbaumDownloadTestCase):
    def test_the_walker_is_told_not_to_follow_scan_pages(self):
        # They are downloaded by the other phase; following them here would fetch
        # the whole book a second time, since the two layers reference each other.
        self.run_download()

        _roots, include = self.closure_calls[0]
        self.assertFalse(include(TITLES[FIRST]))
        self.assertTrue(include(FOUNDATION))

    def test_the_root_page_is_added_to_the_enumerated_roots(self):
        # A prefix search on "ROOT/" cannot match ROOT itself.
        self.run_download()

        roots, _include = self.closure_calls[0]
        self.assertIn(ROOT, roots)


class TestStructure(BirnbaumDownloadTestCase):
    def test_records_the_sections_a_page_defines(self):
        self.run_download()

        self.assertEqual(self.read_structure()["pages"][FOUNDATION]["defines"], [SECTION])

    def test_records_what_the_scan_pages_transclude(self):
        # This is the link between printed pagination and liturgical text, and the
        # main reason structure.json exists.
        self.run_download()

        scan = self.read_structure()["pages"][TITLES[FIRST]]
        self.assertEqual(scan["transcludes"], [{"title": FOUNDATION, "section": SECTION}])

    def test_reports_references_that_resolve_to_nothing(self):
        self.assertEqual(self.run_download() and self.read_structure()["dangling"], [])

    def test_flags_a_dangling_reference(self):
        SOURCE_WIKITEXT[FOUNDATION] = "<קטע התחלה=something else/>x"
        self.addCleanup(
            SOURCE_WIKITEXT.__setitem__,
            FOUNDATION,
            f"<קטע התחלה={SECTION}/>text<קטע סוף={SECTION}/>",
        )

        self.run_download()

        self.assertIn(
            {"title": FOUNDATION, "section": SECTION}, self.read_structure()["dangling"]
        )

    def test_says_it_is_derived(self):
        self.run_download()

        self.assertIn("regenerate", self.read_structure()["generated_from"])


class TestSkipSource(BirnbaumDownloadTestCase):
    def test_skipping_the_source_phase_downloads_only_the_scans(self):
        self.run_download(include_source=False)

        self.assertEqual(self.closure_calls, [])
        self.assertFalse(
            wikisource.birnbaum_siddur_source_text_directory(self.root).exists()
        )


class TestCli(unittest.TestCase):
    def test_refuses_to_run_without_a_contact_address(self):
        # Wikimedia's User-Agent policy wants a reachable address; without one we
        # should stop rather than send a placeholder.
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(wikisource, "download_book") as download:
                exit_code = main(["--dry-run"])

        self.assertEqual(exit_code, 1)
        download.assert_not_called()

    def test_passes_the_contact_address_through(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(wikisource, "download_book") as download:
                exit_code = main(["--contact-email", "example@opensiddur.org", "--dry-run"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(download.call_args.args[0], "example@opensiddur.org")
        self.assertTrue(download.call_args.kwargs["dry_run"])


if __name__ == "__main__":
    unittest.main()
