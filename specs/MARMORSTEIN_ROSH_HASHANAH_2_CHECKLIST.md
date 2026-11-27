# Second-day maḥzor: working checklist

Use this checklist with [the implementation specification](MARMORSTEIN_ROSH_HASHANAH_2.md)
and [scan digitization instructions](SCAN_DIGITIZATION_INSTRUCTIONS.md).
The source repository's `sources/marmorstein_rosh_hashanah_2/progress.json` and
batch evidence determine current acceptance, not a historical checkpoint here.

## Volume setup

- [x] Create coordinated processor, source and project worktrees from updated defaults.
- [x] Initialize processor submodules, its own dependencies and compiled schema.
- [x] Identify the second-day scan, bibliography, licence and scan credits.
- [x] Inventory all 385 physical scans; retain OCR as unverified candidates.
- [x] Cache scans1–12 outside Git; verify unique scan identities and image hashes.
- [x] Survey opening printed labels/languages and record evidenced corrections.
- [x] Preserve first-day text/settings and release submodule pins; separately review
      the necessary volume-two bibliography additions to the edition indexes.
- [x] Open linked draft PRs: processor331, sources60 and projects110.
- [ ] Map the remaining services/appendices and choose substantial, coherent batches
      from actual page boundaries. Verify each newly encountered label and pairing.

## Every batch: complete these gates in order

Create a source batch record naming the exact scans, partial-page boundaries,
input hashes, evidence paths, outstanding questions and accepted scope.
Use `pending`, `passed` or an evidenced `not_applicable` for each gate.
An unchecked gate prevents acceptance; a reviewer must approve any exclusion.

1. [ ] **Scope and images:** account for every page/region, including blanks and
       paratext; cache full-resolution images and verify scan/facs identities.
2. [ ] **Primary reading:** transcribe images faithfully, including instructions,
       pointing, abbreviations, notes, marginal cues and reading order. Save it
       before consulting the independent transcription; identify every omission.
3. [ ] **Blind second reading:** record actual model, requested effort, session,
       image hashes and raw output. Require all marks in scope; a reading that
       explicitly omits cantillation cannot satisfy a pointing review.
4. [ ] **Comparison/adjudication:** compare words, marks, order and extent;
       settle disagreements against enlarged images. Ask numbered questions with
       each question immediately before its complete image snippet. Preserve
       answers by occurrence and keep uncertain critical readings explicit.
5. [ ] **JLPTEI:** encode exact documentary text, citations as notes, sic/corr for
       source mistakes, semantic rubrics, per-leaf paratext gates, complete main titles
       and responsibility statements, unique facs, independent milestone
       scopes and existing canonical identities. Preserve bibliography/credits.
6. [ ] **Translation alignment:** verify every shared boundary and actual extent;
       omit linkage words and absent translations without shifting neighbors.
7. [ ] **Recitation/conditions:** assemble canonical transclusions in order;
       expand turns/repetitions; keep ritual actions and speaker directions.
       Verify true/false/undecided settings, local scope and day/rite variants.
       For non-recited front matter, record why this gate is not applicable.
8. [ ] **Independent encoding/order audit:** review guideline adherence, identities,
       source extent, alignment, conditions and expanded order; resolve findings.
9. [ ] **Mechanical checks:** schema, naming, features, registry and reference
       resolution; relevant synthetic behavior tests. Prove that existing day-one
       witnesses and settings remain unchanged or separately review any change.
10. [ ] **Exports:** build the applicable documentary Hebrew/parallel and expanded
        PDF/HTML; inspect actual text, columns, note order, hierarchy, marginal
        page-change links and navigation destinations. Record visual sampling
        separately from mechanical all-page checks.
11. [ ] **Independent presentation review:** provide frozen artifacts/screenshots,
        completed reports and hashes. Resolve all blocking findings; record any
        accepted nonblocking limitation with its exact scope.
12. [ ] **Acceptance:** bind source, encoding, structure and export approvals to
        current hashes; require no unresolved reading disputes. Record explicit
        critical uncertainty rather than claiming an unreadable mark is certain.
        Update page counts only for complete accepted scans, commit/push evidence
        and generated projects, then start the next batch.

## Current batch A: scans1–4, cover and title/imprint leaves

Front matter is a coherent preliminary batch; larger prayer batches follow it.
The blind survey of scans5–12 does not make those pages part of this acceptance.

