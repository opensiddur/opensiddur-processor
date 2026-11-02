# Importing prayers from opensiddur.org

opensiddur.org is a WordPress site of about 4,100 posts. Roughly 3,250 are under
"Prayers & Praxes". Most are under a free licence and set the source text, a translation
and sometimes a transliteration side by side. This importer turns the prayers whose text
is on the site into JLPTEI projects, and keeps them current as the site changes
(issue #186). The code is in `opensiddur/importer/opensiddur_org/`; each module's docstring
says what it does.

## The source: the monthly GitHub export

The whole site is exported at the start of each month to
<https://github.com/aharonium/opensiddur.org>. The importer reads that export, never the
live site. The export is cloned as a sister repository of `opensiddur-ai` and
`sourcetexts`, at `opensiddur-repos/opensiddur.org/`. It is a plain clone with no
worktrees, because we never branch it.

What the export holds:

- `posts/<permalink category path>/<slug>_(<post_id>).json`, one file per post. The fields
  are `post_id, title, author, coauthors, date, last_updated, excerpt, content, categories,
  tags, custom_fields, featured_image, source_link, permalink, slug`.
  - `content` is the rendered HTML, the same markup the `feinstein_haggadah` importer
    already reads.
  - `custom_fields` carries the licence (`open_content_license`, an HTML `<a>`),
    `languages_meta`/`scripts_meta` (ISO 639-3 and ISO 15924 codes) and
    `date_src_start`/`date_src_end`. Those are the date range of the original work, and a
    part may be zero (`1440-00-00`).
- `categories and tags/categories.json`: categories with their `parent_id` and `post_ids`.
- `contributors/contributors_by_id.json`. Every WordPress user has an `author_slug`, a
  `display_name`, a `role_label`, `sibling_ids` and a `status`.
  - One person often has several users, one per role: "Isaac Gantwerk Mayer",
    "Isaac Gantwerk Mayer (translation)", "Isaac Gantwerk Mayer (transcription & naqdanut)".
    `sibling_ids` ties them together.
  - The site also keeps `inactive` profiles for people who never used it, mostly the
    translators of the printed books it transcribes.
- `posts/posts.json` and `tags.json` are not needed: a coauthor's `profile_link` names their
  user directly, and a post carries its own tags.
- No media. Uploads appear only as `https://opensiddur.org/wp-content/uploads/...` URLs.

How the export changes:

- Diffs are noisy. A bulk re-save on the site rewrites `last_updated` in thousands of files.
- A post that moves category is deleted at its old path and added at a new one, with the
  same `_(ID)`.
- A deleted post simply disappears.

## Decisions

- **One project per post and language**, named `<title>-<author>-<date>-<lang>` by
  `specs/NAMING_SCHEME.md` (`maoz_tsur-mordekhai-1240-he-latn`). The post ID is recorded in
  each project's `index.xml`, which is how a post's projects are found again; a retitled post's
  project is renamed. The text file is named from the post's URN.
- **Source-only posts are one project.** An empty "Contribute a translation" column is
  dropped silently. If that column has text, it usually holds the original of quoted
  verses, so it is imported as a source column.
- **Transliteration columns are their own projects**, e.g. `maoz_tsur-mordekhai-1240-he-latn`.
  - On the site they are written by hand and follow no single scheme.
  - Some are historical sources in their own right, such as Leo Wiener's 1898
    romanization of Yiddish.
  - So they are imported as written, not regenerated.
- **`span.divine-referent` becomes `j:divineName` in every language**, not only Hebrew.
- **Acrostics are semantic, not typographic.** `span.acrostic` becomes
  `<tei:seg type="acrostic">`, alongside `seg type="refrain"` (`schema/JLPTEI-3.md`).
- **Existing URNs come first.** A post that is a version of a text already in the
  collection uses that text's URNs: a psalm, Maoz Tsur, the Ḥanukkah blessings. See
  [URNs](#urns).
- **`last_updated` decides whether a post needs refreshing.** A post whose `last_updated`
  matches the manifest is not rewritten.
- **Licences are decided once, per column.** See [Licences](#licences).
- **Only people who made the digital text get a contributor URN.** See [Credits](#credits).
- **Output is deterministic.** The same input gives byte-identical TEI. The access date
  recorded in the TEI is the upstream commit date, not the clock.
- **A post is cited by its post ID.** The source bibliography links to
  `https://opensiddur.org/?p=<post_id>`, which WordPress redirects to the post wherever it is
  filed, so the bibliography of an edition always leads back to the right page. The permalink
  is not kept: it changes whenever the post moves category. See [Header](#3-convert-tei_builderpy-convertpy).
- **What the post says about itself is a colophon, not front matter of the source.** See
  [The post's own words](#the-posts-own-words-colophon).

## Stages

### 1. Download (`download.py`)

1. Clone the upstream if it is missing, otherwise fetch it.
2. Read files at `--ref` (default `origin/master`) with `git show`, so whatever is checked
   out is never touched.
3. Write `sourcetexts/sources/opensiddur_org/`:
   - `posts/<post_id>.json`: in-scope posts, copied verbatim and stored flat by ID, so a
     category move changes no path here.
   - `categories.json` and `contributors_by_id.json`.
   - `manifest.json`: the upstream repository, commit and commit date, and the categories
     selected. Per post it records the upstream path, `last_updated` and a sha256.
4. Rewrite a post only when its `last_updated` changed. A run at an unchanged upstream
   commit, with the same selection, writes nothing.
5. `--category ID` restricts which posts are copied. The selection is remembered, and
   posts no longer selected or in scope are removed.

### 2. Scope and triage (`parse_post.py`, `languages.py`, `scope.py`, `survey.py`)

**A post is in scope** when it passes both tests:

- **Category:** it is in category 1132 ("Prayers & Praxes") or a descendant.
- **Content:** it carries prayer text the site itself sets. That means a
  `table.toggleable-table` with text in a column, or a body of `div[lang]` blocks.

**Out of scope**, with the reason recorded:

- `list-of-*` index posts and essays.
- Posts whose substance is a file link (`a.mtli_*`) or an embed.

**The parser** (`lxml.html`, XPath) strips `<script>`, `<style>` and the iframe plugin's
boilerplate. It reads:

- **Columns:** each `<th>` names a role and a language, e.g. "Source (Hebrew)" or
  "Transliteration (romanized Hebrew)".
  - Roles are matched forgivingly, because the site has typos such as "Souce" and
    "Tranlsation".
  - When the `<th>` and the `div@lang` name different languages, the rules in
    [Columns the converter resolves](#columns-the-converter-resolves) decide which is right.
  - They may differ only in precision and still agree: "Aramaic" over `jpa-Hebr`, or a
    transliteration whose markup leaves out the Latin script.
- **Rows:** one `<tr>` per stanza or block. Lines are split on `<br>`, and a line holding
  only `&nbsp;` marks a stanza gap. A cell of `<p>`s is prose. A row whose every cell is a
  heading opens a section.
- **Spans:** `divine-referent`, `instruction`, `acrostic`, `citation`, and emphasis.
- **Footnotes:** taken from the plugin's inline tooltip, numbered through the post.
- **Sources:** the `<h3>Source(s)</h3>` captions and links, recorded but never downloaded.
- **Intro and notes:** the paragraphs before and after the table. They are the post's own
  words, not the source's; see [The post's own words](#the-posts-own-words-colophon).

Languages are mapped from ISO 639-3/15924 to BCP 47 (`heb-Hebr` → `he`,
`yid-Latn` → `yi-Latn`, `lad-Hebr` → `lad`).

**Each in-scope post is classified** as `standard` or `irregular:<reasons>`. The reasons
are:

- a `<th>`/`lang` disagreement
- an unknown role or language
- colour-coded word alignment
- more than one table
- prose with no table
- verse and prose mixed in one column
- a heading inside a cell of text
- two columns in the same language
- an unregistered contributor
- no URN decision, or an existing URN with unmapped rows

#### Columns the converter resolves

These rules were decided on 2026-11-01, from the survey of all of category 1132. A post that
one of them settles is not irregular for that reason.

- **When the header and the markup disagree on a language:**
  1. If the markup is a WordPress default (`heb`, `eng`), the header wins. The Kaddish's
     "Source (Aramaic)" is often marked `heb-Hebr`, and Romanian or German columns `eng-Latn`.
  2. If the header names a Jewish variety of the markup's language, the header wins, because
     it is the more specific: "Ladino" over `spa-Latn`, "Judeo-Italian" over `ita`.
  3. Otherwise the markup wins. A "Source (Hebrew)" column marked `yid-Hebr`, `fra-Latn` or
     `ara-Arab` holds Yiddish, French or Arabic, and an "Arabic" column marked `jye` is
     Judeo-Yemeni Arabic.
  4. Posts these rules get wrong are listed in `post_decisions.yaml`: the header wins in
     62205 (`arc`, not `txb-Hebr`) and 64855 (`en`, not `mr`). In 36267, rule 2 already
     reads "Romanization (Yiddish)" over `deu-Latn` as `yi-Latn`.
- **A transliteration header that names no language**, such as "Transliteration
  (Romanization)", takes the source column's language with `-Latn`.
- **"Hebraization (X)"** is a transliteration into Hebrew letters: `<X>-Hebr`.
- **Two columns in one language but different scripts** get script subtags, e.g.
  "Bukhori/Cyrillic" and "Bukhori/Judeo-Tajik" become `bhh-Cyrl` and `bhh-Hebr`.
- **Two or more columns in the same language and script are each their own project**, aligned
  by the same row milestones. This covers translations from different dates or translators,
  literal and singable versions, a source and its adaptation, and masculine and feminine
  god-language. The first column in a language has the plain name; each later one adds a
  variant before the language, drawn from its header (`1852`, `literal`, `adaptation`), or its
  column number when the header says nothing more. Like a title, the variant follows the
  header, so editing the header renames the project.
- **"Initials", "Acrostic Initials" and "Acrostic" columns are dropped.** Their letters are marked in the
  source text as `seg type="acrostic"` where a line begins with the stanza's initial.
- **"Commentary" and "Description" columns become notes** on their row in the project of the
  column they sit beside (the nearest column with text to the left, else to the right): a
  commentary as `note type="commentary"` after the row's text, a description as
  `note type="description"` before it (see "Kinds of rubric" in `schema/JLPTEI-3.md`).
- **A table with no column headers** takes each column's role from the column in the same
  language of another table in the post; where there is none, the Hebrew column is the source
  and the others are translations.
- **Coloured text means what the post's introduction says it means**, so each colour of each
  colour-coded post is given a meaning, recorded in `post_decisions.yaml` (decided
  2026-11-01):

  | The colour marks (meaning) | Encoding |
  |---|---|
  | the author's amendment of, or addition to, an older prayer (`amendment`) | `j:conditional type="marked"` on the `opensiddur:variant` feature `urn:x-opensiddur:condition:<text URN's path>/amended`, true; a word it replaces (`green \| original`, 19667) is wrapped in the same condition, false |
  | alternative wordings (`alternative <name>`) | the same, one variant `…/<name>` per alternative; `male`/`female` test `opensiddur:person` `gender`, and a rite's name tests `opensiddur:rite` |
  | the melody to read in (`cantillation <melody>`) | `seg type="cantillation" subtype="<melody>"` |
  | words in another language (`language <lang>`) | `seg xml:lang="<lang>"` |
  | a quoted verse (`quotation`) | `seg type="quotation"` |
  | words supplied to fill a gap (`supplied <who>`) | `seg type="supplied" subtype="<who>"` |
  | a ketiv beside its qere (`ketiv`, 67262) | `tei:choice` with `j:written`, and the word before it as `j:read` |
  | a ketiv before its qere (`ketiv first`, 1548, 1769, 2657, 28690) | the same, with the word after it, or the span coloured `qere`, as `j:read` |
  | acrostic letters (`acrostic`, 52874) | `seg type="acrostic"` |
  | text the site hides in white (`hidden`, 38069: instructions to destroy a place or kill a person) | kept, in a condition on the variant `…/concealed`; a setting that makes it false leaves it out |
  | emphasis only (`none`, 21219, 38595) | the colour is dropped |

  A cell set in a colour has each of its lines coloured; `<font color>` is a colour too. JLPTEI's quotation, supplied and
  cantillation `seg` types are documented in `schema/JLPTEI-3.md`.

  A condition's default cannot be written into the text: a declaration in the text would
  override the settings file, and nothing could choose the original. So when no setting
  chooses, both readings stand, set off as any undecided passage is. A settings file chooses
  by setting the variant (or the rite, or the gender).
- **A post with no table** is read from its `div[lang]` blocks:
  - When they are all in one language, the post is one project and each block is a row, as
    in a one-column table.
  - When they alternate languages (Hebrew, English, Hebrew, English…), each consecutive pair
    is one aligned row, as in a two-column table. An empty block still holds its place.
    Blocks that do not alternate cleanly leave the post irregular, to be decided one by one.
  - **A post that sets its text outside the site's toggleable tables** is described by a
    `layouts` decision in `post_decisions.yaml`: XPaths to the elements holding its text, in
    order (a `table`, or a `div[lang]` that becomes a one-column table). Before the first is
    the introduction and after the last the notes, as with a table. A layout may also:
    - name a table holding the introduction in several languages, a column each; each
      language's introduction goes in the project of that language (11906);
    - split a column whose cells hold several parts (the text before the first paragraph,
      then each `p`) into a column per part, under headers it gives, so the header rules read
      their roles; `null` drops a part (11906: number, explanation, translation,
      transliteration);
    - make what follows the text a source rather than notes, when it credits where the text
      was first published (14515);
    - transclude, where it stands in the notes, a passage the post quotes from a text already
      in the collection, rather than copying it: a book sets it from the edition it prefers,
      and the post's authors are not credited with it (3778's Micah 7:19).
  - Text before the first block and after the last is the post's own words, as with a table.
  - A post with text between its blocks may be an essay about the prayers it quotes, such as
    1769 (Tikkun Ḥatsot); which posts are essays is decided one by one (`essays` in
    `post_decisions.yaml`). Each top-level element holding `div[lang]` blocks (a blockquote) is
    one quoted passage: a row of a table with a column per language, the text
    `<post URN>/quoted`, in every language's project. The essay's paragraphs are the post's
    text, `<post URN>`, in the project of its own language, transcluding `<post URN>/quoted/<k>`
    where passage *k* stands. That project's index transcludes the essay; the others' the
    passages. What follows the last rule (`<hr>`) is the post's own words. An essay is always
    given new URNs, whatever its passages quote.
  - Art and essays that quote no prayer text are out of scope: 3393, 55035 and 56696
    (shiviti and illustrations), 12374 (a periodic table of the aleph-bet), 25888
    (pedagogy), 12754 (a reflection) and 56027 (a role-playing activity).
- **Verse and prose in one column, a heading inside a cell, and more than one table** are
  encoded as [Body](#3-convert-tei_builderpy-convertpy) describes, and are no longer reasons
  a post is irregular.

**`survey`** writes `output/opensiddur_org_triage.{json,md}`, which is untracked. It gives
counts by irregularity, language set, licence and category; the licences awaiting a
decision; and the URN proposals.

### 3. Convert (`tei_builder.py`, `convert.py`)

**Header**

- **Titles:** split from the `Hebrew | English` title. A part in Hebrew letters is taken as
  Hebrew, one in Latin letters as English, and one in another script is tagged by script
  only (`und-Arab`). The title in the project's language is `main`; the others are `alt`.
- **Licence:** from `licence_decisions.yaml`. An allowed licence that is not the post's own
  says why, as a `tei:p` in `tei:availability`.
- **Credits:** see [Credits](#credits).
- **`sourceDesc/bibl xml:id="project_source_bibl"`:**
  - the titles and the original authors
  - opensiddur.org as distributor
  - the date of the original
  - the upstream commit date as the access date
  - `<tei:idno type="url">https://opensiddur.org/?p=<post_id></tei:idno>`, the export's
    `source_link`, as the **first** `idno type="url"`. The exporter's bibliography links each
    entry to its first URL (`exporter/metadata.py`, `_url`), and a link by post ID still
    reaches the post after it moves category, where the permalink would not.
  - `<tei:idno type="opensiddur.org">` with the post ID
  - the Source(s) captions and links
  - the upstream commit, in an encoding note

**Body**

- The post is one `tei:div`, whose `corresp` is the post's URN, headed by its title in the
  project's language.
- Each row opens a `tei:milestone` (`unit="stanza"`, or `"paragraph"` for prose) whose
  `corresp` is the same in every language. That is what aligns the parallel texts.
- Line cells become `lg`/`l`; prose cells become `p`. A column may mix the two: each row's
  cell keeps its own form, side by side in the same `div`, with the row milestones between
  them.
- A heading inside a cell closes the current `tei:div` of that column's project and opens a
  new one headed by it. Row milestones are unaffected, so the languages stay aligned.
- A post with more than one table holds that many texts. Each table is its own file, with its
  own URN, in the same project, and the project's `index.xml` transcludes them in order.
  - A column belongs to the project of the column in an earlier table with the same language,
    role and header words. Another work in that language (a different translation, or the
    source where an earlier table had a translation) is a project of its own, named by a
    variant, so that its credits and licence are its own.
  - Each table is matched on its rows alone: the post's title names the post, not every table
    (4957, "Psalms 67 and Ana b'Khoach"). Two tables never share a text's URN.
- A cell in another language than its column (Aramaic in a Hebrew column) carries
  `xml:lang`.
- Spans and notes map as follows:

| Source | JLPTEI |
|---|---|
| `instruction` | `tei:note type="instruction"` |
| `divine-referent` | `j:divineName` |
| `acrostic` | `tei:seg type="acrostic"` |
| `citation` | `tei:bibl` |
| `em`, `strong`, `sup` | `tei:hi rend="italic"`, `"bold"`, `"superscript"` |
| footnotes | `tei:anchor` plus `tei:standOff type="notes"` |
| intro and notes | `tei:div type="colophon"` in the index's `tei:front`, gated on `opensiddur:paratext` |

- The intro and notes go in the project whose language they are written in: for Latin
  letters English if the post has it, else another Latin-script language, else the first.
  See [The post's own words](#the-posts-own-words-colophon).
- The footnote plugin's own list of notes after the post is dropped; notes are read from
  their tooltips.
- The index's body transcludes the text by its URN.

**Validation and pruning**

- Every file is validated before it is written.
- Stale files are pruned, and so are the projects of languages the post no longer has, but
  only for the posts being converted. A post rejected outright loses the projects an earlier
  run wrote; any other post that is no longer converted keeps them, with a warning.
- Then each project's URN and contributor references are checked.
- `--register` appends the registry records a new post's URNs need, after the post
  converts: the post, and each row with text in an imported column.

### The post's own words (colophon)

A post says things about the text it publishes that are not part of that text, and that no
JSON field holds apart: they are in `content`, in the paragraphs before and after the table
(set off from it by `<hr />`), and `excerpt` usually repeats the first of them. Typical
examples:

- where the text was first published ("first published in *The Union Prayerbook*, CCAR,
  1918, on page 110");
- who transcribed or translated it, and from what;
- what the transcriber changed ("I have replaced 'Adonai' with 'YHVH.' –Aharon Varady");
- an introduction to the text by the person who posted it.

This is colophon material about the digital edition, so it is front matter of a different
kind from front matter the source itself printed (a book's own preface, a translator's note
in the original edition). It is encoded so that the two can be told apart:

```xml
<tei:front>
  <j:conditional xml:id="..._introduction">
    <tei:fs type="opensiddur:paratext"><tei:f name="include"><tei:binary value="true"/></tei:f></tei:fs>
  </j:conditional>
  <tei:div type="colophon" subtype="introduction">
    <tei:p>...</tei:p>
  </tei:div>
  <j:endConditional target="#..._introduction"/>
  <!-- the same for the notes after the table, subtype="notes" -->
</tei:front>
```

- `type="colophon"` marks the post's own words; `subtype` says whether they came before the
  table (`introduction`) or after it (`notes`).
- Front matter that belongs to the source, if a post ever carries any, keeps an ordinary
  `tei:div` type (`preface`, `introduction`) without `colophon`. A post sets the source's
  own text in its table, so the importer does not produce it today.
- Like all paratext, the colophon is gated on `opensiddur:paratext/include`.
- `excerpt` is not imported, because it repeats the introduction.
- The exporter builds its own colophon (the logo and links) from the headers
  (`exporter/metadata.py`). A book that has `type="colophon"` divisions sets them **after**
  that colophon, not where they stand in the front matter, in both the PDF and the HTML
  outputs (decided 2026-10-29). They are still subject to the paratext gate.

### Licences

`licence_decisions.yaml` maps each licence URL the site uses to a decision:

- **Allowed:** the six JLPTEI licences (CC0, PD Mark, CC BY 3.0/4.0, CC BY-SA 3.0/4.0).
- **Allowed as the PD Mark**, with the basis recorded:
  - United States Government works (17 U.S.C. §105)
  - edicts of government (Compendium II §206.01)
- **Fair use (§107) and library reproduction (§108)** are not licences. A source column
  whose original was published before 1931 is clearly in the public domain and gets the PD
  Mark. Every other column of such a post, translations of public-domain originals
  included, waits for a decision about that post.
- **Anything else, and no licence at all,** is undecided until the maintainer decides. The
  decision is recorded in the YAML's `posts`, for the whole post or for some of its
  columns. A column can also be **held** while permission is sought; it is skipped like an
  undecided one, and reported as held.
- **No decision about a post is permanent.** Each records the post's `last_updated` and
  licence when it was made (`as_of`, `licence`). When a later export updates or relicenses
  the post, the decision lapses and the post is decided again. The export of 2026-11-02, for
  example, relicensed 53593 (rejected in the pilot as fair use) CC BY-SA 4.0.

`convert` imports allowed columns, skips rejected ones, and reports undecided ones.

### Credits

- **A coauthor with a role who uses the site** made the digital text. That means their
  account, or one of its siblings, is `active`. They get a `tei:respStmt`:
  - translation → `trl`, on translation columns
  - transcription or naqdanut → `trc`, on source and transliteration columns
  - The name `ref` is `urn:x-opensiddur:contributor:opensiddur.org/<slug of the person's
    user with no role>`.
- **A coauthor with a role and only an inactive profile** is credited in the source bibl,
  with a `respStmt` and no URN. An `opensiddur.org` URN claims that the person contributed
  to the Open Siddur.
- **A coauthor without a role, or with a death date,** is an original author, a
  `tei:author` in the bibl.
- **"Unknown" and "Anonymous"** are credited with nothing.
- **New contributors are registered by hand.** `convert --emit-contributor-candidates`
  writes candidate `contributor.jsonl` lines to `output/`; they are reviewed in the
  opensiddur-ai pull request.

### URNs

Each post's URN decision is made once. It is recorded in
`specs/opensiddur_org/post_urns.jsonl` as one of:

```json
{"post_id": 12322, "kind": "existing", "urn": "urn:x-opensiddur:text:poem:maoz_tzur", "rows": {"1": "urn:x-opensiddur:text:poem:maoz_tzur/1", "...": "..."}}
{"post_id": 41025, "kind": "new", "urn": "urn:x-opensiddur:text:prayer:the_blessings_over_kindling_the_light_of_chanukah", "rows": {"1": "urn:x-opensiddur:text:prayer:hadlaqat_ner_chanukah/blessing"}}
{"post_id": 22916, "kind": "new", "urn": "urn:x-opensiddur:text:poem:banu_choshekh_leqaddesh_seidenberg"}
```

- An `existing` post is, as a whole, a version of a text in the collection: a translation,
  including an interpretive one, or an adaptation. It takes that text's URN and has no URN of
  its own.
  - Rows that map carry the existing part URNs.
  - Where the version departs from the original (verses merged, a passage rewritten, a stanza
    added), the first departing row's milestone corresponds to the span of the original the
    run stands in for, as a range (`…:bible:psalms/29/3-6`), and the rest of the run carries
    no milestone of its own. Added material gets a milestone with no `corresp`, which only
    ends the scope before it. `match` records each departing row's span in `spans`.
  - So everything stays aligned and no URN is minted. The departing text is an alternative to
    the original's: an edition that wants it gives the post's project priority as a source
    for the transclusion. (A transclusion can only target a URN, which is why a departure is
    not a file of its own.)
  - Such a post is not marked with `opensiddur:variant`: the version is the work itself.
    `opensiddur:variant` is for posts that draw attention to an amendment (see the colours,
    under [Columns the converter resolves](#columns-the-converter-resolves)).
- A `new` post's rows are `<urn>/<n>`, numbered from 1 over rows that are not headings,
  except where `rows` names an existing text. A post that includes an existing text among
  other material, like the Ḥanukkah blessings, is new as a whole: it keeps its own URN and row
  milestones, and corresponds to the existing text where it includes it.

**`match`** proposes existing URNs. It works from an index of the opening words of every
`@corresp` scope in the collection's Hebrew projects (prayers, poems and the Bible, never
`siddur:` positions).

- The index is cached in `output/`.
- Words are compared as consonant skeletons, with every spelling of the divine name made
  one and with internal ו and י dropped, so that full and defective spellings agree.
- A blessing is told apart by the words after its formula.
- When a lookup finds several candidates:
  - a part is preferred over the text it opens;
  - otherwise the candidate whose opening agrees with the row the longest is chosen;
  - otherwise the work that the unambiguous rows point into decides.
- A row that runs on into the next unit of its text is left unmapped, because one milestone
  cannot stand for two units.
- A URN is never given to two rows of one post.
- A slug or title naming a psalm restricts candidates to that chapter.
- The post's title is compared with the registry's labels.

How `match` handles each post:

- A post with no candidate at all is given a new URN at once, `text:poem:<name>` for a post
  tagged as a piyyut or poem and `text:prayer:<name>` otherwise.
  - `<name>` is the post's title, as `specs/NAMING_SCHEME.md` names a project's: its Latin
    part up to the attribution, folded to ASCII. Its Hebrew prefixes are first joined to
    their words as the table writes them: a letter whose shva the romanization elides with an
    apostrophe, or a prefix letter with a hyphen, takes its `e` ("l’Garesh" is `legaresh`,
    "Y’qar" `yeqar`, "l-Tsur" `letzur`), and the article "ha-" joins its word. Each word is
    then respelled by `specs/naming/spellings.yaml`, a prefixed word by its word, since a URN
    follows the transliteration table where a project title keeps the post's own romanization
    (`maoz_tzur_…`, not `maoz_tsur_…`). A
    name cut at 60 characters does not end on a word like "of" or "the". The original
    author's name follows, as the project's author field gives it, or as the title's "by"
    gives it when no one else is credited (`chanukah_wise`, `rock_of_ages_gottheil`), since a
    new text on the site is someone's. It is respelled by the list like the rest (Yaaqov ibn
    Tsur gives `_tzur`); the person's own spelling stays in the label and the credits. The
    slug is not used: the bibliography's link still leads to the post on the site. A name is
    kept once given (`specs/opensiddur_org/post_urns.jsonl`), so a rule changed later renames
    an older post's text only when that file is respelled with it.
  - If that name is taken, `_<post_id>` is appended.
- Every other post gets a proposal in `output/opensiddur_org_urn_proposals.jsonl`.
  - A proposal is accepted without review when the slug or title names the text (a psalm, a
    registry label) or at least half its rows map. A sample of the accepted proposals is
    listed in the pull request.
  - A proposal with neither gives the post a new URN.
  - Rows of a new post that resemble an existing text are ignored: a shared opening phrase is
    not enough, and a false correspondence is worse than a missing one.
  - A proposal can still be reviewed and edited, then recorded with `match --accept <id>`, or
    replaced by a new URN with `--new <id>`.

### 4. Pilot: Ḥanukkah (category 183)

83 in-scope posts at upstream commit `2420d574f2` (2026-10-01).

- **68 converted**, into 128 projects: Hebrew, English, German, Yiddish, French, Ukrainian
  and Ladino (in Hebrew and Cyrillic letters), with seven transliterations.
- **URNs:** 13 proposals accepted (one with corrections) and one replaced by a new URN.
  - Six versions of Maoz Tsur use its stanzas.
  - The candle-lighting posts share `hadlaqat_ner_chanukah/blessing`, `sheasah_nissim` and
    `shehecheyanu`.
  - A qerovah for the Ḥanukkah Amidah shares the Amidah's blessings.
- **Contributors:** 13 registered.
- **Licences decided** in `licence_decisions.yaml`: posts 34548 (the Hebrew only), 47938
  and 53593.
- **Checks:** every file validated; `urn_registry --check` has no errors; every URN
  reference resolves; re-conversion is byte-identical.
- **Rendering:** parallel PDFs of 12322 (Maoz Tsur, including its `he-Latn`
  transliteration), 22916 and 65015 (footnotes) align at every row.

The 15 posts not converted are the worked examples for the skill (stage 6):

| Post | Why |
|---|---|
| 4957 | two tables (Psalm 67 and Ana b'Khoaḥ); proposal pending |
| 16071 | Psalm 30 in rows of several verses each; proposal pending |
| 13727, 28623, 53601 | prose with no table |
| 18267 | more than one table |
| 18422 | colour-coded alignment; two English columns |
| 41217, 48034 | two English columns |
| 41025, 59104, 66455 | verse and prose mixed in one column |
| 47590 | Judeo-Arabic marked as Hebrew |
| 53572 | a column headed as a Judeo-Arabic transliteration, set in Hebrew letters |
| 53593 | rejected (a modern work claimed as fair use) |

Post 34548's English translation is not imported until its licence is clarified.

### 4a. Bulk import (the export of 2026-11-02)

3,249 in-scope posts at upstream commit `624215eef0`.

- **3,242 converted**, into 5,661 projects in 108 languages and scripts. The largest groups
  are English (3,211), Hebrew (1,549), German (312), Yiddish (93) and Jewish Palestinian
  Aramaic (60).
- **URNs:** 176 posts use existing URNs and 3,073 have new ones.
- **Not converted:**
  - 3778, 11906 and 14515 waited on decisions about each post, since made (`layouts`):
    - 3778, Dolgin's Tashlikh practice: one English text; its notes transclude Micah 7:19.
    - 11906, Weiss and Rank's Seven Blessings: Hebrew, English and `he-Latn`, each row on
      the existing Sheva Berakhot URNs (`borei_peri_hagafen`, then
      `sheva_berakhot/shehakol_bara` … `asher_bara`), with the authors' explanation of each
      blessing as a note and their essay as each language's introduction.
    - 14515, Cohen's Vidui meditation: Hebrew and English on `ashamnu/1`–`24`, registered for
      it as parts of the existing `ashamnu`, one per confession in the traditional order.
  - 4017 and 29942's English are held (see `licence_decisions.yaml`).
  - 29959, 36831 and 52834 are rejected on licence.
- **Checks:** `urn_registry --check` and `validate_names` have no errors, and every URN
  and contributor reference resolves.
- **Rendering:** parallel PDFs and HTML of 4957 (two tables), 19667 and 67442 (colour-coded
  alternatives) and 1769 (an essay) render and align.
  - 1769's essay quotes a Hebrew passage that has no translation. A book of the English
    project must therefore list the Hebrew project in `priority.transclusion`.
- **What the full export turned up:**
  - Malformed source links: a second `#` (50267) and a truncated `%` escape (50879).
  - Lines that only named a post's download files ("DOWNLOAD: PDF | ODT"), in 39 posts.
    These are dropped.

## Later work

### 5. Updater (`update.py`)

This runs monthly, after each upstream export:

```bash
uv run python -m opensiddur.importer.opensiddur_org.update [--prune]
```

1. It downloads the export (stage 1) and compares the manifest before and after, by post ID
   (`_(ID)`), not by path. A post's `last_updated` decides whether it changed, so the
   export's bulk re-saves are not changes.
2. It also compares the full set of exported IDs, to tell deletions from posts that left
   scope.
3. It classifies each post the download wrote or removed:

| Class | Meaning | Action |
|---|---|---|
| `new` | newly published, or entered scope | match its URNs (stage 3) and convert it |
| `changed` | `last_updated` differs | reconvert it |
| `override-stale` | changed, and `post_decisions.yaml` holds a decision about it | report it, for the decision to be reviewed; not reconverted |
| `left-scope` | still exported, but no longer a prayer or no longer filed under 1132 | report it; with `--prune`, remove its projects |
| `deleted` | no longer exported | likewise |

4. It converts the new and changed posts and registers their new URNs. Conversion is
   all or nothing per post: a post that fails leaves its projects as they were.
5. `--prune` removes a departed post's projects unless another project refers to a URN that
   only they hold (its `corresp`), which would leave the reference with nothing to resolve
   to. Those are kept and reported.
6. It writes `output/opensiddur_org_update_<date>.md`, named by the export's date. That file
   becomes the description of the run's pull requests. It lists, under **Needs review**:
   - stale decisions;
   - posts that failed or were not converted, with the reason. A licence decision about
     one post lapses when the post is updated or relicensed, so a held or rejected post
     that changed is listed here and asked about again;
   - changed posts whose rows changed in number. Their row URNs were decided against the
     old rows, so `post_urns.jsonl` is reviewed for them.

Reconverting a post whose content did not change produces no TEI diff, because the output
is deterministic. A run against the export already imported does nothing.

### 6. A skill for irregular posts

`.claude/skills/opensiddur-org-post-to-jlptei/`, modelled on `scan-to-jlptei`. It writes a
per-post override (column relabelling, row-to-URN maps, verse milestones inside a row), or
a hand-written body when no override can describe the post. It starts from the pilot's
irregular posts above.

## Open questions

- Do any other category trees count as prayers, such as compilations? The first cut is
  1132 only.
- Is `status` a reliable sign that someone used the site? It separates the pilot's print
  translators from its contributors, but the export does not document it.
- How should `seg type="acrostic"` be displayed in the PDF and HTML exports? For now it is
  plain text.
- Row URNs of new posts are numbered. Named stanzas would be better where a post's stanzas
  have names.
