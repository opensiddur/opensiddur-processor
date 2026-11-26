# Open Siddur Exporter

The exporter takes data in JLPTEI files and converts it into directly
consumable formats, like PDF and HTML.

The exporter operates in two stages:
1. **Compilation**: Given a starting file and a settings file, generate a compiled pseudo-TEI file that includes all of the data needed to convert into a final format in a linear form. The compilation step is common to all output formats.
2. **Output format**: Given the compiled file, output to the consumable format. The current output formats are:
    1. TeX typesetting system (LuaLaTeX, via [`reledmac`](https://ctan.org/pkg/reledmac) + [`reledpar`](https://ctan.org/pkg/reledpar) for critical-edition apparatus and parallel-text alignment)
    2. PDF, via the same LuaLaTeX pipeline
    3. An electronic book: one self-contained HTML file whose undecided passages are resolved on the reader's device

## Run the compiler

See
`uv run python -m opensiddur.exporter.compiler --help`

## Export to PDF

For TeX and PDF export, you'll need a TeX Live install with the LuaLaTeX
pipeline (`lualatex`, `bibtex`, `reledmac`, `reledpar`, `polyglossia`,
`biblatex`). The PDF stage runs `lualatex` and `bibtex` itself, as many passes
as reledmac needs; `latexmk` and `biber` are not used. On Debian/Ubuntu the installer script `install-tex.sh` covers it:

```bash
sudo bash opensiddur/exporter/tex/install-tex.sh
```

For round-trip command examples, see `scripts/tei-to-pdf.sh` — the same
`-s <settings-file>` flag drives both the compiler and the PDF stage, so any
typography settings in the YAML are forwarded to the LuaLaTeX preamble.

PDF page destinations use an independent shipout counter
(`hyperref`'s `hypertexnames=false`), so title leaves and restarted folios cannot
create duplicate page anchors. Printed page numbers and PDF page labels keep
their normal numbering. Contents entries, bookmarks and generated page references
link through their labels rather than reconstructing a destination from a folio.
The exporter does not generate alphabetical indexes using `\hyperpage`, which
requires the default folio-based destination names.
Generated destination names are internal to each PDF build; external links to old
named destinations need updating after regeneration. Viewer links using `#page=N`
continue to select physical PDF page N.

## Electronic books

An electronic book is one HTML file with its styles, scripts and data inline, so it opens
offline from wherever it is saved. A printed book has to settle every condition when it is
compiled. Whatever it cannot settle is printed with the rubric that says when to read it.
An electronic book leaves the settings a reader supplies to the reader: the rite, who is
present, a house of mourning, and so on. Its settings panel decides those passages on the
reader's device, and the text changes as the settings do.

Compile with `--destination electronic`, then render:

```bash
uv run python -m opensiddur.exporter.compiler -s SETTINGS --destination electronic -o book.xml
uv run python -m opensiddur.exporter.html.html book.xml book.html -s SETTINGS
```

or `python -m opensiddur.exporter.books --format html` for the books in the settings directory.

- `--destination electronic` withholds the reader's feature structures (every one not derived
  from the date, the time or the place; see `client_settings.py`) from the settings file's
  declarations and the static defaults, so their conditions stay undecided.
- Each undecided conditional records in `p:pinned` the values the compile did know for its
  condition: what the document declared there, and what was derived from it.
- The settings file's declarations become the book's defaults. Read without scripts, the
  page shows exactly what the PDF of the same settings file shows.
- Calendar settings are answered on the device: see below.

**The day.** The device works out the day as a compile does, from a date, a time and a place,
with the calendar's port (`html/assets/calendar.js`). The settings panel's *Day and place*
says how it knows the day:
- **Now,** the default unless the book says otherwise: the device's clock, read as the wall
  clock at the place. While the book
  is open it checks the clock every 20 seconds and when it comes back into view. When what the
  day decides changes, at dawn or at nightfall say, the text changes, and the passage on screen
  stays where it is (the first one below the toolbar, kept in place by `reader.js`).
- **A day and time the reader chooses.**
- **No particular day:** nothing is worked out, and the reader sets the kind of day by hand
  (the controls marked `when: no-date` in `basic_settings.yaml`).

**How a book starts** is its settings file's, in a section of its own for the electronic book,
`electronic` (`settings.ElectronicSettings`, documented in `doc/exporter-settings.example.yaml`):
`day: now | none`, and `columns: both | primary | parallel`. A haggadah, read ahead of the seder
as well as at it, starts with no particular day. `psalm_titles: uniform` gives every whole psalm
one bilingual heading in place of its edition's (`html/psalms.py`), for a book compiled from
editions that title psalms differently. The reader's own choices, once made, are
remembered and win; Clear all goes back to the book's.

The place is the reader's: a city from `html/places.yaml`, the device's location, or
coordinates with a time zone. The device reads the clock in that zone, and decides Israel by
it. The compiler decides Israel by looking the zone up from the coordinates, so the two agree
when the zone is the one the coordinates are in: a test holds every city to it, and the
device's location comes with the device's own zone. Until there is a place, nothing that needs
one is worked out: passages that turn on the day show every option, as in print. (The parsha is
worked out anyway: it needs only the date.) Choosing a place clears what was set by hand for
want of one: "Where" (`when: no-place`), and Israel in Advanced.

The book shows only what is appropriate for the day it works out:
- A section that declares what kind of day it is for -- a `j:declare` of
  `opensiddur:holiday-aggregate` features, as the weekday services declare that they are not
  Shabbat or yom tov -- is gated on that declaration (`day_gates.py`). On a day of another kind
  it is left out, so a reader never reaches a section whose settings contradict the date. With
  no date it is kept, as in print. The gate is judged against the day, not against what an
  enclosing text or the volume declares, which the section's declaration overrides.
- A reader who sets the day by hand to other than the date gives -- yom tov in Advanced on a
  weekday, say -- has said it is another day: the date is set aside, with everything it implies
  (the clock, a chosen day, the place), and the book follows the reader's settings alone. The
  status line says so. Clearing the setting brings the date back.

Everything worked out can be overridden in Advanced, as a declaration overrides a derivation in
a compile. The reader's settings, the place and a chosen day are kept in `localStorage`, under
the book's id. The clock's time is not.

The device resolves each condition against four layers, the earliest first: the device's
clock, the book's defaults, the reader's settings, and what the compile pinned
(`client_settings.LAYERS`). The calendar's derivations run over all four. The reference is
`client_settings.resolve`, which runs the compiler's own derivations over the same layers.
- A pinned value that no derivation reads is laid over what the other layers derive
  (`OSCal.READ_FEATURES`). Derived once, that serves most of a book.
- The compile pins, for each undecided condition, the features it reads, and where it reads
  anything derived, every feature a derivation reads (`derivation_graph.READ_FEATURES`, the
  same list as `OSCal.READ_FEATURES`). So a document's own date, service or minyan holds where
  it stands, whatever the clock says, and a place keeps its zone.

The settings panel has four parts:
- **Columns,** in a book with parallel text: both, or one language alone ("Hebrew only",
  "Translation only"). It is a display preference, not a setting the text turns on: it sets
  `data-columns` on the page, and `reader.css` hides the other column. A row whose shown column
  has no words (`col-empty`, marked by `html.xslt`) keeps the other, so no passage is lost.
  `html.py` `columns` names the columns by their languages.

**Rows off screen.** A row of parallel text is laid out only as it is reached
(`content-visibility: auto`), and until then is taken to have an estimated height. A row with no
text left to show would be taken to have that height too, and scrolling through a run of them
shows blank space that shrinks as it is reached. So:
- a row with no words at all (both columns `col-empty`) is always laid out;
- a row all of whose text the settings can hide is numbered (`markers.py` `_rows`,
  `BookConditions.rows`), and hidden whole once none of it shows, by the same rules on the
  device (`condition.js` `scopeCss`) and without scripts (`html.py` `scope_css`);
- the browser's own scroll anchoring is off: it anchored on rows still taking their heights,
  and pulled the page back as the reader scrolled. `reader.js` keeps the reader's place across
  what it changes, holding the rows around it laid out until the change settles.
- **Day and place,** in a book with passages that turn on the day (above).
- **The top:** the settings that decide the most of the book's text. The build decides which,
  for each book, and writes them into it.
- **An Advanced box,** holding every feature the book's conditions read, one by one.

The top settings are plain choices that set several features at once: where, the day of the
week, the kind of day, the service, the reading cycle and the rite. They are defined in
`html/basic_settings.yaml`, along with the words for single features. Each option sets only
what it is sure of. Options that would change nothing in a given book are left out of it.

A control or a single feature marked `top: true` in that file is at the top in every book that
has a use for it, however little of the text it decides: a reader looks for it there. A control
that sets such a feature is at the top in its place. The front-matter settings
(`opensiddur:paratext`) are marked so. They follow the ranked settings and do not count towards
the six.

The kinds of day are not written by hand. `html/kinds_of_day.py` defines each kind as a test on
what the compiler derives for a date ("Pesah, first day" is the dates on which `pesah` is 1). It
scans five years of the calendar, in Israel and outside it, and keeps only the features that
come out the same on every such date. So Rosh Hodesh leaves Hanukkah unset, because Rosh Hodesh
Tevet falls in Hanukkah, and an ordinary day leaves the omer unset.

The result is committed as `html/kinds_of_day.json`. After changing the kinds, or the calendar,
run `python -m opensiddur.exporter.html.kinds_of_day`; a test fails if the file is stale.

The reading cycle is the reader's in an electronic book, so the humash carries both cycles.

A page reference (`tei:ref type="page"`) becomes a link to the passage. The words around it come
from the source ("continued on page"), so the link shows a symbol, →, where print has the number:
the XSLT parameters `page-ref-text` and `page-ref-label` set it and its spoken label.
- The destination is chosen as for the PDF (`page_references.py`), and an optional reference
  whose passage the book leaves out is dropped, as in print.
- The reader's settings can hide the first occurrence of a destination. Every occurrence is
  labelled, and the link goes to the first one shown.
- An optional reference is hidden while no occurrence of its destination shows
  (`BookConditions.optional_references`).
- A required reference to a passage the settings hide stays, and goes nowhere.

The device's evaluator (`html/assets/condition.js`) is a port of the compiler's
(`condition_eval.py`, `client_settings.py`). The tests run the same corpus
(`opensiddur/tests/fixtures/condition_agreement/`) through both, the JavaScript under Node.
Without Node those tests are skipped, unless `OPENSIDDUR_REQUIRE_JS=1`, as CI sets it. Point
`OPENSIDDUR_NODE` at a Node binary that is not on the `PATH`. CI runs Node 24; to get the same
major version without installing Node, take the binary from the `nodejs-wheel` package:
```bash
export OPENSIDDUR_NODE=$(uvx --from 'nodejs-wheel>=24,<25' python -c \
    "import nodejs_wheel, os; print(os.path.join(os.path.dirname(nodejs_wheel.__file__), 'bin', 'node'))")
```
The path is inside the uv cache, so run this again after the cache is cleaned or pruned.

The calendar has a port too, `html/assets/calendar.js`: the derivations of `calendar/compute.py`
and the modules beside it, the derivation graph, and the settings stack they run on
(`derived_settings.py`). Given the same date, time and place, it derives what a compile does.
`test_calendar_agreement.py` runs both over sampled days, places, times and the moments either
side of each zman, and compares every derived value exactly. Set
`OPENSIDDUR_CALENDAR_SWEEP=full` to sweep every day of several years; it takes some minutes. A
change to the calendar derivations needs the same change in `calendar.js`.
- The Hebrew calendar and the weekly readings follow pyluach (MIT; its notice is in the file).
- The zmanim are NOAA's low-accuracy equations, with hdate's definitions of each zman. hdate
  uses astral instead when astral is installed, and a test fails if it is.
- Times are compared as the place's wall clock reads them, as the compiler compares them.
- The device gives the time zone with the place. It does not look up a zone from coordinates,
  as the compiler does with tzfpy.

## Released books

The books a release builds are settings files in
[`opensiddur-projects/settings/`](https://github.com/opensiddur/opensiddur-projects/tree/main/settings),
one subdirectory per book, named for the project it is built from, holding that book's variants:

```
settings/
  chumash-opensiddur-he/
    annual.yaml       # description: one parsha a week, the annual cycle
    triennial.yaml    # description: a third of each parsha, the triennial cycle
```

Each file names the root file it formats with a `book:` key and says how it differs from its
siblings with `description:` (below). On the first of each month, opensiddur-projects'
`release.yml` calls this repository's `.github/workflows/release-projects.yml`, which tags
opensiddur-projects with the date (`vYYYYMMDD`) and builds the books with the latest
opensiddur-processor release (see [RELEASE_PROCEDURE.md](../../RELEASE_PROCEDURE.md)). It lists them
(`books --list`, which leaves out a book whose `requires_processor:` that release
does not meet)
and starts a `release-book.yml` job for each, which builds that book in the formats its
`formats:` lists (below) and attaches them to the release as `<project>-<variant>-<tag>.html` and
`.pdf` (e.g. `chumash-opensiddur-he-annual-v20261201.pdf`).

To build them locally (after syncing the reference database):

```bash
uv run python -m opensiddur.exporter.books                  # all books, into ./books/
uv run python -m opensiddur.exporter.books chumash-opensiddur-he          # every variant of one book
uv run python -m opensiddur.exporter.books chumash-opensiddur-he/annual   # one variant
uv run python -m opensiddur.exporter.books --check          # validate only, build nothing
uv run python -m opensiddur.exporter.books --list           # names, as JSON: ["chumash-opensiddur-he/annual", ...]
uv run python -m opensiddur.exporter.books --format pdf     # only the printed books
uv run python -m opensiddur.exporter.books chumash-opensiddur-he/annual --formats  # its formats, as JSON
```

Each book is built in its own `formats:`. `--format` narrows that to one; a book that does not
list it is skipped, not failed.

A book that fails is reported and skipped and the rest are still built; the exit status is
nonzero if any failed. Each book's compiler and LaTeX output goes to
`<output>/<book>-<variant>.log`.

Pull requests to opensiddur-projects run `--check`, so a broken settings file fails there
rather than at release. It checks that each file:
- is in a book's subdirectory (`settings/<book>/<variant>.yaml`; a file anywhere else is an
  error, not silently left out of the release);
- parses, and matches the settings schema below, including `book:` and `requires_processor:`
  keys;
- names a project and file that exist;
- can be typeset on that machine: every font chain, the defaults included, has an installed
  font. Without fontconfig this is an error rather than skipped.

A processor that does not meet a book's `requires_processor:` fails its check. Between releases
`main` is the development of the next release, which meets a requirement of that release (see
[Settings file versioning](#settings-file-versioning)).

## Settings file

To control compilation, use a YAML-based settings file.
The settings are defined below:

### Description and book
```yaml
description: >
  One parsha a week, the annual cycle. The triennial variant beside it
  reads a third of each parsha.
book:
  project: chumash-opensiddur-he
  file_name: index.xml
  title: Humash   # optional
```
`description` is free text for people: what these settings make and why they differ from the
book's other variants. `book` is the root file the settings format. With a `book:`, the compiler needs only `-s`; `-p`/`-f`
still override it. Both the project and the file must exist. Optional, except in
`opensiddur-projects/settings/`, where every file is a book.

### Release formats
```yaml
formats: [html]
```
The forms `books` and the release build this book in: `html`, the electronic book, and `pdf`,
the printed one. Both, unless the settings say otherwise. A book whose reader chooses the day
on the device, and that is not wanted in print, lists only `html`. At least one, each once.

### Distribution notices
```yaml
distribution:
  notice:
    logo: art/our-logo.png   # relative to this file; `default` or `none`
    logo_width: 1in
    position: center
    text: [Distributed by Our Congregation, https://example.org]
  back_notice: none
```
Every book carries the Open Siddur Project's distribution notice, with its logo, and a statement
on disposing of sacred texts. Neither needs a setting. The notice is on the verso of the first
title page; a book with no title page, or whose title pages are not set, has it on a page of its
own at the start of the front matter. The electronic book has it after its title page. The
statement is on the last page, after the colophon. `back_notice` has an `electronic` and a
`print` version: the PDF takes `print`, the electronic book `electronic`. Either part can be
replaced, or set to `none`. In the PDF, `typography.styles.distribution_notice` and `back_notice` set
their type. `books --check` reports a logo that is not there. The example settings file
(`doc/exporter-settings.example.yaml`) gives the defaults in full.

### Transclusion priority
```yaml
priority:
  transclusion:
    - prj1
    - prj2
    - ...
```

When a file is transcluded by URN and a project is not specified, take the file from the URNs in this list of projects, in this order (first to last). For example, if I reference: `urn:x-opensiddur:text:bible:genesis/1/1`, and my transclusion priority is `tanakh-wlc-he`, then `tanakh-jps-1917-en`, the text will be derived from the WLC.

If no transclusion priority is specified, the project that owns the first file processed is used.

### Instructions priority
```yaml
  instructions:
    - prj1
    - prj2
    - ...
```

When instructional notes are given, take them from the given projects, in the given order instead of from the project being processed. 

### Annotation sources

```yaml
annotations:
  - prj1
  - prj2
  - ...
```

From which projects should notes (such as editorial notes or commentary) be derived?
Unlike instructions and transclusions, annotations are not in prioritized order; the annotations from all listed projects will be included when available.

### Printing annotations once

```yaml
print_once:
  commentary: true
  editorial: false
```

A note is set wherever its target is, so text that is transcluded more than once repeats its notes. Each flag
makes the notes of the same `@type` set only at the first occurrence of their target in the book. Both are
`false` by default. Instructions and citations belong to every occurrence of their text and cannot be listed.

This decides how often a note is set. Whether a note belongs in a given context at all is decided by the note's own
`j:condition` (see *Conditional notes* in `schema/JLPTEI-3.md`). A note that is out of context where its text first
appears is set at the first occurrence where it is in context.

### Parallel texts

```yaml
parallel:
  projects:
    - tanakh-jps-1917-en
  column_order: primary_first   # or primary_last
```

When the compiler builds a document, it also looks up matching content in
each of the listed `parallel` projects (by `corresp` URN) and emits
`p:parallel`/`p:parallelItem` blocks. The PDF stage feeds those blocks into
`reledpar` so the verses on each side stay aligned across page breaks, or, in
the `interleaved` layout, sets each block's translation directly after it.
A block with text on one side only (for example, Hebrew whose English
document carries only anchors for its notes) is set at the full page width
between column blocks, with any notes from the empty side attached to it.

`column_order: primary_first` puts the primary stream on the left page (or
left column for a `pairs` layout, or first in an `interleaved` one);
`primary_last` swaps them. The left page is the verso: for facing pages in a
book bound on the right, put the Hebrew on the right with `primary_last`.

### Typography

The `typography` section says how the exported document should look: paper and margins, fonts,
the size and weight of each kind of text, line spacing, line numbers, how notes are marked,
running heads. It is read by the PDF/TeX stage only; the linear-XML compiler ignores it.

**[`doc/typography.md`](../../doc/typography.md) is the full reference** — every key, its type,
its allowed values, its default and what it affects.

```yaml
typography:
  fonts:
    hebrew: ["Frank Ruehl CLM", "Ezra SIL", "SBL Hebrew", "FreeSerif"]  # tried in order
    latin: "Linux Libertine O"
  page:
    paper: letterpaper          # a4paper | letterpaper | legalpaper | a5paper | b5paper
                                # | executivepaper | custom
    base_font_size: 11pt        # 10pt | 11pt | 12pt
    sides: two                  # two | one
    margins: {inner: 1in, outer: 0.75in}
  paragraphs:
    line_spacing: 1.0           # 0.5-3.0
  styles:
    heading1: {size: xx-large, weight: bold, align: center}
    note: {size: 9pt}
  line_numbers:
    enabled: true
    increment: 5
  notes:
    placement: footnote         # footnote | endnote | none
    anchor: interlinear         # interlinear | superscript | inline
  parallel:
    layout: pairs               # pairs -> two columns/page; pages -> facing pages;
                                # interleaved -> each block followed by its translation
  table_of_contents:
    enabled: false
    depth: 4
  page_header: {}               # running heads; see doc/typography.md
  page_footer: {}
```

Every key is optional, and every default reproduces the output this exporter has always
produced — a settings file need only say what it wants changed.

Every key is also *checked*. An unknown key, a value outside a closed list, a malformed length
or a font chain with nothing installed is an error naming the offending path, raised before
anything is rendered, as is a setting the PDF stage would accept and do nothing with (an
`align` on a role set mid-line, say). A setting that was quietly dropped would leave a document
missing what was asked for with nothing to say why. The electronic book reflows and honours
only a few settings; `doc/typography.md` lists them.

Note that which text goes on which side of a parallel layout is `parallel.column_order` in the
compiler section above, not in `typography` — the compiler is what decides the order the
streams are emitted in.

## Settings file versioning
Note that this file is likely to change slightly in format as more output
formats are introduced.

A settings file can say which processor versions build its book:
```yaml
requires_processor: ">=0.7.0"
```
A PEP 440 requirement (`>=0.7.0`, `>=0.7,<0.9`). A processor that does not meet it refuses
the file, in the compiler, the output stages and `books --check`, instead of building a broken
book. The settings live in opensiddur-projects and the processor here, and a release pairs a
book with one processor: a book that needs a fix should say so. Between releases `main` is the
development of the next one (`0.7.0.dev0` after 0.6.0), which meets a requirement of that
release, so a book can require a fix as soon as it is merged.

Every book in `opensiddur-projects/settings/` must declare it (`books --check`). The monthly
book release builds with the latest processor release and leaves out (`books --list`) a book
whose requirement that release does not meet, until one does. The requirement is read before
the rest of the file is validated, since a book waiting for a newer processor usually uses a
key an older one does not know.
