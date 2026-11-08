"""Compiled JLPTEI to an electronic book: one self-contained HTML file.

The book is a document and a program at once. Its text is html.xslt's rendering of the compiled
file; its program resolves the passages the compile left undecided, on the reader's device,
against the reader's own settings and the device's clock (assets/calendar.js,
assets/condition.js, assets/reader.js). Styles, scripts and
data are all inline, so the one file is the whole book: it opens from a disk, a USB stick or
an email, offline, and needs nothing else.

Read without scripts, the page is the printed book: <style id="os-cond-default"> holds the
rules a compile of the same settings file would have applied, computed here.

Compile with `--destination electronic` first, so that the settings a reader supplies are left
for the reader:

    python -m opensiddur.exporter.compiler -s SETTINGS --destination electronic -o book.xml
    python -m opensiddur.exporter.html.html book.xml book.html -s SETTINGS
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import html
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from lxml import etree
from PIL import Image
from pydantic import ValidationError

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.version import processor_version
from opensiddur.common.xslt import xslt_transform_string
from opensiddur.exporter.cli_common import (
    SettingsError,
    add_settings_arguments,
    load_output_settings,
    prepare_compiled_tree,
)
from opensiddur.exporter.calendar.compute import FS_HOLIDAY, FS_PURIM_OBSERVANCE
from opensiddur.exporter.client_settings import is_reader_supplied, resolve
from opensiddur.exporter.condition_eval import TriState, condition_features, condition_from_json, value_to_json
from opensiddur.exporter.constants import PROCESSING_NAMESPACE, TEI_NS
from opensiddur.exporter.derived_settings import STATIC_DEFAULTS
from opensiddur.exporter.html.css import css_length, typography_css, xslt_parameters
from opensiddur.exporter.html.markers import BookConditions, prepare
from opensiddur.exporter.html.psalms import normalize as normalize_psalm_titles
from opensiddur.exporter.metadata import ISBN_TYPES, Colophon, SourceRecord, build_colophon
from opensiddur.exporter import notices
from opensiddur.exporter.notices import RunKind
from opensiddur.exporter.settings import (
    DistributionNotice,
    DistributionSettings,
    ElectronicSettings,
    SettingsYaml,
)

logger = logging.getLogger(__name__)

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
XSLT_FILE = HERE / "html.xslt"

P_DESTINATION = f"{{{PROCESSING_NAMESPACE}}}destination"
P_PROJECT = f"{{{PROCESSING_NAMESPACE}}}project"
P_FILE_NAME = f"{{{PROCESSING_NAMESPACE}}}file_name"
P_PARALLEL_ITEM = f"{{{PROCESSING_NAMESPACE}}}parallelItem"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


# ── Settings ────────────────────────────────────────────────────────────────

def book_defaults(settings: SettingsYaml) -> dict[str, dict[str, Any]]:
    """What the book starts from, for the settings a reader supplies.

    The static defaults, overlaid with the settings file's declarations: the values a compile
    for print would have used, which an electronic compile left for the reader to change.
    """
    defaults: dict[str, dict[str, Any]] = {}
    for fs_type, features in STATIC_DEFAULTS.items():
        if is_reader_supplied(fs_type):
            for name, value in features.items():
                defaults.setdefault(fs_type, {})[name] = value_to_json(value)
    for fs_type, features in settings.declarations.items():
        if is_reader_supplied(fs_type):
            for name, value in features.items():
                defaults.setdefault(fs_type, {})[name] = value
    return defaults


# ── Conditions ──────────────────────────────────────────────────────────────

def expression_states(
    book: BookConditions, defaults: dict, reader: dict | None = None,
) -> list[TriState]:
    """How each of the book's expressions resolves, for the given reader settings."""
    return [
        resolve(expression["cond"], pinned=expression["pinned"], reader=reader or {},
                defaults=defaults)
        for expression in book.expressions
    ]


