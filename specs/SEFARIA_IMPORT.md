# Importing from Sefaria

Sefaria (https://www.sefaria.org) publishes its library under open licences. This importer
converts Sefaria works into JLPTEI projects, a Hebrew and an English project for each work.
The first works are the five CC-BY Metsudah linear volumes of Rabbi Avrohom Davis
(Metsudah Publications):

| Sefaria title | volume | status |
|---|---|---|
| Weekday Siddur Sefard Linear | weekday siddur, 1981 | **pilot, imported** |
| Shabbat Siddur Sefard Linear | Shabbat siddur, 1981 | **imported** |
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
  Selichot have some of depth 2 ("Chapter", "Paragraph"), read as a leaf per chapter. Where the
  structure table places the leaf itself rather than its chapters (each day of the Selichot,
  whose chapters are its selichot and the runs of the service between them), the chapters are
  aligned one by one and then joined into the one leaf, numbered on, each chapter opening a text
  at its first phrase (`align.join_chapters`). The Song of Songs, an inner node of the Shabbat
  siddur whose chapters the table places one by one, stays a leaf per chapter.
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
  Parts that do the same job are the same part: Nusach Sefard's Kedushah opening נקדישך is
  the Kedushah's opening, though Ashkenaz says נקדש.
- **Near-identical printings are one text.** A later printing in the same volume that is mostly
  the same keeps the text's URN as a variant, its own words a conditional insertion.
- **Verse collages are named by function or incipit.** The six remembrances are
  `shesh_zekhirot`; a collage with a common incipit is named by it (`yehi_khevod`, `hodu`,
  `vayvarekh_david`). Each verse inside carries its `bible:` URN.
- **One URN with opensiddur.org.** A text an opensiddur.org post also prints shares one URN
  with it (see URNs).
- **Calendar conditionals.** The book's seasonal and occasional passages are conditional on the
  calendar (and on the quorum, the recitation, the food eaten), from its own rubrics and
  labels (see Conditions).
- **Rite.** "Sefard" is Nusach Sefard (Nusach haAri), the Chassidic variant of the Ashkenazi
  rite — not the rite of the Sefaradim or Edot haMizrach. The project headers say so.
- **Licence.** Sefaria marks the Metsudah versions `CC-BY`, which Sefaria's own code maps to
  CC BY 3.0. The credit is to the publisher, Metsudah Publications, and the translator, with
  Sefaria acknowledged as the digitizer. The translation is part of the book, as Birnbaum's is of
  his, so the translator is the source bibl's `tei:author` (with a note that the English is
  theirs), not a `tei:respStmt`: a respStmt credits a contributor to the encoding, by URN. A version whose licence changes is refused by the
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
  mismatch is an error. A decision may also name, in `opens`, Hebrew segments that begin a
  text the book does not mark (untranslated songs printed one after another; the day's Kiddush,
  whose songs and verses have no bold openings); a leaf whose counts agree may have a decision
  for this alone.

