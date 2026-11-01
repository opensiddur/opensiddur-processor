# Asher 1912 scan subsection

Load for Archive item `selichothdavidasher1912`: David Asher’s Selichoth,
Vallentine & Sons, London, 1912–5672 reprint (first published in 1866).
This is the edition linked by opensiddur-processor issue 207.

## Evidence and pagination

The scan has 411 leaves, reported dimensions 2013×3106. Address pages by `sN`
(one-based scan identity, IA leaf N−1), never by printed label alone: Hebrew and
English sides share a printed number. Record both the printed Hebrew label and
its numeric value when verified. Language and translation pairing are independent
of physical left/right position and must be verified from images.

Archive’s page-number JSON is sparse and wrong in places: IA leaf 30 prints 14,
not its machine label 1. Scandata lacks printed labels. Retain the metadata as
candidate evidence and apply explicit image-verified corrections to derive pages.json.

Use shared scan tools with `--book asher_selichot --source-root <sources>`.
Images and crops live under `output/asher_selichot/`; evidence belongs under
`sources/asher_selichot/`. No Wikisource check is required or currently established.
Archive OCR was configured for English: compare it with English readings only.
For Hebrew, read independently from images and record the second reading’s scope.
Do not auto-settle qamats-qatan or assume Birnbaum’s punctuation/glyph conventions.

## Refrain and prayer interpretation

- Leaf 2: English title and imprint, explicitly dated 1912–5672.
- Leaves 31–32: Hebrew טו / English 15, במוצאי מנוחה and its translation.
- Leaves 23–26: Hebrew יא–יב / English 11–12, containing אל מלך יושב
  and ויעבור plus adjacent texts. Encode only the referenced ranges as dependencies;
  retain boundary context in readings and identify the slice precisely.
- The Hebrew poem has English rubrics with embedded Hebrew. Preserve their language
  boundaries and direction; its translation is prose, not matching printed verse lines.
  Align semantic stanzas, keeping Hebrew lineation and English paragraphs independent.
- Refrain cues such as לשמוע and “Hearken, &c.” are printed abbreviations.
  Store cues in `abbr` and the complete verified refrain in `expan`; the final
  “On the outgoing, &c.” refers to the opening stanza, not just the short refrain.
- The concluding “Say …” points back to אל מלך יושב and ויעבור. Documentary
  output retains the instruction. Expanded output replaces it with transclusions of
  this edition’s encoded prayers, and omits the opening refrain-repetition rubric
  when the refrains are expanded. Never substitute another edition’s wording.
- Retain the English footnote on page 15 and verify it appears once.
- Document every expansion and target range in the source README. Do not attribute
  expanded words to printing on a leaf where only a cue appears.

## Output and measurement

Use `readings.abbreviations: abbreviated` for the documentary edition and `expanded`
for prayer-use output. Both are release books, in opensiddur-projects
`settings/asher_selichot/`. Releases set the Hebrew in Ezra SIL, and the PDF
checks measure from it (rows 17.5-18.3pt apart; mutool splits its Hebrew lines by
word, so group Hebrew by baseline). Verify both compiled and rendered outputs; derive row/column
thresholds from their actual typography rather than copying Birnbaum’s numeric values.

The edition uses SBL Hebrew at 12pt because the available CLM faces lack U+00B7.
Its measured gutter is x=288pt on odd PDF pages and x=324pt on even pages.
All expanded stanza starts share a baseline. In documentary output, the first
differs by 13.55pt after unequal rubric lengths; the other seven share a baseline. The poem check allows at most 16pt and requires the same page.
These are edition calibration values, not defaults for other settings or scans.
For a first-day-only export, run `python -m opensiddur.importer.asher_selichot.check_pdf PDF --complete --control`
(with `--expanded` for the expanded view). The shared direction check separately
reverses Hebrew glyph runs as its failing control.

## First-day continuation

`sources/asher_selichot/poetry-structure.json` records image-verified Hebrew
lineation for the first-day litanies and additional poems. Mi Sheanah on s46
(Archive n45, printed 22) has 20 verse lines with terminal הוא יעננו refrains;
Anenu on s44 has 35 terminal עננו responses. Rahmana on s46 has four ענינא
responses followed by different petitions. Keep each response inside its verse
as `tei:seg type="refrain"`; do not repeat it editorially or turn it into a
heading. Raised dots can delimit poetic clauses in these specified units, but
are not a universal rule making every dotted prayer a poem. The English
translations retain their independently printed prose or litany breaks.

The Hebrew and English title pages are Archive leaves n1 and n2. The first-day
opening is n5/n6; its first printed numeral is 3 on n7/n8. Do not assign a printed
number to the opening from the contents table or a later cross-reference.
Psalm 145:9 continues across n5→n7 and n6→n8 within a prose paragraph; retain the
source page break within the verse rather than inventing a verse boundary.