def scope_css(book: BookConditions, states: list[TriState]) -> str:
    """The rules that show and hide the book's scopes. condition.js's scopeCss writes the same
    rules on the device; a test holds the two to it."""
    hidden: list[str] = []
    settled: list[str] = []
    for cid, expression in enumerate(book.scopes):
        state = states[expression]
        if state == TriState.FALSE:
            hidden += [f".c{cid}", f".m{cid}"]
        elif state == TriState.TRUE:
            # A passage that is simply said: the rubric that said when goes with its rules and
            # brackets. Commentary the compiler anchored on the rubric stays.
            settled += [f".m{cid}.cm-close", f".m{cid} > .rubric", f".m{cid} .cm-br"]
    # A row none of whose text shows goes whole (BookConditions.rows).
    for number, sets in enumerate(book.rows):
        if not any(all(states[book.scopes[cid]] != TriState.FALSE for cid in scopes)
                   for scopes in sets):
            hidden.append(f".r{number}")
    for number, destinations in enumerate(book.optional_references):
        if not all(any(all(states[book.scopes[cid]] != TriState.FALSE for cid in scopes)
                       for scopes in occurrences) for occurrences in destinations):
            hidden.append(f".oref{number}")
    css = ""
    # Expanded books can exceed a browser's selector limit for one rule.
    # Keep every selector effective, including scopes near the end of the book.
    for selectors in (hidden, settled):
        for start in range(0, len(selectors), 256):
            css += ",".join(selectors[start:start + 256]) + "{display:none}\n"
    return css


#: Names for the columns' languages, by the first part of their tag.
LANGUAGE_NAMES = {"he": "Hebrew", "en": "English", "arc": "Aramaic", "yi": "Yiddish"}


def columns(root: etree.ElementBase) -> dict[str, dict[str, str]] | None:
    """The two columns of the book's parallel text, each with its language and its label.

    Each role's language is the one most of its items have. The Hebrew column is "Hebrew" and
    the other "Translation"; a book with neither column Hebrew names its primary column by its
    language. None for a book with no parallel text.
    """
    found: dict[str, Counter] = {"primary": Counter(), "parallel": Counter()}
    for item in root.iter(P_PARALLEL_ITEM):
        role = item.get("role")
        if role in found:
            found[role][(item.get(XML_LANG) or "").split("-")[0]] += 1
    if not all(found.values()):
        return None
    langs = {role: counts.most_common(1)[0][0] for role, counts in found.items()}
    hebrew = next((role for role in ("primary", "parallel") if langs[role] == "he"), None)
    named = hebrew or "primary"
    return {role: {"lang": langs[role],
                   "label": (LANGUAGE_NAMES.get(langs[role], langs[role]) if role == named
                             else "Translation")}
            for role in ("primary", "parallel")}


def calendar_scopes(book: BookConditions) -> int:
    """How many scopes turn on the calendar: the device answers them once it has a place."""
    turning: list[bool] = []
    for expression in book.expressions:
        features = condition_features(condition_from_json(expression["cond"]))
        turning.append(any(
            not is_reader_supplied(fs) and name not in expression["pinned"].get(fs, {})
            for fs, name in features))
    return sum(1 for expression in book.scopes if turning[expression])


# ── About the book ──────────────────────────────────────────────────────────

def book_title(root: etree.ElementBase, settings: SettingsYaml) -> str:
    title = ((settings.book and settings.book.title) or "").strip()
    if title:
        return title
    found = root.find(f".//{{{TEI_NS}}}titleStmt/{{{TEI_NS}}}title")
    return " ".join("".join(found.itertext()).split()) if found is not None else "Open Siddur"


def book_id(root: etree.ElementBase, title: str) -> str:
    """A stable name for the book, under which the reader's settings are kept."""
    source = f"{root.get(P_PROJECT, '')}/{root.get(P_FILE_NAME, '')}/{title}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def generator() -> str:
    installed = processor_version()
    return f"opensiddur-processor {installed}" if installed else "opensiddur-processor"


