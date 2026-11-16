"""Synthetic Sefaria works for the importer's tests. Nothing here reads sourcetexts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opensiddur.importer.sefaria.source import leaf_hashes, read_work_source
from opensiddur.importer.sefaria.works import Work

HE_VERSION = "Test Siddur: Hebrew, 1981"
EN_VERSION = "Test Siddur: Hebrew, 1981 [en]"

WORK = Work(
    key="test_siddur",
    title="Test Siddur",
    versions={"he": HE_VERSION, "en": EN_VERSION},
    projects={"he": "test_siddur-tester-1981-he", "en": "test_siddur-tester-1981-en"},
    title_en="The Test Siddur",
    title_he="סידור בדיקה",
    rite="A test rite.",
    licence="https://creativecommons.org/licenses/by/3.0/",
    publisher="Test Publications",
    place="New York",
    translator="A. Translator",
    date="1981",
)

#: A small siddur: one inner node with two leaves, and a top-level leaf.
#: Each leaf is a list of (Hebrew, English) segments.
MORNING = [
    ("", "<small><i>Upon waking, say:</i></small>"),
    ("<b>מוֹדֶה אֲנִי</b> לְפָנֶֽיךָ", "I give thanks to You"),
    ("מֶֽלֶךְ חַי וְקַיָּם", "living and everlasting King<sup class=\"footnote-marker\">1</sup><i class=\"footnote\">God lives.</i>"),
    ("", "<small><i>After washing, say:</i></small>"),
    ("<b>רֵאשִׁית חָכְמָה</b> יִרְאַת יְהֹוָה", "The beginning of wisdom is fear of Adonoy"),
    ("שֵֽׂכֶל טוֹב", "good understanding"),
]
AMIDAH = [
    ("<b>אבות</b>", "<b>FOREFATHERS</b>"),
    ("<b>בָּרוּךְ</b> אַתָּה יְהֹוָה אֱלֹהֵֽינוּ", "Blessed are You, Adonoy, our God"),
    ("וֵאלֹהֵי אֲבוֹתֵֽינוּ", "and God of our fathers"),
    ("<small>לְר\"ח:</small> רֹאשׁ הַחֹֽדֶשׁ הַזֶּה", "<i>Rosh Chodesh</i>"),
]
BLESSINGS = [
    ("<b>הַלְ֒לוּיָהּ</b> הַלְ֒לִי נַפְשִׁי", "Praise God! Praise, my soul"),
    ("אֶת־יְהֹוָה", "Adonoy"),
    ("", "<small>(Mourner's Kaddish.)</small>"),
]

TREE: dict[str, Any] = {
    "Morning": {"Upon Arising": MORNING, "Amidah": AMIDAH},
    "Blessings": BLESSINGS,
}
HE_TITLES = {"Morning": "שחרית", "Upon Arising": "השכמה", "Amidah": "עמידה", "Blessings": "ברכות"}

STRUCTURE = {
    "Morning": "chol/shacharit",
    "Morning / Upon Arising": "chol/shacharit/upon_arising",
    "Morning / Amidah": "chol/shacharit/amidah",
    "Blessings": "berakhot/test",
}


def _titles(key: str) -> list[dict[str, Any]]:
    return [{"primary": True, "lang": "en", "text": key},
            {"primary": True, "lang": "he", "text": HE_TITLES.get(key, key)}]


def _schema(tree: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for key, value in tree.items():
        if isinstance(value, dict):
            nodes.append({"key": key, "titles": _titles(key), "nodes": _schema(value)})
        else:
            nodes.append({"key": key, "titles": _titles(key), "nodeType": "JaggedArrayNode",
                          "depth": 1, "sectionNames": ["Paragraph"]})
    return nodes


def _text(tree: dict[str, Any], side: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in tree.items():
        out[key] = _text(value, side) if isinstance(value, dict) else [pair[side] for pair in value]
    return out


def make_index(tree: dict[str, Any] = TREE, title: str = "Test Siddur") -> dict[str, Any]:
    return {"title": title, "heTitle": "סידור בדיקה",
            "schema": {"key": title, "titles": _titles(title), "nodes": _schema(tree)}}


def make_version(tree: dict[str, Any], lang: str, *, version_title: str | None = None,
                 license: str = "CC-BY") -> dict[str, Any]:
    return {"title": "Test Siddur", "language": lang, "license": license, "status": "locked",
            "versionTitle": version_title or (HE_VERSION if lang == "he" else EN_VERSION),
            "versionSource": "https://example.org/book",
            "text": _text(tree, 0 if lang == "he" else 1)}


def make_source(tree: dict[str, Any] = TREE):
    return read_work_source(make_index(tree), make_version(tree, "he"), make_version(tree, "en"))


def write_work_dir(directory: Path, tree: dict[str, Any] = TREE, *, last_export: str = "2026-11-01T00:00:00") -> Path:
    """A downloaded work, as ``download.py`` leaves it, with a manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    index, he, en = make_index(tree), make_version(tree, "he"), make_version(tree, "en")
    for name, data in (("schema.json", index), ("he.json", he), ("en.json", en)):
        (directory / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    manifest = {
        "last_export": last_export,
        "files": {
            "schema.json": {"md5Hash": "s"},
            "he.json": {"md5Hash": "h", "version_title": HE_VERSION, "license": "CC-BY", "url": "u-he"},
            "en.json": {"md5Hash": "e", "version_title": EN_VERSION, "license": "CC-BY", "url": "u-en"},
        },
        "leaves": leaf_hashes(read_work_source(index, he, en)),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return directory


def write_structure(path: Path, structure: dict[str, str | None] = STRUCTURE) -> Path:
    import yaml

    path.write_text(yaml.safe_dump(structure, allow_unicode=True), encoding="utf-8")
    return path
