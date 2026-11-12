# Heidenheim–Marmorstein, first day of Rosh ha-Shanah (1965)

Contribution to [issue 214](https://github.com/opensiddur/opensiddur-processor/issues/214).
The complete project is the 355-leaf Archive item
`mahzor-lyom-rishon-shel-rosh-hashanah-day-one-jenny-marmorstein-1965`.
The pilot and six front leaves are complete. Full-volume work proceeds from
the beginning in scan order, as requested. The opening entrance prayers,
weekday Minchah, festival preparations and Kabbalat Shabbat through s17
(printed page 11) have been transcribed and independently reviewed. This is not a complete
mahzor. Its PRs remain draft while the full-volume transcription is unfinished.

The accepted installment s18–s23 (Archive n17–n22, paired Hebrew and English
printed pages 12–14) covers Barekhu through Ga’al Yisrael in 19 language files.
Human source adjudications, enlarged readings and two independent guideline,
alignment and order audits were followed by acceptance of s24–s25 (printed
p. 15), Hashkivenu through Half Kaddish, bringing the total to 31 leaves.
The evening Amidah on s26–s33 is also accepted, bringing the total to 39
leaves; the next source page is s34 (Archive n33). PR 297 is merged; character-highlighting
support for the required `tei:c` encoding is isolated in merged exporter PR 298.

## Repositories and outputs

All three repositories use `feat/marmorstein-rosh-hashanah-1`. Their default
checkouts live under `master/`; processor and projects actually name that branch
`main`, whereas sourcetexts names it `master`.

- Processor: `opensiddur.importer.marmorstein_rosh_hashanah_1` and reusable scan helpers.
- Sources: `sources/marmorstein_rosh_hashanah_1/`, with metadata, OCR candidates,
  immutable first/independent readings, selected reading spans, adjudications and progress.
- Projects: `prayerbook_for_the_new_year-heidenheim-1965-he`,
  `prayerbook_for_the_new_year-marmorstein-1965-en`, and
  `machzor_expanded-opensiddur-he`.

Images, cropped bands, raw model process responses and generated exports remain
in untracked `output/marmorstein_rosh_hashanah_1/`. No image belongs in Git.

## Source and identity contracts

The scan is authoritative. OCR is a candidate, never a completed transcription.
`pages.json` is regenerated from Archive metadata plus image-evidenced
`page_corrections.json`. Every scan has a unique `sN` identity, where Archive leaf
is `N-1`. Printed pagination restarts; it is never a primary key. Use the absolute
Archive leaf image URL in `tei:pb/@facs`, printed labels in `@n`, and omit `@n`
when unpaginated. Psalm chapter labels in the appendix are not page numbers.

Reuse canonical registry URNs and existing project identities before proposing
anything new. Preserve this edition's wording and pointing under those identities;
do not copy another edition's text because its URN matches. Numeric scripture
references are canonical. A partial chapter witness maps only its actual verses;
do not advertise an excerpt as the entire chapter. Use milestone boundaries,
independent of paragraphs and page turns, and terminate scopes before other text.

Omit printed Hebrew linkage cues from accepted English prayer words; shared canonical
milestones provide the linkage. Preserve the cues in immutable image-reading evidence.
Encode biblical citations as standoff `tei:note type="citation"` annotations targeting
the passage, following existing projects, rather than as prayer text or instructions.
Omit enclosing parentheses in generated citation notes while retaining them in
the reviewed source readings and evidence. English witnesses
exist only for printed English material. Missing English is not an empty file,
placeholder, or invitation to use another translator automatically.

Obvious source misprints use `tei:choice` with the printed form in `tei:sic`
and the correction in `tei:corr`, following the existing authoring convention.
Keep the accepted scan reading and its review hash unchanged. Record editorial
corrections separately in `corrections.json`, with unique textual context and
scan evidence, and apply them through the shared correction utility before
validation. Normal exports use the repository default `readings.errors: corrected`;
`printed` remains available. Do not treat archaic usage, translation choices or
faithful defective Hebrew spellings as obvious typos.

## Page directions and expanded arrangement

Source readings retain printed page numbers and wording, including misprints.
Generated navigation uses `tei:ref type="page"` with an edition-qualified target,
inside independently removable `optional-page-reference` clauses. Preserve nearby
actions and bibliographic citations. Resolve targets from the meaning of the
direction, never a fixed Hebrew/English pagination offset.

The expanded project uses a distinct `siddur:machzor_expanded` root and a single
bilingual structural spine. It owns order and editorial instructions, not copies
of prayer text. All prayer targets are edition-independent canonical URNs, chosen
through settings priorities. Insert referenced passages and repetitions at the
point of recitation; retain conditions, speaker roles, and physical actions.
Never remove a whole rubric because it happens to mention a page.

The pilot's navigation example is the instruction on printed page 8 (Archive
leaves 51 and 52) to insert the Torah blessings from printed page 4. The documentary
view links to this edition's blessing; the expanded view transcludes the three
blessings there. It retains the German-rite custom qualification. The final
arrangement must move the blessings to this location rather than recite them twice.

The complete first-day morning selection must continue through Torah service and
Musaf. Reuse registered calendar, quorum and service settings with local scopes.
Missing Hebrew passages referenced by the print may use compatible existing
sources with recorded provenance. Do not fill English gaps in this installment.

## Independent reading and completion

Printed Rashi script helps identify instructions and speaker labels. Record
that observation in the reading evidence, but do not emit `rend` on rubric
notes: the reader's selected instruction styles control their presentation.
Review payloads include each speaker abbreviation and its expansion, so changes
to either invalidate acceptance. In Kedushah, the shared-response labels mean
קהל וחזן and use the existing `instruction:role/reader_and_congregation`
identity; do not reduce these labels to congregation-only ק׳.

