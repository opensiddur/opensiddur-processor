# Heidenheim–Marmorstein, first day of Rosh ha-Shanah (1965)

Contribution to [issue 214](https://github.com/opensiddur/opensiddur-processor/issues/214).
The complete project is the 355-leaf Archive item
`mahzor-lyom-rishon-shel-rosh-hashanah-day-one-jenny-marmorstein-1965`.
The current installment is a **reviewed pilot with partial front matter**, not a complete mahzor. Its PRs remain draft while the full-volume transcription is unfinished.

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

The requested second reader is available: `claude-opus-5-5`, medium effort.
It reads scan images through read-only tools, without receiving the primary
reading, OCR, registry text, or another edition. Preserve its raw reading and
ambiguities, exact model/effort and session identity. Never count its confident
output alone as image adjudication: the pilot already demonstrates different
consonant and pointing readings between the two readers.

Compare primary and independent readings using `scan.compare`; record pointing
separately from words. Settlements require the exact reading hashes and image
evidence for every disputed reading. Changes invalidate old adjudications.
Unresolved ambiguity stays pending human review. On 2026-11-08 the user confirmed the three pilot marks already encoded by the first reader: the dagesh in הבריות, no extra mark in ליראיו, and the mappiq in לשמה. Those confirmations clear the pilot uncertainties; they do not certify other pages. `--draft` is required to build
unreviewed text. Structural success is not source-fidelity approval.

The pilot includes Torah blessings, Barukh She-amar, I Chronicles 16:8–36 from
Hodu, a Hebrew-only Psalm 24, and the page-direction example. The English title page, copyright page, translator’s preface and following blank leaf are also independently read. The cover emblem and Hebrew calligraphic arranger credit remain pending. Hodu's remaining
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
biblical references are citation notes, not prayer words. Four prayer leaves
(s62–s65, Hebrew/English printed pages 16–17) are now fully accounted for, in
addition to the four completed front-matter leaves. Psalm 34 and the rest of the
volume remain incomplete.

`verify --check` must fail until every leaf is explicitly accounted for and its
content independently reviewed. A page with only an excerpt is never complete.
After the pilot is adjudicated, proceed through the entire volume in printed
order, including front matter and appendices, maintaining the review ledger.

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