- [x] Scope: all four source leaves, including the emblem and calligraphic signature.
- [x] Cache images and save independent primary reading before comparison.
- [x] Save blind preliminary second reading and its explicit limitations.
- [x] Finish enlarged emblem/signature readings and resolve remaining differences (user860–861).
- [x] Complete the documentary encoding, including emblem lettering and monogram.
- [x] Independently verify title correspondence, missing counterparts and credits.
- [x] Record prayer alignment and recitation/expanded order as independently approved
      not applicable to this non-recited batch.
- [x] Obtain independent guideline/encoding review; resolve findingsR1–R3.
- [x] Current files pass schema, naming, feature and registry grammar checks;
      day-two URNs resolve in both projects. Synthetic tests:26 passed,14 subtests.
- [x] Generate and inspect both front-matter PDF/HTML variants and all four scan links;
      test paratext omission and prove preservation of original index content.
- [x] Obtain independent presentation review and close all blocking findings;
      preserve its explicitly accepted nonblocking presentation limitations.
- [x] Freeze source, layout, index, generated XML, PDF/HTML, screenshot and log hashes;
      mark scans1–4 accepted (4/385).

## Next and final work

- [x] Batch B scope: scans5–24, תפלה and full second-night Maariv through Aleinu;
      scan25 begins morning material. Twenty images and overlapping bands cached.
- [x] Finish primary reading/comparison of all20 source pages in batch B; preserve
      independent blind readings, dedicated reader evidence and user adjudications.
      The source gate is closed; encoding, service and export gates remain pending.
- [x] Close the independently reviewed project-separation equivalence record for
      the user-approved volume-two project pair. Historical four-scan source
      acceptance remains; migrated presentation approved after fixing counterpart
      discovery and rerunning all mechanical/browser checks (findingsF1–F3 closed).
- [ ] Repeat all twelve acceptance gates for each subsequent batch through scan385.
- [ ] Review cross-batch joins, duplicate/repeated units, reference destinations and
      full second-day recitation order; retain first-day paths and settings.
- [ ] Build full-volume documentary and expanded artifacts; refresh final evidence
      and independently review full-volume structure plus recorded visual scope.
- [ ] Confirm 385/385 complete scans accepted, no pending disputes or missing required
      recitation, and accurate licences/credits and documented critical uncertainty.
- [ ] Finish linked PRs and CI; merge processor dependencies first, rerun dependent
      project checks, merge and close out managed worktrees preserving needed outputs.

## Historical batch B checkpoint — 2026-11-26

- [x] Resolve questions931–976 with dedicated readers, returning only the
      unresolved973 host letter to the user; record the gimel adjudication.
- [x] Complete independent whole-source verification of scans12–13, including
      source extent, Jerusalem marks and printed paratext. Source approval
      is recorded separately from complete-scan acceptance.
- [x] Encode Emet veEmunah in both languages with six existing canonical parts,
      source paragraphs and three bounded scriptural quotations.
- [x] Close independent Emet source/encoding/code and configured PDF/HTML
      presentation review; preserve the rejected Divine Name markup finding
      and its corrected evidence. Integrate merged exporter PR341 from main.
- [x] Pass branch lint and 43 focused tests (19 subtests).
- [x] Close independent encoding review of the three scan12–13 scripture modules,
      including single-verse identity/provenance and earlier Shema provenance equivalence.
- [ ] Inspect and independently review the three scripture modules’ exports.
- [x] Encode and independently review Hashkivenu and half Kaddish text modules.
- [ ] Close their contextual service and complete-export gates with the rest of
      scans5–24.

Complete accepted scans remain **4/385**. Excerpt approval and complete source
readings do not change that count while service, encoding or presentation gates
for a complete scan remain open.

The complete source5–24 image audit, adjudication and application verification
are approved with no unresolved reading questions. User977 confirmed patah under
alef in the small scan16 rubric. The source ledger now records24 approved source
readings among scans1–24, separately from4/385 complete accepted scans. Remaining
encoding, service/conditional/expanded order and export gates remain open.

The complete evening draft now contains47 prayer modules (87 Hebrew/English
witnesses), documentary service spines and one shared expanded sequence. All
source inputs are hash-checked and every witness regenerates byte-identically
with schema validation.59 focused tests and19 subtests pass. Initial independent
reviews and closure records remain separate from final batch acceptance.