The requested second reader is available: `claude-opus-5-5`, medium effort.
It reads scan images through read-only tools, without receiving the primary
reading, OCR, registry text, or another edition. Preserve its raw reading and
ambiguities, exact model/effort and session identity. Never count its confident
output alone as image adjudication: the pilot already demonstrates different
consonant and pointing readings between the two readers.

After the blind image reading, the secondary reader must also audit adherence
to `schema/JLPTEI-3.md`, `specs/SIDDUR_URN_SCHEME.md`, applicable `AGENTS.md`
instructions and the authoritative ODD. Record the guideline versions or hashes,
files reviewed, model and effort, findings, adjudications and follow-up results.
Check canonical URN reuse, chapter/verse/subverse scopes and terminators,
paragraph independence, citations as notes, rubric and speaker markup,
abbreviations and sic/corr, facsimile identifiers, translation omissions,
local settings and expanded recitation order. Schema validation supplements
this review; it does not replace it. Keep unresolved findings pending rather
than counting the corresponding pages as fully reviewed.

Biblical excerpts carry fully qualified verse or subverse correspondences and
chapter-number context milestones. A whole-chapter correspondence is emitted
only for a complete chapter, such as Psalm 145 in Ashrei; otherwise a request
for that chapter could incorrectly resolve to one quoted verse. Partial Psalm
39:13 uses the shared incipit parts `shimah` and `ki_ger`. Reuse Psalm 55:15/b
for the printed closing clause rather than inventing a new identity.

The opening page's complete collection has the structural identity
`urn:x-opensiddur:text:siddur:rosh_hashanah/entering_synagogue`; its component
prayers and verses retain their existing identities. Documentary transclusions
select the edition explicitly, while expanded prayer transclusions remain
edition-independent. Hebrew dependencies precede English projects in source
priority, with translations selected separately as parallel witnesses.

Following the comparison with Birnbaum, the reusable Kedushah is conditioned
on both repetition and minyan; its printed description stays inside the scope.
The expanded repetition declares minyan true locally. Preparatory Minchah is
restricted to Elul 29 (Hebrew month 6), with its date and ordinary-season context
declared locally. Keep the printed האל הקדוש; do not insert an unprinted
Ten Days substitution into this documentary witness.

Compare primary and independent readings using `scan.compare`; record pointing
separately from words. Settlements require the exact reading hashes and image
evidence for every disputed reading. Changes invalidate old adjudications.
Unresolved ambiguity stays pending human review. On 2026-11-08 the user confirmed the three pilot marks already encoded by the first reader: the dagesh in הבריות, no extra mark in ליראיו, and the mappiq in לשמה. Those confirmations clear the pilot uncertainties; they do not certify other pages. `--draft` is required to build
unreviewed text. Structural success is not source-fidelity approval.

The pilot includes Torah blessings, Barukh She-amar, I Chronicles 16:8–36 from
Hodu, a Hebrew-only Psalm 24, and the page-direction example. The English title page, copyright page, translator’s preface and following blank leaf are also independently read. The cover emblem and Hebrew title-page signature are now human-adjudicated as
`וואלף ב"ר שמשון ז"ל איש היידנהיים`. The user also confirmed the electronic
layout and links. Original uncertain readings are retained as evidence. Hodu's remaining
verses and the rest of the book were not implied by that initial excerpt.

The next reviewed installment completes Hodu with the existing Romemu, Vehu
Raḥum and Hoshiah et ammekha modules (22 paired segments), then adds Psalm 19
(15 paired verses). Existing liturgical excerpt identities retain their biblical
sources on bounded spans. Both source and expanded sequences reuse these identities;
no new prayer identity was registered. The encoder preserves both full and
abbreviated printed Divine Names without changing their pointing.

Independent blind image readings and separate alignment/order audits cover the
addition. Enlarged images resolve defective עֹמֶדֶת and the source misprints
“withold” and “whem”. The audit also corrected an earlier comma adjudication in
Chronicles 16:35; retain that decision history. Hebrew chapter labels and English
biblical references are citation notes, not prayer words. Six prayer leaves
(s60–s65, Hebrew/English printed pages 15–17) and six front leaves (s1–s6)
are fully accounted for. The documentary projects include the half-title, both
source title pages and the copyright verso, with title-page gates; Hebrew subtitles, bylines, place and date retain their roles. Psalm 34 and the rest of the
volume remain incomplete.

`verify --check` must fail until every leaf is explicitly accounted for and its
content independently reviewed. A page with only an excerpt is never complete.
After the pilot is adjudicated, proceed through the entire volume in printed
order, including front matter and appendices, maintaining the review ledger.

### Opening service installment

`primary/opening_s7_s14.json` preserves the first image readings, recorded before
consulting the corresponding independent page transcription.
`independent/opening_s7_s14.json` records Claude Opus 5.5 with the CLI effort set
to medium. Enlarged s7–s8 readings, comparison reports, the encoding audit and
its resolutions are separate evidence. Raw intake does not imply acceptance.

The opening sequence contains entrance prayers, weekday Minchah, eruv
tavshilin, festival candle lighting, and Kabbalat Shabbat. Hebrew-only pages do
not acquire English substitutes. English translation cues remain outside
accepted prayer words, and the marginal Psalm 145 label targets its first verse
as a citation note after the two introductory Ashrei verses.

