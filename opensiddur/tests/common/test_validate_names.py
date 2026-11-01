"""Tests for the naming check.

Every project, settings file, registry and spellings list here is written into a temporary
directory by the test. Nothing reads the real corpus or `specs/naming/spellings.yaml`, so these
keep meaning as both change.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from opensiddur.common.urn_registry import ERROR, WARNING
from opensiddur.common.validate_names import (
    Spellings,
    load_spellings,
    main,
    project_id_problem,
    respell,
    respell_urns,
    urn_paths,
    validate,
    words,
)

SPELLINGS = Spellings(frozenset({"kaddish"}), {"hanukkah": "chanukah", "tsom": "tzom"})

TEXT = "urn:x-opensiddur:text:"


def index(lang: str, *urns: str) -> str:
    idnos = "".join(f'<tei:idno type="urn">{u}</tei:idno>' for u in urns)
    return (f'<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="{lang}">'
            f"<tei:teiHeader>{idnos}</tei:teiHeader></tei:TEI>")


class Corpus:
    """A temporary project, settings and registry directory."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.projects = self.root / "project"
        self.settings = self.root / "settings"
        self.registry = self.root / "registry"
        for d in (self.projects, self.settings, self.registry):
            d.mkdir()

    def close(self):
        self._tmp.cleanup()

    def project(self, name: str, lang: str = "he", files: dict[str, str] | None = None):
        path = self.projects / name
        path.mkdir()
        (path / "index.xml").write_text(index(lang), encoding="utf-8")
        for stem, body in (files or {}).items():
            (path / f"{stem}.xml").write_text(body, encoding="utf-8")
        return path

    def settings_file(self, directory: str, variant: str, project: str):
        path = self.settings / directory
        path.mkdir(exist_ok=True)
        (path / f"{variant}.yaml").write_text(
            f"book:\n  project: {project}\n  file_name: index.xml\n", encoding="utf-8")

    def registry_records(self, *records: dict):
        (self.registry / "prayer.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    def validate(self, **kw):
        kw.setdefault("spellings", SPELLINGS)
        return validate(self.projects, self.settings, self.registry, **kw)


def errors(problems):
    return [p for p in problems if p.severity == ERROR]


class RespellTestCase(unittest.TestCase):
    def test_a_name_is_respelled_word_by_word(self):
        self.assertEqual(respell("hanukkah_tsom_day_4", SPELLINGS), "chanukah_tzom_day_4")
        self.assertEqual(respell("untouched_words", SPELLINGS), "untouched_words")

    def test_only_whole_words_are_respelled(self):
        self.assertEqual(respell("hanukkahs_atsom", SPELLINGS), "hanukkahs_atsom")

    def test_urn_paths_are_respelled_and_projects_and_fragments_are_not(self):
        text = (f'<a corresp="{TEXT}prayer:hanukkah/tsom@hanukkah-tsom-1900-he#tsom"/>'
                '<b ref="urn:x-opensiddur:instruction:hanukkah/add"/>'
                '<c n="urn:x-opensiddur:notes:book/hanukkah"/>'
                '<d ref="urn:x-opensiddur:condition:hanukkah"/> hanukkah in prose')
        self.assertEqual(respell_urns(text, SPELLINGS),
                         f'<a corresp="{TEXT}prayer:chanukah/tzom@hanukkah-tsom-1900-he#tsom"/>'
                         '<b ref="urn:x-opensiddur:instruction:chanukah/add"/>'
                         '<c n="urn:x-opensiddur:notes:book/chanukah"/>'
                         '<d ref="urn:x-opensiddur:condition:hanukkah"/> hanukkah in prose')


class ProjectIdTestCase(unittest.TestCase):
    def test_an_identifier_ending_in_its_language_passes(self):
        for name, lang in (("hasiddur_hashalem-birnbaum-1949-he", "he"),
                           ("tanakh-jps-1917-en", "en"),
                           ("shir_hamaalot-someone-2020-he-latn", "he-Latn")):
            with self.subTest(name=name):
                self.assertIsNone(project_id_problem(name, lang))

    def test_one_field_is_not_an_identifier(self):
        self.assertIn("not a project identifier",
                      project_id_problem("birnbaum_ashkenaz_he_1949", "he"))

    def test_disallowed_characters(self):
        for name in ("Tanakh-jps-1917-en", "tanakh jps-en", "tanakh--en", "tanakh-en-",
                     "tanakh_-en", "tanakh-(jps)-en", "tanakh-jps@1917-en"):
            with self.subTest(name=name):
                self.assertIsNotNone(project_id_problem(name, None))

    def test_the_last_field_is_the_language(self):
        self.assertIn("-en", project_id_problem("tanakh-jps-1917-he", "en"))
        # The language is not the whole identifier.
        self.assertIsNotNone(project_id_problem("he-latn", "he-latn"))


class WordsTestCase(unittest.TestCase):
    def test_numbers_are_not_words(self):
        self.assertEqual(list(words("chanukah_day_4/1")), ["chanukah", "day"])

    def test_urn_paths_drop_project_fragment_and_split_ranges(self):
        text = (f'<a corresp="{TEXT}prayer:amidah/avot@p-he#x"/>'
                f'<b target="{TEXT}bible:genesis/1/1-2/3@w-he"/>'
                '<c ref="urn:x-opensiddur:contributor:opensiddur.org/someone"/>')
        self.assertEqual(list(urn_paths(text)), ["amidah/avot", "genesis/1/1", "genesis/2/3"])

    def test_absolute_and_malformed_ranges(self):
        self.assertEqual(list(urn_paths(f'"{TEXT}bible:nahum/2/2/b-/2/5"')),
                         ["nahum/2/2/b", "nahum/2/5"])
        # A range with no end is read as written, for validate_urn_references to report.
        self.assertEqual(list(urn_paths(f'"{TEXT}prayer:amidah/avot-"')), ["amidah/avot-"])

    def test_instruction_urns_are_read_and_condition_urns_are_not(self):
        text = ('"urn:x-opensiddur:instruction:amidah/birkat_kohanim" '
                '"urn:x-opensiddur:condition:bible:taam-elyon"')
        self.assertEqual(list(urn_paths(text)), ["amidah/birkat_kohanim"])

    def test_a_urn_cited_in_prose_leaves_its_full_stop(self):
        self.assertEqual(list(urn_paths(f"see {TEXT}prayer:amidah/avot. And {TEXT}prayer:aleinu")),
                         ["amidah/avot", "aleinu"])

    def test_a_urn_cited_in_a_parenthesis_leaves_its_closing_parenthesis(self):
        self.assertEqual(list(urn_paths(f"(see {TEXT}bible:genesis/1/1). And ({TEXT}prayer:aleinu)")),
                         ["genesis/1/1", "aleinu"])

    def test_a_malformed_component_is_read_whole(self):
        self.assertEqual(list(urn_paths(f'"{TEXT}bible:reading/yom_kippur_(mincha,_x)"')),
                         ["reading/yom_kippur_(mincha,_x)"])


class ProjectChecksTestCase(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()
        self.addCleanup(self.corpus.close)

    def test_a_clean_project_has_no_problems(self):
        self.corpus.project("selichot-asher-1912-he", files={
            "kaddish_chatzi": index("he", f"{TEXT}prayer:kaddish/chatzi@selichot-asher-1912-he")})
        self.assertEqual(self.corpus.validate(), [])

    def test_a_project_named_the_old_way(self):
        self.corpus.project("asher_selichot_he_1912")
        (problem,) = errors(self.corpus.validate())
        self.assertEqual(problem.where, "asher_selichot_he_1912")
        self.assertIn("not a project identifier", problem.message)

    def test_a_project_whose_name_and_language_disagree(self):
        self.corpus.project("selichot-asher-1912-en", lang="he")
        (problem,) = errors(self.corpus.validate())
        self.assertIn("-he", problem.message)

    def test_a_file_name_with_punctuation(self):
        self.corpus.project("chumash-opensiddur-he", files={"reading_fast_(afternoon)": index("he")})
        (problem,) = errors(self.corpus.validate())
        self.assertIn("file name 'reading_fast_(afternoon)'", problem.message)

    def test_a_malformed_urn_component(self):
        self.corpus.project("chumash-opensiddur-he", files={
            "fast": index("he", f"{TEXT}bible:reading/fast_(afternoon)")})
        (problem,) = errors(self.corpus.validate())
        self.assertIn("URN component 'fast_(afternoon)'", problem.message)

    def test_a_variant_is_reported_once_with_its_standard_spelling(self):
        self.corpus.project("hasiddur_hashalem-birnbaum-1949-he", files={
            "hanukkah_candles": index("he", f"{TEXT}prayer:hanukkah/candles",
                                      f"{TEXT}prayer:hanukkah/maoz_tzur"),
            "tsom_gedaliah": index("he")})
        found = errors(self.corpus.validate())
        self.assertEqual(len(found), 3, found)
        messages = " | ".join(p.message for p in found)
        self.assertIn("'hanukkah' should be spelled 'chanukah' (1 use(s): hanukkah_candles.xml)",
                      messages)
        self.assertIn("'hanukkah' should be spelled 'chanukah' (2 use(s)", messages)
        self.assertIn("'tsom' should be spelled 'tzom'", messages)

    def test_a_project_with_no_language(self):
        path = self.corpus.project("selichot-asher-1912-he")
        (path / "index.xml").write_text('<TEI xml:lang=""/>', encoding="utf-8")
        (problem,) = errors(self.corpus.validate())
        self.assertIn("no xml:lang", problem.message)

    def test_a_project_identifier_is_not_held_to_the_spelling_list(self):
        # A source's own romanization of its name, and a person's name.
        self.corpus.project("maoz_tsom-tsom-1240-he")
        self.assertEqual(self.corpus.validate(), [])

    def test_only_the_named_projects_are_checked(self):
        self.corpus.project("old_name")
        self.corpus.project("tanakh-wlc-he")
        self.assertEqual(self.corpus.validate(projects=["tanakh-wlc-he"]), [])

    def test_a_named_project_that_does_not_exist(self):
        (problem,) = errors(self.corpus.validate(projects=["missing-he"]))
        self.assertEqual(problem.where, "missing-he")


class SettingsCheckTestCase(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()
        self.addCleanup(self.corpus.close)

    def test_settings_under_their_project(self):
        self.corpus.settings_file("chumash-opensiddur-he", "annual", "chumash-opensiddur-he")
        self.assertEqual(self.corpus.validate(), [])

    def test_settings_under_another_name(self):
        self.corpus.settings_file("humash", "annual", "chumash-opensiddur-he")
        (problem,) = errors(self.corpus.validate())
        self.assertEqual(problem.where, "humash/annual.yaml")
        self.assertIn("belongs in chumash-opensiddur-he/annual.yaml", problem.message)

    def test_settings_without_a_book_or_unreadable(self):
        (self.corpus.settings / "humash").mkdir()
        (self.corpus.settings / "humash" / "nobook.yaml").write_text("formats: [html]\n",
                                                                     encoding="utf-8")
        (self.corpus.settings / "humash" / "broken.yaml").write_text(":\n: [", encoding="utf-8")
        (problem,) = errors(self.corpus.validate())
        self.assertEqual(problem.where, "humash/broken.yaml")
        self.assertIn("not readable YAML", problem.message)

    def test_a_missing_settings_directory_warns(self):
        problems = validate(self.corpus.projects, self.corpus.root / "nowhere", None,
                            spellings=SPELLINGS)
        self.assertEqual([p.severity for p in problems], [WARNING])


class RegistryCheckTestCase(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()
        self.addCleanup(self.corpus.close)

    def test_canonical_records_are_held_to_the_spelling_list(self):
        self.corpus.registry_records(
            {"urn": f"{TEXT}prayer:hanukkah", "status": "canonical"},
            {"urn": f"{TEXT}prayer:tsom", "status": "alias",
             "canonical": f"{TEXT}prayer:tzom"},
            {"urn": f"{TEXT}prayer:tzom", "status": "canonical"})
        (problem,) = errors(self.corpus.validate())
        self.assertEqual(problem.where, "registry")
        self.assertIn("'hanukkah'", problem.message)

    def test_an_unreadable_registry_is_an_error(self):
        (self.corpus.registry / "prayer.jsonl").write_text("not json\n", encoding="utf-8")
        (problem,) = errors(self.corpus.validate())
        self.assertEqual(problem.where, "registry")


class SpellingsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "spellings.yaml"

    def load(self, text: str) -> Spellings:
        self.path.write_text(text, encoding="utf-8")
        return load_spellings(self.path)

    def test_reads_both_lists(self):
        spellings = self.load("exceptions: [kaddish]\nvariants:\n  qaddish: kaddish\n")
        self.assertEqual(spellings.exceptions, {"kaddish"})
        self.assertEqual(spellings.variants, {"qaddish": "kaddish"})

    def test_a_common_spelling_cannot_be_a_variant(self):
        with self.assertRaisesRegex(ValueError, "both"):
            self.load("exceptions: [kaddish]\nvariants:\n  kaddish: qaddish\n")

    def test_a_variant_maps_to_a_standard_spelling(self):
        with self.assertRaisesRegex(ValueError, "itself a variant"):
            self.load("variants:\n  hanukkah: chanukkah\n  chanukkah: chanukah\n")

    def test_a_word_is_not_its_own_variant(self):
        with self.assertRaisesRegex(ValueError, "itself"):
            self.load("variants:\n  tzom: tzom\n")


class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()
        self.addCleanup(self.corpus.close)
        self.spellings = self.corpus.root / "spellings.yaml"
        self.spellings.write_text("variants:\n  tsom: tzom\n", encoding="utf-8")

    def run_main(self, *extra: str) -> int:
        with redirect_stderr(io.StringIO()):
            return main(["--project-directory", str(self.corpus.projects),
                         "--settings-directory", str(self.corpus.settings),
                         "--registry", str(self.corpus.registry),
                         "--spellings", str(self.spellings), *extra])

    def test_check_fails_only_when_something_is_wrong(self):
        self.corpus.project("tzom_gedaliah-asher-1912-he", files={"tzom": index("he")})
        self.assertEqual(self.run_main("--check"), 0)
        self.corpus.project("tzom_asher_1912_he")
        self.assertEqual(self.run_main("--check"), 1)
        self.assertEqual(self.run_main(), 0)

    def test_names_only_checks_project_names_and_settings_places(self):
        self.corpus.project("tzom_gedaliah-asher-1912-he", files={"tsom_(fast)": index("he")})
        self.corpus.registry_records({"urn": f"{TEXT}prayer:tsom", "status": "canonical"})
        self.assertEqual(self.run_main("--check"), 1)
        self.assertEqual(self.run_main("--check", "--names-only"), 0)
        self.corpus.settings_file("elsewhere", "annual", "tzom_gedaliah-asher-1912-he")
        self.assertEqual(self.run_main("--check", "--names-only"), 1)
        self.corpus.project("old_name")
        self.assertEqual(self.run_main("--check", "--names-only", "--no-settings"), 1)

    def test_settings_and_registry_can_be_skipped(self):
        self.corpus.settings_file("elsewhere", "annual", "tanakh-wlc-he")
        self.corpus.registry_records({"urn": f"{TEXT}prayer:tsom", "status": "canonical"})
        self.assertEqual(self.run_main("--check", "--no-registry"), 1)
        self.assertEqual(self.run_main("--check", "--no-settings"), 1)
        self.assertEqual(self.run_main("--check", "--no-settings", "--no-registry"), 0)

    def test_an_inconsistent_spellings_list_is_an_error(self):
        self.spellings.write_text("variants:\n  tsom: tsom\n", encoding="utf-8")
        self.assertEqual(self.run_main(), 1)


if __name__ == "__main__":
    unittest.main()