def about_html(
    title: str,
    compiled_file: Path,
    project_directory: Path,
    distribution: DistributionSettings | None = None,
    editions: str = "",
) -> str:
    """The book's colophon: what it is, whose work it is under which licences, and from where;
    then what its digital editions say about themselves (``editions``, see
    :func:`split_colophons`); and after it all, the back notice."""
    back = notices.back_notice_items(distribution or DistributionSettings(), "electronic")
    return colophon_to_html(title, build_colophon(compiled_file, project_directory),
                            back_notice=back, editions=editions)


#: Where html.xslt marks out the colophon divisions it set (see cli_common.relocate_colophons).
COLOPHON_START = "<!--@@COLOPHON-START@@-->"
COLOPHON_END = "<!--@@COLOPHON-END@@-->"


def split_colophons(main: str) -> tuple[str, str]:
    """The book's text without its colophon divisions, and the divisions, which are set after
    the book's own colophon."""
    editions: list[str] = []
    while (start := main.find(COLOPHON_START)) >= 0:
        end = main.find(COLOPHON_END, start)
        if end < 0:
            break
        editions.append(main[start + len(COLOPHON_START):end])
        main = main[:start] + main[end + len(COLOPHON_END):]
    return main, "".join(editions)


def notice_line_html(text: str) -> str:
    """One line of a distribution or back notice: its text escaped, its URLs and emphasis set."""
    pieces = []
    for kind, run in notices.notice_runs(text):
        if kind is RunKind.URL:
            pieces.append(_link(run, html.escape(run)))
        elif kind is RunKind.EMPHASIS:
            pieces.append(f"<em>{_value(run)}</em>")
        else:
            pieces.append(_value(run))
    return "".join(pieces)


def back_notice_html(items: list[str]) -> str:
    """The statement after the colophon, or nothing."""
    if not items:
        return ""
    entries = "".join(f"<li>{notice_line_html(item)}</li>" for item in items)
    return f'<ul class="os-back-notice">{entries}</ul>'


#: How wide, in pixels, the electronic book carries the logo: twice what a reader sees at the
#: default width, for a high-density screen, and not the whole print-resolution image.
LOGO_PIXELS = 400


def logo_data_uri(logo: Path) -> str:
    """The logo as a data: URI, so the book stays one file that opens offline."""
    with Image.open(logo) as image:
        image.thumbnail((LOGO_PIXELS, LOGO_PIXELS))
        # PNG has no CMYK, which a logo made for print often is.
        image = image.convert("RGBA")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def distribution_notice_html(notice: DistributionNotice | None, logo: Path | None) -> str:
    """The distribution notice, after the title page; nothing if the book carries none."""
    if notice is None:
        return ""
    parts = ['<aside class="os-distribution">']
    if logo is not None:
        parts.append(f'<img src="{logo_data_uri(logo)}" alt="" '
                     f'style="width: {css_length(notice.logo_width)}">')
    parts += [f"<p>{notice_line_html(line)}</p>" for line in notice.text]
    parts.append("</aside>")
    return "".join(parts)


#: Where html.xslt leaves room for the distribution notice: after the first title page, or at
#: the head of a book without one.
DISTRIBUTION_PLACEHOLDER = "<!--@@DISTRIBUTION@@-->"


def colophon_to_html(
    title: str, colophon: Colophon, back_notice: list[str] = (), editions: str = ""
) -> str:
    escape = html.escape
    parts = [f"<h2>{escape(title)}</h2>",
             f"<p>An electronic edition from the Open Siddur Project, built by {escape(generator())}.</p>"]
    if colophon.credits:
        parts.append("<h2>Contributors</h2>")
        parts += [f"<p><strong>{escape(role.heading)}:</strong> {escape(', '.join(role.names))}</p>"
                  for role in colophon.credits]
    if colophon.licenses:
        parts.append("<h2>Licences</h2><p>This book includes texts under these licences:</p><ul>")
        parts += [f"<li>{_link(lic.url, escape(lic.name))}</li>" for lic in colophon.licenses]
        parts.append("</ul>")
    if colophon.sources:
        parts.append('<h2>Sources</h2><ul class="os-sources">')
        parts += [f"<li>{source_html(source)}</li>" for source in colophon.sources]
        parts.append("</ul>")
    parts.append(SOFTWARE_NOTICE)
    if editions.strip():
        parts.append(editions)
    if back := back_notice_html(list(back_notice)):
        parts.append(back)
    return "\n".join(parts)