Expanded `section` occurrences share one recursive sequence across languages.
Conditions end locally before the next section. Preparatory weekday Minchah
requires the existing minha setting and excludes Shabbat and Yom Tov. The
morning section requires shaharit and Rosh ha-Shanah day one. Supplementary
Psalm 24 remains in a named appendix. The complete opening תפלה page and printed
weekday Minchah through s12 are accepted after independent fidelity, guideline,
alignment and order review. The expanded Minchah includes Half/Whole Kaddish
from compatible Birnbaum Hebrew, silent prayer, minyan-gated repetition,
Kedushah and simultaneous Modim roles. The first-day morning service remains
incomplete. The following installment extends this opening sequence through s17;
continue in scan order at s18 (Archive n17, printed page 12). The title follows the source rather than describing a pilot installment.

Mah Tovu reuses its existing two-part canonical structure. The four-verse
`mah_tovu/varani` scope is not split merely to follow printed verses; each
scriptural source is bounded independently, and the first-person Psalm 95:6
adaptation is typed explicitly. Hebrew punctuation is a word boundary when
tagging Divine Names, including immediately after maqaf.

### Festival preparations and Kabbalat Shabbat

The s13–s17 batch adds eruv tavshilin and festival lights in their printed
Hebrew/Aramaic and English, then complete Psalms 95–99, 29, 92 and 93 and
Lekhah Dodi in Hebrew. Preserve the actual mixed-language declaration, with
`xml:lang="arc"` on its paragraph. English directions appear once in the common
documentary spine. No English translation of Kabbalat Shabbat is supplied.

The user confirms that this edition follows a different custom from Birnbaum:
include both the opening Psalms and Lekhah Dodi when Rosh ha-Shanah is Shabbat.
Apply inclusion at the expanded structural transclusion level; do not put
Birnbaum's festival omission inside these reusable source texts. The user also
confirms that the initial marginal לכה calls for a congregational repetition
before stanza one. Preserve all ten literal cues as linked instructions outside
the refrain/stanza correspondence scopes. Expanded recitation has eleven full
refrains: the initial reader's rendition, the initial congregational response,
and nine subsequent congregational responses. Give structural occurrences unique
identities while reusing canonical refrain and stanza identities.

The expanded spine gates preparations and services through existing calendar,
service, quorum and mourners settings, with declarations closed locally.
Candle lighting is available on Elul 29 before the incoming festival, including
the combined blessing on Friday before RH-Shabbat. Its outer gate does not
require the next Hebrew date or Maariv to have begun. The combined blessing is
excluded after Shabbat has begun; weekday first-night lighting remains available
in its Maariv context. The shared heading and lighting instruction have the
same gate as the union of the blessing branches; they cannot survive alone.
The combined variant is excluded during Friday twilight as well. Nested all/any/none groups express these choices using
existing calendar features.
The source's Kaddish direction is expanded through the compatible Birnbaum
Mourner's Kaddish, conditional on both minyan and mourners. Separate the poem's
performance direction from its literary acrostic attribution. Source small
speaker labels, including combined קו״ח, remain independently reviewable.

Reuse all existing prayer and Psalm identities. The sole new canonical identity
is `prayer:hadlaqat_ner_yom_tov/shabbat`, a genuine combined Sabbath/festival
calendar variant. A separate, credited Birnbaum extraction resolves the printed Sabbath insertion
into the complete combined wording. Its parent source remains unchanged. The
expanded maḥzor targets the bare canonical variant, which has no English
counterpart. Do not declare the current day to be Shabbat merely to select
this wording: kind-of-day declarations intentionally acquire gates against the
actual day, so that approach suppresses the blessing before sunset on Friday.
The separate combined witness has no such declaration and supplies exactly the
already printed source words, with the control rubric resolved. All source
credits and licences are retained.

Paragraph language and poem reference units are explicit in source segments.
Page boundaries do not add a space after a source maqaf; continuation tests
protect the exact word boundary. Secondary review includes enlarged image
adjudication, alignment, the authoritative ODD and encoding guidelines, and
expanded order. Preserve superseded readings and first-audit findings as
history. Complete-page acceptance requires the final frozen-file review, not
just agreement between two preliminary readings. Eleven compiled settings cases
check festival/Shabbat selection, eruv calendar applicability, minyan/mourners,
all eleven expanded refrains, ten documentary cues and missing-English behavior.
All eight complete Psalm chapters have verified verse counts and order.

### First-night Maariv installment

Keep the reader/congregation column labels as literal Yiddish or English
description notes with canonical role correspondences. Expand the Hebrew
`קו״ח` as `קהל וחזן`. The documentary order retains the role columns’ texts;
the expanded spine orders the call, the congregation’s meditation during the
chant, and the common response, subject to independent order review.

The Shema witness retains its cantillation and enlarged ayin/dalet. Record a
single enlarged character with `tei:c/@rend`. Conditional when-rubrics belong
inside `j:conditional`; descriptions of how to recite belong inside the
passage. Source rubrics may name their language witnesses to avoid supplying
an absent instruction in the facing translation. Publication URNs, as well as
documentary transclusions, name the exact verse range of an excerpt. Record a
single canonical verse boundary across a page continuation. Exact Biblical
quotations within a prayer part carry their own chapter/verse milestones and
terminators inside a `source` span, without ending the outer prayer-part scope.
Incomplete chapters provide numbered chapter context without claiming the
whole chapter; documentary transclusions select an edition-qualified range.

There is no English witness for El melekh ne’eman or the meditation’s final
Psalm 113:2. Preserve those omissions. El melekh ne’eman is conditional on
praying without a minyan; the expanded Barekhu section requires a minyan.
All settings remain local to their recitation context. Hashkivenu follows the
previous installment; s24–s25 now supplies the following Hashkivenu through Half Kaddish sequence.

Enlarged crops supplement the immutable blind readings; crop filenames must
never count as additional scanned leaves. Draft generation labels pending
modules while retaining the reviewed status of previously accepted modules.

## Commands and acceptance