The first day ends partway down n51 (Hebrew) / n52 (English), after the Reader’s
Kaddish instruction and before the large second-day section heading. The running
heading on n51 already says second day; it does not establish the section boundary.
Keep these verified target limits separate from encoded coverage. A partial
entrypoint must identify its actual contiguous coverage and must not bridge pending
pages with isolated excerpt modules. Record progress in `first-day-scope.json`.

The opening has a Latin `Ps. cxlv.` citation on the Hebrew page. Verify
both its increasing glyph x coordinates and its placement in the Hebrew column;
Hebrew-only direction checks cannot detect its reversal or column displacement.
Use `python -m opensiddur.importer.asher_selichot.check_first_day_pdf PDF --control`
for the first-day settings; use `--complete` when rendering through n52. Its 16pt baseline limit is measured for this
output, not a general scan requirement.

For normalized authoring of this edition’s Hebrew text, encode Hebrew two-dot verse stops as U+05C3
HEBREW PUNCTUATION SOF PASUQ (׃), not U+003A COLON (:). Attach these stops and
other closing punctuation to the preceding word. Do not carry the scan’s visual
gap into XML as an ordinary breakable space: TeX can strand the punctuation on a
new line. Preserve physical spacing in the first-pass evidence and document its
normalization. The opening PDF check must reject isolated punctuation lines.

For a contiguous first-day edition, place the reusable prayers and poem at their
original n23–26 and n31–32 positions after encoding intervening text. Pair complete
prayers across languages: facing pages do not necessarily end at equivalent words,
and some litanies order phrases differently. Retain printed footnotes at their
anchors and record apparent citation errors as edition evidence. Verify the final
Reader’s Kaddish rubric, and exclude the second-day text below it on n51/n52.

The recurring אלהינו ואלהי אבותינו invocation belongs to the piyyut’s opening
text, including its English translation. Its visual separation does not make it
a heading: encode it within the Hebrew verse group and English prose paragraph.
Identify the piyyut by the distinctive incipit that follows (for example,
אין מי יקרא בצדק), recording this as an incipit rather than inventing a printed
heading or asserting an independently verified formal title. Preserve the edition’s
spelling and pointing. Only actual section headings belong in `tei:head`.

## Expanded first-day service

Replace fulfilled “Say …” cues with transclusions of their verified target ranges,
including repeated scriptural petitions and Ashamnu. Keep documentary and expanded
entrypoints sharing their source modules through conditional instruction/transclusion
branches. The poem module conditionally supplies its concluding prayers next to
the printed cue; both book views use the same `first_day.xml` assembly.
The final Kaddish Titkabel is not printed in this Asher range. For this
expanded edition, transclude the unqualified Full Kaddish URN
`urn:x-opensiddur:text:prayer:kaddish/shalem`; select Birnbaum’s Hebrew and English
projects as fallbacks in opensiddur-projects `settings/asher_selichot/expanded.yaml`. Preserve that provenance
in documentation and do not present the supplied prayer as an Asher scan reading.
Verify all six Full Kaddish parts, including Titkabel and the closing peace passages,
and check the English column retains its configured secondary-source fallbacks.

For mixed-language footnotes, preserve the explicit language on each paragraph;
the English explanation must not inherit the Hebrew note’s direction. Inspect
Latin glyph positions in the apparatus as well as Hebrew runs and the Psalm
citation. MuPDF can split reversed Latin text into single-character lines, so
group apparatus glyphs by page, font and baseline before measuring their order.
The first-day settings measure apparatus at 9.826pt; their check inspects Latin
runs at sizes up to 10pt. This cutoff is a calibration for these settings.

The first-day Selichot is never during the Ten Days of Repentance. Immediately
before its final Full Kaddish transclusion, declare a scoped first-day Selichot
context and set `opensiddur:holiday-aggregate/aseret-ymei-tshuva` explicitly false.
Close the declaration after the prayer, restoring the caller’s settings. Do not
leave this date-dependent addition undefined or allow an unrelated default date
to activate it. Verify that neither the extra לעילא nor its Ten Days rubric is
present in this final Kaddish, even when the caller supplies a conflicting setting.


## Reusable book structure

`index.xml` and `expanded.xml` are the documentary and expanded book entrypoints,
with both title pages and the currently encoded first day. Both reference the
single `first_day.xml` assembly, which directly transcludes named texts and retains
printed rubrics in source order. Do not create opening/preface/before-piyyut/closing
subdivision files: these were authoring batches, not printed service divisions.
An expanded first-day assembly is redundant because cue replacements are
conditional within the shared text modules and service rubrics.

