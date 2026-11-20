# Heidenheim–Marmorstein, first day of Rosh ha-Shanah (1965)

Contribution to [issue 214](https://github.com/opensiddur/opensiddur-processor/issues/214).
The complete project is the 355-leaf Archive item
`mahzor-lyom-rishon-shel-rosh-hashanah-day-one-jenny-marmorstein-1965`.
**Accepted current encoding: 254 complete scan pages of 355, 720 literal Hebrew/English witnesses and 87 canonical realization payloads.** Coverage comprises PDF 1–253 plus the earlier Hebrew-only appendix pilot 351. The installment is accepted through HaMelekh HaQadosh; all source, importer, generated encoding, identity, alignment, recitation-order and independent PDF/electronic reviews are complete. All 756 XML files validate. The two historical PDF 8 Ashrei corrections are independently adjudicated with exact before/after baseline hashes. No human question is pending.

**Remaining volume: 101 unencoded scan pages; continue at PDF 254 with Attah Vechartanu.** The coordinated digitization PRs remain drafts while this work continues. Current acceptance and validation evidence is recorded in `musaf_s238_s253_acceptance.json`:143 importer tests/126 subtests;125 registry/feature tests/138 subtests;472 exporter XSLT/typography tests/179 subtests;60 actor-cue page-edge positions;36 rite/optional-clause print states;12 source-boundary cases;4 morning service selections;24 batch browser cases and 3 whole-book browser checks. All 3 cumulative PDFs have no overfull boxes, missing glyphs or unresolved internal destinations.

[Exporter PR 311](https://github.com/opensiddur/opensiddur-processor/pull/311) is merged. It supplies occurrence-local named-wording selection through `opensiddur:variant` and `j:option/@corresp`; use it for genuine textual differences rather than service/calendar conditions. The accepted export checkpoint additionally used the separate preview fixes in PRs 310, 312 and 313. These exporter dependencies remain distinct from source acceptance. The coordinated digitization PRs remain drafts while work on the volume continues.

The identity search examined 15,640 registry/project files with Hebrew marks removed and found the existing `urn:x-opensiddur:text:poem:v_yeetayu_kol_leavdekha` and its eight stanza identities. Reuse those identities for this edition and its Marmorstein translation; do not register a new Veyeetayu identity or import the existing Zangwill translation. The remaining identities, spellings and registry hierarchy have passed independent review and the naming/registry checks.

The initial broad whole-root reuse implementation was withdrawn after a negative independent audit. A narrower design is independently approved: pure shared Kedushah parts, pure canonical homes for existing formulas, literal documentary contexts where a page turns inside a phrase, and content-bound correction attestations. Its implementation passed independent code review, including strict guards on deferred page boundaries. A fixed660-witness baseline rejects changes to accepted literal words, fragment fields or unrelated metadata; only explicit identity/pointer changes are allowed. Pure-parts libraries cannot publish a whole-prayer URN or participate as service occurrences. Canonical homes have no page breaks. An opt-in literal context must have an actual scan transition and retains its original break positions. Corrections in a shared home require exact source-context matching, complete source attestations, separation from wording options, and printed/corrected projection proofs. Exact generated encoding, alignment and order passed a separate independent review; final export acceptance remains distinct. A historical queued PDF8 comparison subsequently confirmed two exact source corrections in Ashrei and its documentary copy. The baseline amendment records the old/new hashes and source adjudication; its other658 literal witnesses remain unchanged.

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

The printed Harachum chet is retained in `sic`, with he only in `corr`. Its correction authority and scan evidence remain in the source correction record. The pre-existing Pachdekha English correction must be attached to its shared home and bound to the actual English scan pages: the old printing is s27 and the new printing is s251 (the paired Hebrew opening is s250). References to “caller250” in earlier design notes name that opening, not the English image identity.

A short quotation inside a stanza may keep its chapter/verse milestones inside `tei:seg type="quotation"`. The corresponding importer quotation record uses explicit `inline_scope: true`. This keeps the reference boundaries resolvable while preventing the parallel compiler from turning the inner phrase into a separate stanza row. Canonical chapter/verse `@n` values remain present; the renderer's existing verse-number visibility setting controls whether they are shown. See the bounded-inline-quotation rule in `schema/JLPTEI-3.md`. Verify both exact quoted-range resolution and PDF/electronic layout; do not remove reference milestones to conceal a rendering problem.

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

### Larger continuation: physical scans 76–87

Work in coherent batches of roughly 10–12 leaves where the service boundaries
permit. This batch adds the morning printings of Psalms 92–93, Yehi Khevod,
Ashrei, Psalms 146–150, the Hebrew repetition of 150:6, and the closing Barukh
verses. It stops before the standing rubric and Vayvarekh David on 86/87.
Scans 76–85 have full transcription scope; 86/87 remain partial. Unanswered
source questions prevent acceptance of the affected Hebrew readings.

Keep the first canonical Hebrew witnesses of 92/93/Ashrei and add the English
translations actually printed in the morning section. Preserve the native
morning Hebrew variants with structural occurrence milestones and canonical
quotation sources. Earlier Hebrew-only documentary positions need their own
occurrence roots: omitting a reference from the English index alone does not
prevent the parallel compiler from finding the new canonical translation.
Verify the compiled English slots are empty. Expanded recitation may reuse a
translation printed elsewhere in this volume, through canonical prayer URNs.

Reuse Birnbaum's Yehi Khevod and Barukh compilation/quotation identities. For
verses already mapped in Hoshiah et Ammekha, Emet veemunah, or Vetimlokh,
use occurrence correspondences and canonical `source` links. Whole Psalm 146
must still include its contextual last verse. Preserve bare chapter context
and numbered verse milestones for quoted occurrences without registering a
second canonical Bible definition. Compare duplicate counts with the baseline;
do not claim the whole earlier project is free of preexisting duplicates.

Keep the printed Hebrew 150:6 repetition without inventing a documentary
English counterpart. Expanded order repeats the existing canonical verse in
both languages. Preserve the unpointed printed כל. Encode the English misprint
“nur” as `sic` with `corr` “nor”. Retain the printed קטו יח citation on scan 80
as a note attached to the final Ashrei verse; citations may occur on later
leaves of a passage. The earlier scan-8 printing has no such citation.

Independent enlarged review supplies the first-lamed ḥataf-pataḥ in the new
Halleluyah forms and in morning Ashrei's יהללוך and ואהללה. The user settles
both Jerusalem occurrences in Psalm 147:2 and 147:12 as
lamed + pataḥ + meteg + CGJ + ḥiriq. Preserve the old primary/blind readings and the actual reviewer
model, configured effort, self-reported effort, and adjudication evidence.

Every pointing question must show its enlarged source snippet with a readable
number and description directly beside it. Include the complete vowel row and
room beneath it; verify the requested word is actually present before showing
the crop. Prefer direct message image embeds if tool images fail to display.

Final independent review approves the batch's encoding, alignment, order,
English readings, and inherited documentary context routing. All twelve
displayed questions are resolved. Human adjudication changes exactly seven
Hebrew words, with no change to English, page boundaries or reference scopes.
In Psalm 72:19, כל keeps qamatz and its following maqaf; הארץ has a meteg
on alef beside qamatz. Independent follow-up verifies the precise hosts.
All ten full leaves 76–85 are accepted, bringing the total to 84/355.
The old scan-57 ambiguity remains separate. Validate all 292 XML
files, names/features/registry/references, and 40 exact bilingual unit
comparisons in the compiled books. Keep the separate exporter dependencies
in PRs 299 and 300; this branch changes importer authoring support only.

## Continuation from physical PDF scan 86

The next larger batch covers Vayevarekh David on scan 86 through Yishtabbach
at the top of scans 96–97. Scans 86–95 are its full-page scope; 96–97 remain
partial, stopping before the half-Kaddish rubric. The standing instruction on
86 extends through Barekhu beyond this installment and remains a ritual rubric.

The source modules reuse the existing Vayevarekh David, Attah Hu, Vayyosha,
Az Yashir, Ki Ladonai, Nishmat and subsequent blessing identities. Biblical
quotations use chapter/verse milestones independently of printed paragraphs,
poetry lines and page breaks. The importer now supports fragments of a verse
on successive printed poetry lines, including lines shared by adjacent verses.
A regression case checks shared lines, continuation lines and a page boundary.

Scans 94 and 95 each have Hebrew and English on the same leaf: printed pages
32 and 33 respectively. They are not a facing-page pair. Nishmat continues
from Hebrew 92 and English 93 into the corresponding columns on 94. Missing
English Exodus 15:19 stays absent, in a separate Hebrew-only source module.
The documentary Song retains its two different printed forms of Exodus 15:18;
the expanded spine assembles the first occurrence and an explicit repeat
through edition-independent URN transclusions. Already mapped biblical verses
use source-linked occurrence correspondences, without new canonical identities.

Independent reviews approve the encoding, alignment, recitation order and the
canonical ranged transclusion of Az Yashir through its first Exodus 15:18,
followed by an explicit canonical repeat. Runtime comparisons verify both
languages, the omitted English verse and sixteen continued page boundaries.
Nine full leaves are accepted, bringing the total to 93/355. Scan 90 remains
partial: the probable meteg in הָֽלְכ֥וּ is encoded with low certainty after the
human reader could not settle it. The original PDF offers no higher resolution.
The older scan-57 ambiguity remains pending separately. Scans 96–97 remain
partial; continue there with half Kaddish. Raw primary readings, actual model
responses and unresolved marks remain separate from accepted readings.
Images and generated exports stay outside Git.

Final PDF QA found that starting a range at the outer Az Yashir division
collapsed its parallel verse groups. Start at the source-linked
quoted_exodus_15_1 verse milestone instead, retaining the canonical Bible 15:1
source. The ranged URI ends at quoted_exodus_15_18. Runtime verification must
find eighteen separate verse groups in each language, as well as checking
word content, followed by the explicit canonical repeat. This adds one
occurrence context and changes no prayer words.

## Draft continuation from physical PDF scan 96

The next larger batch spans scans 96–109, starting with the half-Kaddish
rubric after Yishtabbach and ending with Yotzer ha-Meorot before Ahavah
Rabbah. Twenty new bilingual source modules preserve both festival poems,
the weekday/Shabbat opening alternatives, the angelic Qedushah and Ofan.
The three newly identified insertions were searched against the registry,
aliases and current project XML; the Ofan opening vowels and its identity
spelling remain provisional pending human snippet 3.

All new modules remain explicitly draft. The accepted total stays 93/355.
Raw primary readings are frozen separately from actual independent image
readings and subsequent patches. Five numbered source questions are open;
other faint marks remain in the independent reports for adjudication. No
source acceptance may be inferred from schema validation or compilation.

The expanded weekday opening has an editorial condition rubric. Source
Shabbat headings remain condition rubrics, disappearing when Shabbat is
known true. The parenthetic Ofan wording selects exactly one branch; its
printed 'some say' alternative is a labeled, Shabbat-only standoff note.
The importer now supports j:condition on source commentary/citation notes,
with a regression checking true, false and undecided calendar contexts.
Six Ofan stanza groups keep the shared boundary outside the alternatives.
Actual compiled weekday/Shabbat checks verify both languages, the retained
stanza scope and conditional-note suppression.

Retain documentary routing instructions in the documentary index; omit
the obsolete below-page direction from the expanded spine. Quoted biblical
passages keep chapter context, verse milestones, bounded source spans and
explicit termination. El Adon reuses its six canonical stanza extents.
Two obvious English typos retain their source readings in sic/corr.
Source lexical adjudication and final visual export review remain required
before this batch can be accepted.

Draft export verification passes for 357 XML files, 80 compiled prayer-word
comparisons and both calendar paths. The importer tests pass 61 cases and
12 subtests. Documentary and expanded PDF previews were rendered and inspected;
the expanded new section has a bilingual Shema-blessings heading. These checks
do not certify the source readings. The five human snippet questions, other
faint marks and the provisional Ofan opening identity remain pending.

## Continuation: physical PDF scans 108–125

The next larger batch starts at Ahavah Rabbah and ends with the silent Amidah,
before the reader's repetition below the rule on scans 124/125. Seventeen new
bilingual modules share one expanded sequence. Reuse the existing Hebrew-only
El Melekh Ne'eman with its no-minyan condition; supply no English counterpart.
The earlier human Ofan questions are resolved, including the opening אִהֵל;
other earlier source uncertainties remain separately recorded.

Repeated Biblical passages use existing canonical identities in bounded source
spans and registered occurrence correspondences on chapter/verse milestones.
The importer accepts `chapter_corresp` and `source_reference_corresp` for these
contexts. A quote inside an active prayer-part must use explicit contexts deeper
than that part, so refdb's component-depth fallback cannot truncate its scope.
The existing canonical correspondence default remains valid for first mappings.
Local editorial commentary may target an explicit segment `anchor`; the מלכנו
note uses this mechanism without inventing a condition for the source variant.
The source instruction joining אלהיכם to אמת remains in the expanded sequence;
its exact transcription is pending human adjudication.

English review covers 2,835 words across all seventeen units and three citations.
Seven full English leaves are newly accepted, bringing acceptance to 100/355.
Hebrew remains draft, with seven numbered human questions and additional fine
marks awaiting adjudication. The source repository retains actual blind readings,
frozen primary readings, nonblind follow-ups, structural review and resolutions.
Structural approval and exporter checks never imply source acceptance.

Final checks cover 391 XML files, 68 compiled unit/language word comparisons,
eight Shabbat/quorum/recitation combinations, names, features, URNs and reference
resolution. The importer suite passes 67 tests and 12 subtests. The documentary
96-page and expanded 101-page draft previews were rendered and visually checked.


The seven numbered human questions for scans 108–125 were resolved and applied
on 2026-11-13. Their original answers, exact Unicode choices and unchanged
dagesh confirmations are recorded in the source evidence. Both documentary and
expanded Emet junction instructions use the corrected wording. Additional Hebrew
fine-mark adjudication and review reconciliation remain pending; acceptance
stays at 100/355.

## Continuation: physical PDF scans 124–145

The next larger batch covers the reader's repetition, starting below the rule
on 124/125 and ending with the complete Adirei Ayummah hymn on 144/145. It stops
before ובכן דיין אמת אתה / Lael Orekh Din. Twenty-eight new bilingual source
modules preserve the printed words and page-source boundaries. The documentary
edition presents complete weekday and Shabbat alternatives, with one file per
piyyut; bottom-of-page continuation blocks are joined to their own works rather
than interleaved with the other day's text. The expanded
spine assembles one exclusive route and repeats the canonical refrains where
the printed incipit cues require them. Etten Lefoali reuses its existing identity,
`urn:x-opensiddur:text:poem:eten_lefoali_tsedeq_shimon`.

Long reusable poems retain source-layout occurrence boundaries for provenance,
independently of whole-work transclusion. Adderet Mamlakhah, Aafir Nezer, and
Shemo Mefoarim are each reached once as complete works in each language's
documentary index. Printed page boundaries and unique Archive facsimile URLs
remain inside their files. Five abbreviated resume directions have separate
navigation contexts, using optional `repeat_cue/corresp`, so the complete
documentary work includes each cue exactly once without extending a canonical
prayer's scope over it. The
expanded sequence transcludes the canonical prayer words instead. All stanza
scopes are explicitly terminated before unrelated text or navigation.

The human source readings resolve the Frankfurt direction: Attah Hu is omitted
in Frankfurt am Main, and recitation begins directly with Tair Vetaria. Both
structural arrangements use `opensiddur:rite/frankfurt_am_main=false` around
Attah Hu and its ark actions. Metz excludes both recitations of Tair and both
parenthetical Kol Yoshvei passages with `opensiddur:rite/metz=false`. The second
Kol omission is inferred from its matching parentheses, as the user judged
likely; it is not represented as a second explicit printed instruction. These
local features use the existing open rite registry and do not imply other
communities inherit either custom.

Canonical poems remain reusable independently of structural placement. Each Kol
stanza's correspondence begins before its conditional and ends after the
matching end marker. Source parentheses are marked only where printed (the
first English occurrence is unparenthesized). The native Metz omission direction
stays with the first conditional Kol stanza inside the complete documentary
work. Transcluding that canonical stanza again can repeat its relevant native
label when the rite is undefined; a known setting resolves the condition. The expanded order replaces source omission
directions with actual selections. Eight regional/calendar combinations verify
Frankfurt, Metz, and Shabbat separately, in addition to the eight quorum and
recitation combinations.

All four human answers and subsequent independent source adjudication are
retained. The German transcription slip גזייך is corrected to גלייך against
the image; the printed דאַ: is preserved. The explicit human opening
אַאֽפִּיר נֶֽזֶר אָיוֹם is retained over a conflicting later model proposal.
Remaining Hebrew consonant/pointing review and per-line speaker sigla are
explicitly incomplete. All new modules remain draft and acceptance stays 100/355.
Actual blind readings for eleven facing pairs, the frozen primary, comparisons,
and successive structural reviews/resolutions are retained separately.

The repetition requires both a minyan and repetition selection, with declarations
scoped locally. Ark-opening and closing directions are ritual actions, retained
as such. A local melody description has no generic Reader correspondence and
cannot replace unrelated role labels. Schema coverage reaches 447 XML files;
182 compiled unit/stanza language comparisons and eight setting combinations
verify the new order and scopes. The importer suite has 68 tests and 12 subtests.

Literal edition-qualified URN links exposed a separate exporter issue. Its fix
is isolated in processor PR #301, not included in this digitization branch.

## Continuation: physical PDF scans 144–183

The repetition continues from Uvekhen Dayyan Emet Attah and Lael Orekh Din
through the Silluq, repeated Amidah, Avinu Malkenu, Full Kaddish and Torah
prelude (144–161). Eighteen new modules supply 27 language witnesses. Scans
150–155 are six consecutive Hebrew pages: their missing English is not filled.
The source English Silluq stops before the mystical continuation; its printed
incomplete notice is preserved. Modim remains one cross-page paragraph, while
the documentary spine interposes Modim Derabbanan at its printed position.

The human readings of Dayyan Emet Attah, Vekhaalot / Middallei and Veyuqdash
are preserved. Shemo Mefoarim's earlier German direction uses the corrected
שְׁמוֹ מְפָאֲרִים. The unreadable Fürth abbreviation remains uncertain. The
expanded Avinu Malkenu retains all 38 existing petition identities and selects
the printed order or the independently checked Fürth order through the existing
open rite feature. No petition is omitted on the strength of that abbreviation.

The next larger installment covers 22 leaves, scans 162–183, from taking out
the Torah through the haftarah blessings. Twenty-two bilingual modules add
44 language witnesses. Reuse existing prayer identities and existing service
contexts, including Berikh Shemeh, the Ribbono Malle Mishalot family, Torah
blessings, and haftarah blessings. Scripture uses Genesis 21:1–34, Numbers
29:1–6, and 1 Samuel 1:1–2:10; do not create replacement canonical identities.
The documentary first-scroll and haftarah headings are emitted before their
verse-range transclusions so that range extraction cannot discard them.

The expanded Torah service requires a minyan and continues under the morning
selection. It uses five weekday aliyot (1–4, 5–12, 13–21, 22–27, 28–34) or
seven on Shabbat (1–4, 5–8, 9–12, 13–17, 18–21, 22–27, 28–34). Each aliyah,
including Maftir, has Barekhu, the congregation's response, the caller's repeated
response, and the before/after blessings. Split a selected range at source-only
aliyah labels to keep those labels out of expanded recitation without skipping
any verse. Repeat the Thirteen Attributes and Vaani three times, transcluding
their prayer-word scopes so the documentary ג״פ directions are excluded.

Gate Berikh Shemeh, Shema and Echad on the source's Frankfurt exclusion and a
local inclusion variant, preserving the reader-aloud direction. Keep Shabbat
insertions in both languages' final haftarah blessing conditional; known settings
remove the printed parentheses, and the Hebrew conjunction joins Israel without
an intervening space. Preserve ritual scroll actions. Vezot haTorah remains at
its explicit printed location after Maftir; the general lifting rubric's possible
application at the first lifting remains an open custom question. The bare
Half-Kaddish URN resolves to this maḥzor's Ten Days witness.

New importer source fields are `qere_ketiv` on fragments (exact printed `written`
span and selectable `read`), and `end_reference_before_instructions` on segments
(close a verse before its aliyah rubric while retaining the enclosing chapter).
Both interpretations enter review payloads so changing them invalidates review.
An ambiguous or missing printed qere/ketiv span fails generation. Quoted clauses
use existing half-verses or named parts; the exact Qedushah call/response in
Isaiah 6:3, the Numbers 9:23 closing formula, and the Exodus 34:7 prefix before
Venakeh have named boundaries in both supporting Hebrew Bible projects. Preserve
all Bible characters when placing these boundaries.

Every source page boundary retains its original printed label and unique Archive
facsimile. Optional navigation to printed page 85 remains documentary and loses
only its removable clause while its destination is untranscribed. Clearly mark
the unfinished source span before the separate daily-psalm appendix. Expanded
coverage stops after scan 183; the next installment begins with the Shofar service
on 184. Source acceptance remains 100/355. Blind readings, the frozen primary,
the primary's initially missed faint accents, fresh image-only accent candidates,
source disputes and subsequent structural reviews are recorded separately. Draft
structural approval does not accept unsettled pointing or source wording.

The draft progress note belongs to the documentary index (`documentary_notes`),
never a reusable prayer module. Move its anchor after the last main-service
section as coverage advances. Distinguish the oleh's role from the congregation
when repeating Barekhu; reuse the registered instruction role. Review discovery
includes nested independent-reader reports without accepting draft readings.

Current verification covers 518 book XML files and six supporting Bible files,
107 tests plus 22 subtests, 250 compiled word comparisons, 16 conditional
combinations, two Fürth orders, and 50 exact quotation decisions. Documentary
and expanded previews contain 139 and 158 pages. Both electronic exports have
unique IDs and resolved internal links. Exporter reference corrections remain
in separate PR 301; optional absent destinations must suppress their navigation
clauses while required unresolved references still fail validation.

## Shofar, Torah return and cantor prayers (PDF184–199)

The next draft installment covers sixteen physical leaves, ending immediately
before Musaf half-Kaddish on PDF200. It adds 27 modules / 47 language witnesses.
Scans188 and189 mix Hebrew and English and carry distinct printed labels 83 and 84;
190/191 both carry 85. Use the explicit image-verified label map; no arithmetic
between languages or their printed labels is valid here.

Reuse existing Shehecheyanu, Yequm Purqan, Mi Sheberakh, Hanoten Teshuah, Uvenuchoh,
and Hineni identities. In particular, Hineni retains the existing five canonical
stanza boundaries. New identities cover genuinely unmatched blower/cantor prayers
and the Shofar blessing; service occurrences of repeated psalms and verses remain
contexts referencing canonical Scripture. The cantor's Exodus 19:19 quotation ends
before מאד: `vayehi_qol` is bounded by `meod` in both Hebrew Bible providers without
altering any Scripture words. The Numbers 29:1 quotation is half-verse b. The
adapted Psalm 90:17 phrase does not claim the complete canonical verse.

English Psalm 29:7 is absent and stays absent. Source typos “May it by” and
“Wis compassion” use sic/corr while source readings remain unchanged. The printed
Moses / Menasseh annotation is an alternate wording, not two recited names:
fragment `alternatives` maps one exact printed span to two or more `j:option`
readings, and its interpretation enters review hashes. Preserve the human-read
נ״א annotation in a commentary note with abbr/expan. Never mix alternatives with
qere/ketiv or other overlapping fragment readings. Citation abbreviation
interpretations also enter their review payloads.

The expanded weekday Shofar sequence contains all 30 sound calls, nine rows and
one final prolonged sound. Sound names and שֵׁב are actions, not recited prayer
words. Keep both sit directions. Separate the blower's quiet prayer from the
following full Psalm 149; do not label that psalm quiet without source evidence.
Congregation and blower occurrences of Ashrei HaAm are distinct structural
occurrences of one canonical text. The human adjudication confirms that congregational וכו׳ directs only the
printed Psalm 89:16, without adding verses 17–18. Shabbat skips Shofar and enters the communal
prayers. Ashrei remains available without a minyan; public Torah return and
cantor duties require one. Select Psalm 29 on Shabbat and Psalm 24 otherwise.

The native cantor direction requires the same four verses before Hamelekh and
before Musaf Kaddish. Expose opening / hamelekh boundaries within HaEl Betaatzumot
without changing its documentary words. Repeat the verse transclusion at both
positions; keep the morning selection running into a locally declared Musaf
prelude. Move the documentary index-only progress note after the cantor prayers,
before the separate daily-psalm appendix.

Emit source page breaks only at real boundaries. Mid-page modules retain their
own facsimile provenance without creating false page starts. `opening_page` can
place a real boundary before a source rubric; a heading must not duplicate it.
Human-confirmed source cantillation is retained, including the likely erroneous
zarqa over peh in פניך; do not invent its correction. Draft structural review and
source reading acceptance remain separate; accepted leaves stay 100/355.

### Musaf installment, physical scans 200–223

The next 24 leaves supply the complete quiet Musaf Amidah and the opening
repetition through Avot, including *Uppad meaz*. They add 41 modules and 81
language witnesses. Source acceptance stays separate: 224 leaves have independent
image readings, while 100/355 leaves are accepted. Fine marks and uncertain source
labels remain draft; resolved human readings do not accept a whole page.

The Frankfurt-and-affiliated-communities direction on printed p. 93 selects the
left offering formula exclusively, through the existing `frankfurt_am_main`
setting. Its incipit context is `offering_formula/useir_lekhapper`; the default
formula is `offering_formula/ushenei_seirim`. The shared preamble remains common.
The English prints only the default formula, so the Frankfurt branch has no
invented translation. Sabbath offerings and Yismechu preserve their printed
parentheses as marked conditions; resolved weekday/Shabbat selections remove the
markers. Quiet and repetition recitation declarations are local, as is Musaf's
service-time declaration, so morning selection continues through Musaf.

The human-confirmed piyyut opening is `אֻפָּד מֵאָז לְשֶׁפֶט הַיּוֹם`; the provisional,
unpublished identity was corrected to `poem:uppad_meaz`. Six shared stanza
milestones preserve the two printed paragraphs independently of alignment.
`בְּמָשְׁכָם` and `בְּזָכְרָם` are exclusive weekday/Shabbat readings. The reader's
`ח׳` label stands before both alternatives. Ark actions travel with their native
Hebrew modules; no unprinted English direction is supplied.

Source alternatives retain their sigla in apparatus notes at the exact choice.
Misod preserves `ממ״ה` with the human-confirmed expansion `מלך מלכי המלכים` inside
its selected option. The importer therefore permits abbreviation metadata within
an alternative reading and an optional choice `xml_id`; both enter review hashes.
Whole-unit marked conditions also enter the review payload. These capabilities
are covered by importer tests, in addition to actual compiled selection checks.

Exodus “וכל העם רואים” uses the common canonical numbering, 20:18. The opening
of Zechariah 9:15 is bounded by `adonai_tzevaot_yagen` and the following `veakhelu`
verse part, placed in both WLC and Miqra al pi ha-Masorah without changing any
Scripture characters. The following liturgical petition is outside the quotation.
Original English misprints retain `sic/corr`; absent translation remains absent.

Validation covers all 646 book XML files, two supporting Zechariah files, naming,
features, registry and reference resolution, 162 actual compiled occurrence and
language comparisons, eight weekday/Shabbat × Frankfurt × minyan selections,
and 106 exact bounded Scripture quotations. Every new physical leaf has one
source XML `pb/@facs`. Parallel collation retains 21 of those 24 markers; the
leading markers for Hebrew s204, English s205 and English s223 remain a separate
compiler follow-up, with source XML and module facsimile provenance intact.
The next installment begins on physical scan 224 with the Musaf repetition's
Gevurot and piyyutim. The repetition and full volume are not yet complete.

Post-review visual QA distinguishes encoded alternatives from a resolved reading:
external exports show unresolved `j:option` forms with the later forms parenthesized;
inline transclusion takes the first. The 162 word comparisons explicitly compare
first readings and do not assert that the external renderer selects only one.
Exact-choice apparatus notes retain the source siglum without repeating the
alternative words already displayed beside the main reading. Documentary Musaf
has a structural service heading so its running header does not retain the preceding
cantor-prayer heading. The seven Torah quotations on s212–s218 now have
image-adjudicated cantillation; the raw candidate ledger includes historical/resolved items and is
not a count of unresolved readings.

The source-review closure now accepts all 12 English leaves in s200–s223 and
all 12 Hebrew leaves: all 24 of this installment's leaves, and 124 of 355 overall.
The accepted witnesses bind their exact current reading payloads to the initial
blind page readings, subsequent independent image audits, and adjudication records.
All displayed human questions through 70 have resolutions. Crops 60–62 and
71–73 were used for primary adjudication. The final non-Torah source/guideline
audit, enlarged-crop review, and human adjudications 74–77 close all 41 Hebrew
witnesses and 40 English witnesses. The source review for s200–s223 has no
unresolved reading. Representative rendered export checks now pass; the
remaining volume and older review backlog are still incomplete.

Editorial reconstruction uses `tei:seg type="supplied" subtype="scholars"`,
with its basis in a note. The scan s217 words “of our” use this encoding; the
false “devises” emendation on s211 has been removed after image confirmation.
Optional מלכנו, של יעקב and כל use marked `opensiddur:variant` conditions,
with edition-independent condition URNs, instead of duplicated wording options.
Nine actual compilation cases verify true/false/unset selection, and electronic
exports verify the undecided delimiters. The repetition heading already belongs
to the documentary spine; a temporary duplicate module heading was removed.
Refreshed checks pass 162 compiled occurrence/language comparisons, 106 bounded
quotations, eight Shabbat/rite/minyan selections, feature/name/URN validation,
and both HTML exports' internal links and popover targets. These checks were
refreshed after the final source decisions. The documentary/expanded PDF previews
have 172/191 pages, settle in three LaTeX passes each, and have no unresolved
printed references; all 30 documentary internal links resolve. Representative
Musaf pages were visually checked for bilingual alignment, source points,
conditional layout, headings and apparatus placement. Rendering uses separate
exporter PR301 and the recorded temporary rubric keep-with-next preview patch;
the renderer worktree is restored afterward. These remain draft previews.
All 24 unique source page markers survive in documentary XML. Merged exporter
PR301 also preserves all 24 in parallel compilation, including the three formerly
lost leading markers. The regression checks show unchanged visible HTML and
byte-identical PDF typesetting input. The earlier preview/QA snapshots retain
their historical pre-fix marker counts.

## Completion review of the encoded backlog, 2026-11-15

The final human decisions settle the German rubric's final zayin on scan 57
and the meteg in הלכו on scan 90. Both complete leaves are now accepted.
Current source-image comparisons and an independent guideline follow-up also
close the seven English Yotzer leaves 97, 99, 101, 103, 105, 107 and 109.
Acceptance is now 174 of 224 encoded leaves (355 leaves in the volume).
The remaining encoded material is under review; no new installment is started.

The review corrects scan-confirmed spelling and punctuation, including מן־כל
in the morning Kaddish and plene spellings in the Yotzer piyyutim. Exact
quotation sources now use Isaiah 6:3/qadosh, Ezekiel 3:12/b and Psalms 92:2/a.
Occurrence-context verse markers retain the containing canonical verse number,
even when the bounded quotation source names a subverse. Regression coverage
checks named verse-parts and accentual half-verses.

The expanded weekday and Shabbat Yotzer alternatives each have one bilingual
condition rubric and a matching local declaration. Documentary continuation
rubrics remain in the source; the local declarations suppress them in expanded
recitation, including when the outer day choice is undecided. Actual compiler
checks cover unknown/weekday/Shabbat and weekday Frankfurt. Frankfurt Bameh
Madlikin now uses the same frankfurt_am_main feature as the later rite rules.
Independent guideline follow-up approves these changes. Source fine marks are
accepted separately, never on the strength of structural approval alone.

Actual new source/guideline reports, frozen inputs, correction decisions and
human resolutions are retained under independent/completion_review_2026_11
and the completion_review_2026_11_*_acceptance records in the sources.
The complete Melekh Azur Gevurah, At Chil Yom Pequddah, Taalat Zu and Even Chug
piyyutim now have reconciled Hebrew source and alignment acceptance. Existing
canonical identities are retained; corrected At/Zu spellings retain nine legacy
aliases, and new speaker boundaries are occurrence contexts. Other Hebrew
witnesses remain under review. Existing preview
PDFs predate these completion-review corrections and remain draft previews.

The English backlog now has scoped approval for all81 prayer-text witnesses in
scans125–199 and41 documentary/editorial rubric records. Five bounded Hebrew
Yotzer modules and scan96 also clear source/guideline review. Original incomplete
English remains incomplete; obvious printed by/be uses sic/corr. Reusable Torah
speaker/action descriptions travel with modules; unprinted English conditional
labels are removed. Split expanded rubrics cite their actual source173.

Documentary community prayers carry the source Shabbat condition and its rubric;
a page-opening conditional rubric receives its source pb before the condition.
Documentary Shofar passages obey the original weekday-only instruction while
the original mixed navigation directive remains visible outside their scope.
Actual compiler checks cover unknown/false/true selection in both languages.
Current registry, importer and subverse checks pass169tests and38subtests.
Actual parallel compilation verifies eight source-text comparisons and three
new shared speaker rows across the four accepted piyyutim. Other Hebrew witnesses
remain pending: no English approval certifies its Hebrew counterpart, and no
source acceptance is inferred from schema validation.

The bounded morning Amidah review accepts Adonai Sefatai and retains fine-point
questions for the other seven witnesses. Eight missing continuation-page markers
are restored in four bilingual modules (Emet Veyatziv and three Amidah modules).
Three clear Hebrew paragraph joins retain independent prayer-part boundaries.
Actual parallel compilation preserves all eight markers and matches all eight
source-text comparisons; these checks do not certify pending Hebrew readings.

Human adjudications70–80, including the explicit80he-meteg follow-up, now
close all source disputes in Naalah Vedin, Melekh Bedin, two short repetition
passages, the Kaddish preface and the Shofar blower’s quiet prayer. Existing
canonical identities are retained, with two new shared reader-clause occurrence
contexts outside both day branches. Four source-word comparisons and twelve
actual day/language/poem checks pass. Scan126 is fully accepted.

The printed Taalat Zu acrostic description now travels with the reusable poem,
with the scan128 marker before it. Actual independent source/placement review
and single-transclusion verification close scan128. The blessing before the
haftarah retains its complete printed cantillation:26accents,3metegs,1silluq;
all30host placements and two bilingual source-word comparisons pass. Neither
that witness’s acceptance nor schema checks certify other passages on174.
Acceptance is174/224encoded leaves;50remain under review. Current human
questions81–88 concern exact occurrences on116and118; earlier questions are closed.


### Completion review checkpoint: 179 accepted encoded leaves

Acceptance now covers 179 of 224 encoded leaves; 45 remain under review.
All human questions 7–105, including the separate 80 and 95b follow-ups,
are settled and applied. The current open batch is 106–113 on PDF scan122
(printed p.47), with enlarged numbered source snippets.

The ordinary Amidah Avot, Gevurot, Qedushat Hashem, Qedushat Hayom and
Avodah now have source/guideline acceptance, as do the four Hebrew-only
repetition units Qedushat Hashem, Qedushat Hayom, Modim and Hodaah tail.
Actual negative source reports remain intact with exact human adjudications;
whole-payload replay checks bind the corrections to their reviewed snapshots.
The independent structural follow-up approves the precise Malkeinu note
anchor, coherent Modim contexts and bounded Hodaah tail correspondences.

A runtime check exposed unrelated English Eruv Tavshilin being attached to
a Hebrew-only repetition unit. The exporter paired unmatched transclusions
by position. The isolated fix is processor PR309, commit93f33b1, with
206 passing tests and16 passing subtests. Actual maḥzor checks with that fix
preserve four Hebrew-only modules without unrelated English, both real
documentary Modim targets, the page155 marker and the precise note anchor.
This dependency remains separate from the digitization branch. Final volume
exports and visual acceptance still require the fix and the remaining review.

The earlier174/224 checkpoint and its then-open81–88 batch are historical.
Existing PDF/electronic previews predate these corrections and do not certify
the current encoded volume. The 131 unencoded leaves remain outside this
completion-review scope.


### Completion review checkpoint: 180 accepted encoded leaves

Exact human106–113 readings are applied, with nine occurrence-specific metegs.
Nodeh Lkha, first Selah and Lanu retain their confirmed dageshes; Byadekha
retains segol and gains its dalet meteg. The HaEl stroke is the alef-lamed
ligature and adds no mark. Nothing propagates to other occurrences.

An actual final source/guideline review explicitly approves silent Hodaah
and Sim Shalom, with unchanged English alignment and no unresolved findings.
Frozen whole payloads match current data and human-after records; NFC and
four actual bilingual compiler comparisons pass. The separately reviewed
Malkeinu commentary now has its acceptance record, completing scan154.
Acceptance is180/224encoded leaves;44remain. Scan122stillrequiresElohaiNetzor.
All646generatedXMLfilesvalidate. The isolated compilerfixPR309remains a
dependency of final parallel export acceptance. Current questions114–124
concern distinct Shema occurrences on scans110and112, with numbered enlarged
source snippets. All previous questions7–113and80/95bfollowups are settled.
Final PDF/electronic visual review remains pending.


### Completion review checkpoint: 183 accepted encoded leaves

Acceptance now covers183of224encoded leaves;41remain. Allhumanquestions
7–135plus80/95bfollowups are settled and applied; nohumanquestionisopen.
ElohaiNetzor, sixShema-sectionHebrewwitnesses, YehiRatzonTemple,
repetitionAvotOpen andMisodChakhamim bodies now have source/guideline
acceptance. Their citations and sixdocumentaryrubrics are accepted separately.
Scans110,122and124becamecomplete. Scan112stillrequiresEmetVeyatziv.

Human114–124adds sixoccurrence-specificmetegsandtheBachartaBETdagesh,
retainsBatachnuwithoutcolonandVehaadamah11:17withmunach. Human125–129
settlesfinalQadmoniyyotwithholamhaser,ChasdeiDALETdagesh,FiPEdagesh,
BeyameinuBETwithoutdageshandGomelGIMELdagesh. Human130/131confirms
LeimorLAMEDdageshandthisMisodvariant'sנ״א. Human132–135confirms
allfourremainingheadingmarks. Twoactualsourcepunctuationomissions are
restored: Deut11:21Al–HaadamahmaqafandMisod'sfinalcolon. Exactprior
Jerusalem124qamatz+meteg+CGJ+hiriqretainedwithoutreopening.

Actualcurrent-source andguideline reports remain unaltered, including
negativeverdicts and explicitlimits. Acceptance records adjudicate each
actualfindingandbindfrozenwholepayloads. The two markholds in positive
reports(LeimorandMisodsiglum)were explicitlywithheld untilhuman130/131.
Originalrepetitionprimary/blindfilesareselectedforAvot/Misod/header,
ratherthantheearlierreaderpairwhosepage124scopeendsbeforetherepetition.

TwelveactualShema bilingualcomparisons andeighttailcomparisons pass.
Fiveactualexpandedrepetition/minyancases keepbothprayersandarkactions
together,onceeach; knownfalseflags suppress theentirescope. The separate
exporterfixPR309commit93f33b1 remains a finalparallel-exportdependency.
The acceptedpointedheadingandthesixunpointedinstructions/descriptions
haveactualsourceandguidelineclosure. EmetVeyatzivand8Yotzerwitnesses
areunderfreshboundedreview. ExistingPDF/HTMLpreviews remain stale;
finalvisualacceptance has not been claimed.


### Completion review checkpoint: 186 accepted encoded leaves

Acceptance now covers186of224encoded leaves;38remain. EmetVeyatziv has
actualfinalsource/guidelineapproval with no openfindings after human136–146.
The missingExodus15:11cantillation now preservesall11accent/silluqhosts
and2metegs;13orderedhosts areverifiedprogrammatically. HaragtaRESHmeteg,
Gaalta/GadolGIMELdageshesandUmagbiahmappiqareapplied. Goel's apparent
damage is an ALEF-LAMEDligature,confirmedbyhuman;letters/pointsretained.
KayyemetYODsegolandtheabsenceofGaalta-periodmatchthescan. Actualpaired
compilation preservesbothlanguages;17correspmarkers match, comprising
9prayerpartsand4chapter/versepairs. Twelve was the inputsegmentcount,
not the numberofmilestonecorrespondences. Scans112/114/116 arecomplete.

FiveEnglishYotzerwitnesses have freshstructural/alignmentapproval with
unchangedsourcewords. Three scopehashes were temporarily stale while their
quotation/condition boundaries changed; theirprevioussourceapproval is
retainedwithactualnewguidelineclosure. This restoresEnglishpagevalidity,
withoutcountingthosepagesasnewsourceacceptance. Native103/105confirm
page-openingdirectivesandmid-sentencecontinuedShabbatrubricplacement.

Twohalfversequotations now carry explicitnestedchapter/verse/halfverse
markers andmatchingterminators, withtheexistingcanonicalhalfverseURI
onboundedsource. Sixdeeperoccurrencecontextsare registered;theexisting
quote targets andcanonicalidentitiesare unchanged. ExactPs92:2/aand
Ezek3:12/b resolve inWLCandMiqra,withoutcoarsening. EightactualHE/EN
quote-rangechecks and30day/languagecases preserveexactextentsandwords.

The importer now supports an optionalsegment condition_end_corresp that
ends the condition after the segment with that existingcorresp. The ElAdon
continuedShabbatrubric covers allremainingstanzas inbothlanguages; its
endpoint is existingstanza6. Nestedscopes retain their own ends. Missing,
backward,ambiguousandcrossingendpoints are rejected;thereviewhashrecords
the endpoint. Two regressiontests exercise reference/page boundaries and
invalidscopes. All171tests and41subtests pass. This is importer/source work;
the separate exporterfix remains PR309.

Exacthuman147–158 adds14occurrence-specificmetegs, joinsandpoints
שֶׁלַּיּוֹם,corrects the specifiedShabbatBETtopatah,andaddsKolKAFdagesh.
The raisedmarkbyMale is a printingartifact. FourclearElAdontranscription
errors arecorrected: defectiveSovvim/Tovim, Zivamcolon, and noVayizrach
maqaf. A proposedNotnimLoMaqaf remains withheldpendinghuman171. Hebrew
Yotzeracceptance is stillpending, includingadditionalfaintmarkfindings in
the actualthree-sourcefollowup. No genericglyphapproval is inferred.

Allpresentedquestions7–158and80/95bfollowups are settled. Current159–171
have enlargednumberedsnippets. TwoalreadyencodedTorahBiblewitnesses are
under boundedsource/guidelinereview; nonewinstallment has started. Existing
PDF/electronicpreviews remain stale; finalvisualacceptance is pending.


The continued-page marker is now emitted before the segment condition and
its own rubric, so that the rubric inherits the new source page rather than
the preceding page. The regression checks this order. After rebuilding the
reference database,12actualstanza/day/languagecases preserveElAdonstanza2
and3word extents with balancedconditionalmarkers, including starts/ends
inside the extended source condition. The8quoteand30day/languagecases
also pass after this marker-order correction. CachedYotzerimages match the
Archive-scandataoriginalpixel dimensions(1368×2264),so no additional image
detail was inferred from enlargement. Further faint marks remain pending.


Completion-review checkpoint after human195–210: all presented source questions
through210 are settled. ElAdon and LaelAsherShavat now have complete independent
source, guideline and alignment approval; every reading key on PDF scan104 is
current. Accepted coverage is187of224encoded leaves;37encoded leaves and131
unencoded leaves remain. Current questions211–224 concern distinct HakolYodukha
occurrences on PDF102, with inspected numbered source crops. No earlier human
answer is reopened. Twelve exact meteg clusters and four negative readings were
verified; all646generatedXMLvalidate, and8quotation extents,30day/language/unit
cases and12conditional stanza cases pass. Evidence and frozen review inputs
are committed in the source project's completion_review_2026_11 records.


After human211–224, Hakol's11confirmedmetegs andLAMEDsheva are encoded;
222remainswithoutmeteg and224retainsLAMEDdagesh. Its actualindependent
source review confirms those decisions but records4newdistinct uncertainties
(now241–244). EtShem'salreadysettled160a–cfindings are independentlyclosed
andaccepted. Currentquestions225–240concernKhevodoIhel;241–244concernHakol.
The22Melekhrefrainoccurrences remain explicitlyqueued andarenot silently
resolvedfromsimilarwords. Acceptedcoverage remains187of224encodedleaves.
All646XMLvalidate;8quoteextent and30day/language/unitcasespassafteredits.


After human225–244, ten exact metegs are encoded, eight negative readings
retained, both240dageshes retained, and243recorded as a printingartifact.
232usesLAMED,241CHETand244onlytheSECONDאפסALEF. ActualcompleteHakolsource
review plus focused241–244closure now approve the Hebrew witness. Every
readingkeyonPDF102iscurrent:188of224encodedleavesareaccepted,36encoded
leavesremainunderreview. The remaining grouped question245shows all22
MelekhrefrainMEMclusterswithnumberednativecrops;noneisdecidedbyinference
fromotheroccurrences. Khevodoandotherbacklogsourceacceptanceremainpending.
All646XMLvalidate;8quoteextentand30day/language/unitcasespassafteredits.


After human245, KhevodoIhel has15markedMEMrefrains (2,3,4,8,9,10,14–22)
and7explicitlyunmarkedones (1,5,6,7,11,12,13). ActualXMLtokenorder and6
bilingualdaycasesverifytheentiremixedpatternandsharedQOFcontinuation.
Completeindependentsource/guideline/alignmentreviewapproves the poem and
bothcommentarynotes. EveryreadingkeyonPDF106/108iscurrent:190of224encoded
leavesareaccepted;34encodedleavesremainunderreview. Allpresentedquestions
through245aresettled. A new8-witnesssource/guidelinebatchonPDF132–140is
running,withthecontinuousShabbatalternativeandactualroutingcontextincluded.
SourceimagesremainoutsideGit;finalPDF/HTMLvisualacceptanceisstillpending.

Completion review after human readings 246–260 restores the missing acrostic
description, corrects source words and speaker cues in the continuous piyyutim,
and adds bounded bilingual quotation contexts. Canonical scripture URNs remain
the `source`; partial quotations use shared occurrence-context chapter/verse
milestones, with explicit terminators before the surrounding poem resumes.
The existing `dea_5` context is retained while its source is corrected to
Psalms 105:8. The passage “זכור אזכרנו עוד” uses Jeremiah 31:20, verified
against the existing WLC project rather than the reviewer's proposed 31:19.

For a quotation inside a single marked conditional fragment, `quotations`
records the exact text span, canonical `source_reference`, `chapter_corresp`,
and `source_reference_corresp`. The importer preserves the condition and its
source parentheses as one scope, inserts a bounded `seg` and chapter/verse
milestones inside it, and leaves unrelated words outside the quotation.
Ambiguous or overlapping spans are errors; quote metadata participates in
review freshness and registry validation. Both occurrences of Kol Yoshvei
retain independent context identities while referring to Zechariah 14:9.
The expanded sequence retains both outer Metz guards and specializes that
same rite locally inside each guard, avoiding a duplicate imported rubric.

Ten unrendered repeated page-heading records from the former fragmented
arrangement are retained explicitly as superseded documentary records, with
their uncertain raw pointing unaccepted. The complete alternate works remain
governed by the higher-level Shabbat condition and its printed German rubric.
No source words were deleted from generated output by this reconciliation.


Completion review after human readings 246–263 accepts eight additional Hebrew units, the source variant note, and the rendered directives for the continuous weekday/Shabbat alternatives. The corrected block now has explicit internal speaker alternation and 25 bounded bilingual scripture quotation contexts; canonical text identities are reused. All presented questions through263 are settled. The actual compiler passes50 bilingual quotation-extent checks and12 rite/refrain cases, and all646 generated XML files validate. Current acceptance is193 of224 encoded leaves;31 encoded leaves and final PDF/HTML visual acceptance remain. The next seven-unit review around scans136–144 is being triaged. Historical repeated page labels remain preserved, unaccepted as raw pointing, in superseded records.


Completion review through human277 accepts the remaining morning piyyutim, Avinu Malkenu and full Kaddish, with bounded bilingual scripture contexts and corrected source readings. Current acceptance is202 of224 encoded leaves;22 encoded leaves in the Torah and shofar/cantor sections remain under final review. The source Avinu abbreviation remains explicitly low-certainty after human examination; its faithful critical encoding is accepted without claiming a certain letter. All646XMLvalidate, and current naming, feature and URN-reference checks pass. Final PDF/HTML visual acceptance and the131 unencoded leaves remain outstanding.


The next completion checkpoint accepts206 of224 encoded leaves, including the full Genesis21, Numbers29:1–6 and Samuel1:1–2:10 readings, five shofar witnesses, Psalm29 and the cantor four-verse group. Exact enlarged reading adjudication corrected four biblical marks and separated the parashah/aliyah labels in printed order. Ten human questions278–287 are displayed with numbered enlarged snippets and remain pending. Further Torah/return source corrections are preserved as draft material awaiting final review; no source acceptance is inferred from schema validity. All646XMLvalidate and current names/features/URN checks pass. Final PDF/HTML inspection remains outstanding;131 leaves remain unencoded.


### Canonical realization and Musaf review closure

PR311 is merged (d324c5a); its managed worktree is archived. The repeated
Musaf contexts now transclude canonical prayer/Bible identities instead of
registering edition wording as new prayer identities. Named local wording
conditions reproduce each printing; Hebrew and English share the expanded
sequence. Shared homes identify both printings, retain exact source provenance,
and keep contextual page breaks and rubrics in their own occurrence files.

All660 literal unit witnesses and18 separately hashed realization witnesses
are independently accepted. Coverage is238 complete leaves, with excerpts on
240 leaves; PDF238–239 stop before the lower Kedushah. No reading questions
remain through human323. This is acceptance of encoded scope, not of the
unencoded remainder of the355-leaf volume.

The independent code and XML audits, including rejected intermediate rounds,
are retained under sourcetexts `independent/musaf_s224_s239/`. Review hashes
bind occurrence metadata, canonical selections, the shared expanded order and
source printings. All676 generated documents schema-validate;106 importer
tests and57 subtests,38 actual compiler wording/scope/name checks and32
canonical-home/context checks pass. Naming, feature and registry/reference
checks are required before publishing the coordinated branch update.

Exporter issues discovered during export review remain isolated: PR310 fixes
PDF rubric/note layout, PR312 preserves Divine Name semantics through inline
transclusion, and PR313 preserves each local rubric when its edition wins
instruction selection. Preview QA uses their combined temporary branch;
none of these exporter fixes is folded into this digitization change.