Initialize submodules, run `uv sync --all-groups`, and build schemas first.
Pass `--source-root` to the standalone source worktree's `sources/`, and
`--project-directory` to the standalone project worktree's `project/`.

```bash
python -m opensiddur.importer.marmorstein_rosh_hashanah_1.download --contact-email ADDRESS --agent-model MODEL --pages s60 s61
python -m opensiddur.importer.marmorstein_rosh_hashanah_1.download --regenerate
python -m opensiddur.importer.marmorstein_rosh_hashanah_1.build --draft
python -m opensiddur.importer.marmorstein_rosh_hashanah_1.verify --write-report
python -m opensiddur.importer.marmorstein_rosh_hashanah_1.verify --check
```

Run RelaxNG and Schematron validation before any generated XML write. Check names,
registered features, registry integrity and reference-database resolution. Compile
documentary Hebrew, documentary parallel and expanded settings for print and
electronic output. Inspect rendered pages, mixed-language direction, reference
destinations, alignment after omissions and missing-English behavior.

Test shared algorithms with synthetic inputs: independent navigation clauses,
required canonical expansions, preservation of ritual actions, pointing disputes,
stale adjudications and mandatory independent models. Edition wording is reviewed
against images, not snapshotted as a unit-test expectation.

Deliver linked repository PRs referencing issue 214, marked draft until the
complete-volume acceptance criteria pass. Merge processor dependencies first.

The pilot exposed reversed word order in the English translation of a Hebrew
heading on a single structural spine. The accompanying renderer fix wraps the
whole translated heading in its language direction; synthetic regressions cover
both Hebrew-to-English and English-to-Hebrew headings.


## Hashkivenu through Half Kaddish (s24–s25)

Seven reusable units in both languages preserve the festival Hashkivenu ending,
Exodus 31:16–17, Psalm 81:4–5, Numbers 14:17, Psalm 25:6 and Half Kaddish.
The existing Hashkivenu opening and ending extents and Veshamru structural URN
are reused. Pure Bible excerpts remain free of occurrence conditions. Shabbat
and minyan guards belong to service order; the printed fixed Ten Days Kaddish
witness carries its own calendar scope. Preparatory Elul 29 Kaddish remains
bound to the compatible Birnbaum Hebrew dependency, whose component references
are now self-qualified. This prevents festival English from filling an absent
preparatory translation and retains Birnbaum’s calendar-responsive wording.

The literal חזן label lies before the first prayer-part milestone. Instructions
use semantic types without rend attributes. Partial chapter context does not
claim a whole chapter. The human-confirmed segol in בכסה and enlarged image
adjudications are retained with the blind readings and two independent audits.
The reviewer’s final settings finding was fixed in the generator and verified
locally: documentary electronic variants start with electronic.day=none.
Regeneration and serialized HTML checks confirm fixed source words remain
available regardless of the device date; expanded settings retain their behavior.
After explicit user authorization, Claude Opus 5.5 at medium effort independently
reviewed the final settings, generator and regression test: pass with no required
changes. Reviewed file hashes stayed unchanged. The source repository retains
this final review as independent/hashkivenu_documentary_settings_review.json.

The accepted build validates 95 XML files. The focused importer suite passes
102 tests and 41 subtests. Eight runtime cases protect service/quorum choices,
ordinary-day dependencies and missing translations; four Bible scope checks
confirm excerpts do not claim entire chapters. Whole-volume acceptance remains false.


## Evening Amidah (s26–s33, printed 16–19)

The next installment supplies the full silent Amidah in fifteen Hebrew/English
modules, from Adonai sefatai through the Temple prayer. Existing registered
festival composite roots distinguish its Avot, Gevurot, day blessing, Avodah,
Hodaah and peace blessing from the edition’s earlier ordinary Minchah. Reuse
canonical prayer-part milestones for the words; do not invent new identities
for service placement. The shared expanded spine declares silence, without
repetition, locally and includes each module once. No Maariv Kedushah is supplied.

Twelve source-parenthesized Sabbath clauses use j:conditional type=marked.
Keep parentheses in the raw readings and remove them during generation so
selected prayer text has no delimiters and undecided conditions use the
exporter’s standard delimiters. Rashi אם שבת. labels remain condition instruction
notes without rend. The seal’s optional vav joins Israel directly. Preserve
the unpointed parenthetical (מלכנו), whose condition is unspecified and whose
English translation is absent, without inventing a setting or translation.

Full scriptural quotations have chapter context, verse correspondence and
explicit terminators outside their source spans: Psalms 51:17, 146:10, 60:7,
19:15; Isaiah 5:16; Malachi 3:4. The generator applies the same placement to
earlier quoted passages. All 92 earlier language files retain identical printed
words and correspondence sequences. The existing Psalm 19:15 reference mapping
remains preferred; both printed occurrences remain present in each documentary
language witness. No whole-chapter identity is claimed by an excerpt.

Preserve the original English “Thou has created” as has/hast in sic/corr.
Human adjudication confirms the bet dagesh in באפו, no first-yod sheva in
the prefixed Divine Name, and dalet dagesh plus holam and first-nun meteg
in ופקדננו, with no fe/qof dagesh. Raw blind differences, superseded readings
and actual configured reviewer model/effort remain in the source evidence.

Current checks: 125 schema-valid XML files; 104 focused importer tests and 41
subtests; names/features/registry/reference checks; seven Amidah runtime cases
and six bilingual scripture scope checks. Earlier eight Kaddish/runtime cases
still pass, including ordinary Minchah and missing-English protection. Both frozen-file independent audits passed after marked-conditional corrections
and human source adjudications. Accepted coverage is 39 of 355 leaves, with
48 independent image readings. Final PDF/HTML exports accompany this installment.

## Evening conclusion and home customs (s34–s38)