## Day gates in the running order

Every service with a calendar day is gated on it in `index.xml`/`expanded.xml`, from
`asher_selichot/occasions.py`, using only calendar-derived features. A dated edition
prints that day's service; an undated one prints all of them, silently. The Elul days
follow the first-day rubric (from the Sunday before the New Year, or the Sunday a week
earlier when it falls on Monday or Tuesday; never on the Sabbath) and are said in
order, so a short year never reaches the later days: Rosh Hashanah on Thursday gives
three, on the Sabbath five, on Monday six, on Tuesday seven. Each gate is the union of
its Hebrew date and weekday over Rosh Hashanah's four weekdays. The Ten Days always
hold four weekdays between Tzom Gedaliah and Erev Yom Kippur, which are Asher's second
to fifth penitential days in order. Elul gates declare `aseret-ymei-tshuva=false` and
Ten Days gates declare it true. Circumcision is ungated: no calendar knows it, and a
condition on `opensiddur:override` would drop it from every undated edition.

Use `ashrei.xml` with `prayer:ashrei` and `kaddish_chatzi.xml` with
`prayer:kaddish/chatzi`. The distinct piyyutim have their own files and `poem:`
URNs named for their distinctive incipits: `ein_mi_yiqra_betsedeq`,
`im_avoneinu_rabu_lehagdil`, `tavo_lefanekha_shavat_hinnun`, and
`bemotzaei_menuhah`. The common invocation remains in each poem's opening.
Reusable prayers and repeated verse ranges likewise use prayer identities,
independent of Asher or the day on which this source prints them. The source
README's module table records the reading-ID to filename/URN correspondence.
Do not add experimental-phase labels to titles, filenames or canonical identities.


## Second-day continuation

The second day begins below the first-day closing rubric on n51/n52 and ends
above the third-day section heading in the middle of n59/n60. These openings
print 25–29 in both languages; do not treat the final running third-day heading
as a section boundary. Use the printed day heading as the top-level service
heading and its printed Hebrew פזמון as a subordinate heading. Do not invent an
English pizmon caption where none is printed. Enable
`typography.table_of_contents.enabled: true` with `depth: 2` in these export settings.

Israel Nosha has six Hebrew verse groups paired with English prose paragraphs.
Use named stanza milestones to align them; retain page breaks inside a continuing
verse. Four כי אתה cues expand the edition’s full refrain; the final וישראל נושע
cue expands the first stanza including its refrain. The seven English footnotes
include two distinct occurrences of “The three patriarchs.” Keep the unusual
singular “God of our Father!” as printed, pending any documented adjudication.

The second-day opening rubric reuses the printed first-day ranges through
כי רבו עוונינו, then El erekh apayim through ורב חסד לכל קראיך. Its conclusion
reuses the closing range beginning Zekhor rahamekha and a secondary-source Full
Kaddish. Preserve first-day context only for the first day: second-day Kaddish
must not inherit `first_day=true`. Scope its copied pre-Rosh-Hashanah conclusion
with `first_day=false`, `aseret-ymei-tshuva=false`, then restore caller context.
Expanded output omits each instruction whose prescribed text is present.

Use `python -m opensiddur.importer.asher_selichot.check_book_pdf PDF --control`
(and `--expanded` for that view) for the two-day book. It scopes the older
first-day checks to the bookmarked first-day range, excludes the generated TOC,
and independently checks second-day stanzas, notes and expansion boundaries.

## Third-day continuation and swapped openings

The third day starts below the second-day conclusion on n59/n60 and ends above
the fourth-day section heading on n67/n68. Its verified printed page sequence is:

| Printed page | Hebrew scan / Archive leaf | English scan / Archive leaf |
|---|---|---|
| 29 | s60 / n59 | s61 / n60 |
| 30 | s62 / n61 | s63 / n62 |
| 31 | s66 / n65 | s67 / n66 |
| 32 | s64 / n63 | s65 / n64 |
| 33 | s68 / n67 | s69 / n68 |

The Archive openings for 31 and 32 are swapped. Read in image-verified printed
order while retaining actual scan identities on facsimile links. Record the
ordering evidence in `third-day-scope.json`; never infer a missing page solely
from a discontinuity in the physical scan sequence.

The three independent piyyutim use incipit identities `eqra_beshimkha_lehahaziq_bekha`,
`taarog_eilekha_kaayal`, and `shahar_qamti`. Shahar qamti has six Hebrew verse
groups paired with English prose, four נפשי refrain choices, and a final שחר
choice supplying its entire opening including the refrain. The last English
full refrain ends with a period, while the first ends with an exclamation mark;
retain each printed occurrence. Keep all eight English footnotes at their
image-verified anchors. The Palestine note follows “thy poor people.”

