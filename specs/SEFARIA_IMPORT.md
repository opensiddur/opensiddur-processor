# Importing from Sefaria

Sefaria (https://www.sefaria.org) publishes its library under open licences. This importer
converts Sefaria works into JLPTEI projects, a Hebrew and an English project for each work.
The first works are the five CC-BY Metsudah linear volumes of Rabbi Avrohom Davis
(Metsudah Publications):

| Sefaria title | volume | status |
|---|---|---|
| Weekday Siddur Sefard Linear | weekday siddur, 1981 | **pilot, imported** |
| Shabbat Siddur Sefard Linear | Shabbat siddur, 1981 | later |
| Machzor Rosh Hashanah Ashkenaz Linear | Rosh Hashanah machzor | later |
| Machzor Yom Kippur Ashkenaz Linear | Yom Kippur machzor | later |
| Selichot Nusach Lita Linear | Selichos, 1986 | later |

Issue: opensiddur-processor #307. Code: `opensiddur/importer/sefaria/`.

## The source

Sefaria exports its library monthly to the public bucket `gs://sefaria-export`, read over
HTTPS at `https://storage.googleapis.com/sefaria-export/`. The Sefaria-Export repository on
GitHub holds only `books.json`, the index of the bucket; the text left git in 2026, and the
old history is the read-only Sefaria-Export-Archive.

For each work the importer reads three files:

- `schemas/<Title>.json` — the index record. A liturgical work is a *complex text*: a tree of
  named sections (schema nodes, each with an English `key` and English and Hebrew titles)
  whose leaves are jagged arrays. The Metsudah leaves have depth 1 ("Paragraph"); Shabbat and
  Selichot have some of depth 2 ("Chapter", "Paragraph"), read as a leaf per chapter.
- The Hebrew and the English version files, `json/<categories>/<Title>/<Language>/<versionTitle>.json`:
  the same tree, its leaves arrays of strings. Never `merged.json`, which mixes in every other
  version (for Yom Kippur and Shabbat, a near-empty "Community Translation" with junk in it).

Sefaria's file names drop the colon a versionTitle may contain, so the URLs come from
`books.json`, never built by hand. The bucket keeps no old copies: each export overwrites its
files. The copy committed to `sourcetexts` is therefore the only pin there is.

**The linear layout.** Each string is one phrase — one line of the printed linear page — and
Hebrew segment *n* is translated by English segment *n*. An English rubric stands opposite an
empty Hebrew segment. The two versions mostly have the same number of segments per leaf; where
they do not, it is decided (see Align).

**Markup.** `<b>` (the opening words of a prayer; unpointed and whole, a heading), `<small>`
(Hebrew: a quieter line, a seasonal insertion, or an unpointed label; English: a rubric), `<i>`
(English: a transliterated word or a rubric), `<big>`, `<span>` (Hebrew inside English), `<br>`,
and footnotes, `<sup class="footnote-marker">` followed by `<i class="footnote">`, in the English
only. Seasonal and variant wording is in parentheses.

## Decisions

- **One project pair per work.** Each Sefaria work is a Hebrew and an English project,
  `<title>-davis-<date>-he|en` ([NAMING_SCHEME.md](NAMING_SCHEME.md)), even where two works
  share a printed source (Weekday and Shabbat share one NLI record).
- **Existing URNs first.** Above the phrase, every text reuses the collection's URN where the
  collection has the text (`prayer:`, `poem:`, `bible:`; places in the book are `siddur:`).
  Nothing is minted for a text the collection already names.
- **Phrases align through `metsudah:`.** See
  [SIDDUR_URN_SCHEME.md](SIDDUR_URN_SCHEME.md#metsudah--the-phrases-of-the-metsudah-linear-layout).
  The path is the enclosing text's, never a volume's, so the same phrase has one URN across
  the Metsudah volumes.
- **Functionally the same is the same.** A text or phrase that is functionally the same and
  mostly the same in wording keeps the same URN, across volumes and across rites (the
  siddurim are Sefard, the machzorim Ashkenaz). Matching is fuzzy, not exact.
- **Rite.** "Sefard" is Nusach Sefard (Nusach haAri), the Chassidic variant of the Ashkenazi
  rite — not the rite of the Sefaradim or Edot haMizrach. The project headers say so.
- **Licence.** Sefaria marks the Metsudah versions `CC-BY`, which Sefaria's own code maps to
  CC BY 3.0. The credit is to the publisher, Metsudah Publications, and the translator, with
  Sefaria acknowledged as the digitizer. A version whose licence changes is refused by the
  download until a decision is made.
- **Deterministic output.** The access date is the export date (`last_export.txt`), never the
  clock; an unchanged export rewrites nothing.

## Stages

### 1. Download (`download.py`)

```bash
uv run python -m opensiddur.importer.sefaria.download [--work KEY ...]
```

Writes `sourcetexts/sources/sefaria/<work>/`: `schema.json`, `he.json`, `en.json` (indented,
one segment to a line, so that a later export reads as a diff), `README.md` and
`manifest.json`. The manifest records each file's URL, the bucket's `md5Hash` and
`generation`, the sha256 as stored, the export date, and for every leaf its segment counts and
a hash of each version's segments. A file whose `md5Hash` is unchanged is not fetched again;
a run that fetches nothing writes nothing. The download checks the md5 of what it fetched,
the versionTitle, and that the licence is still `CC-BY`.

The works and everything that differs between them are in `works.yaml`.

### 2. Align (`align.py`)

Pairs each leaf's Hebrew and English segments:

- the same number of segments: one to one;
- **trailing extras**: the longer version's extra segments all at the end, every extra English
  segment a rubric, or at most three extra Hebrew segments — accepted and listed in the report
  (in the Weekday Siddur, 12 leaves: rubrics after the last Hebrew, and two leaves of
  untranslated Hebrew);
- otherwise a decision in `alignment_decisions.yaml`, naming by 1-based index the Hebrew with
  no English (`he_only`) and the English with no Hebrew (`en_only`), with the hashes of the
  leaf it was made for (`as_of`). A decision lapses when its leaf changes. An undecided
  mismatch is an error.

### 3. Texts and rubrics (`blocks.py`, `markup.py`)

A leaf is a stretch of the book, not one text. The book marks where each text begins — the
first words in bold, or a heading — so a leaf is divided into:

- **texts**: from one opening to the next. A bold opening continues the text before it when
  that text has only its heading, or when the segment before was printed whole in bold (the
  two lines of the Shema's first verse). An unpointed label in parentheses (`(פלוני/פלונית)`)
  is a placeholder inside the text;
- **rubrics between texts**, which belong to the book's running order;
- **headings** with no text before the next.

Pointing tells a heading from text that happens to be bold: Metsudah's headings (`<b>אבות</b>`)
are unpointed, its liturgy pointed.

### 4. URNs (`match.py`)

Each text's URN, in order of preference:

1. **The same text again.** A text this volume printed earlier is that text: one project
   carries a URN once. Printings are paired phrase by phrase (`map_phrases`, on consonant
   skeletons): the later printing is the text where half the earlier one's phrases are found
   in it without long gaps, and is cut where the earlier printing ends; an earlier printing that
   ran on past a later one is cut where the later one ends.
   - **A repeat** prints exactly the first printing's words, phrase for phrase, and transcludes
     it.
   - **A variant** is mostly the same with words of its own — a passage added (Nachem in
     Minchah's Boneh Yerushalayim on Tisha b'Av), left out, or worded otherwise. It keeps the
     text's URN, and the one text file holds every printing: the first printing's words, a
     phrase a variant leaves out conditional on that variant being false, and each variant's
     own words after the phrase they follow, conditional on it being true — `j:conditional`
     on `opensiddur:variant`, whose feature is the variant's condition URN,
     `urn:x-opensiddur:condition:<text path>/<variant>`, the variant named by the `siddur:`
     place that prints it (`…:prayer:amidah/yerushalayim/chol_minchah_shemoneh_esreh`). Each
     place that transcludes the text declares (`j:declare`) which of its variants it prints,
     so each compiles as its own printing; a transclusion elsewhere that declares nothing keeps
     every passage. A variant's own phrases are numbered after every number the text has used.
     A long passage of its own stands inside the text, rather than ending it, when the book
     introduces it with a rubric and the rest of the text follows it in order; and a passage
     that is a text the collection names (Nachem is Birnbaum's
     `amidah/nachem_hashem_eloheinu`) carries that text's URN, part by part, on
     `tei:milestone unit="prayer"`.
2. **An existing text.** The block's opening is looked up in the incipit index of the
   collection's Hebrew projects (`util/incipit.py`, shared with the opensiddur.org importer).
   The opensiddur.org imports and the Sefaria imports themselves are left out: their openings
   are formulas that match unrelated texts. Words are compared as consonant skeletons, a maqaf
   separating words. Every match must agree with the block over the candidate's whole collected
   opening (sixteen words), not just the key that found it: many texts open "יהי רצון מלפניך"
   and go on differently. The lookup goes in tiers, the first that finds a text winning:
   six words (a blessing only by the words after its formula, which every blessing shares);
   four words — for a blessing, two to five after the formula (פוקח עורים) — when one text
   agrees clearly best, which finds another rite's wording (Sefard וְלִתְפִלָּתָם, Ashkenaz
   וּבִתְפִלָּתָם); and the same a word or two out of step, past a label or heading word the
   collection's text opens with (`א אזה מקמן`, `ישתבח ישתבח`) or one the book's block lacks
   (`ואמונה`, its `אמת` ending the Shema). A match moves up to the whole text it is part of
   only when the whole is encoded, opens with it, and the block holds three quarters of the
   whole's other parts; otherwise it stays the part, and the block is cut where another part
   opens (the Kaddish divides into its parts this way), or where a text the index holds whole
   ends. A block is also cut before a blessing's formula in its middle: a new blessing is a
   text of its own. Scripture is kept as a text only as a whole chapter opened at its first
   verse; a block that opens mid-chapter (Hodu) is liturgy quoting scripture.
3. **A new text**, `prayer:` plus at least three words of its Hebrew incipit romanized
   (`util/transliterate.py`, the JLPTEI-3 table) and respelled by `specs/naming/spellings.yaml`
   — two words ("yehi_ratzon") would claim an opening many texts share; unpointed and
   parenthesized words (labels) are skipped, and a blessing is named after its formulas
   (`al_mitzvat_tzitzit`, not `barukh_attah`). Lengthened until it is not taken.

Every decision is recorded at once in `specs/sefaria/metsudah_urns.jsonl` — one line per text,
keyed by work, leaf and the Hebrew index of its first phrase, with its kind
(`existing`/`new`/`repeat`), incipit, evidence and a hash of its words (`as_of`). Records are
sticky: a reviewer may correct a URN in the file and rerun, and a rerun on an unchanged export
decides nothing. A cut is recorded by the record of the text after it, and replayed from it.
When a text's words change, its record lapses and is reported; the text keeps its URN (and its
phrases their numbers) when its opening still agrees, and is decided again otherwise.

Phrase numbers are 1, 2, 3… unless an earlier volume named the text's phrases: then the
record carries the numbers `map_phrases` gives (`phrases`).

### 5. Convert (`convert.py`, `tei_builder.py`)

```bash
uv run python -m opensiddur.importer.sefaria.convert [--work KEY ...] [--register]
```

Each language's project is laid out as the house style lays out a siddur:

- `index.xml`: the header with the full source bibl (the version's Sefaria page, its
  versionTitle as `idno type="sefaria"`, the export date as the access date, the md5s in the
  encoding note, the rite), and a `siddur:siddur` division transcluding the book's top-level
  parts.
- **structure files** `siddur_<path>.xml`, one per schema node, named by the node's `siddur:`
  URN from `structure/<work>.yaml` (every node must be placed): an inner node transcludes its
  children; a leaf has its heading, the rubrics between its texts, and a transclusion of each
  text.
- **text files**, one per text, named by its URN: a `tei:div` with that URN, the text's
  heading, and a `tei:milestone unit="phrase"` with its `metsudah:` URN before each phrase.
  Where a phrase opens a verse of scripture the collection encodes, a `tei:milestone
  unit="verse"` with the verse's `bible:` URN is set before it, and closed after the phrase that
  ends the verse (sof pasuq or colon) unless another verse follows — so a liturgical text that
  quotes scripture (the Six Remembrances, Hodu, Ashrei's psalms) reuses the verses' URNs, once
  in a project. A text's variants are merged into its file (see URNs).

| Sefaria markup | JLPTEI |
|---|---|
| bold | dropped (presentation) |
| unpointed bold or small Hebrew, whole segment, beside an English heading | `tei:head` |
| the same beside an English rubric or nothing | `tei:note type="instruction"` |
| English with no Hebrew | `tei:note type="instruction"`; printed whole in bold, `type="description"` |
| small pointed Hebrew | `tei:hi rend="small"` |
| `<small>לְר"ח:</small>` before the words it governs | `tei:note type="instruction"` |
| English italic | `tei:hi rend="italic"` |
| `<big>` | `tei:hi rend="large"` |
| `<span>` | `tei:foreign xml:lang="he"` |
| `<br>` | a space |
| footnote | `tei:anchor` + `tei:note type="commentary"` in `tei:standOff type="notes"` |

Every file is validated (RelaxNG and Schematron) before it is written; a file an earlier run
wrote that this run does not is removed. `--register` appends the new URNs — minted texts and
`siddur:` places with their parents — to `specs/urn_registry/`. The run's report,
`output/sefaria_<work>_report.md`, lists the leaves aligned by the trailing rule, the URNs
decided and the decisions that lapsed.

Book settings: `settings/<he project>/linear.yaml` in opensiddur-projects sets the English
beside the Hebrew.

### 6. Monthly update (`update.py`)

```bash
uv run python -m opensiddur.importer.sefaria.update [--work KEY ...] [--no-download]
```

Run after the monthly export (on the 2nd or later), with the `sourcetexts` checkout at its
latest commit. It downloads, then compares each leaf of the new manifest with the one
`sourcetexts` last committed:

| class | meaning | action |
|---|---|---|
| unchanged | same segments | nothing |
| text-changed | different words, same segment counts | reconverted; its texts' records lapse and are re-decided, phrase numbers kept |
| resegmented | a version's segment count changed | reported; the alignment decision and phrase numbers are reviewed before converting |
| added / removed | the schema gained or lost a leaf | reported; the structure table must place it |
| metadata | a version's title, licence or URL changed | reported; a licence change is decided before converting |

With nothing to review, the work is converted with `--register`. The report,
`output/sefaria_update_<date>.md`, becomes the description of the run's paired pull requests
(sourcetexts, processor for decision files and registry lines, projects).

## Later work

- The other four volumes: a `works.yaml` entry and a structure table each; their phrases
  reuse the Weekday Siddur's numbers where the text is shared.
- **Conditions on the calendar.** A variant is selected by where it is printed, not yet by
  the day: Nachem is printed at Minchah, conditional on that place, not on Tisha b'Av.
  Seasonal insertions are marked in the book (`<small>לְר"ח:</small>`, "On
  Chanukah:", "Ten Days of Penitence") and are text, with their rubric, in the pilot. They are
  to become `j:conditional` — `type="marked"` where the book marks them
  (see `schema/JLPTEI-3.md`, conditional presentation) — and the index's services gated by
  occasion as Birnbaum's are.
- Kaddish responses and the reader's and congregation's parts as speaker roles
  (`instruction:role/…`).
- Sefaria's `links/` (citations from the footnotes to Tanakh and Talmud) as `bible_hint`s for
  matching, and as `tei:bibl`/`tei:ref` on quotations.

## Open questions

- The project titles of the later volumes, from their title pages.
