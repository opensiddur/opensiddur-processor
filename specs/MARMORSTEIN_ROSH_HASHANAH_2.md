# Digitize Heidenheim–Marmorstein: Rosh ha-Shanah, second day

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

The Hebrew and English volumes share the existing edition projects:

- `prayerbook_for_the_new_year-heidenheim-1965-he`
- `prayerbook_for_the_new_year-marmorstein-1965-en`

Add a distinct second-day entry point `day_two.xml` and separate source bibliography
for volume two; preserve day-one files, settings, targets and accepted evidence.
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