The small Hebrew-only repeated-verse instruction on printed 31 retains Hebrew
language and direction; mixed English/Hebrew rubrics retain their own language
spans. Expanded day-three instructions follow the same verified opening,
repeated-verse, prayer-pair and conclusion ranges as day two. Scope its secondary
Full Kaddish with its own declaration, `first_day=false` and Ten Days false.

Running page headers are pagination evidence, not body headings. In particular,
“PROPITIATORY PRAYERS FOR THE FIRST DAY.” above Bemotzaei menuhah is an English
running header: retain it in source evidence, omit it from the poem body and
TOC, and preserve the actual Hebrew פזמון heading. The day headings remain
at the top bookmark level, above the piyyut's printed heading.

## Days four through seven

Use the large body headings to delimit these days; the running headers can
announce the following day before its body begins. The paired ranges overlap
because two days share a printed page.

| Day | Archive leaves | Pizmon stanza groups |
|---|---|---|
| Fourth | n67–n76 | 5 |
| Fifth | n75–n84 | 8 |
| Sixth | n83–n92 | 5 |
| Seventh | n91–n100 | 9, including the opening refrain |

Keep independently printed Hebrew and English cue positions. In day five,
“O extend thy grace” follows the ocean stanza's English refrain cue, while
its Hebrew counterpart precedes that cue. Do not move the English sentence
across the cue to match Hebrew grouping. Day five prints only two prayer-pair
instructions; the other days in this table print three.

The sixth-day final חוקר cue appears only in Hebrew. Expand its verified Hebrew
opening without inventing an English cue or repetition. Day seven prints an
additional English `(Help us, &c.)` after its opening full refrain; preserve that
English choice without adding a Hebrew counterpart. Its Hebrew repetition rubric
names נשענו and עזרנו in reverse order: preserve the documentary wording and use
the complete image-verified refrain for expansion, documenting the resolution.
The English page-47 numeral is not visible: keep its printed label unknown and
record page 47 and translation pairing as separately verified evidence.

Bind this edition's spaced Hebrew phrase dots to the preceding word using a
nonbreaking space, including prose and expanded choice branches. Preserve it
through Unicode normalization; NFKD alone turns U+00A0 into a breakable space.
Check the serialized XML and rendered glyph rows for stranded dots (SBL Hebrew
extracts the printed dot as ∙). Stop day seven at its closing Kaddish cue before
the large Erev Rosh Hashanah heading on n99/n100. Source scope/proofreading files
record the detailed boundaries and unresolved independent Hebrew review.

## Erev Rosh Hashanah

The service begins under the large body heading on n99/n100 (printed 49) and
ends at the Reader’s Kaddish cue on n183/n184 (printed 91), before Gedaliah.
It has two pizmon headings; keep each above its repetition instruction and below
the service heading. The English page heading is “DAY BEFORE NEW YEAR”.

Read Hebrew and English repeat instructions independently. Most Hebrew cues add
רחמיך רבים and אל תבוא from printed 52 before the familiar כרחם אב range;
most English cues begin at “Like a father” on 9. The printed-58 English cue instead
begins at “Thy mercy is great” on 52. After Shofet kol haarets, Hebrew stops before
the Daniel verses, which follow in full on 71, while English explicitly repeats
them. Keep Ark instructions when expanding: after Shelosh esreh middot the Ark
opens between El melekh and Vayaavor; after Shofet the Hebrew closes it before
the pair, but English closes it after the pair. Scope the final secondary-source
Full Kaddish with first_day=false and Ten Days=false.

Zekhor berit alternates two different refrains; do not apply a single-refrain
pizmon default. Both its final Zekhor cue and Shofet’s final cue repeat the complete
opening. Preserve bracketed responses in Shelosh esreh middot, including the
closing bracket attached to its verse. Tefillah teqah contains 26 printed superscript numbers with no identified
targets. Preserve them as unresolved printed note markers; do not describe them
as references or presume that explanatory notes exist. Its English
body contains לשון הרע and needs an explicit Hebrew language span.

When Erev cues refer to printed 52, use that page’s bounded reprinted petitions
(`prayer:kerachem_av`, `prayer:selichot/ki_lo_al_tzidqoteinu`), preserving their
wording and punctuation. English cues citing 9/10 use the earlier ranges; do
not assume that repeated passages are identical.

Expanded repeat cues can list different petitions in Hebrew and English. Set
them as one paired prose paragraph with inline transclusions and a shared
alignment milestone for the cue; retain bounded prayer targets in the source
modules. Separate external blocks for unequal target lists can shift later
translations. Verify the compiled pairings and the page-52 translation wording
before rendering, in addition to checking passage starts in the PDF.