**Misprints** (`corrections.yaml`, `corrections.py`). A clear misprint in a segment — a
typographical error, or a slip that makes one printing of a text differ from the book's other
printings of it ("if His Messiah" in the Weekday half Kaddish, "far above" for the lone לְעֵלָּא
in the Selichot's first half Kaddish) — is listed by work, leaf (its path before chapters are
joined), version, 1-based segment, the words as printed (`sic`) and as corrected (`corr`). After
alignment the words are marked in their segment: the files write both, `tei:choice/tei:sic +
tei:corr`, for `readings.errors` to choose (corrected by default), and every comparison of words
(matching, a text's printings, the opening a larger text shares with a smaller one) uses the
corrected words. An entry whose words are not in its segment exactly once is an error. Wording
that is a translator's choice is not a misprint, and stays as printed.

### 3. Texts and rubrics (`blocks.py`, `markup.py`)

A leaf is a stretch of the book, not one text. The book marks where each text begins — the
first words in bold, or a heading — so a leaf is divided into:

- **texts**: from one opening to the next. A bold opening continues the text before it when
  that text has only its heading, or when the segment before was printed whole in bold (the
  two lines of the Shema's first verse). An unpointed label in parentheses (`(פלוני/פלונית)`)
  is a placeholder inside the text, and an unpointed response beside its English (`אמן`,
  "Amein.", between the lines of the prayer for rain) is words of the text;
- **rubrics between texts**, which belong to the book's running order. An unpointed label
  that `conditions.yaml` holds as a condition (`<b>לפסח</b>`, "On Pesach", in the festival
  Musaf) is a rubric inside the text it governs, however boldly it is printed, not a heading;
- **headings** with no text before the next.

Pointing tells a heading from text that happens to be bold: Metsudah's headings (`<b>אבות</b>`)
are unpointed, its liturgy pointed. Unpointed Hebrew set wholly in small print is an instruction
however long it runs (`ש"ץ מתחיל בקול רם והצבור עונין אחריו פסוק אחר פסוק ...`). A Hebrew numeral
and a stop before the line (`יא. <small>חתום שמעון בר יצחק</small>`, `ד. <b>במוצאי מנוחה</b>`)
is the number the Selichot gives a selichah: a label, a rubric before the text it numbers
(`markup.is_numbered`).

### 4. URNs (`match.py`)

Each text's URN, in order of preference:

1. **The same text again.** A text this volume printed earlier is that text: one project
   carries a URN once. Printings are paired phrase by phrase (`map_phrases`, on consonant
   skeletons): the later printing is the text where half the earlier one's phrases are found
   in it without long gaps, and is cut where the earlier printing ends; an earlier printing that
   ran on past a later one is cut where the later one ends.
   - **A repeat** prints exactly the first printing's words, phrase for phrase, and transcludes
     it. Exactly its words lined otherwise are a repeat too, cut after the phrase they end in
     (`regrouped_length`): the Selichot prints the close of the service phrase by phrase on its
     first day and in untranslated paragraphs on the days after.
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
2. **A curated choice** (`equivalents.yaml`, found by a block's opening words, optionally in one
   leaf, or any of a list of leaves): the URN the matcher cannot decide from the words alone. A text that does the same job
   as one the collection names, and is mostly its words, is that text whatever rite prints it —
   Nusach Sefard's Kedushah (נקדישך, and כתר at Musaf) is Birnbaum's `amidah/qedushah`, its
   morning אהבת עולם is `ahavah_rabbah`, its separately printed מעין שלש openings are
   `meein_shalosh`'s parts. A choice can also name a text the collection does not hold yet:
   a verse collage by its function (`shesh_zekhirot`) or common incipit (`yehi_khevod`), or
   the name an opensiddur.org post already has (`shirat_hayam`). `joins` make a block
   continue the text before it in its leaf, the rubrics and headings between becoming pairs
   inside it (the Shema's paragraphs; the six remembrances, their labels descriptions). A join
   may name words the text before must have (`after`): the Kaddish's parts the book sets apart
   (its response, יתברך, תתקבל, יהא שלמא, על ישראל, עושה שלום) join only a Kaddish, even one
   that runs on at the end of the block before it (Ashrei, then the half Kaddish). The
   choices apply to every Metsudah volume; they are knowledge about texts, not decisions about
   one block. A text chosen this way is not cut by a shorter later printing, and a later
   printing of it that differs is its variant. A choice may name the words its text ends with
   (`ends`), and runs of words it must also have (`with`): only a block that has them is that
   text, the one reaching furthest into the block winning, then the one with more `with` —
   each Kaddish is chosen whole this way, `kaddish/shalem` (with תתקבל) and not the half
   Kaddish or the Mourner's that open alike, and a block that runs on into such a text
   unmarked is cut where it opens (Ashrei, then a half Kaddish whose Sefard words do not agree
   closely with Birnbaum's) — and the text ends there, cut
   before what the book runs on into without marking it (the day's verses after the
   Selichot's Vayaavor), never earlier for a text it holds (the full Kaddish's
   הוּא יַעֲשֶׂה שָׁלוֹם). A choice may name a text its text opens with (`transcludes`): where
   the volume prints that text and the block opens with its words, phrase for phrase, words no
   variant of the larger text changes, the larger text's file transcludes it and holds only its
   own words after it — each larger Kaddish transcludes the volume's half Kaddish. The
   transcluded text stands for everything in the place it takes, so its first printing must
   have the same rubrics there and the same English. Which of its variants is said is the
   place's to declare: the larger text's file holds its first printing, so each place
   transcluding the larger text declares the smaller text's variants not printed (the
   Selichot's closing full Kaddish, with לְעֵלָּא מִן כָּל, on the Ten Days as on the other days).
3. **The next part of the same text.** Where the block before it (rubrics apart) is a part of a
   text, a block that one of its keys finds among that text's parts — and agrees with at least
   as well as with any other candidate — is that part: the Kedushah's קדוש קדוש קדוש is
   `amidah/qedushah/qadosh` there, not Yotzer's. A poem's stanzas (`…/stanza_N`) another rite
   words a little otherwise are found by agreement rather than by their first words: a stanza
   ends where the collection's next stanza agrees best over its collected opening, if at least
   0.75 (`STANZA_AGREEMENT`; two lines off, Nusach Lita's Yisrael Nosha agrees at most 0.62),
   and the block after a stanza is the stanza it agrees with best. Each keeps the book's words:
   the volume's file for the stanza transcribes them.
4. **An existing text.** The block's opening is looked up in the incipit index of the
   collection's Hebrew projects (`util/incipit.py`, shared with the opensiddur.org importer).
   The opensiddur.org imports and this work's own projects are left out: their openings
   are formulas that match unrelated texts. The other Metsudah volumes' Hebrew projects are
   in it, so that a text one volume minted is found by the next rather than minted again.
   The index reads a word across inline elements (`לַ<j:divineName>יהוה</j:divineName>`) but
   not across an empty one (a note's anchor) or a kri and ketiv; a paseq separates words as a
   maqaf does; and the divine name behind a prefix is one spelling (`לַייָ`, `לַיהֹוָה`). Words are compared as consonant skeletons, a maqaf
   separating words and הללו יה one word. Every match must agree with the block over the
   candidate's collected opening (sixteen words; a short text's own words only), not just the
   key that found it: many texts open "יהי רצון מלפניך" and go on differently. The lookup goes
   in tiers, the first that finds a text winning: six words (a blessing only by the words after
   its formula, which every blessing shares); four words — for a blessing, two to five after
   the formula (פוקח עורים) — when one text agrees clearly best, which finds another rite's
   wording (Sefard וְלִתְפִלָּתָם, Ashkenaz וּבִתְפִלָּתָם); and the same a word or two out of
   step, past a label or heading word.
   - **What the index records.** For each `@corresp` scope: its opening, collected past its end
     so that a short part is found by its neighbours, and how many of those words are its own
     (its scope ends at its element's end or the next milestone of its unit); its last words;
     what it transcludes, and the part it opens or ends with by transcluding (a conditional
     transclusion — Modim de-Rabbanan, said only in the repetition — neither opens nor ends
     it); and whether it is a milestone inside another text's words. A text that opens by
     transcluding a part is indexed by that part's opening, not by its own words after it.
   - **Moving up.** A match moves up to the whole text it is part of when the whole opens with
     it and the block holds three quarters of the whole's other parts (a part's own words, a
     word or two for Ya'aleh Veyavo's occasions), or when the block ends with the whole's
     closing formula (`ברוך אתה ה׳ חונן הדעת`) — a blessing in another rite's words. A block
     that opens like nothing the index holds is still the blessing whose closing formula it
     ends with, when one text has it.
   - **Cuts.** Otherwise a match stays the part, and the block is cut where another part opens
     (the Kaddish divides into its parts this way, the part going on agreeing past its first
     six words), or where a text the index holds whole ends. A text made of parts that is cut
     where one of its own parts opens is the part it opens with (the Kaddish's יתגדל lines would
     be `kaddish/yitgaddal`; the Metsudah volumes' Kaddishes are chosen whole instead, above).
     A block is also cut where it runs
     into another text the collection names (Vezot Hatorah, then Yehi Ratzon Milifnei Avinu):
     a six-word match agreeing closely over its opening, not scripture (save a whole psalm,
     below), not a part of the same
     text or something it transcludes, not a later stanza of a poem, not a verse the
     collection quotes inside a text (a milestone), and — for a short text — followed here by
     what follows it there (Adonai Sefatai is followed by the Amidah; a line quoted from the end
     of Avinu Malkenu is not), and not words the collection prints the text going on with
     (Asher's Vayaavor goes on with the Thirteen Attributes, which a stanza of Ezkerah quotes).
     A text this volume printed earlier counts as one the collection names (the Selichot's
     עֲשֵׂה עִמָּנוּ, after a selichah, without a bold opening). The block is then decided again
     up to the cut. No cut leaves a
     word on its own. A block is cut before a blessing's formula in its middle — a new blessing
     is a text of its own — unless the block is one text that ends with the closing formula of
     the text it opens like (Barukh She'amar's litany and blessing).
   - **A psalm after a text.** A block that runs on into a whole psalm, its first verse to its
     last, is cut before it (Psalm 130 after Yishtabach; Psalms 121 and 150 in Kiddush
     Levanah; each day's psalm after its introduction) — unless the block opens with a verse
     (Vihi Noam, Psalms 90:17 and then Psalm 91, is one collage), the psalm is a part of the
     text the collection names it as (Hallel's), or the collection prints the text going on
     into it.
   - **Scripture.** A block that opens a chapter at its first verse (its first half, `/1/a`,
     will do) is that chapter, and ends where the chapter's last verse does — where that verse
     opens after the verse before it, since a refrain may open an earlier verse alike (Psalm 99,
     verses 5 and 9) and the text after the chapter may quote it (Uva Letziyon, Psalm 20:10); a block that is one whole verse is that verse (`bible:malachi/3/4`); a block that is
     two or more verses in order, whole, is that run, named by its range
     (`bible:proverbs/31/10-31`, `bible:psalms/148/1-6`; a long verse ends where its last words
     do; a word the source splits in two still opens its verse, the letters agreeing), and a
     run followed by a text the collection names that is not scripture (Vayechulu,
     then Magen Avot; the Musaf verses, then ומנחתם ונסכיהם) is cut there. Verses followed by
     more verses not in order are a collage, one text (below). Scripture is named by its
     place, so a range is `existing`, never minted. Any other block that opens mid-chapter is
     liturgy quoting scripture, its verses marked inside it (below).
   - **The same opening.** Texts that open with the same words (הודו ליהוה כי טוב כי לעולם
     חסדו opens Psalms 106, 107, 118 and 136) are told apart by what follows: the candidate
     whose collected opening agrees best over all of it is taken.
   - **A closing that goes on.** A last phrase of at most four words opening "and" after the
     words of a known text (מקדש השבת / וישראל וראשי חדשים; להדליק נר של שבת / ושל יום טוב)
     carries the closing on; it is not cut off as a text of its own.
   - **A later printing.** When this volume printed the text before and the block differs, it
     is a variant where it opens as the first printing does; where it is only the part the text
     opens with (Musaf's Retzeh, after the morning's whole Avodah), it is that part.
5. **A new text**, `prayer:` plus at least three words of its Hebrew incipit romanized
   (`util/transliterate.py`, the JLPTEI-3 table) and respelled by `specs/naming/spellings.yaml`
   — two words ("yehi_ratzon") would claim an opening many texts share; unpointed and
   parenthesized words (labels) are skipped, a blessing is named after its formulas
   (`al_mitzvat_tzitzit`, not `barukh_attah`), a petition after "yehi_ratzon" and two words
   past its formula (`yehi_ratzon_shetishlach_meherah`), and a response before a text is
   dropped (`keshem_shenikhnas_laberit`, not `amen_…`), and so is a selichah's address
   (`eikh_niftach_peh`, not `eloheinu_velohei_avoteinu_…`, as Asher's Selichoth names them).
   Lengthened until it is not taken in `prayer:` or `poem:`, whose texts of one path would share
   their `metsudah:` phrases. A numbered selichah the lookup does not find is first compared,
   its address apart, with every whole poem the collection holds: the one that agrees best
   over its collected opening, if at least 0.75, is that poem worded otherwise (Nusach Lita's
   אָדוֹן דִּין אִם יְדֻקְדַּק is Asher's `adon_din_im_yiddeqen`). A text the book numbers is
   otherwise minted in the work's
   `numbered_texts` namespace (`works.yaml`): the Selichot's numbered selichot are `poem:`, the
   prayers between them `prayer:`.

**Shared with opensiddur.org.** A Metsudah text that an opensiddur.org post also prints shares
one URN with it: where a post as a whole is the text, its record in
`specs/opensiddur_org/post_urns.jsonl` is `existing` with that URN (Ahavat Olam posts are
`ahavah_rabbah`; Aleinu posts `aleinu`); where a row of a compilation is the text, its
`rows` map it there (the Birkat Hamazon stanzas for a brit, Hanerot Halalu, Vehu Rachum). The
post's own URNs are then gone from the registry, with no alias (before 1.0). The posts are
reconverted (`opensiddur_org.convert --post …`) in the paired projects pull request.

Every decision is recorded at once in `specs/sefaria/metsudah_urns.jsonl` — one line per text,
keyed by work, leaf and the Hebrew index of its first phrase, with its kind
(`existing`/`new`/`repeat`/`variant`), incipit, evidence and a hash of its words (`as_of`). Records are
sticky: a reviewer may correct a URN in the file and rerun, and a rerun on an unchanged export
decides nothing. A first printing's record is current only while no block before it prints
the text, so a text a later rule cuts off earlier in the book (Psalm 67 in Kiddush Levanah,
before the counting of the Omer) makes the later record a later printing. A cut is recorded by
the record of the text after it, and replayed from it — after any new blessing before it.
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
  An instruction that applies only where the text is printed is the place's, set before the
  transclusion, never in the text's file: the rubrics a text opens with, before its first words
  ("The Chazzan recites the following half-Kaddish"), go to the structure file. A condition the
  text opens with stays with it where every printing opens so (Condition rubrics, below), and so
  does a rubric after a heading of the text's own.

| Sefaria markup | JLPTEI |
|---|---|
| bold | dropped (presentation) |
| unpointed bold or small Hebrew, whole segment, beside an English heading | `tei:head` |
| the same beside an English rubric or nothing | `tei:note type="instruction"` |
| English with no Hebrew | `tei:note type="instruction"`; printed whole in bold, `type="description"` |
| small pointed Hebrew | `tei:hi rend="small"` |
| `<small>לְר"ח:</small>` before the words it governs | the phrase a `j:conditional`, the label its note (see Conditions); a label `conditions.yaml` does not list, `tei:note type="instruction"` |
| English italic | `tei:hi rend="italic"` |
| `<big>` | `tei:hi rend="large"` |
| `<span>` | `tei:foreign xml:lang="he"` |
| `<br>` | a space |
| footnote | `tei:anchor` + `tei:note type="commentary"` in `tei:standOff type="notes"` |

**Conditions** (`conditions.yaml`, `conditions.py`). The book's calendar and other conditions
become `j:conditional`, from a curated table:

- **Condition rubrics.** An English rubric that says when the passage after it is said ("During
  the Ten Days of Penitence add:", "From the Musaf of Shemini Atzeres until the Musaf of the
  first day of Pesach you should say:", "On Sunday:", "If there are at least 10 men, add:") is
  matched by a regular expression and becomes the conditional's note in English (the Hebrew,
  which prints no rubric, carries the same conditional without one): a condition, not printed
  once it is true. Inside a text it governs the phrases after it up to the next rubric, or,
  where its passage opens with a parenthesis, to the phrase that closes it, or to the end of the
  variant's passage it is in; the conditionals nest with the variants'. A rubric between the
  condition and the first words it governs ("Chazzan:", an explanation) is inside it. `through`
  ends the passage with the phrase whose words end so (מודים דרבנן, printed inside the Hodaah,
  `through: ברוך אל ההודאות`). Between texts it gates the next text's transclusion in the
  structure file — or, marked `section: true` (the Kedushah, "When the Chazzan repeats the
  Shemoneh Esrei"), everything to the next heading, or, with `until`, to the rubric that matches
  it, past any heading (Tachanun, to "The Chazzan recites the following Kaddish"); either ends
  at the next condition rubric, and at the end of the leaf; a rubric `until` names may also
  open the next text. That rubric comes after the section, unless `until_included: true` makes
  it the section's last (each day's psalm ends "(Deliver us...; Mourner's Kaddish.)", before
  the next day's rubric; the Kaddish after Tachanun is said either way). The rubrics before the
  condition a text opens with are the place's, before its gate. A text that opens with a condition rubric keeps it in its own file only
  when every printing of it opens with that rubric; otherwise each place that prints it is
  gated by its own rubric, and the text's file is unconditional (Psalm 130, said in the Ten
  Days after Yishtabach and among the winter psalms every Shabbos). A rubric over a section
  is always the place's: it opens there as it would between texts (each day's introduction
  and its psalm, cut apart). `instead_of_previous: true` makes the text before the rubric the alternative,
  conditional on the opposite ("A woman says:": שלא עשני אשה unless female, שעשני כרצונו if so).
- **Conditions follow Birnbaum.** A condition Birnbaum already encodes is written as Birnbaum
  writes it, so that the two books agree: the days Tachanun is omitted (Birnbaum's list, with
  Pesach Sheini, which this rite adds, and the `override` occasions — a mourner's house, a
  circumcision, a wedding — and, at Minchah, the eves of those days and Fridays), the days the Torah is read, the Kohanim's blessing
  (`practice/birkat-kohanim` in the repetition with a minyan), the meal's host and guest
  (`meal-context`), a woman's blessing (`person/gender`), the father of a Bar Mitzvah. Such
  conditions are YAML anchors under `definitions`, used by every rubric that needs them. Where
  the book prints its own list (Psalm 20, El Erekh Appayim), its list is followed.
- **Leaves.** A leaf the book says when to say only at the end of the leaf before ("On days
  when the Torah is not read continue with Ashrei") is gated where its parent transcludes it:
  `leaves`, by work and leaf path.
- **Directives.** Rubrics that read like a condition but are reviewed and are not — a stage
  direction ("When the Holy Ark is opened"), where to turn ("On regular weekdays continue …"),
  or a choice among blessings no setting makes (what you see, smell or eat) — are listed under
  `directives`, and stay instructions.
- **Labels.** A Hebrew label before a phrase (`<small>לְר"ח:</small> רֹאשׁ הַחֹדֶשׁ הַזֶּה`, לפסח,
  לסכות, לר"ה, לש"ע וש"ת) makes the phrase conditional, the label its note.
- **Inline alternatives.** A parenthesized alternative opening with an abbreviation the table
  lists (`(בעשי"ת הַשָּׁלוֹם)`, `(בעשרה אֱלֺהֵינוּ)`) is a `type="marked"` conditional, the
  abbreviation its note; where the table says it replaces words beside it (`הַשָּׁלוֹם` for
  `שָׁלוֹם`, `וּלְעֵלָּא מִכָּל` for `מִן כָּל`), those words are conditional on the opposite, as
  Birnbaum conditions `האל הקדוש` against `המלך הקדוש` — in the same phrase, or, where the
  alternative ends its phrase, at the opening of the next (the Kaddish).
- Conditions are written in the registry's types (`holiday`, `holiday-aggregate`,
  `day-of-week`, `service-time`, `hebrew-date`, `quorum`, `recitation`, `override`,
  `practice`, `meal-context`). `conditions.yaml` is checked for its grammar when it is loaded,
  and the projects written from it by `validate_features` against the registry. The report lists the condition
  rubrics found, and the rubrics that read like a condition ("On …", "During …", "From …",
  "A woman …", "The following … is said on …") but are in neither `rubrics` nor `directives`:
  they stay instructions until reviewed.

Every file is validated (RelaxNG and Schematron) before it is written; a file an earlier run
wrote that this run does not is removed. `--register` appends the new URNs — minted texts and
`siddur:` places with their parents — to `specs/urn_registry/`. The run's report,
`output/sefaria_<work>_report.md`, lists the leaves aligned by the trailing rule, the URNs
decided, the decisions that lapsed and the condition rubrics.

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
| curated | text-changed, where a misprint correction of the changed version (`corrections.yaml`) or an alignment decision whose `as_of` is not the new leaf's (`alignment_decisions.yaml`) applies | reported under "Text changed where a misprint correction or alignment decision applies (review before converting)"; the entry is removed, moved or re-decided before converting |
| resegmented | a version's segment count changed | reported; the alignment decision and phrase numbers are reviewed before converting |
| added / removed | the schema gained or lost a leaf | reported; the structure table must place it |
| metadata | a version's title, licence or URL changed | reported; a licence change is decided before converting |

A resegmented leaf with a correction or decision is noted as such in its line of the report: a
correction's segment number may now point at a different segment that holds the same words.

With nothing to review, the work is converted with `--register`. If the conversion still refuses
a correction or an alignment decision, the work's section of the report says "Not converted:"
with the error, and the run goes on to the next work. The command exits non-zero when any work
needs review or failed to convert. The report,
`output/sefaria_update_<date>.md`, becomes the description of the run's paired pull requests
(sourcetexts, processor for decision files and registry lines, projects).

## Later work

- The other four volumes: a `works.yaml` entry and a structure table each; their phrases
  reuse the Weekday Siddur's numbers where the text is shared.
- **Conditions with no setting.** A choice no registered feature makes — which blessing for
  what you see, smell or eat beyond מעין שלש, having forgotten רצה or יעלה ויבוא — stays an
  instruction (`directives`); a feature for it is a registry change first.
- Kaddish responses and the reader's and congregation's parts as speaker roles
  (`instruction:role/…`).
- Sefaria's `links/` (citations from the footnotes to Tanakh and Talmud) as `bible_hint`s for
  matching, and as `tei:bibl`/`tei:ref` on quotations.

## Open questions

- The project titles of the later volumes, from their title pages.