#: Hebrew script, whose runs are isolated in a citation so that they do not reorder the
#: punctuation around them (the counterpart of \\texthebrew in the printed bibliography).
_HEBREW_SCRIPT = re.compile("[\u0590-\u05ff\ufb1d-\ufb4f]")


def _value(text: str) -> str:
    escaped = html.escape(text)
    return f"<bdi>{escaped}</bdi>" if _HEBREW_SCRIPT.search(text) else escaped


def _link(url: str, text: str) -> str:
    """A link to a web address. Anything else (a URN, or a script) is shown, not linked: the
    book opens offline from an email, and a link there must go where it says."""
    if re.match(r"https?://", url, re.IGNORECASE):
        return f'<a href="{html.escape(url)}">{text}</a>'
    return text


def _names(names: list[str]) -> str:
    return " and ".join(map(_value, names))


def source_html(source: SourceRecord) -> str:
    """One source as a citation: who, what, which edition, where and when, and a link.

    In the order a bibliography gives them, so that the electronic book cites what its printed
    counterpart does.
    """
    pieces: list[str] = []
    if source.authors:
        pieces.append(_names(source.authors))
    elif source.editors:
        pieces.append(_names(source.editors) + (" (eds.)" if len(source.editors) > 1 else " (ed.)"))
    if source.title:
        pieces.append(f"<cite>{_value(source.title)}</cite>"
                      + (f": {_value(source.subtitle)}" if source.subtitle else ""))
    if source.authors and source.editors:
        pieces.append("Edited by " + _names(source.editors))
    if source.edition:
        pieces.append(_value(source.edition))
    imprint = ", ".join(_value(part) for part in (
        ", ".join(source.address), source.publisher or source.distributor, source.date) if part)
    if imprint:
        pieces.append(imprint)
    pieces += [_value(f"{'ISBN' if kind in ISBN_TYPES else kind}: {value}" if kind else value)
               for kind, value in source.identifiers]
    if source.url:
        pieces.append(_link(source.url, html.escape(source.url))
                      + (f" (accessed {_value(source.urldate)})" if source.urldate else ""))
    pieces += [_value(note) for note in source.notes]
    # A piece's own full stop, even inside its markup (a title ending "ed."), is the one the
    # citation ends that piece with.
    return ". ".join(_TRAILING_STOP.sub(r"\1", piece) for piece in pieces) + "."


_TRAILING_STOP = re.compile(r"\.((?:</\w+>)*)$")


#: The book's scripts are a program, apart from the texts it shows, and under its own licence.
SOFTWARE_NOTICE = (
    "<h2>Software</h2>"
    "<p>The scripts in this book, which choose what it shows, are free software from "
    '<a href="https://github.com/opensiddur/opensiddur-processor">opensiddur-processor</a>: you can '
    "redistribute them and change them under the terms of the "
    '<a href="https://www.gnu.org/licenses/lgpl-3.0.html">GNU Lesser General Public License</a>, '
    "version 3 or any later version. They come with no warranty. Their source is in the book "
    "itself, and in that repository.</p>"
    "<p>The Hebrew calendar and the weekly readings follow "
    '<a href="https://github.com/simlist/pyluach">pyluach</a>, copyright © 2014 Meir S. List, '
    "under the MIT licence, which is given in full in the calendar's script. The times of day "
    "use NOAA's solar equations.</p>"
)


# ── The book ────────────────────────────────────────────────────────────────