Use `python -m opensiddur.importer.asher_selichot.erev_rosh_hashanah
<compiled-expanded.xml>` before the PDF build to check all 12 expanded
petition pairings; it rejects lost page-52 translation wording.

Transliterate אלוהַּ as `eloah`; use `el_eloah_dalefah_eini` for the poem
filename and canonical identity.

## Tzom Gedaliah

The large service heading begins below Erev on n183/n184, printed 91. The complete
service ends at the final conclusion cue on n207/n208, printed 103. Keep the
service heading above its Hebrew-only פזמון heading in the bookmarks and contents.
Horita derekh teshuvah has eight shared stanza units across printed 99–100, with
seven abbreviation choices per language. The English Reuben/Judah stanza repeats
its refrain between the two examples; Hebrew repeats after both. Preserve the
cue's independently printed position and the page break inside the continuing verse.

The opening repeats the earlier page-1/2–7 range, ending at Shomea tefillah’s
“for it is great,” before the reprinted Selah lanu. The abbreviated Hebrew
כי רבו citation is ambiguous; document the editorial boundary supported by
the explicit English cue and adjacent reprint. Do not duplicate Selah lanu. The preliminary prayer pair uses
El erekh apayim and preliminary Vayaavor; later pairs use El melekh and Vayaavor.
Hebrew petition cues name additional introductory petitions; English cites 9/10.
Keep unequal lists in one paired inline-transclusion paragraph, as for Erev.
The closing repetition ends at גמירא בשביא, including Mahi umasi. The final cue
starts at מכניסי רחמים, excluding Mahi umasi. These are separately bounded ranges.
In the secondary-source Full Kaddish declare first_day=false and Ten Days=true,
then restore caller context. Gate the service in the index with the calendar's
`opensiddur:holiday/tzom-gedalia`; an undecided gate has no printed instruction.

English printed 103 has a marginal Hebrew note עשרה הרוגי מלכות without a visible
matching body marker. Preserve it with an explicitly documented editorial attachment
to the final cue, carried into expanded output; do not claim its original target.
In the combined PDF, this apparatus can sit below the following service heading
on the same page. Retain the known Gedaliah note when clipping its body for checks;
a vertical body boundary alone cannot establish apparatus ownership.
English printed 92 contains תשובה in the body and שתית in a footnote. Give these
Hebrew spans explicit language and check their rendered direction.

Before rendering, run `python -m
opensiddur.importer.asher_selichot.tzom_gedaliah <compiled-expanded.xml>` to
check the four paired petition expansions and their earlier translation wording.
Then run the book PDF checks with the standalone source root and `--control`;
Gedaliah checks measure all eight shared pizmon starts, note occurrence and
fulfilled cue / closing range boundaries.

For supplied secondary-source readings, omit fulfilled “add” rubrics as well as
Asher's own fulfilled “say” cues. The Gedaliah assembly uses an explicitly empty
editorial override for `instruction:aseret_yemei_teshuvah/add`, selected by the
Asher instruction priorities. Retain performance instructions such as “Reader.”
Check the compiled text and rendered PDF for the unwanted rubric; do not infer
its suppression merely from correct selection of the Ten Days text.

Before a whole-book PDF build, audit each opening's final referenced phrase against
its target module and the immediately following printed paragraph. Do not copy
another day's expansion list without this check. In Gedaliah, including the old
Selah lanu module would duplicate the following reprint. Verify the expanded
opening includes that prayer once; the PDF checker also tests an injected duplicate.

## Second penitential day

The second day of the Ten Days of Repentance occupies n209–n232, printed 104–115.
Keep its large bilingual body heading above the Hebrew-only פזמון heading. The
final conclusion cue is at the bottom of printed 115; the running headers do not
supply additional body headings. Its opening has the same ambiguous Hebrew כי רבו
citation as Gedaliah: the explicit English endpoint and following Selah lanu
reprint bound the expansion at Shomea tefillah, before Selah lanu.

All four repeated-petition cues explicitly cite printed 52 in English as well as
Hebrew. Use that page's bounded reprinted petitions for both languages, with one
shared alignment milestone and inline transclusions. The closing repetition ends
at Mahi umasi / גמירא בשביא; the final continuation begins Makhnise rahamim.
The supplied Full Kaddish uses first_day=false and Ten Days=true; the existing
Asher empty editorial override suppresses its fulfilled “add” instruction.

