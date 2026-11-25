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
- [ ] Obtain independent presentation review and close all blocking findings.
- [ ] Freeze accepted payload/artifact hashes and mark the four leaves accepted.

## Next and final work

- [ ] Batch B begins with תפלה on scan5 and second-night Maariv on scan6; determine
      a coherent endpoint and include each facing translation/continuation.
- [ ] Repeat all twelve acceptance gates for each subsequent batch through scan385.
- [ ] Review cross-batch joins, duplicate/repeated units, reference destinations and
      full second-day recitation order; retain first-day paths and settings.
- [ ] Build full-volume documentary and expanded artifacts; refresh final evidence
      and independently review full-volume structure plus recorded visual scope.
- [ ] Confirm 385/385 complete scans accepted, no pending disputes or missing required
      recitation, and accurate licences/credits and documented critical uncertainty.
- [ ] Finish linked PRs and CI; merge processor dependencies first, rerun dependent
      project checks, merge and close out managed worktrees preserving needed outputs.