The compiled matrix passes communal/individual recitation, mourner presence,
optional Malkenu, Motzaei Shabbat true/false, two real evening dates and first-/
second-day selection. Final rubric/dependency closure and complete PDF/HTML
presentation review are still required; accepted coverage remains4/385.


## Implemented batch B architecture

- The complete entrance and second-night service use 47 prayer modules and 87
  witnesses, documentary wrappers and one shared expanded sequence.
- The second-night expanded profile selects its own entry. The accepted first-day
  entry and profile stay unchanged; borrowed Kaddish/Yigdal provenance is reviewed
  separately without changing their prayer words or canonical scopes.
- Final checks cover the actual shipped first-day profile, real evening dates,
  individual/communal recitation, mourners, optional Malkenu, exact compiled words,
  paired rubric direction and source-arrow hitboxes on every output page.
- Exporter corrections are isolated in PR 344, before processor PR 331 and the
  dependent projects PR 110. Source readings and review evidence are in PR 60.

The source batch checklist is the current gate status and acceptance record.
Historical counts and pending gates above describe their earlier checkpoints.


## Morning installment: scans25–45

- [x] Complete hash-bound primary and independent readings and adjudication.
- [x] Encode103 documentary witnesses across62 source units; preserve missing
      translations and legitimate source variants.
- [x] Reuse canonical identities through selected shared printings; preserve
      earlier Night gaps and apply the separately reviewed eight-mark amendment.
- [x] Build documentary and expanded morning sequences; verify27 combinations
      of rite, gender and Shabbat settings and correct German study-block order.
- [x] Validate current XML, names, features, registry and shipped profiles;
      independently review generators and actual compiled content.
- [x] Integrate merged exporter PR347 and retain its closeout evidence.

Final PDF/HTML and complete-scan acceptance are recorded in the source batch
checklist and hash-bound acceptance record, not inferred from generation or these
implementation milestones. Next material begins at scan46 after that gate closes.


## Pesuqei deZimrah installment: scans46–63

- [x] Cache and inventory the18 physical pages; verify the boundary before
      Yehi Khevod on scan64 (64–65 are preview pages, outside this batch).
- [x] Preserve three primary image-reading records and a canonical identity audit.
- [x] Complete blind independent reading. Claude completed46–51; its service
      blocked outputs52–63. The user selected GPT-6.2 Sol at medium effort,
      whose two frozen image-only readings cover52–63. Preserve both failed
      Claude attempts; localized uncertainties remain for source adjudication.
- [ ] Reconcile wording, fine marks and paratext against enlarged images;
      use one neutral dedicated reader per unresolved question before the user.
- [ ] Approve complete source readings and bind literal witness recipes to them.
- [ ] Reuse existing prayer/Bible URNs, retaining earlier canonical providers and
      literal contextual quotations where a verse is printed again. Do not claim
      the Chronicles16:8–36 excerpt as a complete chapter witness.
- [ ] Preserve the Hebrew-only Psalm91:16 repeat and absent English Psalm136:25;
      prove that new counterparts do not fill earlier untranslated occurrences.
- [ ] Append documentary and shared expanded sequences inside Shacharit, with
      repeated canonical calls where recitation requires them and no fake heading.
- [ ] Complete independent encoding/guideline/alignment/order/condition review.
- [ ] Pass schema, naming, feature, registry, refdb and affected-code checks.
- [ ] Freeze and independently approve documentary Hebrew, documentary parallel
      and expanded PDF/HTML, including all page links and cross-batch transitions.
- [ ] Record complete-scan acceptance before advancing beyond scan63.

Source gate status and immutable evidence live in
`batches/pesuqei_s46_s63/checklist.json` in the volume-two source directory.
Accepted coverage remains45/385 while these gates remain open.

The scans46–63 source/recipe has independent approval except question1023
(the scan62 maqaf). All34 prospective XML documents validate, and the actual
27-case conditional matrix preserves the Hebrew-only Psalm91 ending repeat
and Psalm136:25 without neighboring English drift. Production generation and
complete-scan acceptance remain gated on the human reading and final exports.
Exporter PR349 fixes redundant backlinks across full-width translation gaps;
its code review and588tests passed, with final expanded export closure pending.
`ACTIVE_REVIEW.json` identifies current source payloads; earlier working readings
and rejected compositions are historical evidence. Accepted coverage is45/385.