Bein keseh le'asor has seven shared semantic units, seven Hebrew abbreviation cues
and six English cues. The surety and supplication passages form one shared unit:
Hebrew prints an additional cue between them, while English joins them before
its cue. Preserve that internal difference. The opening crosses printed 111–112;
retain the page break inside the continuing verse line, without moving its preceding
text after the break when wrapping the refrain. Its final cue repeats the complete opening.
Shaarei shamayim is verse, with the terminal ותעל תפלתם clauses marked as refrains.
The English introduction calls the gates seven, though the body enumerates eight;
retain this printed wording. Both body and apparatus contain Hebrew spans.

Readings, immutable first captures, complete pre-OCR snapshots, comparison hashes,
adjudication and pending independent Hebrew review are recorded in the source's
`penitential-second-day*` evidence files. Check the seven shared pizmon starts,
notes, mixed-language apparatus, fulfilled cues, and supplied-prayer boundaries
through the book PDF checker, including its deliberately broken controls.

## Seasonal Half Kaddish

The shared Half Kaddish on printed 3 (n7) prints a single לְעֵלָּא. Preserve that
scan reading. The service edition includes an explicitly documented editorial
second לְעֵלָּא under `opensiddur:holiday-aggregate/aseret-ymei-tshuva=true`,
following the user's seasonal correction; it is not another word printed on n7.
Keep the existing מִן כָּל wording. Scope pre–Rosh Hashanah services with Ten Days
false, and the Gedaliah / penitential-day opening expansions with Ten Days true;
restore caller settings afterward. Check the Half Kaddish as well as Full Kaddish:
correct selection in the closing prayer does not prove the opening is correct.
Reverse verification removes only the documented editorial addition before
comparing the shared module with the printed page-3 reading.

## Later penitential days

The third day runs from n233/n234, printed 116, through the upper part of
n257/n258, printed 128. The fourth day begins on that same facing pair. Bound
services by their body headings, retaining prior-service notes below a new
heading when the apparatus belongs to the earlier text.

Shemaenu selihati has six shared semantic units, six Hebrew abbreviation choices
and four English choices. Hebrew prints a refrain between the lily and dove
stanzas; English joins them. Its final Hebrew cue repeats the opening stanza,
while English ends with the full refrain and no repeat cue. Do not invent an
English opening repeat. Full printed refrains stay ordinary text with refrain
markup. The scan can misprint: a garbled word, a wrong citation number, an
unmatched quotation mark. Readings keep the print; each clear misprint is listed
in sourcetexts `scan_reading/corrections.json`, which the build applies as
`tei:choice/tei:sic + tei:corr` (`readings.errors` picks the form; corrected by
default). Archaic spellings are not misprints. Problems of fact or wording stay
as printed and go to `specs/asher_selichot/OPEN_QUESTIONS.md` for a decision.
Where the decision is an explanation rather than a correction, it goes in
`scan_reading/editorial_notes.json`: a standoff `tei:note type="editorial"` on an
anchor, beginning "Editor:", printed where a book lists the English project under
`annotations`.

The fourth penitential day occupies n257–n282, printed 128–140, between large
body headings shared with the third and fifth days. Yoshev beseter has eight
shared stanza groups, six short refrain cues and one opening-stanza repeat in
each language. Its final printed English refrain includes “given to me”, whereas
the opening says “given me”; preserve those full occurrences independently.
The printed-130 petition cue starts at “Enter not into judgment”, excluding the
already printed mercy verse. Use the nested `selichot/rahamekha_rabbim/al_tavo`
range, then the printed-52 father/mercy and Daniel ranges. Do not copy another
cue's broader starting point. The apparent truncated “ardent pass” at the end
of English printed 133 has no visible continuation on 134; retain and document
it pending independent review rather than completing an unseen word.

The fifth penitential day occupies n281–n308, printed 140–153 upper, ending before
the Erev Yom Kippur body heading. Ezkerah elohim veehemayah has five shared units:
the thirteen-attributes opening, Ezkerah, Middat harahamim, Tamakhti, and Yehi ratson.
Only the final Hebrew יי יי / English “The Eternal, &c.” cue repeats the complete
opening. Do not convert the opening's identical initial words into a cue, invent
short refrain repetitions, or invent a repetition rubric. The Hebrew פזמון is
a real subordinate heading; English has none. The five petition-repeat cues use
the complete printed-52 ranges. Hebrew and English notes include mixed language
text that requires explicit direction. Wrap even a single Hebrew reference letter
(such as א in the Job/Joma footnote on printed 144) in its own Hebrew foreign
span, while the surrounding English note remains English. Measure Latin glyph
positions as well as Hebrew runs; an English note wrapped as Hebrew can reverse
word order while each Latin word still looks normal. Preserve the apparent printed English
“recited has thirteen attributes” on 147 and the reversed page citation 12, 11;
record image adjudication rather than silently correcting the edition.

