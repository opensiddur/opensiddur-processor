# Converting the Birnbaum siddur from its scan

The evidence is the page. Philip Birnbaum's *ha-Siddur ha-Shalem* (1949) is converted by
reading the scanned print, Hebrew recto and facing English verso, and writing the TEI
from what the page says. The transcriptions of this book that exist are used only as a
proofreading check on the reading, never as its source.

This supersedes the wikitext-driven approach on `feat/birnbaum-he-importer`. That branch
built the text from the Hebrew Wikisource transcription, which is not this book: it
renders Birnbaum's English rubrics into Hebrew of its own, adds Eretz Yisrael customs,
and corrects the text. Most of the importer it needed existed to undo that distance —
and it still wanted his rubrics entered by hand from the scan, because the transcription
does not contain them. Reading the scan first removes the distance instead of correcting
for it.

**Pointing check for every installment:** a single printed dot may represent both
holam and a shin/sin dot. Encode each logical mark on its proper letter; for
example, write `מֹשֶׁה` with U+05B9 on mem and U+05C1 on shin. Do not copy a
comparison transcription’s omitted mark. See [the combined-dot rule](#a-combined-shin-dot-and-holam-is-two-marks-and-both-are-encoded).

## What is on disk

The line is drawn at what a machine can remake. **Images stay out of every repository**: a
leaf is re-fetchable from the Archive, and the enlarged bands are cut from it by
`pages.py`, so 63MB of the working directory is worth nothing in git.

```
output/birnbaum_scan/pages/{printed}.jpg      the full-resolution leaf, untracked
output/birnbaum_scan/bands/{printed}_{i}.png  overlapping bands, enlarged, untracked
```

**The reading is committed**, because nothing regenerates it. In `sourcetexts`, under
`sources/birnbaum_siddur/scan_reading/`:

```
readings/{printed}.md         what the page was read to say
hebrew/{printed}.txt          the Hebrew lifted out of that reading
transcription/{printed}.txt   the Wikisource slice it was compared against
```

and in this repository, the measurement and the tooling:

```
specs/birnbaum_scan/accuracy.md    the transcription-distance measurement
specs/birnbaum_scan/verdicts/      which side each difference was decided for
specs/birnbaum_scan/settings_*.yaml the export settings the commands below name
opensiddur/importer/birnbaum_scan/ pages.py fetches and cuts; compare.py measures;
                                   build/ writes the TEI
```

`transcription/` duplicates 12K of a file already in `sourcetexts`. That is deliberate: the
slice boundaries are a judgement, and without them `accuracy.md` cannot be rechecked.

```bash
export OPENSIDDUR_CONTACT_EMAIL=... OPENSIDDUR_AGENT_MODEL=...
uv run python -m opensiddur.importer.birnbaum_scan.pages 81 82 83   # fetch and cut up
```

**The scan is 1541×2291 per leaf and that is not a derivative.** `ia/derivatives/
*_scandata.xml` states it and the live JPEG headers confirm it, so `_large` and the plain
`.jpg` are the same file and the 488 MB PDF would add nothing. At that size a qamats is a
few pixels tall, which is why `bands()` cuts the page up and enlarges it 3×: the bands are
what makes pointing legible. Bands overlap so a line falling on a seam is whole in one of
the two that share it.

## How far the transcription stands from the print

`opensiddur.importer.birnbaum_scan.compare` counts the differences between a reading and
a transcription in three buckets, comparing word skeletons first so that a different word
is never counted as a different vowel:

| bucket | what counts |
|---|---|
| whitespace | spacing, line and paragraph breaks, maqqef against space |
| consonants | the base-letter skeleton — a word added, dropped or spelled differently |
| vowels | pointing only, over an identical skeleton |

Which side the page supported is **not computable**. A difference starts `unresolved` and
is set to `print` or `reading` by someone going back to the image; the tally reports the
buckets split by verdict, because a raw count conflates the transcription departing from
the print with a misreading.

Measured on printed pages 81 and 83, 164 words: **no misreadings**. All thirteen
differences are the transcription departing from the print — its own Hebrew rubric where
Birnbaum sets English, a five-word Eretz Yisrael passage he does not print (its own
footnote says so), a segol its own footnote concedes he did not use, and four
qamats-qatan spellings of a glyph the print does not distinguish.

**This print does not distinguish qamats from qamats qatan.** They are one glyph. A
diplomatic transcription of it writes U+05B8 throughout; U+05C7 is an interpretation, and
belongs to whoever makes it.

## What the print does, that the encoding has to carry

Found by reading, and each one changes how a passage must be encoded:

**The asterisk is a substitution, not an addition.** An asterisk in the running text,
repeated before the rubric, marks the passage as substitutable: *"\*Between Rosh Hashanah
and Yom Kippur substitute:"*. The ordinary reading and the alternative are exclusive, so
each is written under its own conditional and the ordinary one is negated. Four occur in
this unit, and the fourth (p. 95) says *say* rather than *substitute* — his wording is per
position and is set as he printed it, never normalised.

**Two columns can mean two different things.** Birkat ha-Shanim's seasonal phrase (p. 87)
is an alternation: one column or the other, inside one sentence. Modim and Modim
d'Rabbanan (p. 91) are simultaneous, split by a printed vertical rule — the congregation
says one while the Reader says the other. The second is conditioned on the repetition and
the first on nothing.

**Column geometry inverts between the two sides and means nothing by itself.** The Hebrew
page sets the columns in Hebrew reading order and the English page mirrors their physical
placement so that reading order is preserved. Encode the season or the occasion, which the
headings state; never the position. *Crop and look before asserting which column is which*
— the arrangement reads backwards at a glance, and did.

**Order columns by reading order, which is rightmost-first on a Hebrew page.** That puts
רֹאשׁ הַחֹֽדֶשׁ first among Ya'aleh v'Yavo's three (p. 89) and the summer phrase first in
Birkat ha-Shanim (p. 87), where the right column is וְתֵן בְּרָכָה. The facing English page
confirms it independently, since mirroring the placement preserves the order: "Bestow a
blessing" is leftmost on p. 88 and so is read first there too.

**Where the columns are simultaneous rather than alternative, the conditional one goes
first.** Modim and Modim d'Rabbanan (p. 91) begin at the same vertical position, and the
instruction over the second says the congregation "responds **here**" — which points at the
moment Modim begins. Linearised with Modim first, "here" would land at the *end* of Modim,
which is not where the congregation starts. Nothing in a single column can express
simultaneity, so the order is chosen to keep the instruction's deixis true; that is the
only thing the choice can preserve.

**A bare day-name over a column is an instruction**, short for "say this on Rosh Hodesh".

**He states the diaspora rain rule as a civil date** — December 4th — and gives no Eretz
Yisrael date at all. He prints no summer insert in the Gevurot: מוריד הטל is nowhere.

**Al ha-Nissim is two complete passages**, Ḥanukkah then Purim, each under its own rubric
and its own parentheses. Not one passage with a variable middle.

**Three headings in the whole unit, all English**: SHEMONEH ESREH (p. 82), KEDUSHAH
(p. 84), ABRIDGED SHEMONEH ESREH (p. 97 — on a *Hebrew* page). Everything else that
structures these pages is a rubric, "Priestly blessing recited by Reader:" included.

**Parentheses are his.** Preserve printed parentheses in the raw scan reading.
When parentheses only mark a conditional addition, the functional encoding may
replace them with the conditional’s brackets or an explicit instruction; do not
render two sets of optional-passage delimiters.

**The two sides cite different pages for the same cross-reference.** Hallel is page 565 on
the Hebrew side and 566 on the English; each points at its own language. Verified at 3× on
both.

**A page turn falls mid-sentence** and is not a paragraph break. `tei:pb` is in
`model.milestoneLike` and valid inside `tei:p`.

**The speaker labels are Hebrew-side only**, in small roman capitals set inline. The
English page sets "Reader:" as its own centred italic line, and at the Kedushah responses
gives no label at all, translating the words instead.

**Birnbaum gets no `respStmt`**, in either project. A `respStmt` records who *digitised* a
text; he is the author of the one being digitised, and is recorded as a source. That the
English is his own translation is said in the English project's `tei:editionStmt` and in a
`tei:note` on `project_source_bibl` — beside the citation, where a reader looking for who
made the book will find it. Crediting him as `trl` instead would claim he did work he did
not do, and push the people who did read the scan out of view.

## The front matter

Twenty-five leaves precede printed page 1, and the book divides them by language exactly as
it divides its body. Read off the scan; the Wikisource transcription of these pages is
proofread and was used only as a check, which is how it turned up wrong on the dedicatee's
name — the print reads WERBELOWSKY, not Werblowsky.

| leaf | designation | holds | side |
|---|---|---|---|
| 1 | `[1]` | blank | — |
| 2 | `[2]` | the Hebrew title page | he |
| 3 | `[I]` | the English title page | en |
| 4 | `[II]` | copyright, rights statement, Hebrew typesetting imprint, printer | en |
| 5 | `[III]` | the dedication | en |
| 6 | `[IV]` | הַתֹּכֶן, the Hebrew table of contents | he |
| 7 | `[V]` | CONTENTS, the English table of contents | en |
| 8 | `[VI]` | blank | — |
| 9 | `[VII]` | ACKNOWLEDGMENTS | en |
| 10 | `[VIII]` | blank | — |
| 11–25 | `IX`–`XXIII` | INTRODUCTION, in three parts he numbers himself, with footnotes | en |

**The book numbers only leaves 11–25.** It prints `IX` on leaf 11 and `XXIII` on leaf 25,
which fixes leaf 3 as `I`; leaves 3–10 are therefore designated `[I]`–`[VIII]`, in brackets,
and leaves 1–2 precede the sequence and are numbered from the scan as `[1]` and `[2]`. The
brackets are the whole of the claim: this is a number the book implies and does not print.
`tei:pb/@ed` here is `1949` alone — the second token names a printing, and front matter is
printed once.

**Both tables of contents are deferred.** They index some 600 printed pages the projects do
not hold yet. Their leaves still carry a page break, so nothing renumbers when they are read.

**The reading is XML, not markdown.** `sourcetexts/.../scan_reading/front/` holds one
well-formed fragment per section, and `build/front.py` splices them in. For the body a
markdown reading and the TEI are two artifacts because the TEI is assembled from Python; here
the fragment *is* the reading, and a parallel prose copy of it would only drift.

**Birnbaum's introduction has to reach the Hebrew compile.** He wrote it in English and the
print has no Hebrew counterpart, so the English project realises it and the Hebrew index
transcludes it, issuing no `corresp` of its own — see `front:` in
[`SIDDUR_URN_SCHEME.md`](SIDDUR_URN_SCHEME.md). Two things had to change for that to work:

- `priority.transclusion` in every `settings_*.yaml` now names the English project after the
  Hebrew. The list is a filter rather than a preference, so a URN no listed project realises
  raised `No prioritized URNs found` instead of resolving to the one project that has it.
- `common.pb()` briefly read `pages.json` for the leaf a page falls on, which looked like
  removing a duplicate and was not: the prayer modules call it at import time, so no part of
  the importer could be imported without the sourcetexts submodule, and CI does not
  initialise one. The mapping is written out again, and a test checks it against
  `pages.json` wherever the submodule is present, so it cannot drift. **A unit test here
  tests the code, never the reading** -- the builders' tests stand synthetic fragments in
  place of `scan_reading/front/`.
- `reledmac.xslt` grouped front-matter prose under the *root* language. In a Hebrew-rooted
  project every line of the English introduction came out reversed. It now groups by the
  prose's own language, so each language gets its own numbered stream.

**The comparison of the old and new translations (p. XXI) is a `tei:list`, not two divisions.**
A `tei:div` may not be followed by a `tei:p`, and the comparison sits mid-section with
paragraphs after it; a labelled list is `model.inter` and sits among them. It is also the
better reading of the page — two labelled alternatives, not two divisions of the introduction.

**The dedication's three display lines are `tei:lg`/`tei:l`.** Written as one paragraph broken
by `tei:lb`, the trailing line break left an empty line box that the next heading was set into,
and ACKNOWLEDGMENTS printed on top of the dedicatee's name.

## The projects

| project | holds |
|---|---|
| `hasiddur_hashalem-birnbaum-1949-he` | the Hebrew of the 1949 print |
| `hasiddur_hashalem-birnbaum-1949-en` | Birnbaum's own English, from the facing pages |

Three tiers: `index.xml`, a unit file holding document order and no words of its own, and
one file per prayer holding the words, the conditionals and the `tei:pb`. Both projects
emit **identical** URNs under their own project ids, which is what aligns them; a URN
repeated inside one document would break the join silently, so none is — and since nothing
downstream complains when one is, `test_no_project_emits_the_same_urn_twice` is what
actually holds the line.

Two units so far, in the order the book prints them:

| unit file | URN | Hebrew pages | English pages |
|---|---|---:|---:|
| `all_shacharit_yeladim.xml` | `siddur:all/shacharit/yeladim` | 1 | 2 |
| `chol_shacharit_amidah.xml` | `siddur:chol/shacharit/amidah` | 81–97 | 82–98 |

### A second unit means a second `@ed` sigil

`common.pb` takes a **required** `sigil`. The second token of `@ed` names which printing a
page break belongs to, and while there was one unit a default was harmless. With two it is
a trap: a break authored in the wrong module would be stamped as the other unit's printing,
and neither the schema, nor the compiler, nor the rendered PDF would say so. Each prayer
module binds its own sigil once at import, so no call site carries it, and
`test_a_sigil_must_be_named_and_is_never_guessed` keeps the default from creeping back.

### `all` is a new occasion, and it was not a local decision

Shaḥarith li-Yladim is said every morning — Sabbaths and festivals included — so `chol`
would have filed it under weekdays, which the book does not do. Adding to the closed
occasion list is a change to `SIDDUR_URN_SCHEME.md`, and it is made there, with the rule
for when `all` is right and when it over-claims.

### One text printed twice, in different words

The children's page ends with a three-sentence meditation that page 95 prints far longer,
after the Shemoneh Esreh. Same opening words, different text — so it takes a URN of its
own, `prayer:yeladim/elohai_netzor`, and `amidah_elohai_netzor.xml` is untouched. Sharing
`prayer:amidah/elohai_netzor` between them would have been wrong twice over: the words
differ, and `refdb` refuses a URN mapped twice inside one project anyway.

### The same rubric, roman on one side and italic on the other

The children's opening sets its four rubrics in **roman** on the Hebrew page and in
**italic** on the English one, word for word the same rubrics. Inside the third one that
inverts: `arba kanfoth` is italic against the roman rubric on the Hebrew page, and on the
English page, where the rubric is already italic, it is not distinguished at all.

The encoding does not follow the type. Both sides mark the term as `tei:foreign` — the
intent is identical on the two pages, a transliterated Hebrew term, and only the
realisation differs, because an italic term inside an italic rubric has nowhere to go.
Recording which side is roman belongs in the reading; choosing how to render it belongs in
the typography settings; neither belongs in the URN. The first reading of page 2 got this
backwards in both directions, which is the argument for checking a styling claim against
both pages side by side at 5x rather than against one page and an assumption.

### A printed paragraph that holds several texts and shows no seam

Under "When dressed:" the print sets nine distinct texts as ONE run-on paragraph, and the
facing English does the same with no visual break at all. The two sides join on exact URN
equality, so anything that must line up with its translation needs a URN — and there is
nothing else here to line up on. They are paired at `tei:seg` inside the single `tei:p`.
Splitting them into transcluded files would align them too, and would destroy the printed
paragraph. The two Shema verses inside that paragraph keep their own canonical names
rather than nesting under the composite: they are the same words wherever the book prints
them, and a later unit that prints them has to align with this one.

Naming follows [`SIDDUR_URN_SCHEME.md`](SIDDUR_URN_SCHEME.md). Ya'aleh v'Yavo and Al ha-Nissim are top-level
because both are also said in Birkat HaMazon — nest only what lives in one place.

## Building and checking

```bash
W=opensiddur-projects/project
uv run python -m opensiddur.importer.util.validation "$W/hasiddur_hashalem-birnbaum-1949-he/amidah_avot.xml"
uv run python -m opensiddur.exporter.refdb --project-directory "$W"
uv run python -m opensiddur.exporter.validate_urn_references hasiddur_hashalem-birnbaum-1949-he --project-directory "$W"
uv run python -m opensiddur.exporter.compiler -p hasiddur_hashalem-birnbaum-1949-he \
    -f chol_shacharit_amidah.xml -s specs/birnbaum_scan/settings_undecided.yaml \
    -o output/amidah.xml --project-directory "$W"
uv run python -m opensiddur.exporter.pdf.pdf output/amidah.xml output/amidah.pdf \
    -s specs/birnbaum_scan/settings_undecided.yaml --project-directory "$W"
```

Swap `-f chol_shacharit_amidah.xml` for `-f all_shacharit_yeladim.xml` to build the
children's unit instead. Every `prayer:` and `siddur:` URN a project emits must have a
line in `specs/urn_registry/`, which `refdb` is what checks it against — an unregistered
URN is an error, not a warning.

`refdb` must be re-run before `validate_urn_references`; a stale index reads as
unresolved references. Indexing the whole corpus takes several minutes, and it uses the
same `database/reference.db` the test suite does, so never run the two at once.

**Compile for a day and a place, or the conditions are untested.** Reading the XML proves
nothing. `settings_undecided.yaml` declares the service and the recitation and no date, so
every day-dependent reading survives with its rubric; `settings_15jan_jerusalem.yaml`
names a day and a place, and nothing conditional should survive it.

## A combined shin dot and holam is two marks, and both are encoded

**Decision.** Where a holam falls on the letter before a shin, or on the shin itself,
Birnbaum prints **one dot** doing the work of both the holam and the shin dot. Many
printers do the same; it is a typographic economy, not a claim about the word.

The holam is logically present, so **both characters are encoded** -- U+05B9 for the holam
and the shin dot -- even though only one dot is on the page. `מֹשֶׁה` is written with its
holam, not as `משֶׁה`.

**This is the one place the reading deliberately departs from what the page shows**, and it
is worth being explicit about why, because everything else in this procedure runs the other
way:

- The rule everywhere else is that the page is the evidence and the reading records what is
  printed. Qamats qatan is refused for exactly that reason: this print has one qamats glyph
  and U+05C7 would be an interpretation laid over it.
- The combined dot is not the same case. A qamats qatan is a *reading* of a mark that is
  genuinely there; the combined dot is a *single mark standing for two* that the language
  requires and the compositor merged to save a dot. Encoding one character would not be
  faithfulness to the page -- it would make the text say something Hebrew does not.
- The test that separates them: ask whether dropping the mark changes what the word **is**.
  Writing U+05B8 where an editor would read U+05C7 leaves the word intact. Dropping the
  holam from `מֹשֶׁה` does not.

So a transcription that omits the holam under a combined dot is wrong, and the diff will
report it as a difference in *vowels* -- which is how this was found on printed 23.

### Printed page 29 proves it, because the edition's editors disagreed with themselves

Pittum ha-Ketoreth sets `שלש` twice and `ושלשה` once, each with **one dot** between the
lamed and the shin. The Wikisource editors had to decide what that dot was, and within
eight words they decided both ways:

| the print | the edition | what it dropped |
|---|---|---|
| `שלש` (twice) | `שְׁלֹש` | the final shin's dot |
| `ושלשה` | `וּשְׁלשָׁה` | the lamed's holam |

Neither is defensible on its own: `שְׁלֹשׁ` needs a holam *and* a shin dot or it is not
that word. So the single printed dot cannot be either mark alone, and the only account that
fits the page is that it is both. That is an argument from the evidence rather than from
convention, and it is the strongest one available -- no crop at any magnification could
have settled it, because there is genuinely only one dot there.

## The footnote apparatus

The print carries two apparatuses. *Commentary* sits at the foot of the Hebrew page, keyed
by a Hebrew catchword set in bold, and runs across the opening: a note begun under a
Hebrew page finishes under the facing English one. *Scripture citations* are numbered,
keyed to superscripts, and printed on the English pages only. Both are Birnbaum's own
statements about his book, in his introduction, and both are confirmed by every page read.

They are `tei:note` in one `tei:standOff[@type="notes"]`, told apart by `@type`:
`commentary` carries the catchword in `tei:label`, `citation` carries the printed numeral
in `@n`. The apparatus is its own file, with a header and no `tei:text` of its own --
valid, because `tei:standOff` is a `model.resource` exactly as `tei:text` is.

### What the foot of a page actually holds

Printed pages 21-26 settle the shape, and page 24 shows both apparatuses at once:

    ────────────────────────────────────────
    were posted in the synagogues to watch the services. … The additional
    word ובגלוי is not found in early texts.
        רבון כל העולמים is mentioned in Yoma 87b as a Yom Kippur prayer.
    ──────────
    ¹ Leviticus 26:42.

- **Two blocks, each under its own rule, in a fixed order.** The full-measure rule
  separates the body from the commentary; a short rule separates the commentary from the
  citations. Commentary first, citations second.
- **A commentary note carries no mark in the running text.** Not a numeral, not an
  asterisk, not a dagger. It finds its text through the quoted lemma alone. Only the
  citations are marked, with superscript numerals that restart at 1 on every page.
- **A note that runs across the opening is set once, continuously.** Page 24's block opens
  mid-sentence with no lemma, being the tail of the note whose head is under Hebrew page
  23. Two feet, one note — which is the fifth PDF measurement this unit owes.
- **A lemma is unpointed**, and one covering a span joins its ends in one of two ways: an
  en dash (`קדש את שמך–ברבים`, page 25) or a spaced ellipsis (`וידבר . . . ועשית כיור`,
  page 27). Both mean a lemma with two ends, so the printed form is carried and not
  normalised to one of them. Hebrew also appears inside a note's own prose, inline and
  unpointed.
- **A note's page is decided by which apparatus it belongs to, not by where its text is.**
  English page 22 has no apparatus at all, because the note on its text (`בהר ה' יראה`) is
  commentary and is set under Hebrew page 21. The English Wikisource transcription attaches
  every `<ref>` to the English page and so records the wrong foot for every commentary note;
  it is a guide to *which* notes a page has and not to where they sit.

### The notes are read from the transcription, and checked three ways

Eighty-six notes is too many to retype, and the English Wikisource transcription of this
scan carries every one at the point the print marks it. So they are extracted, and then
checked — because the transcription is a second look at the same evidence and not a second
witness.

**The lemma must be a quotation of the text it annotates.** Every catchword is quoted from
the prayer, so its consonantal skeleton has to appear in that prayer's skeleton. 37 of the 47
lemma-keyed notes pass outright. The ten that do not are the print's own practice, not
errors: seven **name** a prayer or a person rather than quoting it (`קדושה`, `יעלה ויבוא`,
`רבי ישמעאל בן אלישע`), and three are spelled **plene** where the pointed text is defective
(`עושה` for `עֹשֶׂה`, `נצור` for `נְצֹר`), because an unpointed catchword has to be readable
without points. Confirmed on printed 48's own foot.

**The count of numbered citations must match the reading.** The readings record the feet of
nine English pages independently of the transcription, and `EXPECTED_CITATIONS` asserts the
two agree. They did not at first: a citation naming more than one book — `Numbers 24:5;
Psalms 5:8; 26:8; 95:6; 69:14.` — was classified as commentary, so printed 4 counted two
where the page prints three.

**The Archive's own OCR is a third reading of the same images**, made by a process that
never saw the transcription, and it is good enough on English prose to answer one question:
are these words on the page at all? `check_notes_against_ocr.py` scores every commentary
note against the OCR of its opening. **Median 95%**, two below 75% — and reading those two
found one real error (printed 84's note drops two letters) and one false alarm (printed 86's
page carries a damaged glyph, `wh.ch`, and the transcription reads it correctly).

Fifty of the eighty-six notes sit on page feet not read during this pass. That check is what
put two of them in front of a pair of eyes instead of sixteen page images, and it is a
ranking rather than a verdict — the dropped letters it led to are `is` and `in`, too short
for it to have scored at all.

**The total must add up.** 86 read, 84 encoded, and the two left out are named: they annotate
Mi Khamokha and Adonai Yimlokh, in the Ge'ulah blessing of the Shema, which these projects do
not hold. A note quietly missing is indistinguishable from a note never read, so the number
is carried in the generated module's docstring and asserted in the tests.

One lemma and three words of note text are corrected against the images; one apparent error
is **his**, and is set as printed — see `readings/english_28_48.md`, "A slip of his own".

### A note is keyed to the nearest canonical URN, not to an id

Three ways were available, and the choice is not obvious:

1. **An `xml:id` in the annotated file, with the apparatus in that same file.** This is
   what `tanakh-jps-1917-en` and `tanakh-miqra_al_pi_hamasorah-he` do, and it is forced rather than chosen:
   `refdb.get_references_to` matches an `#id` target only within the one project and file
   that declares it, so an id cannot reach across a file boundary at all. It also welds
   the apparatus to the text, and a note set that cannot be detached cannot be exchanged.
2. **A citation-target URN emitted at every annotatable position.** Any note could then
   key to any position -- but the registry would have to carry the citation targets of
   every source, which is a large permanent cost for positions most of which nothing ever
   annotates.
3. **The nearest canonical URN the text already carries.** Chosen.

Three wins because it is the only one that lets note sources be **switched and combined
across projects**: a second edition's commentary on the same liturgy targets the same
URNs and drops straight in beside this one, and either can be left out. Nothing new is
emitted for it, and nothing already generated changed when the apparatus was added.

The cost is that a note is only as precisely placed as the nearest URN. Where a lemma
falls mid-paragraph with no URN at that point, **the fix is to give that phrase a
`tei:seg` with its own canonical URN** -- which is what the alignment of the two columns
would want anyway -- and never to reach for an anchor.

### A note is realised once, and not in both columns

A note reaches its text by URN, and `refdb` matches a URN target in every project. The two
sides of a parallel text realise the same URNs -- that is what makes them parallel -- so a
note attached to either is found while compiling *both*, and the reader gets it twice per
opening. Each column now drops the projects that are themselves columns; an apparatus
project that is not a column still reaches the primary one.

The apparatus is realised in the English project, as the introduction is, because the
commentary is English prose about Hebrew words. What that gives up is real and worth
stating: the commentary begins physically under the Hebrew page in the print, and will not
in the rendered PDF.

A note carries no URN of its own. `urn:x-opensiddur:notes:` names an apparatus *file*, so
one edition's notes can be swapped for another's; a note is not a text, and `@target`
already says what it annotates.

## The section as compiled, measured

31 pages two-column, from `settings_undecided.yaml`. What was measured and what it said:

- **Every parallel block has two columns.** 210 blocks, none with fewer. Of these 120 carry
  both scripts; the rest carry one, and every one of those is a rubric or a heading the print
  sets in English **on both pages** — his practice throughout this book — or a poem heading
  the English page has and the Hebrew page does not.
- **Line numbers are in the margins and restart per page.** Left column right-aligned at the
  measure's left, right column left-aligned at its right; page 3's left series runs 5, 10, 15,
  20 and page 2's right series restarts within the page at each `\pstart` group.
- **The section's headings are painted left to right**, including the two the English page
  carries alone.
- **A footnote's mark and its text are on the same page** — *nothing to measure*. The
  apparatus is not built yet, so this measurement is reported as having no input rather than
  as passing. An assertion with nothing to assert on is not a green light.

**Two false positives are worth recording, because both came from the measurement and not
from the PDF.** A first version called any numeral a line number, and reported `rules 4 and
5 do not apply` — words in Rabbi Ishmael's seventh rule — as two numbers colliding with the
text. A second clustered margin numbers by their left edge, which is right for the right
column and wrong for the left, where they are right-aligned; it then reported twenty pages
as starting at 10. Neither was in the document.

That is the same shape as everything else this pass turned up: **the step being done by
hand, or by a rule invented on the spot, is the step that is wrong.**

## The apparatus renders (was: a parallel compile dropped it)

**[opensiddur-processor#124](https://github.com/opensiddur/opensiddur-processor/issues/124), fixed in
[#126](https://github.com/opensiddur/opensiddur-processor/pull/126).** Kept here because the
symptom is worth recognising again: while it stood, a single-column compile carried all 61
notes of this unit and a two-column compile carried none, and everything else was green --
the apparatus validated, `refdb` indexed it, every target resolved, the registry was clean.
Only compiling two-column and looking for the notes found it.

Against the fix, the three units carry **84 notes in a parallel compile**: 61 in Birkhoth
ha-Shaḥar, 22 in the Amidah, 1 in Shaḥarith li-Yladim. None is duplicated, and all of them
sit in the English column -- the one project that realises the apparatus.

### The fifth measurement, now that there is something to measure

`\Bfootnote` appears 61 times in the TeX and 61 marks with it. In the PDF:

- **Every note is set once.** Each note's opening words appear on exactly one page. Nothing
  is emitted into both columns, which is what `_primary_annotations` exists to prevent.
- **Every note's opening is on a page**; none is lost.
- **Two long notes continue overleaf** -- Yigdal's on printed 12 and the laver's on printed
  28. That is what a note longer than the page's apparatus does, and what the print does
  itself: his long notes run across the opening.

A caution about the measurement rather than the document: a first pass matched each note by
its first three long words and reported two notes "set on two pages". Widening the window to
six showed each on exactly one. **Three words of English are not a fingerprint**, and a
measurement that cannot tell a duplicate from a coincidence has not measured anything.

What is given up remains as recorded above: the commentary begins physically under the
Hebrew page in the print, and in the rendered PDF it is in the English column.

## Rosh Ḥodesh is computed correctly (was: wrong on most Rosh Ḥodesh days)

**[opensiddur-processor#125](https://github.com/opensiddur/opensiddur-processor/issues/125), fixed in
[#127](https://github.com/opensiddur/opensiddur-processor/pull/127).** Kept here for how it was
found rather than for what it was.

While it stood, `opensiddur:holiday/rosh-hodesh` was right on 5 of the 17 days that are
Rosh Ḥodesh in 5786: six computed as `0`, six carried an inverted day number, and Rosh
Hashanah was reported as Rosh Ḥodesh. One line did all three —
`heb.month in (1, 3, 5, 7, 9, 11)` admitted only the odd-numbered Hebrew months, and the
second day of a two-day Rosh Ḥodesh always falls on the 1st of an even one. Ya'aleh v'Yavo
in the Amidah is conditioned the same way, so it was affected too.

Against the fix all nineteen of 5786's Rosh Ḥodesh days compute correctly, and this unit's
two musaf conditionals resolve as they should on every settings file:

| settings | Sabbath musaf | Rosh Ḥodesh musaf |
|---|---|---|
| `undecided` | stands, with its rubric | stands, with its rubric |
| `shabbat_rosh_chodesh_jerusalem` (18 Apr 2026) | said | said |
| `rosh_chodesh_jerusalem` (17 May 2026) | dropped | said |
| `15jan_jerusalem` and the other weekdays | dropped | dropped |

**How it was found is the part worth keeping.** Every settings file in this directory named
a weekday, so the Rosh Ḥodesh conditional had only ever been seen resolving to *false*. It
took writing a settings file for the purpose of making it fire — and then the date chosen,
18 April 2026, was a Sabbath that is also Rosh Ḥodesh, so the Sabbath passage appeared and
the Rosh Ḥodesh passage did not. A date picked with less care would have shown a conditional
resolving false, and that would have been read as proof it worked.

The two settings files are kept apart deliberately: one names the **second day of a two-day**
Rosh Ḥodesh and the other a **one-day** Rosh Ḥodesh, and `compute._rosh_hodesh_day`
distinguishes them.

## The section as compiled, measured

31 pages two-column, from `settings_undecided.yaml`. What was measured and what it said:

- **Every parallel block has two columns.** 210 blocks, none with fewer. Of these 120 carry
  both scripts; the rest carry one, and every one of those is a rubric or a heading the print
  sets in English **on both pages** — his practice throughout this book — or a poem heading
  the English page has and the Hebrew page does not.
- **Line numbers are in the margins and restart per page.** Left column right-aligned at the
  measure's left, right column left-aligned at its right; page 3's left series runs 5, 10, 15,
  20 and page 2's right series restarts within the page at each `\pstart` group.
- **The section's headings are painted left to right**, including the two the English page
  carries alone.
- **A footnote's mark and its text are on the same page** — *nothing to measure*. The
  apparatus is not built yet, so this measurement is reported as having no input rather than
  as passing. An assertion with nothing to assert on is not a green light.

**Two false positives are worth recording, because both came from the measurement and not
from the PDF.** A first version called any numeral a line number, and reported `rules 4 and
5 do not apply` — words in Rabbi Ishmael's seventh rule — as two numbers colliding with the
text. A second clustered margin numbers by their left edge, which is right for the right
column and wrong for the left, where they are right-aligned; it then reported twenty pages
as starting at 10. Neither was in the document.

That is the same shape as everything else this pass turned up: **the step being done by
hand, or by a rule invented on the spot, is the step that is wrong.**

## The apparatus renders (was: a parallel compile dropped it)

**[opensiddur-processor#124](https://github.com/opensiddur/opensiddur-processor/issues/124), fixed in
[#126](https://github.com/opensiddur/opensiddur-processor/pull/126).** Kept here because the
symptom is worth recognising again: while it stood, a single-column compile carried all 61
notes of this unit and a two-column compile carried none, and everything else was green --
the apparatus validated, `refdb` indexed it, every target resolved, the registry was clean.
Only compiling two-column and looking for the notes found it.

Against the fix, the three units carry **84 notes in a parallel compile**: 61 in Birkhoth
ha-Shaḥar, 22 in the Amidah, 1 in Shaḥarith li-Yladim. None is duplicated, and all of them
sit in the English column -- the one project that realises the apparatus.

### The fifth measurement, now that there is something to measure

`\Bfootnote` appears 61 times in the TeX and 61 marks with it. In the PDF:

- **Every note is set once.** Each note's opening words appear on exactly one page. Nothing
  is emitted into both columns, which is what `_primary_annotations` exists to prevent.
- **Every note's opening is on a page**; none is lost.
- **Two long notes continue overleaf** -- Yigdal's on printed 12 and the laver's on printed
  28. That is what a note longer than the page's apparatus does, and what the print does
  itself: his long notes run across the opening.

A caution about the measurement rather than the document: a first pass matched each note by
its first three long words and reported two notes "set on two pages". Widening the window to
six showed each on exactly one. **Three words of English are not a fingerprint**, and a
measurement that cannot tell a duplicate from a coincidence has not measured anything.

What is given up remains as recorded above: the commentary begins physically under the
Hebrew page in the print, and in the rendered PDF it is in the English column.

## Known defect in the calendar: `rosh-hodesh` is wrong on most Rosh Ḥodesh days

**[opensiddur-processor#125](https://github.com/opensiddur/opensiddur-processor/issues/125)**. Not caused
by this work and not fixed by it, but found by it and load-bearing for anything conditioned
on Rosh Ḥodesh — which in this book is Ya'aleh v'Yavo in the Amidah as well as the musaf
passage on printed 35.

It is worse than it first looked. In 5786 the value is right on 5 of the 17 days that are
Rosh Ḥodesh: six compute as `0`, six carry the wrong day number, and Rosh Hashanah is
reported as Rosh Ḥodesh. The issue carries the full table and a fix.

`opensiddur.exporter.calendar.compute` marks the days of Rosh Ḥodesh like this, in 5786:

| date | Hebrew date | `opensiddur:holiday/rosh-hodesh` |
|---|---|---|
| 19 Jan 2026 | 1 Shevat | 1 |
| 17 Feb 2026 | 30 Shevat | 2 |
| **18 Feb 2026** | **1 Adar** | **0** |
| 19 Mar 2026 | 1 Nisan | 1 |
| 17 Apr 2026 | 30 Nisan | 2 |
| **18 Apr 2026** | **1 Iyar** | **0** |

A one-day Rosh Ḥodesh is 1 and is right. A two-day Rosh Ḥodesh gives **2 on its first day
and 0 on its second**, so the second day is not Rosh Ḥodesh at all as far as any condition
can tell — and the day numbering is inverted besides, since the 30th of the previous month
is the *first* of the two days. Six of the twelve months in 5786 have a two-day Rosh Ḥodesh.

The cause is one line, `compute.py:550`: `heb.month in (1, 3, 5, 7, 9, 11)` admits only the
odd-numbered Hebrew months, and the second day of a two-day Rosh Ḥodesh always falls on the
1st of an even one. The same file's `compute_torah_reading` tests `day in (1, 30)` with no
month filter, which is the right test.

The condition itself is written correctly — `<tei:numeric value="1" max="2"/>` means "any of
its up to two days", and `condition_eval` compares it as a range. The defect is upstream of
that, in what the calendar computes.

**How it surfaced, and why it matters for method.** Choosing 18 April 2026 to test the
Sabbath and Rosh Ḥodesh conditionals together — a Saturday that is also Rosh Ḥodesh — showed
the Sabbath passage appearing and the Rosh Ḥodesh passage not. A settings file chosen without
that care would have shown the Rosh Ḥodesh conditional resolving false and been read as
proof it worked. `settings_rosh_chodesh_jerusalem.yaml` therefore names 17 May 2026, a
**one-day** Rosh Ḥodesh, and says in its own comments why.

## Known defects in the parallel PDF

Found by compiling this unit two-column; both are in the exporter, not in the TEI.

**Fixed here: a facing title in the other language was typeset backwards.** A spanning
heading is set inside the `hebrew` environment when the primary column's title is Hebrew,
and `\OSheadTranslation` received the facing column's title with no direction wrapper of
its own — so an English title under a Hebrew one came out with its letters painted in
reverse order, `NERDLIHC ROF REYARP GNINROM`. It went unnoticed until now because it
needs the two columns to head a section in *different* languages: the Amidah heads both
sides in English, and Shaḥarith li-Yladim is the first unit where the print does not.
`\OSheadTranslation` now wraps its argument against the title's own language, in either
direction. Note what the reading order of `pdftotext` says about such a heading: nothing.
It reorders RTL runs on output, so a reversed heading comes back looking correct — the
defect is only visible in the glyphs' own x coordinates, read in ascending order.

**Fixed here: an instruction set in a fixed-width box ran off the page.**
`\OSInstructionBlock` and `\OSInstructionLine` set the rubric in `\hbox to \linewidth`,
which cannot break, and `\linewidth` inside reledpar's parallel setting is the page rather
than the column. So every rubric wider than half the measure overhung the margin — invisible
in a single-column compile, where the measure is the whole page, and unmissable in a
parallel one. A `\parbox` of the same width does not help, for the same reason. Both macros
now set the rubric as ordinary text between two `\newline`, which is measured by whatever
column it lands in. That gives up the flush margin and keeps the words on the page.

**Fixed here: the labelled list was not set as a list at all.** The visible symptom was that
"THE NEW TRANSLATION" printed at the head of its first paragraph rather than on a line of its
own, but the label was only the part that showed. `reledmac.xslt` had no template for
`tei:label`, `tei:list` or `tei:item`, so all three fell to its pass-through fallback, which
descends without emitting a sentinel. Paragraph boundaries in that stylesheet are made by an
`f:para-break` that only `tei:p`/`tei:ab` and `tei:lg` emit, so nothing separated the label
from the paragraph after it — and, because the list and the item were equally unhandled, the
item's four paragraphs became four sibling `\pstart`s with no mark of where an item began or
ended. Birnbaum sets the passage as two labelled blocks; it came out as one continuous run of
prose. The reading and the encoding were right, as this said; what was missing was the whole
list, not the label's line break.

The label now takes a line of its own, out of the line numbering, styled by
`styles.list_label` (small caps by default); the item's paragraphs are indented on both
margins by `lists.item_indent` (`2em` by default), so the two alternatives read as two blocks.
It is placed the way a `tei:head` is — the same problem — but emits no running-head mark and
no PDF outline entry, because a list label names an alternative inside a section rather than
opening one. The indent applies in a single-column stream, which is where labelled lists are
used: the front matter is set full width, and under reledpar a whole column is one `\pstart`
with no paragraph head to hang the skip on.

**Open: a paragraph's overflow can be typeset in the facing column.** Where a Hebrew
paragraph is short and its English counterpart runs longer, the tail of the English lands
in the Hebrew column — "all kinds of its produce for the best." under Birkat ha-Shanim,
"thou hast always been our hope." under Modim. It is reledpar's column assignment, not the
alignment: the two sides pair correctly everywhere, and naming the divisions (which the
pairs now all are) does not change it. Three occurrences in eleven pages.

## What is done, and what is next

Done: printed pages 81–97, the weekday shacharit Amidah, both projects, 60 files, all
validating. Done: the front matter, scan leaves 1–25 — both title leaves, the dedication, the
acknowledgments and the introduction — 3 further files and a `tei:front` on each index.
Done: printed pages 1–2, Shaḥarith li-Yladim, the first of the surrounding units and the
first opening of the body — 12 further files, a new occasion, and 18 new registry lines.

Next, in the order the evidence suggests:

1. **Birnbaum's footnotes.** He runs two apparatuses: commentary keyed by Hebrew lemma,
   set across the opening so a note begun under a Hebrew page finishes under the facing
   English one; and numbered scripture citations keyed to superscripts in the English
   text. Page 1 is a second witness, and a simpler one: its single lemma-keyed note sits
   at the foot of the Hebrew page, does not run across the opening, and the facing English
   page carries no apparatus at all — so an opening with exactly one note, and no
   continuation to model, is the cheapest place to start. They are a standoff apparatus and belong in their own file. The introduction's own
   footnotes are not these: they are ordinary inline `tei:note`, already encoded.
2. **The two tables of contents**, once there is enough of the book for them to point at.
3. **Finish the accuracy measurement** for pages 85–97, which is cheap now and is the
   evidence for whether this scales.
4. **The surrounding units**, page by page.

## Weekday opening: IA n73–n76, printed 49–52

The next reviewed installment is Psalm 30, Mourners’ Kaddish, Hareni mezamen, and
Barukh sheamar. **It stops before Hodu**, even though Hodu begins on the same opening.
The unit is `chol_shacharit_pesuqei_dezimrah.xml`; its name is the full unit's name,
but its present contents and bibliography cover only this reviewed opening. Extend
that unit as subsequent pages are read, rather than creating a unit per scan batch.

`he_pesukei.py` and `en_pesukei.py` hold the text. The scan readings are recorded in
`sourcetexts/sources/birnbaum_siddur/scan_reading/{hebrew,english,readings}/49–52`;
`hebrew/51.txt` and `english/52.txt` are explicitly partial-page readings. The two
commentary notes begin under 49 and 51 and end under 50 and 52. `notes_pesukei.py`
records them; the Hodu note is deferred with Hodu itself.

### Shared Kaddish, without another printing's page break

The first three paragraphs are word-for-word the earlier Kaddish d’Rabbanan.
Their existing context divisions remain, and **nested `tei:seg`s** give the common
words the canonical names `prayer:kaddish/yitgadal`, `/yehe_shmeh`, `/yitbarakh`.
Mourners’ Kaddish transcludes those segments. The earlier page break sits outside
the shared segment, so printed 47 does not turn up inside printed 49. Its final two
paragraphs have their own names under `kaddish/yatom`: they omit `טובים` and
`ברחמיו`, respectively, and cannot reuse d’Rabbanan's ending.

The second `לעלא` carries the Ten Days condition. Both Kaddishes share that
condition and the standardized instruction **“During the Ten Days of Repentance,
add:”**, registered as `instruction:aseret_yemei_teshuvah/add` and supplied by
`ten_days_addition()` in the builder’s common module. Its `resp` marks editorial
responsibility: this wording is not presented as a quotation from Birnbaum.
The raw reading retains the printed parentheses; the functional encoding omits
them. The renderer places the instruction before a single pair of conditional
brackets around only the added word, so the rest of the paragraph is visibly
outside the addition. Instructions within paragraphs do not suppress these
scope brackets; an instruction alone cannot show where the addition ends. The earlier preview had only
literal parentheses, explaining its different appearance.

When the condition is MAYBE, the instruction accompanies the second word in both
Kaddishes. Compiling for 15 January 2026 in Jerusalem leaves one occurrence;
16 September 2026 leaves two. Neither dated compile leaves an unresolved
conditional. As for existing instruction-bearing conditionals, the compiler
retains the instruction when TRUE and removes it with the passage when FALSE.

### An untranslated passage needs an empty alignment position

Hareni mezamen is printed only in Hebrew. The English project records an empty
corresponding division, with an XML comment saying no English text is printed.
This supplies an alignment position, **not a translation**. Omitting the English
position caused the sequence aligner to pair English Barukh sheamar with Hebrew
Hareni and leave Hebrew Barukh sheamar without its facing text. The empty position
keeps the English column blank there and the next prayer aligned.

Psalm 30's citation is inside its prayer file, beneath the service heading. Putting
both consecutive headings in the unit caused the PDF to repeat the English service
heading. Its biblical correspondence encloses the whole psalm, including the final
Reader passage. The two Reader labels are Hebrew-side only.

### Reproduce and review this installment

Use new worktrees in all three repositories. From the code worktree:

```bash
W=../../opensiddur-projects/feat_birnbaum-shacharit-opening/project
O=../../output/birnbaum_shacharit_opening
uv run python -m opensiddur.importer.birnbaum_scan.build.build_he --project-directory "$W"
uv run python -m opensiddur.importer.birnbaum_scan.build.build_en --project-directory "$W"
uv run python -m opensiddur.exporter.refdb --project-directory "$W"
uv run python -m opensiddur.exporter.compiler -p hasiddur_hashalem-birnbaum-1949-he \
  -f chol_shacharit_pesuqei_dezimrah.xml -s specs/birnbaum_scan/settings_undecided.yaml \
  --project-directory "$W" -o "$O/parallel.xml"
uv run python -m opensiddur.exporter.pdf.pdf "$O/parallel.xml" "$O/parallel.pdf" \
  -s specs/birnbaum_scan/settings_undecided.yaml --project-directory "$W"
```

Checked: both compiled languages equal the readings word for word, apart from
removing the conditional word’s literal parentheses and adding the identified
editorial instruction (268 Hebrew and 555 English whitespace-delimited words), four source page breaks (49–52), two notes
once each, no Hodu, both date outcomes, schema validity and resolved references.
The four-page review PDF includes the exporter's metadata. The printed Reader
passages carry matching subpart URNs; the PDF aligns the enclosing prayer as a whole,
so the final Reader lines need not sit at the same vertical position as their English.

## Hodu through Yehi khevod: printed 51–58, IA n75–n82

This installment ends **before Ashrei**, including neither its opening verses nor its
commentary. `chol_shacharit_pesuqei_dezimrah.xml` now starts at **Hareni mezamen**,
then Barukh sheamar, Hodu, Romemu, Vehu rahum, Hoshia et amekha, Psalm 100, and
Yehi khevod. Psalm 30 and Mourners’ Kaddish move to `chol_shacharit_opening.xml`,
which the index places immediately before this wrapper. Their text is unchanged.
The wrapper remains partial and can grow through the rest of Pesukei dezimrah.

### Biblical identity and composite paragraphs

The ordered paragraphs use `siddur:chol/shacharit/pesuqei_dezimrah/{incipit}` URNs,
as requested for this installment. Individual verses use `bible:` URNs. Hodu's
verses are I Chronicles 16:8–36; Psalm 100 has the chapter URN and five verse URNs.
The other paragraphs collect verses from different psalms; Yehi khevod also uses
I Chronicles 16:31, Proverbs 19:21 and Exodus 15:18. The edition's reference note
omits Exodus 15:18, so the encoded identification supplies it without altering the
printed note. “יְיָ מֶלֶךְ, יְיָ מָלָךְ” is liturgical text, not a complete biblical
verse, and has a `siddur:` subpart URN. The scriptural continuation uses Exodus's URN.

`pesukei_data.py` records each Hebrew/English verse pair read from the scan, including
page turns. `pesukei_passages.py` emits one canonical `corresp` per distinct verse.
Subsequent occurrences retain their own words with a biblical `source` pointer:
English I Chronicles 16:31 changes punctuation; Hebrew Psalm 20:10 has a meteg in
`הַמֶּֽלֶךְ` on 57 but not on 55. The occurrences are not silently harmonized.
Reader labels are outside the verse segments and appear only on the Hebrew side.

Inline transclusion of these segments currently fails the parallel compiler's
structural-frame reconstruction; citation pointers allow this installment to retain
biblical identity and paragraph alignment without changing the compiler. They identify
repeated scripture but do not create second canonical mappings or force an identical
reading. That implementation limitation is separate from the textual variation.

### Reading and verification

Read the scan first, including enlarged details, then compare resolved Wikisource
slices. The comparison is stored by passage (`transcription/*_51_58.txt`), since the
spans run across printed page turns. Verdicts and tallies are in the usual code-side
locations. The first reading's full/defective spellings and pointing were corrected
against the enlarged images; the retained `קִרְאוֹ` at Hodu's beginning is what the
print shows, despite the expected shuruq. The raw reading preserves the book rather
than correcting it to another Bible edition.

The Hebrew page starts the Psalm 100 omission rubric; its facing English page repeats
it. The conditional excludes 9 Tishri, 14 Nisan, and the conjunction of Pesaḥ and
Ḥol ha-Mo‘ed. It does not incorrectly exclude Ḥol ha-Mo‘ed Sukkot. Compilation checks
cover all three exclusions plus an ordinary weekday and Ḥol ha-Mo‘ed Sukkot.

The excerpt's primary and parallel bodies match their raw readings: 679 Hebrew and
1,306 English whitespace-delimited words, seven commentary notes, and no Ashrei or
Mourners’ Kaddish. Psalm 100 retains its complete biblical identity while its English
superscription starts on a separate line. The page turn inside English “for-ever”
is encoded inside the joined word “forever”. XML and URN validation pass.

Use the `feat_birnbaum-hodu` worktrees in all three repositories. The generated excerpt
is `output/birnbaum_hodu/parallel.pdf`; `output/birnbaum_parallel.pdf` is the complete
encoded book so far. Both use `specs/birnbaum_scan/settings_undecided.yaml`.
The environment's sandbox prevented running the schema container and snap-packaged uv;
validation used the main checkout's compiled schemas after confirming identical ODD
source, and its existing Python environment with imports from the new worktree.

From the new code worktree, regenerate with:

```bash
W=../../opensiddur-projects/feat_birnbaum-hodu/project
O=../../output/birnbaum_hodu
uv run python -m opensiddur.importer.birnbaum_scan.build.build_he --project-directory "$W"
uv run python -m opensiddur.importer.birnbaum_scan.build.build_en --project-directory "$W"
uv run python -m opensiddur.exporter.refdb --project-directory "$W"
uv run python -m opensiddur.exporter.compiler -p hasiddur_hashalem-birnbaum-1949-he \
  -f chol_shacharit_pesuqei_dezimrah.xml -s specs/birnbaum_scan/settings_undecided.yaml \
  --project-directory "$W" -o "$O/parallel.xml"
uv run python -m opensiddur.exporter.pdf.pdf "$O/parallel.xml" "$O/parallel.pdf" \
  -s specs/birnbaum_scan/settings_undecided.yaml --project-directory "$W"
```

For the entire book, compile `index.xml` instead of the excerpt filename.

## Ashrei through Half Kaddish: printed 57–70, IA n81–n94

The weekday Pesukei dezimrah wrapper now runs from Hareni mezamen through the
concluding Half Kaddish, inclusive. The preceding Mourners’ Kaddish remains in the
opening file. The next unencoded passage begins on printed 71–72.

`pesukei_completion_data.py` records the paired scan readings; `pesukei_completion.py`
builds their biblical mappings and printed order. Ashrei contains Psalms 84:5 and
144:15, the complete Psalm 145, and Psalm 115:18. Psalms 145–150 each have a chapter
URN containing all their verse URNs, with the Psalm 145 superscription inside verse
1. The remaining scripture uses verse URNs in Psalms, I Chronicles, Nehemiah,
Exodus, Obadiah and Zechariah. Composite liturgical arrangements use the siddur
namespace; Yishtabach and Half Kaddish use their prayer URNs.

Repeated scripture retains occurrence-specific text and a biblical `source` pointer.
The repeated Psalm 150:6 sits outside the complete chapter mapping; it is printed
only in Hebrew, so the English retains an empty corresponding division. Exodus
15:18 occurs twice in both languages; the Hebrew first occurrence spells לעֹלם
without vav and the repetition spells לעולם with vav. The preceding Yehi khevod
already defines the verse's canonical mapping. Nehemiah 9:8 retains a line break
before וכרות inside the same verse; Birnbaum's note explains the paragraph division
and the circumcision custom. No additional calendar condition is inferred from it.

Half Kaddish reuses the three shared Kaddish segments, including the standardized
Ten Days instruction and a conditional around only the second לעילא. Compilation
for 2026-01-15 yields one occurrence; 2026-09-16 yields two. Neither dated result
contains unresolved conditions or page breaks from the earlier Kaddish printing.

The page readings complete the previously partial 57–58 files and add 59–70 in
both languages. Enlarged scan bands were checked against the later Wikisource
comparison; the stored comparison slices, verdicts, and accuracy report document
the retained differences. Nineteen additional apparatus entries preserve the
printed commentary and numbered scripture references.

Verification: both projects validate; the URN registry has no errors or warnings;
each complete psalm has exactly its expected verses; the compiled wrapper contains
26 commentary notes. Its body matches the page readings (1,823 Hebrew and 3,524
English whitespace-delimited words), after removing the printed conditional's
literal parentheses. Focused importer tests pass (177 tests, 286 subtests).

Use the `feat_birnbaum-ashrei` worktrees in all three repositories. The review
excerpt is `output/birnbaum_ashrei/parallel.pdf`, and the entire encoded book is
`output/birnbaum_ashrei/full_parallel.pdf`. Build and compile commands are as in
the preceding installment, substituting these worktree/output paths; compile
`index.xml` for the full book. All previews use `settings_undecided.yaml`.

Visual review: the excerpt is 16 pages including metadata. Its Kaddish shows one
pair of brackets around only the added לעילא. The exporter aligns enclosing
passages, so English Psalm 145 continues below its Hebrew counterpart. Adjacent
commentary/reference markers at the same Ashrei anchor overlap in this preview;
both notes themselves are present and legible. This remains a rendering limitation.

## Shema and its blessings: printed 71–82, IA n95–n106

The weekday morning service now continues from Half Kaddish through Barekhu,
Yotzer or, Ahavah rabbah, Shema and Emet veyatziv, ending at Gaal Yisrael before
the existing Amidah instructions. `chol_shacharit_shema.xml` is a separate unit
between Pesukei dezimrah and the Amidah. The obsolete “before Ashrei” subtitle
has also been removed from the completed Pesukei unit's metadata.

`shema_data.py` contains the paired scan readings; `shema.py` builds the five
prayer files and wrapper. All twenty verses of Deuteronomy 6:4–9, 11:13–21 and
Numbers 15:37–41 have biblical URNs. The concluding Exodus quotations retain
occurrence-specific wording and biblical source pointers, since their canonical
mappings already occur in Pesukei dezimrah. The Kedushah responses cite their
partial Bible verses without claiming the entire verses. Barukh shem reuses the
existing prayer text inside an occurrence-specific siddur division, so its new
commentary does not attach to the earlier recitations.

Barekhu preserves the Reader, congregation-and-Reader and silent-meditation
rubrics. Reader labels within the blessings remain where the scan prints them.
El melekh neeman is conditional on `opensiddur:quorum/minyan = false`, as
requested. The conditional is inside its paragraph: unknown minyan status shows
the printed instruction and one bracket pair around only the addition. The
book's surrounding parentheses are retained in the raw reading, not doubled in
TEI. Compilation with minyan true omits the addition; false includes it. The
Reader's three-word repetition is discussed in Birnbaum's commentary but is not
separately printed in the body; the encoding does not invent another occurrence.

Page breaks include the English division inside “compassionate.” Printed 81's
Hebrew raw reading is completed before its existing Amidah portion; the new
English 82 raw file contains only this installment's pre-Amidah text. Sixteen
apparatus entries preserve the commentary and numbered references. Enlarged
scan bands were used to decide the later Wikisource comparison; passage slices,
verdicts and measurements are recorded alongside previous installments.

Checks: the new files and both indexes pass RelaxNG/Schematron validation; the
URN registry has no errors or warnings. Compiled bodies match the scan readings
(952 Hebrew and 1,827 English whitespace-delimited words), all twenty Torah
verses are present in order, and all sixteen apparatus notes survive compilation.
Both minyan settings resolve correctly. The focused importer suite passes
177 tests and 302 subtests; its existing unit-order expectation includes Shema.

Worktrees in all three repositories: `feat_birnbaum-shema`. Build commands are
as above with that worktree name. Compile `chol_shacharit_shema.xml` for the
excerpt or `index.xml` for the whole book. The previews are
`output/birnbaum_shema/parallel.pdf` and
`output/birnbaum_shema/full_parallel.pdf`, using `settings_undecided.yaml`.
As before, validation uses copied compiled schemas after verifying identical ODD
source, because the local schema container cannot start in this sandbox.

Visual review: the excerpt is ten pages including metadata. The private addition
has one bracket pair in each language and the excerpt ends at Gaal Yisrael.
Existing exporter limitations remain visible: enclosing prayer alignment leaves
unequal column lengths, and multiple apparatus markers at one anchor can overlap.
The note bodies are present; those rendering issues are not new encoding rules.
The regenerated full parallel is 88 pages, also copied to
`output/birnbaum_parallel.pdf`. Each new prayer is transcluded once in the full
book; Shema's compiled division is split around its shared Barukh shem transclusion.

## Weekday Arvit, printed 189–220 (IA n213–n244)

The service is addressable as `siddur:chol/arvit`, with section wrappers for the optional
opening, blessings before Shema, Shema, blessings after Shema, Amidah, Kaddish, Alenu,
seasonal Psalm 27 and the house-of-mourning Psalm 49. The wrappers declare `maariv`
and silent recitation; repetition is false even if a containing export selected the
Reader's repetition for daytime services. Conditions for whole prayers belong to these
callers. Shared Shema, Amidah, Kaddish and closing texts retain their existing URNs and
receive the additional Arvit printings and page turns.

`opensiddur:service-context / immediately-after-minha` is a boolean supplied by the
caller. True omits the Psalm 134 opening; false includes it on ordinary weekdays;
undefined leaves the opening MAYBE with Birnbaum's rubric. Saturday night instead
retains the printed direction to Psalms 144 and 67 on pages 535–536. The Saturday-night
continuation after Half Kaddish and the Omer counting are likewise printed directions
to later pages, whose texts are not included in this installment.

Ata Chonantanu is selected on Hebrew Sunday at Arvit or the night following the last
festival day, with separate Israel/Diaspora dates. The shared knowledge blessing has
milestone boundaries around its opening and conclusion to allow the insertion; its
Hebrew conjunction is conditional on that same Arvit occasion. Shalom Rav is used as
printed; the fast-day Sim Shalom choice in Mincha does not carry over into Arvit.

Psalm 27 uses the previously confirmed seasonal endpoint, and Psalm 49 uses the existing
house-of-mourning setting (MAYBE in the undecided edition). A printed instruction to say
Kaddish is realized by transcluding it, without a second redundant instruction after it.

## Before the Sabbath service, printed 221–236 (IA n245–n260)

`shabbat/preparations` groups the Sabbath candle-lighting blessing, parental blessing,
and complete Song of Songs. It has its own bookmark hierarchy and follows weekday Arvit
in the index; it does not claim to be the complete Sabbath service.

Song of Songs uses `bible:song_of_songs`, eight chapter divisions, and 117 biblical verse
milestones. The Hebrew and English preserve their own paragraphs and page turns;
English 7:1 and 8:5 each cross a paragraph boundary within a single verse. Chapter 7
begins with “Return, return”, following the printed Hebrew numbering. The small written
form marker at 2:13 is retained as `tei:choice` with `j:written` and `j:read`.

The shared priestly blessing gains biblical milestones for Numbers 6:24–26 and its
additional printing at 221–222. The parental blessing transcludes that biblical range.
The sons’ opening quotes only part of Genesis 48:20 and retains that source on a bounded
quotation; the daughters’ opening has its own prayer URN. Select these formulas with
`opensiddur:blessing-recipient / gender` (`male` or `female`), not the reciter’s personal
setting. An unspecified recipient keeps both alternatives MAYBE with the printed rubrics.

All forty commentary/citation entries on these pages are retained, including the two
introductions continued across pages. Preserve Birnbaum’s translation even where it
differs from a familiar Bible rendering, notably “do not tell him” (5:8), “Your chest”
(7:3), and “topaz pink” (5:14).

## Kabbalat Shabbat, printed 237–250 (IA n261–n274)

`shabbat/kabbalat_shabbat` contains Psalms 95–99 and 29, Ana Bekoach and Barukh Shem,
Lecha Dodi, the welcome for mourners, Psalms 92–93, and Mourners’ Kaddish. Its separate
`shabbat/kabbalat_service` caller applies the whole-service festival omission. The book
index groups it and the preceding preparations under `shabbat`, outside `chol`.

The calendar is that of the incoming Shabbat. When Shabbat itself is Yom Tov, omit the
whole section. When the preceding Friday is Yom Tov, begin at Psalm 92; use the last
festival day appropriate to Israel or the Diaspora. The Friday exception is in the
section wrapper, not in the reusable psalm or poem files. Unknown calendar settings
remain MAYBE with explanatory rubrics. `opensiddur:service-context / mourners-present`
is a separate, initially unknown setting for the condolence formula; it must not be
inferred from the reciter being a mourner or from a house-of-mourning setting. Kaddish
uses the existing minyan gate and Ten Days of Repentance wording.

All eight psalms (86 verses) have biblical chapter/verse addresses. Full chapters now
own the six biblical addresses previously carried by isolated excerpts from Psalms
29, 95 and 99. Those earlier excerpts keep their exact printed text, local milestone
correspondences, and biblical `source` spans. This prevents ambiguous resolution while
preserving such differences as “powers” in the Wednesday Psalm 95:3 excerpt and “gods”
in its complete chapter. Psalm 93 is transcluded from the earlier Friday psalm.

Ana Bekoach is shared in full, with seven stanza milestone ranges added. Enlargement
of printed 243 confirms `ושמע` in line seven; it is not a variant omitting the conjunction.
Barukh Shem and the five Kaddish paragraphs also reuse their existing texts. Shared
passages retain their earlier stress marks and punctuation, and any commentary already
attached to their canonical text remains available at the repeated occurrence.

Lecha Dodi has nine stanza milestones and separately addressed refrains. Printed 243
has the opening refrain twice in Hebrew, while 244 translates it once; retain that
asymmetry. Hebrew stanzas have four hemistichs, represented by four `tei:l` elements;
English stanzas are paragraphs. Preserve the instruction before the stanzas and the
instruction to rise and turn toward the door before the last stanza. Biblical allusions
in the poem do not make it a sequence of complete biblical verses: it uses poem URNs.

The thirteen new commentary paragraphs are represented by twelve entries: the two
paragraphs on Psalm 93 share one occurrence-specific anchor. Join commentary continued
across facing pages. English biblical verses and paragraphs have independent boundaries,
notably within 95:9, 96:10, 96:13 and 98:9. Hebrew Reader cues close the preceding verse
scope before the instruction and reopen at the following verse.

## Bameh Madlikin — printed 251–256 (IA n275–n280)

The Kabbalat Shabbat wrapper now continues through all seven mishnayot of Shabbat
chapter 2, the Rabbi Elazar passage from Berakhot 64a, and Kaddish d’Rabbanan.
The direct six-page reading is in `scan_reading/readings/bameh_madlikin.md`.

The chapter uses `mishnah:shabbat/2` and `mishnah:shabbat/2/1`–`/7`, with
`unit="mishnah"` milestones independent of page breaks. Its festival omission
belongs to the study caller, not to the reusable chapter. “Omitted on festivals”
is interpreted to cover both a festival Friday and a festival Shabbat; the former
uses the existing incoming-date calculation with Israel/Diaspora distinctions.
The following Rabbi Elazar passage and Kaddish are outside that chapter gate.
The service caller still omits the entire Kabbalat Shabbat on a festival Shabbat.

The Talmud excerpt uses `talmud:berakhot/64a/amar_rabbi_elazar`; its biblical
quotations retain local milestones with biblical `source` spans. This preserves
Birnbaum’s wording while leaving canonical biblical mappings unambiguous.
Eleven commentary paragraphs and both numbered source notes are encoded, including
the continued דמאי note. Notes sharing an anchor retain separate paragraphs.

The closing Kaddish is separate from the chapter, with its own bookmark and minyan
gate. Its Hebrew and five English paragraphs reuse the earlier Kaddish d’Rabbanan.
The English peace petition here says “and a happy life”, where printed 48 says
“and life”; an occurrence-specific realization preserves this difference without
changing the earlier prayer. Shared printings retain the earlier stress marks
and punctuation. The second לעילא uses the established Ten Days conditional
and its instruction, without duplicating the print’s parentheses.

The local peace petition derives its Hebrew from the shared importer reading;
five other Kaddish paragraphs are transcluded. Both sides use the local milestone
for this petition, keeping their paragraphs aligned. The exporter also displays
earlier commentary attached to shared Kaddish texts at this new occurrence;
those inherited notes are additional to the thirteen paragraphs on these pages.

## Sabbath morning Kiddush and table hymns (printed 423–436; IA n447–n460)

`shabbat_day_meal.py` continues immediately after Musaf's Adon Olam. The addressable
`shabbat/day_meal` wrapper contains `kiddush` and `zemirot`; the latter contains all
five hymns, with child bookmarks. The direct readings and ten commentary notes are
recorded in `scan_reading/readings/shabbat_day_meal.md` in sourcetexts.

The three new poems are Barukh Adonai Yom Yom, Barukh El Elyon, and Yom Zeh Mekhubad.
Stanzas and refrains use milestones. Yah Ribbon and Tzur Mishelo transclude their
matching Friday-night stanzas and refrains; local variants preserve the second
printing's English “Supreme”/“lion’s” and Hebrew `בָּא`. The wine blessing and Exodus
31:16–17 are shared. Exodus 20:8–11 retains the Kiddush printing's unnumbered text,
pointing, and divine-name spelling, with local milestones and biblical source spans,
without redefining the earlier Decalogue's canonical verse correspondences.

Full Hebrew refrains face the abbreviated English incipits exactly where printed.
The paired compilation was audited for all 63 verse/stanza/refrain text units, ten
commentary notes, and matching milestone alignment. The apparent printed citation
error “Jeremiah 60:34” remains prose in the commentary, not a fabricated Bible URN.

Regenerate with `build.build_he` and `build.build_en`, pointing `--project-directory`
at the projects worktree. Validate the changed XML, sync both Birnbaum projects, and
run `opensiddur.common.urn_registry --check` with that project directory **and its
synchronized reference database**. Compile `shabbat_day_meal.xml` for the focused
proof and `index.xml` for the complete parallel. The focused proof is ten pages
including credits. Importer and registry regression checks: 296 tests and 1,103
subtests passed; registry: zero errors and warnings. The previously compiled prayer
text remains an unchanged prefix in both languages.


## Pirkei Avot (printed 477–534; IA n501–n558)

The entire unit is `urn:x-opensiddur:text:siddur:pirkei_avot`, with six independently
addressable chapter wrappers at `/1` through `/6`. Each wrapper includes its printed
Kol Yisrael and Rabbi Hananya formulas around the chapter text. The chapter texts
use `urn:x-opensiddur:text:mishnah:avot/{chapter}/{mishnah}` milestones. Birnbaum’s
printed paragraph numbers and page-spanning paragraphs remain independent of the
canonical boundaries. The appended sixth chapter uses the conventional Avot 6
address; the printed explanation of its origin remains in the apparatus.

Three uses share these files:

* In the siddur, `opensiddur:pirkei-avot/season` gates the whole transclusion,
  with Birnbaum’s seasonal rubric in the caller. The caller also requires at least
  one selected chapter, avoiding an empty Avot heading on a skipped week.
* Inside Avot, six independent `chapter-1` through `chapter-6` features gate
  the chapter transclusions. Known Hebrew date and Israel/diaspora location derive
  the weekly selections; missing inputs leave them MAYBE, with editorial instructions.
* For the complete independent text, set all six chapter features to TRUE, and
  `season` as well if compiling through the siddur caller. Each selection rubric is its
  `j:conditional`'s own, so a chapter known to be read prints without it.
  Explicit chapter values override calendar derivation, including combined chapters.

The complete preset is `specs/birnbaum_scan/settings_avot_complete.yaml`. Without
calendar inputs, all chapter selectors and the seasonal selector remain unknown, and
each chapter is printed with the rubric that says when it is read.

The weekly schedule follows Hebcal’s summer cycle:
https://github.com/hebcal/learning/tree/main/pirkeiavot . It begins after Pesach
(allowing 22 Nisan in Israel), skips Shavuot and Shabbat on 8 or 9 Av, repeats three
single-chapter rounds, and combines the final chapters before Rosh Hashanah.
In the shortest seasons the final round has only 3–4 and 5–6. This is an editorial
calendar convention, not additional wording attributed to Birnbaum.

Readings and corrections live in `scan_reading/readings/avot-477-534.json`,
`avot.md`, and `avot-corrections.json` in sourcetexts. Both XML projects are generated
by `build.build_he` and `build.build_en`; `notes_avot.py` preserves commentary and
printed source citations, with directional markup on Hebrew catchwords and quotations.

## Hanukkah, Megillat Hashmonaim and Purim (printed 709–730; IA n733–n754)

`hanukkah_purim.py` adds the Hanukkah lights, all six Hebrew Maoz Tzur stanzas,
the 76-verse Megillat Hashmonaim, and Purim’s Megillah blessings and concluding
poems. The source audit is `scan_reading/hanukkah_purim/` in sourcetexts, including
unchanged initial readings and the enlarged-scan adjudication ledger.

The addressable book sections are `siddur:chanukah` and `siddur:purim`.
`prayer:megillat_hashmonaim` is independently reusable: its verse milestones
preserve Hebrew-only printed numerals while the two languages retain their own
paragraph breaks. It is not assigned biblical URNs. The quotation in verse 39
uses bounded biblical source spans. Maoz Tzur’s untranslated sixth stanza keeps
an empty English alignment anchor. Shared Shehecheyanu and Sheasah Nissim are
transcluded, with the additional printings recorded.

Shehecheyanu is selected on the first Hanukkah night. The Purim caller omits
Asher Heni in the morning but always includes Shoshanat Yaakov and its concluding
lines. The printed “On Purim morning:” instruction marks the starting point; it
neither gates the following poem nor creates an empty conditional bracket.
All seven notes are in `notes_hanukkah_purim.xml`, with the two-page introduction
to Hashmonaim joined once and Hebrew catchwords explicitly marked for direction.

Regenerate both projects with `build.build_he` and `build.build_en`, as above.
Compile `hanukkah.xml` and `purim.xml` with `settings_undecided.yaml` for the focused
parallel proofs; `index.xml` includes them at the end of the encoded book.


## Concluding prayers (printed 753–790; IA n777–n814)

`concluding_prayers.py` encodes marriage, meals, miscellaneous blessings, bedtime
Shema, children's bedtime prayer, and the State of Israel prayer. Both project
indexes include the hierarchical `siddur:concluding_prayers` wrapper. Compile
`concluding_prayers.xml` with `settings_undecided.yaml` for the focused proof.
The source audit, original readings, reviewed readings, notes, rubrics, correction
ledger and machine comparisons are in `scan_reading/concluding_prayers/`.

The ceremony's seven blessings put wine first; `prayer:sheva_berakhot/after_meal`
puts it last, as the user specified. Ordinary, wedding and Brit Milah Grace share
`prayer:birkat_hamazon` components. Brit Milah inserts its Harachaman after Bamarom.
Calendar additions derive from the existing holiday and day-of-week settings.
Migdol uses a day on which Musaf is recited, independent of the current service.

`opensiddur:meal-context` accepts booleans `zimmun`, `guest`, `wife-and-children`,
`father-is-host`, and `mother-is-host`; `meein-shalosh-food` is one of `wine`,
`fruit`, `cake`, `cake_wine`. Unspecified values remain MAYBE. The existing
`opensiddur:quorum/minyan` controls Eloheinu in zimmun. Me'ein Shalosh's four
Hebrew food alternatives use empty English anchors without empty English
conditionals: Birnbaum translates them generically, not individually.

The last three English page numbers are direct scan evidence in the correspondence
importer; regenerate pages.json rather than editing it. The final English page
belongs to the body together with its facing Hebrew page.