The next installment preserves the printed sequence of Hebrew pages 20–23:
s35 (printed 20) precedes s34 (printed 21), then s36/s37 (Hebrew/English 22),
and s38 (Hebrew 23). Do not infer language, sequence or translation pairing
from scan parity. The original 355-page PDF and its extracted images are the
independent check on physical scan numbering; cache names and Archive leaves
remain distinct from printed labels. Preserve full unique Archive leaf URLs.

Reuse the existing synagogue Vayekhulu, Meein Sheva, MishnahShabbat 2,
Amar Rabbi Elazar, RH Kiddush, wine/fruit/Shehecheyanu, apple prayer, greeting
and Aleinu identities. One additional Talmud identity names the checking-
clothing passage from [Shabbat 12a](https://www.sefaria.org/Shabbat.12a), after registry/alias/project searches found
no identity for it. Preserve this edition’s wording, not another Talmud witness.
The page 21 study paragraph is unpointed text, not an instruction. Mishnah
milestones do not create paragraph breaks; keep printed Hebrew section letters.

The synagogue sequence after the silent Amidah is Vayekhulu on Shabbat;
Meein Sheva on Shabbat with a minyan; full Kaddish with a minyan; Bameh Madlikin and
its study passages on Shabbat or according to the printed Frankfurt custom;
Savri, wine blessing, RH Kiddush and Shehecheyanu; Aleinu, Mourner Kaddish
with a minyan and mourners, and Yigdal. Keep the fixed המלך הקדוש witness scoped
to the Ten Days. Do not import Birnbaum’s different festival omission custom.

A named home-customs appendix repeats the Kiddush words in their home order,
adding the printed Sabbath Genesis prefix, Hamotzi, apple blessing/prayer,
and the four labeled Hebrew greeting alternatives. One generic English greeting
remains one translation; no gender-specific English is invented. The appendix
shares first-night/maariv selectors and does not enter the morning selection.
Birnbaum Hebrew supplies only missing Kaddish, Yigdal and Hamotzi words; retain
credits/licences and do not manufacture English for absent source passages.

Genesis 1:31b is a half-verse excerpt, not a witness for the whole verse or chapter.
The source בלחש  and בקול descriptions stay at their actual word boundaries,
outside semantic quotation spans. Full quotations use chapter/verse milestones
and explicit terminators. Recipient labels remain descriptions, outside prayer
words; source abbreviations preserve both printed forms and expansions.
All instruction/abbreviation interpretations are part of the review-hash payload.
Source-parenthesized Kiddush insertions use the same marked Shabbat condition
behavior as the Amidah: absent when false, unmarked when true, marked when unknown.

Draft validation: 148 schema-valid XML files; 112 importer tests and 41 subtests;
feature, naming and registry checks; eight actual expanded print-compilation cases
cover weekday/Shabbat, quorum, Frankfurt custom, two Kiddush occurrences, home
appendix, source continuation and neighboring services. Three independent audits approve the encoding, alignment and expanded order.
All human source adjudications are complete: 44 of 355 leaves are accepted,
53 independently read and 51 contain excerpts. Continue at scan page 39.
Whole-volume acceptance remains false.

The documentary Kiddush arrangement has matching Hebrew/English service files.
Their headings and introductions stay inside the shared service transclusion,
after Hebrew-only evening material. This preserves correct heading placement
in parallel exports. The Hebrew prayer title inside its German instruction is
a Hebrew foreign span. Human adjudication confirms Frankfurt’s pataḥ-alef,
the pointed small-type titles and all five disputed dageshes. The printed
feminine participle after masculine שהוא is preserved as sic עוֹשָׂה beside
corr עוֹשֶׂה; raw image readings remain unchanged.

All 27 final review targets match the accepted XML after reversing only
acceptance metadata and the explicitly human-confirmed final שבת pointing.
All 122 earlier language modules remain unchanged. The guarded accepted build
validates 148 files and leaves no DRAFT metadata in the generated projects.

## Morning preliminaries (scan pages 39–43)

Transcribe the tallit preparation on printed p.1, entrance/pre-morning prayers
on pp.2–3, Shaḥar Avaqeshkha and Yigdal. Page39 has actual English blessing
and Psalm translations below its Hebrew text on the same leaf. Keep its
untranslated intention and closing petition Hebrew-only. English linkage
words are evidence, not prayer words; the English ritual instructions retain
their Hebrew prayer names. All source page boundaries use exact Archive leaves.

Reuse existing tallith, Mah Tovu, Gabirol and Yigdal identities, and Biblical
verse/subverse identities. Add only five structural context records, not new
canonical prayer identities. Contexts distinguish the new documentary
occurrences from earlier printings without forcing one local spelling or
pointing onto both. The identical Hebrew Mah Tovu reuses the earlier canonical
witness inline; its context retains the morning facsimile, and the English
provides its first edition witness. A unique occurrence milestone directly
in the source paragraph preserves Psalm 17:6's second English rendering,
“I called” rather than “I call”, without declaring a second canonical verse.

Existing earlier s7 Hebrew Bible witnesses remain the canonical lookup in
this edition. Expanded recitation deliberately reuses those witnesses and
repeats the canonical verse where required. Documentary compilation retains
the actual later readings. Actual paired-output verification checks every
one of the eighteen morning Psalm occurrences and the complete Mah Tovu
against their own source words, with no duplicate-alignment warnings or
parallel compilation failures. This evidence resolves the reviewer's concern
about possible cross-position pairing; it does not assert that the s40
pointing replaces the earlier canonical witness.

The generic Gabirol poem root is retained; its four already registered stanza
identities come from the legacy _39123 root. Likewise the generic Yigdal root
reuses the existing thirteen yigdal_daniel part identities. These are shared
text extents, not newly named translations. Hebrew poetic lines use lg/l;
English printed prose paragraphs keep their own boundaries. Verse milestones
remain independent of paragraphs and page breaks. The short Numbers15:38
quotation retains its source annotation without claiming the unprinted ends
of that verse or inventing a named subverse absent from the shared table.

Two separately transcluded service files per language keep the tallit section
and following prayer heading anchored around untranslated passages. Source
headings are printed only where present; service-file metadata may describe
its contents. The expanded morning sequence starts with this tallit/entrance
material and continues into the existing morning excerpts. The earlier
generic entrance sequence is selected only outside Shacharit, preventing a
double recitation when morning is selected. Existing local service/calendar
settings and the common bilingual spine remain in use.

The edition now supplies Yigdal in both languages, so canonical transclusion
replaces the earlier Birnbaum dependency for that poem in Maariv as well.
Compatible Birnbaum Hebrew still supplies the missing Kaddish/Hamotzi words,
with credits and licences preserved. No English is invented. The original
“Lister” and transposed “מסדורים” receive separate sic/corr layers while raw
image readings preserve the source. Small Rashi-script attribution/metre
abbreviations have explicit expansions, bound into the review payload.

Human adjudication gives “בקשה לר׳ שלמה בן גבירול. ב׳ תנועות ויתד וב׳ תנועות.”,
confirms ordinary יְיָ for the heavy Name sort, and identifies the tallit
heading’s extra ink as a smudge beside hataf-patah, not a meteg. The bet in
בתורה and both dalet dagesh/vav shuruq in לְאַחְדּוּתוֹ are confirmed.
Three independent audits and actual paired compiler checks settle the source,
guidelines, alignment and order. Accepted: 49 of 355 leaves; continue at scan 44.

## Opening morning blessings (scan pages 44–47)

Complete both printed pages 4–5, including Adon Olam, washing the hands,
Asher Yatzar, the existing three Torah blessings, Numbers 6:24–26, Elu Devarim
and Elohai Neshamah. Reuse the existing prayer roots and the ten incipit
stanza identities of the canonical Adon Olam. Preserve ten Hebrew couplets
and twelve English paragraphs, with stanza scopes independent of paragraph
breaks. Biblical milestones bound the three complete Numbers verses; their
chapter is excerpt context, not a whole-chapter witness. The study composite
uses the existing `prayer:ellu_devarim` identity without pretending to quote
an entire Mishnah or Talmud passage word for word.

Add one structural service context and paired `morning_blessings.xml` files.
Retain the pilot Torah blessings verbatim, including the confirmed mappiq in
לשמה and the two different vowels in תורתך. Remove the false opening page
break from Laasoq now that the complete page opens earlier in the service.
The actual page-5 boundary before Vehaarev remains. Mid-page directions keep
their links without creating a new page break. Preserve the exact original
German-rite direction and printed page number in raw evidence, with an empty
edition-qualified page reference in the independently removable parenthesis.
The Hebrew prayer name in that English instruction remains.

The expanded sequence uses the explicit `opensiddur:rite/german` binary.
For German rite, Elohai Neshamah follows Asher Yatzar immediately, and the
complete five-unit block (three Torah blessings, Numbers 6:24–26 and Elu
Devarim) moves to the later printed-page-8 insertion. For non-German rite,
the whole block remains between Asher Yatzar and Elohai Neshamah. Keep the
block intact through the end of Elu Devarim, and include each block and
Elohai Neshamah exactly once when the rite is known. Unknown rite retains
both explicitly labeled alternatives. This is a rite condition, not a generic
variant switch; broad Ashkenaz and other regional custom flags do not
implicitly decide the German feature. Both languages share one spine.

The later position retains the source's existing p.8 structural anchor before
Barukh She-amar. Scans 48–53 remain partial/untranscribed; subsequent
installments fill the intervening material without moving this anchor or
claiming complete service coverage.

Independent full-page, enlarged and tight-crop readings retain their actual
hashes, disagreements, model identifiers and effort self-reports. The tight
images settle the gimel dagesh, final-kaf dagesh and both initial bets in
בקרבי. The user confirms pataḥ under resh and sheva under alef in
וְהָרַאְיוֹן; preserve it literally without speculative correction.
Two independent documentary source/guideline/alignment/order audits and PDF
inspection approve these four source leaves (53 of 355 accepted). The user has clarified the whole-block relocation and the explicit rite
condition. Expanded-order implementation is now verified separately; its
independent review and exports are recorded with the source evidence.

### Continued morning blessings: physical scans 48–51

Transcribe complete printed pages 6–7 in both languages, through Aval
Anachnu. Reuse the existing `birkhot_hashachar` child identities, including
`shelo_asani_goy` for this edition's נכרי wording, and the existing
`ribbon_kol_haolamim` and `aval_anachnu` roots. The superficially similar
`ribbon_haolamim` identifies another prayer and must not be substituted.

Keep the source's continuous cross-page paragraph independent of canonical
boundaries: `shetargilenu` ends after להשתעבד לך; `gomel_chasadim` begins
ותננו היום. Use two `prayer-part` milestones and their terminator within
one paragraph, with the actual page boundary before להשתעבד. Transclude
the range of both existing identities in the documentary and expanded spines.

Use the existing `opensiddur:person/gender` symbol values `male` and
`female`, as Birnbaum does, to select the mutually exclusive blessings in
service order. Reusable word modules stay ungated. Preserve the original
English women’s instruction on both documentary pages as the conditional’s
own note; expanded alternatives have bilingual condition labels. Known
settings suppress obsolete labels and the other alternative; undefined
settings retain both. Keep this choice independent of German rite and
Shabbat. Insert all continued material before the established later German
Torah-study anchor, preserving the accepted whole-block relocation.

The English source duplicates the women’s blessing in a second full-size
paragraph. Retain its exact paragraph as `choice/sic` with empty `corr`,
using an explicit occurrence selector so an identical first paragraph cannot
be corrected accidentally. Preserve the original `everyday` in the later
English petition as `sic`, correcting only its spacing in `corr`. Raw primary
and independent transcriptions remain unchanged; correction markup is a
separate editorial layer. Omit Hebrew linkage cues from English prayer words.
Treat the small לעולם introduction ending ויאמר as a semantic directive;
no instruction `rend` attributes are added.

All source questions in this installment are resolved by human adjudication
and a final independent verification. Literal readings include גַּב־, רֹב,
שֶׁשָּׂמַחְתָּ־בּוֹ, both בן words without bet dagesh, בריתך without bet
dagesh, לּוֹ, יְּשׁוּעָתֵנוּ, בְּסֵתֶר in both directive copies, מֵעֵינָי
and בִזָּיוֹן (bet without dagesh, zayin with dagesh). These are direct
transcription corrections; the original English errors retain sic/corr.
Independent review limitations about codepoints and stale inline copies are
resolved by full-document and normalization checks. Actual initial reader
hashes/disagreements and configured effort/self-report remain separately
preserved.

Scans48–51 are accepted, bringing source coverage to57of355leaves. Guarded
build:222schema-valid XML files, no pending unit reviews. Names, features,
registry and references pass; all21new paired rows, six compiled conditional
cases and final production HTML condition/anchor checks pass. The final222XML
text trees match the human-corrected reviewed draft; acceptance metadata is
the only subsequent change. Inspected accepted exports have47documentary and
50expanded pages. Separate exporter PR299 supplies the keep-with-next fix,
verified by436tests and160subtests including real-PDF geometry with a negative
control; it is not included in this digitization branch. Complete-volume and
whole-service acceptance remain false. Continue at physical scan52 (Archive
n51).


### Continuation: physical PDF scans 52–55

Printed p8 adds five bilingual source units; pp9–10 add six Hebrew-only
offerings units. Existing canonical prayer and Bible URNs are reused. Four
structural occurrence/service contexts distinguish morning occurrences without
inventing new prayer identities. Expanded morning Shema targets its occurrence
context to avoid selecting the earlier evening verse witness.

The shared spine places the p8 continuation before the German rite’s later
Torah/study block and offerings after it. No absent English is supplied.
Hebrew-only service witnesses omit obsolete English files and service references.
A regression test covers this behavior. Verse boundaries survive the source
page break within Numbers28:4; citations are notes and the original English
“Thou has” uses sic/corr. Documentary page navigation stays edition-qualified.

Primary, blind, enlarged, accent and tight-image readings retain their actual
differences. Independent Claude Opus5.5 review (configured medium) approves
guidelines, alignment and order. Human answers confirm the four Numbers marks
and both p8 dageshes; accepted words exactly match the reviewed draft.
Four service/rite cases and eight paired rows pass, including identical-word
BarukhShem reuse and no English fallback for offerings. Coverage is61of355
leaves; the next physical PDF scan is56 (Archive n55). Whole-volume and complete
service acceptance remain false.


### Draft continuation: physical PDF scans56–59

Thirteen Hebrew-only modules continue the offerings/study order through the
Temple-restoration prayer on printed p14. Existing canonical identities cover
the incense passages, Biblical verses, AnaBe-khoaḥ stanzas, eight mishnayot and
thirteen rules. One BarukhShem occurrence context prevents the earlier evening
בלחש direction from leaking into this printing. No English is supplied.

The documentary Shabbat condition retains the source Hebrew-script German
rubric; the expanded condition uses bilingual editorial labels and locally
declares Shabbat. Reusable Biblical words remain ungated. All true/false/unknown
branches are verified in compiled output and production electronic CSS.

Side-column acrostics and the poem attribution are source commentary, outside
recited words. The generic annotation output preserves note kind and semantic
acrostic markup. New Mishnah labels follow their own milestones so a range
transclusion retains the first א. Earlier reviewed label conventions are
unchanged. All thirteen compiled units match the draft words exactly; eight
labels, seven acrostic notes and missing-English behavior are checked.

Human snippet adjudications settle the Hebrew readings. Actual
blind disagreements and later erroneous deletion proposals remain archived;
correctly located isolated crops confirm all printed repetitions. The original
אֶחָת pointing typo is preserved in sic with intended אַחַת in corr. The partial
Lev2:11 quotation identifies half-verse b. Independent guideline/order review
covers the actual generated XML and includes enlarged punctuation evidence.

The German instruction retains the human-confirmed samekh in איינגעסאַלטעט.
Its preceding word's final glyph remains unreadable: ז is tentative and encoded
as tei:c with cert="low", not a silent normalization to modern German. Independent
review verifies all human corrections and the uncertainty markup. Only this
instruction remains unaccepted; all thirteen prayer/study modules are reviewed.

Draft build:252schema-valid XML files; naming/features/registry/URN references
pass;218targeted tests and636subtests pass. Scans56,58,59 are accepted, bringing
coverage to64of355. Scan57 remains source-glyph-uncertain. Refreshed draft exports
retain that status; stable accepted exports are not replaced. Prior pilot leaves
60–65 already cover the continuation; resume new primary reading at66 while
tracking the unresolved instruction separately. Whole-volume acceptance is false.
The refreshed documentary PDF and expanded HTML pass their checks. A reported
top-margin defect in the expanded PDF was a preview-reading mistake: a fresh
render and PDF coordinates show Ana Be-khoaḥ correctly below the running head
(prayer words at102.507pt; header bottom76.849pt). The unchanged expanded PDF
passes reinspection; no exporter correction was needed.

### Continuation: physical PDF scans66–69

Add bilingual Psalms34,90,91 after Psalm19; include only the Psalm91 continuation
from scans70–71, leaving their Psalm135 text for the next installment. Preserve
Hebrew34's verse-line layout and the other printed running paragraphs. Chapter
and verse milestones remain independent of page/paragraph boundaries, including
English34:18 and both witnesses of91:2 across different source page breaks.

The Hebrew-only second91:16 is a structural occurrence of the existing canonical
verse, without an invented English repetition or a new prayer identity. Human
point-for-point confirmation authorizes its reuse. Raw primary, blind, enlarged
and isolated readings retain actual disagreements and explicit retractions.
Human answers settle the two resh hataf-pataḥ vowels, pe/ayin of פעלך, bet of בהם,
lamed of לנו and meteg on the shin of יושיע. Independent final review verifies
their exact placement and approves guidelines, alignment and order.

The259-file draft validates;12whole-psalm word comparisons and6cross-page verse
checks pass. Scans66–69 are accepted, bringing coverage to68/355. Only Psalm91’s
continuation is reviewed on70–71; resume primary work with their Psalm135 text.
The earlier scan57 German glyph remains low-certainty, and whole-volume/service
acceptance remains false. Final previews retain that overall draft status.

### Draft continuation: physical PDF scans 70–73, with Psalm 136 continuation 74–75

Add bilingual Psalms 135 and 136 after the Hebrew-only Psalm 91 closing repeat.
Use existing canonical chapter/verse identities, with page boundaries inside
135:12 and before 136:17. Psalm 135 retains running paragraphs; Psalm 136 uses
verse lines and semantic refrain spans. English 136:2, 3, 8, 17, 18 prints lead
and refrain on one line. Raw first readings retain the initial missed line-8
layout, with its later independent correction recorded separately.

English 136:25 is absent in the edition. Both documentary and expanded spines
use ranges 1–24 / Hebrew-only 25 / bilingual 26, preventing alignment drift or
invented translation. Documentary range starts are edition-qualified; the end
inherits the start's project. The expanded spine remains edition independent.
Each response stays inside its verse scope, including two-line English 26.

The full Divine Name audit individually inspects 89 enlarged occurrences across
14 pages: restore 88 printed holams, preserve the distinct Elohim-type form in
Deuteronomy 11:17 on scan 20. Retain prefixes, all other points and accents.
Original primary/blind hashes, superseded full-page judgments, actual reviewer
provenance and the rejected הודע locator match remain in the evidence. Generated
XML changes are independently verified. Three earlier Halleluyah forms also
have first-lamed hataf-pataḥ. The human confirms that the additional tiny mark is not a meteg. All six
Halleluyah occurrences retain first-lamed hataf-pataḥ without meteg; the
three earlier reviews are restored after independent final verification. Jerusalem 135:21 uses
lamed + qamats + CGJ + hiriq, verified by codepoint.

The range also exposed empty pre-range poetry shells in marker compilation:
24 earlier lines became blank lines before Hebrew verse 25. Exporter correction
and regression tests are isolated in processor PR 300, outside this content
branch. The existing rubric export dependency remains PR 299. Validate actual
compiled range order, all 26 Hebrew / 25 English refrains, exact whole-psalm
words and both electronic/PDF books. The 2026-11-12 no-meteg adjudication
completes this installment: full scans 70–73 are accepted, bringing coverage
to 72/355. Only Psalm 136 continuation is accepted on 74/75; Psalm 33 is next.
The earlier scan 57 German glyph remains separately low-certainty. Prayer
words and the previously inspected draft exports are unchanged.

### Continuation: Psalm 33 on physical scans 74–77

Add Hebrew and English witnesses for all 22 verses, reusing existing canonical
Bible chapter/verse identities from the Tanakh and Birnbaum projects. Preserve
both source running paragraphs. Verse 17 crosses each language's page boundary
without a duplicate milestone: Hebrew וּבְרֹב / חֵילוֹ, English “its might” /
“it will not save.” Source chapter citations are linked notes. The expanded
morning spine transcludes the chapter after 136:26, using one bilingual sequence
and edition-independent URNs; documentary references qualify their editions.

Primary and blind English readings match exactly. Enlarged individual crops
confirm all 13 Divine Name holams, superseding the blind full-page omissions.
Preserve the actual count rather than the reader's mistaken prose count of 15.
The shin meteg in Shiru 33:3 is independently settled. Record the attached
final-he loop and Yismach chet knob as printing shapes rather than extra signs.
Keep every raw reading and follow-up, corrected crop box and actual reviewer
model/effort in the source evidence.

Human adjudications settle every displayed question: Rannenu has first-nun
hataf-pataḥ without dagesh; Heitivu's meteg is on tet, Maasehu's on shin, and
Vayehi's on yod beside its segol (none on he). The Ohev/Kones/Noten holams,
Kones kaf dagesh, defective Ledor/Vador spelling and Zamru-lo maqaf are
confirmed. Independent final XML review and exact codepoint checks verify
these hosts. Actual committed pre/post source comparison verifies only four
Hebrew word changes; English, all other words and structure are unchanged.

Full scans 74/75 are now accepted, bringing coverage to 74/355. Only Psalm 33's
continuation is accepted on 76/77; later Psalms 92/93 are next. The earlier
scan 57 German glyph remains separately low-certainty. Complete-volume and
service acceptance remain false.

Validate the 265 XML files, feature/name/registry/reference checks, exact words
and 22 shared verse identities in both compiled books, and the four internal
verse-17 page breaks. Inspect refreshed PDF pages and electronic links after
the human corrections. No new exporter changes are needed; use the separately tracked PR 300 range fix and
PR 299 PDF rubric fix for previews.
