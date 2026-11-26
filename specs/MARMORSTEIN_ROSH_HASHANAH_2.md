# Digitize Heidenheim–Marmorstein: Rosh ha-Shanah, second day

Track execution in the [working checklist](MARMORSTEIN_ROSH_HASHANAH_2_CHECKLIST.md).
Each page batch must complete its source, encoding, order and presentation gates
before acceptance is recorded and the next batch begins.

Current acceptance is recorded in the source repository's `progress.json` and
`batches/maariv_s5_s24/checklist.json`. The opening implementation covers scans
1–24 of 385; scan 25 begins morning material. Startup checkpoints below are historical.

## Scope and source

Continue issue [214](https://github.com/opensiddur/opensiddur-processor/issues/214)
with the second volume of the 1965 *Prayerbook for the New Year*: Hebrew arranged
by Wolf Heidenheim, English translated by Jenny Marmorstein, published by Victor
Goldschmidt in Basle. Verify the title-page details against this volume's images.

- Archive item: `mahzor-lyom-sheni-shel-rosh-hashanah-day-two-jenny-marmorstein-1965`.
- Source record: <https://opensiddur.org/?p=69124>.
- Source record identifies CC0 and credits Aharon N. Varady for imaging and document
  preparation. Preserve the record separately from digitization responsibility.
- The web page republishes the translator's preface from volume one; do not insert
  that web addition into this volume's documentary transcription unless printed
  here. An editorial cross-reference can point to the companion volume.

Required reading: [scan digitization instructions](SCAN_DIGITIZATION_INSTRUCTIONS.md),
[general encoding guidelines](../schema/JLPTEI-3.md), the authoritative
[ODD](../schema/jlptei.odd.xml), [URN scheme](SIDDUR_URN_SCHEME.md), and the
[first-day specification](MARMORSTEIN_ROSH_HASHANAH_1.md). Day-one customs and word
readings are comparisons, not evidence of what this volume prints.

## Coordinated repositories and preservation

Use branch `feat/marmorstein-rosh-hashanah-2` in managed processor, sourcetexts and
opensiddur-projects worktrees, based on updated default branches. Initialize this
processor worktree's submodules, dependencies and compiled schema. Make source
and project changes only in their standalone worktrees. Do not commit the moved
release submodule pins.

Keep source data in `sources/marmorstein_rosh_hashanah_2/` and cache images under
`output/marmorstein_rosh_hashanah_2/`, outside Git. Use the shared Archive client
and scan utilities. The initial download entry point reuses the existing
book-profile-based metadata/OCR downloader; no day-one assembly is invoked.

User decision (2026-11-25): volume two has its own project pair. Hebrew and
English share a title field; the first-day project names remain unchanged:

- `prayerbook_for_the_new_year_second_day-heidenheim-1965-he`
- `prayerbook_for_the_new_year_second_day-marmorstein-1965-en`

Use `index.xml` as the documentary project entry point with its own volume-two
source bibliography; preserve day-one files, settings, targets and accepted evidence.
Use `urn:x-opensiddur:text:siddur:rosh_hashanah/day_two` for this volume's structural
entry point, registering structural identities before publishing them. Prayer
identities remain canonical and edition-independent. Reuse existing modules only
when image comparison establishes the actual wording; otherwise encode another
witness or a bounded printing in accordance with the existing project model.
Never overwrite a day-one witness simply because both use the same canonical URN.

Extend the existing `machzor_expanded-opensiddur-he` with a second-day structural
sequence under its existing distinct root. Keep a single bilingual order, using
canonical transclusions, with documentary Hebrew, documentary parallel and expanded
second-day settings. Preserve the first-day settings and recitation paths. Source
selection must distinguish printed witnesses and day-specific structural occurrences
without inventing new canonical identities for repeated prayers.

Second-night decisions: preserve the printed doubled leela and omit English
where absent. Malkenu is the existing named optional wording, independent of the
calendar. Vattodienu and the fire/Havdalah pair depend on Motzaei Shabbat; close
their scopes before Vattitten Lanu and Shehecheyanu respectively. Keep Yigdal
outside the minyan/mourner gate. Preserve the printed Divine Name forms, including
an absent holam and the two-yod abbreviation. User723 concerns the combined
shin-dot/holam in שָׁלֹשׁ; it does not authorize supplying a missing holam in the
Tetragrammaton. The earlier broader statement here was an unsupported inference
and is withdrawn. Genuine authorized reconstructions remain separately evidenced.

The second-night entry has its own day2/Maariv selection and output profile in
the existing expanded project. Preserve the first-day index and its shipped
profile unchanged, including Erev Rosh ha-Shanah. One global source-priority list
cannot prefer two different editions for the same canonical prayers when an
undated combined index displays both days, so each per-day profile selects its
own shared bilingual sequence. Compatible unprinted Hebrew dependencies keep
explicit first-day bibliography and licences; they introduce no first-day English
notes or translations into the new documentary projects.

Day-two Yitbarakh ends before its untranslated Psalm113:2 tail, which the new
spine transcludes once separately. The older first-day Hebrew Yitbarakh range
includes that tail. Record this cross-witness extent divergence and keep a
separately reviewed first-day terminator correction as maintenance work; do not
silently fall back between those two ranges in the new sequence.

## Inventory, opening batch and review

1. Inventory every Archive leaf, including blanks, cover, title, other front matter
   and appendices. Derive `pages.json` from metadata. Image-verified printed labels,
   languages and reciprocal facing-page relationships belong in
   `page_corrections.json`; machine labels remain unverified candidates.
2. Communicate with one-based physical PDF scan pages. Each `tei:pb/@facs` uses the
   unique Archive leaf URL (`sN` is leaf `n(N-1)`); `@n` preserves printed pagination.
3. Begin at scan 1. Cache scans 1–12 as the opening survey, then set the first
   substantial reading batch at a coherent textual boundary visible in the images.
   Do not skip the opening material or begin at a familiar prayer later in the book.
4. Record a primary image reading and a blind second image reading separately.
   Preferred reviewer is Claude Opus 5.5, medium effort; record the actual model,
   setting and session. The user has authorized Claude reviews and Archive scan
   sharing. Keep the first transcription and OCR away from the blind reviewer.
5. Compare readings, enlarge disputed marks and ask numbered questions immediately
   before their complete snippets. Persist answers by occurrence and question ID;
   continue the established question sequence after 859 to avoid ambiguous references
   to old questions. Preserve explicitly critical uncertainty with its evidence.
6. Review source fidelity, encoding-guideline adherence, canonical reuse, alignment,
   rite/calendar conditions and expanded order independently. Bind each approval
   to its exact payload and guidelines. Do not label inventoried/OCR pages accepted.
7. Generate and inspect documentary and expanded PDF/HTML for the batch. Complete
   source, structure and presentation review before accepting it and moving on.

## Encoding and recitation decisions to establish from this volume

- Preserve Hebrew pointing, source abbreviations, Hebrew-script German instructions
  and English notes; no substitute translations for absent English passages.
- Treat Hebrew linkage words beside English as alignment evidence, not translated
  prayer words. Biblical citations become anchored notes without enclosing
  parentheses in generated links; verify number-only citations in context.
- Use chapter/verse and prayer-part milestones with exact terminated scopes,
  independently of layout. Record genuine source typos through sic/corr.
- Keep Rashi-script role and ritual instructions semantic, without `rend` styling.
  Distinguish congregation, cantor and combined role abbreviations by the image.
- Preserve documentary page directions using edition-qualified page references and
  optional navigation clauses. Expand the directed text in recitation order while
  retaining ritual actions, repetitions, speaker directions and conditions.
- Read any alternating or page-bottom piyyutim as continuous complete alternatives,
  with one module per work and unique structural occurrences. Do not interleave
  their fragments in the expanded recitation.
- Reuse established calendar/service/quorum/rite settings, declared locally. Test
  actual second-day selections and undecided alternatives, rather than copying
  first-day gates or importing Birnbaum's different customs. Derive only settings
  that the calendar/registry supports; do not fake dates to select wording.
- Keep morning material and Avinu Malkenu within Shacharit where applicable; inspect
  the actual transition through Torah service and Musaf. Group related appendices
  under appropriate parent bookmarks rather than flattening all headings.
- Retain margin scan links on source-page changes, including returning pages, without
  per-paragraph repetitions. Inspect provenance at each canonical range's start.

## Acceptance and delivery

Maintain separate counts for inventory, encoded pages, independently reviewed pages
and accepted pages. The inventory determines this volume's total; never inherit
355 from day one. No acceptance is claimed by this startup specification.

Run schema, naming, feature, registry and reference-database checks. Test reusable
behavior with synthetic cases, not real source-word snapshots. Inspect actual
PDF/HTML links, columns, note order, conditional alternatives and bookmark hierarchy;
freeze artifact hashes and completed QA reports before independent presentation review.

Deliver linked processor/source/project PRs referencing issue214. Merge processor
registry/schema dependencies first, rerun project validation against main, then merge
dependent projects. Preserve day-one outputs and acceptance evidence throughout.

## Startup checkpoint (2026-11-25)

All **385** leaves are inventoried; scans1–12 are cached and their printed labels
and languages have a primary image survey. The opening prayer is scan5 (printed1),
followed by second-night Maariv on scan6 (printed2); it is not a continuation of
the first-day volume's scan numbering.

Primary front-matter readings cover scans1–4. Two draft `day_two.xml` documents
have been generated, leaving the accepted day-one files untouched. Scans3–4 have
complete draft word readings; scan1's emblem and scan2's calligraphic signature
remain partial/disputed. **No page is accepted.** No service or expanded-day-two
sequence or export setting has yet been generated.

Claude Opus5.5 completed a blind preliminary image reading of scans1–12. The CLI
requested medium effort, while its response labels itself low; retain both in
`opening_review.json`. The reader explicitly omitted Shema cantillation on
scans6/8/10. Consequently this is not a completed independent pointing review.
Do not count it as final approval or use its words as an independent primary
transcription. Finish primary reading and targeted image review, adjudicate the
emblem/signature, then complete encoding, order and presentation review.

## Project separation after front-matter acceptance

The original shared-project startup is superseded by the user-approved separate
volume-two projects. Preserve its four accepted source readings and historical
artifacts unchanged. Bind the renamed publication URNs, bibliography pointers and
new index entry points through an independent equivalence review before claiming
that the migrated presentation is accepted. The scans5–24 batch covers תפלה and
the complete second-night evening service through Aleinu.

## Documentary citation markers

Use `typography.notes.anchor: superscript` in this volume's documentary output
profiles. In the Deuteronomy11:13–21 Hebrew excerpt, the default zero-width
interlinear marker drifted away from its text anchor. The supported superscript
setting keeps the marker attached; the four remaining-Shema Hebrew/parallel
PDF/HTML excerpts passed independent presentation review with this setting.
This is a configured-output decision, not a change to the exporter default.
The source record `batches/maariv_s5_s24/shema_remaining_presentation_review.json`
binds the reviewed outputs; its excerpt approval does not accept complete scans.

## Reviewed night-service module decisions

The scan12 Hashkivenu witness preserves one printed paragraph and maps its ending
through the existing `hashkivenu/hapores_sukkat_shalom` root milestone. Use that
root or the whole prayer in the service spine; this witness does not provide the
deeper `/text` identity used by the first-day separate ending file. Kaddish uses
Aramaic paragraphs inside the Hebrew project. Contextual speaker directions and
calendar/quorum or seasonal selection are still separate required spine audits.

Scan24 prints Aleinu without an English counterpart in this batch; leave that
translation absent. Scan15 prints “Thou has created”: keep that wording in source
evidence and encode an eventual obvious-typo correction with `sic`/`corr`, rather
than silently changing the transcription.

## Implemented opening installment

The source-bound recipes generate 47 prayer modules with 87 Hebrew/English
witnesses. Documentary `second_night.xml` keeps the Hebrew-only entrance before
the shared `maariv_service.xml` boundary, so the English evening heading cannot
float above the entrance. Each language preserves its own printed roles.

The expanded project's `second_day_evening.yaml` selects `second_night.xml`
directly. Its first-day `index.xml` and `undated.yaml` remain unchanged. One
global priority list cannot preserve both volumes' translation gaps in a combined
undated entry. The second-night profile prefers this volume's Hebrew and English,
with compatible first-day Hebrew dependencies and no substitute English.

Aleinu maps only its established whole-prayer identity; this witness does not
claim incompatible first-day child scopes. Complete Kaddish combines the new
half Kaddish with existing ending identities. Borrowed Kaddish and Yigdal retain
first-day scan provenance inside the actual transcluded ranges. Their words and
canonical scopes remain unchanged; the provenance and paragraph changes have
separate equivalence evidence.

Final code, condition-matrix, schema/reference and PDF/HTML presentation approvals
are bound to frozen inputs in the source batch ledger. Excerpt and historical
checkpoint approvals do not replace that complete-batch acceptance record.