For cumulative PDF checks, measure the TOC number column on each mirrored page.
With the current Asher export margins, its left cutoff is 475pt on odd pages and
511pt on even pages; the ordinal in “3rd” can reach 480pt on a continuation page.
Do not treat that ordinal as a destination number. A note anchored to the end of
one service can appear below the next service's body heading on the same page.
Retain the verified previous-service apparatus when clipping day checks; the
second penitential day's “With reference to Ps. xlii. 9.” is such a case after
adding the third day. Confirm ownership from the source anchor and PDF, rather
than moving the note into the following service.

## Erev Yom Kippur

This service begins below the fifth penitential day on n307/n308, printed 153,
and ends at the Reader’s Kaddish on n319/n320, printed 159. The Second Fast running
header already appears over its closing text; only the large body heading starts
that following service. Preserve the Erev heading above its Hebrew-only פזמון.
Gate its running-order entry on native Hebrew date month 7, day 9.

Yertseh tsom ammekha has seven paired stanza units, including one crossing the
printed-156/157 page break. Its refrains are printed in full, with Hebrew defective/
plene and English “this sign”/“that sign” variants. Mark those full refrains as
refrains without replacing their wording. Only the final ירצה / “Be pleased” cue
expands the complete opening. There is no printed repetition instruction.

Read this opening independently: Hebrew names Ashrei through Shomea tefillah,
while English names “for thou hearest prayer” with an inconsistent page citation.
The source evidence documents the complete shared Hebrew preliminary range as
an editorial expansion; retain both documentary citations and the unresolved
superscript-like mark after English page 7. Do not claim that phrase ends Ashrei.
The preliminary prayer pair and the closing petitions are reprinted in full.
Supply only Full Kaddish at the final cue, with first_day=false and Ten Days=true;
retain the Reader performance role, omit its fulfilled “says Kaddish” instruction,
and do not import another day’s Makhnise rahamim conclusion.

The English Ezek. xxxvi. 25. footnote at the bottom of printed 159 belongs to
Erev’s closing purification passage, although the Second Fast body intervenes
above the apparatus. Retain that source-owned note with Erev; when adding the
Second Fast later, do not assign it by vertical position alone.

## Monday–Thursday–Monday fast series and final boundaries

The contents call the first two services “Second Fast” and “Fifth Fast”; Hebrew
לשני / לחמישי identifies weekdays, not penitential-day ordinals. The first
Monday fast runs from n319/n320 (printed159) to n335/n336 (printed167), ending
above Thursday's large body heading. Its final Ezekiel footnote sits below that
heading and stays with Monday. Gate the three fasts on the Monday, Thursday and
Monday after the first Sabbath of Iyar or Marheshvan (Hebrew days 3–9, 6–12, 10–16).

Malakhei rahamim has eight shared stanza units, six short אולי יחום / “Perchance”
cues, and a Hebrew-only final full refrain plus opening-repeat cue. Its stanza
openings אולי ירחם are full text, distinct from the short refrain cues. Never add
an English closing repetition where the translation prints none. Retain unsupplied
weekday Amidah, usual-service, and Torah performance instructions when expanding
prayer-pair and refrain cues. Do not inherit another service's Full Kaddish ending.

The scan ends at s411/n410, printed204, with the circumcision pizmon. Monday's
English concluding rubric claims Torah/haftarah readings at volume end, whereas
Hebrew leaves page fields blank. The final scans contain no such readings: retain
the printed statement as evidence and record an absent target, without inventing
a URN or resolving it to unrelated text.

Thursday/Fifth Fast runs from n335/n336 (printed167 lower) through n341/n342
(printed170), before the final Monday on printed171. Its Yisrael nosha is a
reprint variant under the existing common poem identity, with six shared stanza
units, four short cues and a concluding full-opening cue in each language.
Preserve its full refrain hyphenation variants and the apparent English final
pair citation “pp. 1, 12.”. Its opening and conclusion repeat bounded Monday
ranges; the expanded conclusion inherits fourteen Monday notes alongside two
Thursday notes, but no Full Kaddish. It is the Thursday of the series (weekday five,
days 6–12). When measuring stanza starts, scope the actual
pizmon after its heading: earlier scripture also contains Israel is saved.

The final Monday (Last of the Three Fasts) covers n343/n344 through n349/n350
upper, printed171–174. It is the last Monday of the series (days 10–16).
Its Hebrew petition-repeat cue on printed172 has no English counterpart: retain
an empty paired expansion boundary rather than inventing English text. Ezkerah's
Thirteen Attributes opening is prose followed by four verse stanza units; its
only abbreviated cue repeats that opening at the end. Preserve the maqqef join
across printed173/174. Opening and conclusion use Monday ranges without importing
a Full Kaddish or discarding unsupplied weekday-service instructions.