def _inline(text: str, closing: str) -> str:
    """Text to go inside an element that ends at `closing`, which it must not contain."""
    if closing in text.lower():
        raise ValueError(f"cannot inline text containing {closing!r}")
    return text


# ── The settings panel ──────────────────────────────────────────────────────

BASIC_SETTINGS_FILE = HERE / "basic_settings.yaml"
PLACES_FILE = HERE / "places.yaml"
#: At most this many settings at the top of the panel...
BASIC_LIMIT = 6
#: ...each deciding at least this share of the text that any setting decides.
BASIC_THRESHOLD = 0.01


def read_basic_settings(spec_file: Path = BASIC_SETTINGS_FILE) -> dict[str, Any]:
    with open(spec_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def celebrated_purim(settings: SettingsYaml) -> int | None:
    """The day of Adar this volume celebrates as Purim: its settings file's, or the default.

    None when the settings file leaves it undefined.
    """
    declared = settings.declarations.get(FS_PURIM_OBSERVANCE) or {}
    if "day" in declared:
        return declared["day"]
    return STATIC_DEFAULTS[FS_PURIM_OBSERVANCE]["day"]


def _settle_purim(options: list[dict[str, Any]], purim_day: int | None) -> None:
    """Purim and Shushan Purim, as kinds of day, cannot say which is celebrated as Purim; the
    volume can. So a book takes `purim-observed` on those two days from its own volume's."""
    if purim_day is None:
        return
    for option in options:
        holidays = option["set"].get(FS_HOLIDAY, {})
        for name, day in (("purim", 14), ("shushan-purim", 15)):
            if holidays.get(name):
                holidays["purim-observed"] = int(purim_day == day)


def basic_controls(
    spec_file: Path = BASIC_SETTINGS_FILE, purim_day: int | None = None,
) -> list[dict[str, Any]]:
    """The composite controls (basic_settings.yaml), each with the features its options set.

    `purim_day` is the day the volume celebrates as Purim (see `celebrated_purim`).
    """
    controls = read_basic_settings(spec_file)["controls"]
    for control in controls:
        if "options_from" in control:
            with open(spec_file.parent / control.pop("options_from"), encoding="utf-8") as f:
                control["options"] = json.load(f)
            _settle_purim(control["options"], purim_day)
        control["features"] = sorted(
            {(fs, name) for option in control["options"]
             for fs, features in option["set"].items() for name in features})
    return controls


def _useful_options(book: BookConditions, control: dict[str, Any]) -> list[dict[str, Any]]:
    """The control's options that decide something in this book.

    Measured against nothing set at all, not against the book's defaults: an option the book
    starts from (the humash's annual cycle) is still one the reader must be able to name.
    """
    def states(reader):
        return [resolve(e["cond"], pinned=e["pinned"], reader=reader)
                for e in book.expressions]

    unset = states({})
    return [option for option in control["options"] if states(option["set"]) != unset]


def settings_catalogue(
    book: BookConditions,
    controls: list[dict[str, Any]],
    always: frozenset[tuple[str, str]] = frozenset(),
) -> list[dict[str, Any]]:
    """What goes at the top of this book's settings panel, best first.

    The candidates are the composite controls the book has a use for -- those setting a
    feature its conditions read -- and every feature no such control covers. Each scores the
    text it decides: the characters of the scopes that read any of its features, each scope
    counted once. The top `BASIC_LIMIT`, if they decide at least `BASIC_THRESHOLD` of the
    book's conditional text, are the basic settings; everything is in the Advanced box anyway.

    A control marked `top`, or a single feature in `always`, is a basic setting whenever the
    book has a use for it, however little text it decides; so is a control that sets a feature
    in `always`, which is then not offered alone. These follow the ranked ones and do not count
    towards the limit.
    """
    features = {(f.fs, f.name): f for f in book.features}

    def chars(cids: set[int]) -> int:
        return sum(book.scope_chars[cid] for cid in cids)

    candidates: list[tuple[int, bool, dict[str, Any]]] = []
    covered: set[tuple[str, str]] = set()
    for control in controls:
        read = [key for key in map(tuple, control["features"]) if key in features]
        if not read:
            continue
        options = _useful_options(book, control)
        if not options:
            continue
        covered.update(read)
        cids = {cid for key in read for cid in features[key].cids}
        top = bool(control.get("top")) or any(key in always for key in read)
        candidates.append((chars(cids), top, {
            "type": "control", "id": control["id"], "label": control["label"],
            **({"note": control["note"]} if control.get("note") else {}),
            **({"when": control["when"]} if control.get("when") else {}),
            "options": options}))
    for key, feature in features.items():
        if key not in covered:
            candidates.append((chars(set(feature.cids)), key in always,
                               {"type": "feature", "fs": feature.fs, "name": feature.name}))

    candidates.sort(key=lambda candidate: -candidate[0])
    floor = BASIC_THRESHOLD * book.conditional_chars
    ranked = [entry for score, _, entry in candidates[:BASIC_LIMIT] if score and score >= floor]
    return ranked + [entry for _, top, entry in candidates if top and entry not in ranked]


def always_basic(spec_file: Path = BASIC_SETTINGS_FILE) -> frozenset[tuple[str, str]]:
    """The single features basic_settings.yaml marks `top`."""
    words = read_basic_settings(spec_file).get("features") or {}
    return frozenset((fs, name) for fs, features in words.items()
                     for name, spec in features.items() if spec.get("top"))


def feature_words(spec_file: Path = BASIC_SETTINGS_FILE) -> dict[tuple[str, str], dict[str, Any]]:
    """The labels basic_settings.yaml gives single features, and their values, by feature."""
    words = read_basic_settings(spec_file).get("features") or {}
    return {(fs, name): {"label": spec.get("label"),
                         "values": {str(value): label
                                    for value, label in (spec.get("values") or {}).items()}}
            for fs, features in words.items() for name, spec in features.items()}


def read_places(places_file: Path = PLACES_FILE) -> list[dict[str, Any]]:
    """The places the settings panel offers, each with its coordinates and time zone."""
    with open(places_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def book_json(
    book: BookConditions,
    book_identifier: str,
    defaults: dict,
    basic_settings: Path = BASIC_SETTINGS_FILE,
    purim_day: int | None = None,
    book_columns: dict[str, dict[str, str]] | None = None,
    start: dict[str, str] | None = None,
    contents_depth: int = 4,
) -> str:
    calendar = calendar_scopes(book)
    words = feature_words(basic_settings)
    controls = basic_controls(basic_settings, purim_day)
    data = {
        "version": 1,
        "id": book_identifier,
        "expressions": book.expressions,
        "scopes": book.scopes,
        "defaults": defaults,
        "features": [
            {"fs": f.fs, "name": f.name, "values": f.values, "scopes": f.scopes,
             "kind": f.kind, "calendar": f.calendar,
             **({"label": words[(f.fs, f.name)]["label"],
                 "valueLabels": words[(f.fs, f.name)]["values"]}
                if (f.fs, f.name) in words else {})}
            for f in book.features
        ],
        "basic": settings_catalogue(book, controls, always_basic(basic_settings)),
        "sections": book.sections,
        "optionalReferences": book.optional_references,
        "rows": book.rows,
        "calendarScopes": calendar,
        # Only a book with passages that turn on the day needs places to work it out at.
        "places": read_places() if calendar else [],
        # The parallel text's columns, which the reader can show one at a time.
        "columns": book_columns,
        # How the book starts, before its reader chooses: the settings file's `electronic`.
        "start": start or ElectronicSettings().model_dump(),
        "contentsDepth": contents_depth,
    }
    # No "<" at all inside the script element: not only "</script" ends it, "<!--" can change
    # how the parser reads what follows. "\u003c" is the same character to JSON.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_book(
    compiled_file: Path,
    settings_file: Path | None = None,
    project_directory: Path | None = None,
    basic_settings: Path = BASIC_SETTINGS_FILE,
) -> str:
    """The electronic book, as one HTML document."""
    project_directory = Path(project_directory or PROJECT_DIRECTORY).resolve()
    # The reader's device chooses the faces, so whether this machine has them is moot.
    settings = load_output_settings(settings_file, resolve_fonts=False)
    typography = settings.typography

    root = etree.parse(str(compiled_file)).getroot()
    if root.get(P_DESTINATION) != "electronic":
        logger.warning(
            "%s was not compiled with --destination electronic: the settings a reader would "
            "choose were decided when it was compiled", compiled_file)

    if settings.electronic.psalm_titles == "uniform":
        normalize_psalm_titles(root)
    # The reader's settings can hide the first occurrence of a destination: label them all.
    prepare_compiled_tree(root, every_occurrence=True)
    book_columns = columns(root)
    book = prepare(root)
    notice = notices.distribution_notice(settings.distribution)
    main = xslt_transform_string(
        XSLT_FILE, etree.tostring(root, encoding="unicode"),
        xslt_params={**xslt_parameters(typography), "distribution-notice": notice is not None})
    if notice is not None:
        if DISTRIBUTION_PLACEHOLDER not in main:
            logger.warning("%s: html.xslt left no place for the distribution notice; the book "
                           "is built without it", compiled_file)
        main = main.replace(
            DISTRIBUTION_PLACEHOLDER,
            distribution_notice_html(notice, notices.resolve_logo(notice, settings_file)), 1)
    main, editions = split_colophons(main)
    defaults = book_defaults(settings)
    title = book_title(root, settings)

    replacements = {
        "@@GENERATOR@@": html.escape(generator()),
        "@@TITLE@@": html.escape(title),
        "@@STYLE@@": _inline(
            (ASSETS / "reader.css").read_text(encoding="utf-8") + typography_css(typography),
            "</style"),
        "@@DEFAULT_CONDITIONS@@": scope_css(book, expression_states(book, defaults)),
        "@@MAIN@@": main,
        "@@ABOUT@@": about_html(title, compiled_file, project_directory, settings.distribution,
                                editions),
        "@@BOOK@@": book_json(book, book_id(root, title), defaults, basic_settings,
                                celebrated_purim(settings), book_columns,
                                settings.electronic.model_dump(include={"day", "columns"}),
                                contents_depth=typography.table_of_contents.depth),
        "@@CALENDAR_JS@@": _inline(
            (ASSETS / "calendar.js").read_text(encoding="utf-8"), "</script"),
        "@@CONDITION_JS@@": _inline(
            (ASSETS / "condition.js").read_text(encoding="utf-8"), "</script"),
        "@@READER_JS@@": _inline(
            (ASSETS / "reader.js").read_text(encoding="utf-8"), "</script"),
    }
    page = (ASSETS / "book.html").read_text(encoding="utf-8")
    # One pass, so that a token's value -- the book's own text -- is never searched for tokens.
    return re.sub(r"@@[A-Z_]+@@", lambda match: replacements[match.group(0)], page)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="Render a compiled JLPTEI file as a self-contained electronic book.")
    parser.add_argument("input_file", type=Path, help="Compiled XML (--destination electronic).")
    parser.add_argument("output_file", type=Path, help="The book, an .html file.")
    add_settings_arguments(parser, "The settings file it was compiled with.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    # Checked first, so that only an error in the settings is reported as one.
    try:
        load_output_settings(args.settings_file, resolve_fonts=False)
    except (SettingsError, ValidationError) as e:
        print(f"Settings error: {e}", file=sys.stderr)
        sys.exit(1)
    page = build_book(args.input_file, args.settings_file, args.project_directory)
    args.output_file.write_text(page, encoding="utf-8")
    print(f"Electronic book written to: {args.output_file}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    main()
