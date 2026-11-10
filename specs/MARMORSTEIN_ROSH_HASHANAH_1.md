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
alignment and order audits bring the accepted total to 29 leaves. Raw blind
readings of s24–s25 remain unassembled. PR 297 is merged; character-highlighting
support for the required `tei:c` encoding is isolated in exporter PR 298.

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
current accepted installment and remains to be assembled from the next blind readings.

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