Tenth of Tevet covers printed174 lower–178 upper, n349–n358, with a native
asara-btevet occasion gate. Its Avotai has fourteen shared stanza units and
thirteen Hebrew/twelve English short cues, all expanding the complete opening.
The final English stanza has no cue. Distinguish stanza-opening קמי פיהם from
כל־קמי within the preceding stanza; preserve maqqef words when segmenting.
English to-/wards spans a facsimile break and renders as one word. Keep all ten
source notes and the fourteen notes inherited from Monday's expanded conclusion.

Fast of Esther covers printed178 lower–183 upper, n357–n368, and uses native
taanit-esther. Bematei's eight shared stanza units contain seven Hebrew short
cues and zero English body cues, despite the English repetition rubric. Never
invent English refrains from that rubric. Empty counterpart fragments reflect
different page crossings; omit their empty page breaks so facsimile order does
not rewind. Only two prayer pairs precede the pizmon; none follows it. Retain
nineteen English notes, exact source anchors and mixed-language apparatus, and
record the source's inconsistent feet/yards figures rather than correcting them.

Seventeenth of Tammuz occupies printed183 lower–187, n367–n376, with native
tzom-tammuz gate. Sheeh has four shared stanza units: Hebrew ends with a full-opening
cue, English prints one short refrain cue. Do not invent a repetition rubric.
Printed184 interchanges note numbers2/3. A printed superscript only locates
its note, so attach each note where its content belongs (the Manasseh note to
the image, the second-temple note to the breach). Printed185 has three superscript markers without note
texts: encode unresolved markers without invented reference targets or notes.
When a provisional capture guessed apparatus text, retain its immutable evidence,
remove the guesses from working text, and disclose the correction. Incidental OCR
exposure from a preceding service's full-page context must also be disclosed.


## Yom Kippur Katan

Printed188–203 upper, n377–n408, ends above the circumcision heading. Gate it on
the opening rubric's day: the eve of the New Moon, or the Thursday before when the
New Moon falls on the Sabbath or Sunday. The book names no months; the gate follows
the common Ashkenazi custom, omitting the eves of Tishrei, Marheshvan, Tevet and
Iyar. The printed Psalm-order rubrics stay printed instructions; their customs remain
ambiguous (the first says New Moon on Sabbath/Sunday, the last its eve).
Keep once/twice/seven-times repetitions and Ark actions as performance instructions.

Yom zeh has five shared stanza units and four short opening-repeat cues in each
language; Bat ammi has six units and four refrain cues per language at different
positions. Rahmana has ten units, nine full Hebrew responses and eight English
abbreviations. Encode each printed occurrence independently. Bracketed full
responses in Masat kappai and Samar stay marked as refrains even across a page break.
English interrupts Samar after Remember the on193 with a petition rubric before
bull on194; Hebrew puts its counterpart before the poem. Preserve the English
interleaved rubric within the reusable module, with conditional inline expansions.

Petition cues cite9/10 and use the earlier bounded ranges. The first Ashamnu cue
uses the reprint above in Hebrew and the original on18 in English. The second
uses the page200 reprint in both. Opening Kaddish is supplied as Half Kaddish;
closing Reader Kaddish occurs only on the Hebrew page and its expanded English
is editorial. Scope supplied Kaddishes with first_day=false, Ten Days=false;
keep Reader/Mourner roles. Aleinu and Mourner Kaddish use secondary defaults.
Nine source notes must survive exactly once. Enlarged s399 confirms printed
Jer. iii. 2.; do not silently correct a documentary citation. Record incidental
English OCR exposure of the next section when its shared opening has been read.

## Final circumcision recension

Printed203 lower–204, n407–n410, is the final section. Preserve its independent
circumcision recension under the existing Zekhor berit Avraham poem identity.
Two Hebrew cues alternate different full refrains, והשב and ושוב, verified from
this same recension; English has no corresponding short cues. Never invent
English repetitions. The circumcision performance instruction remains in both
views; the supplied-repeat instruction disappears from the expanded view.
English superscript1 after flesh has no apparatus text on either final page:
retain an unresolved marker, without an invented note or reference target.
The words after the small והשב cue at the bottom of203 begin stanza four:
מִפִּי אוֹהֲבֶיךָ עֵד בֵּינְךָ וּבֵין, continuing with יְדִידֶיךָ on204.
Keep this in one verse across the page break. The small refrain cue does not
turn the following body words into apparatus. Do not insert דם before ידידיך
from the English translation’s “blood”; it is absent from the Hebrew scan.
The English section display label is editorial, taken from the final running
heading; document it. There is no Torah/haftarah appendix after this poem.
