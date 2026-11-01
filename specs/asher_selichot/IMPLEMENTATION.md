# Asher selichot encoding and reusable scan workflow

Issue: https://github.com/opensiddur/opensiddur-processor/issues/207

The skill entrypoint dynamically loads the selected edition subsection. Shared tools
accept explicit book profiles; Asher uses scan-based identity because both languages
repeat printed labels. Archive page labels remain candidates until image verified.

Current coverage: title n1/n2 and the first seven complete days through n99/n100.
Daily scope files record image-verified boundaries; the first day ends at n51/n52. Readings are derived from these images; OCR and independent readings check
those readings. The source README records editorial additions and target ranges.

`readings.abbreviations` selects abbreviated (default) or expanded during compilation,
including inline transclusion. Schema adds expan; PDF emits the selected branch.
Documentary/expanded service roots reuse source modules; expanded adds the referenced
prayers in place of the concluding instruction. Expanded output also omits the
fulfilled refrain-repetition rubric; documentary output retains both instructions. The documentary and expanded
settings are release books in opensiddur-projects `settings/asher_selichot/`. Images and render artifacts stay in output/asher_selichot.

Acceptance: synthetic shared-tool and compiler tests; schema and URN validation;
page/language reverse check; paired PDF builds with direction, text, footnote and
reference-boundary checks; checks fail on broken controls; full regression suite.

## First-day continuation

The documentary `index.xml` entrypoints cover title n1/n2 and all first-day
text through Hebrew n51 / English n52. `first_day.xml` directly assembles independently named text modules by canonical
URN, retaining printed rubrics. It reuses the
original El Melekh, Vayaavor and Bemotzaei Menuhah modules at their source positions.

Canonical readings retain immutable scan-first fragments, source page identity,
complete bilingual prayer groups, printed rubrics and anchored footnotes. XML
verification compares each unit with its reading and checks source page order and
the final Kaddish boundary. Synthetic fixtures check crossed page breaks, repeated
footnote anchors, missing anchors, litanies and mixed-language closing instructions.
The documentary settings render the full documentary day. Independent Hebrew
pointing review is pending.

## Piyyut invocation correction

Treat the shared אלהינו ואלהי אבותינו invocation as opening text in each
piyyut, together with its English translation. Preserve the Hebrew invocation as
an introductory line within `tei:lg` and the English within its prose paragraph;
remove the former heading heuristic. Record the distinctive following Hebrew
incipit in source metadata and URN labels, without adding a printed heading or
claiming a separately established formal title. Source words remain unchanged; reusable text identities use common names or distinctive incipits. The scan-specific skill and reverse verifier enforce this rule.

## Expanded complete first day and secondary-source settings

Generate documentary and expanded book entrypoints referencing the same bilingual
`first_day.xml` service assembly.
Conditional branches retain printed cues for documentary output and replace them
with unqualified target URNs when repetitions are present. Register bounded
repeat-range milestones within the two source prose prayers. Supply the poem’s
concluding prayers in a true conditional branch next to its printed conclusion cue. Add reusable Birnbaum Full Kaddish
`prayer:kaddish/shalem`, assembled from six edition-bound existing passages.
The expanded settings select the book entrypoint `expanded.xml`, Asher-first primary priorities,
and Asher/Birnbaum English parallel priorities.

Parallel subcompilation must retain the remaining configured parallel projects as
fallback priorities rather than reducing its priority list to a singleton. Restore
priorities after the scope ends. Verify documentary branches against primary
readings after separately auditing expansion targets and branch polarity; compile
both views and check repeated-passage counts, omitted fulfilled cues, complete
Kaddish, source provenance, direction, footnotes and first-day boundary.

Marker-mode external transclusions must honor false conditional scopes before
resolving a target or emitting suspension markers. This is required for the
shared documentary modules to compile without a configured secondary source.
A regression fixture uses an absent target inside a false scope and checks that
the documentary text after the scope survives.

The generic conditional/fallback corrections and regression tests were merged in
opensiddur-processor PR #217. The apparatus paragraph-direction fix and tests were merged
separately in PR #218. The Asher code PR targets main.

The first-day PDF check also groups small Latin apparatus glyphs by font and
baseline across MuPDF’s fragmented lines. Reject decreasing x coordinates, and
reverse a complete note run as a failing control. The original PDF’s backwards
English explanation on page 9 fails this check. Source words and XML paragraph
language declarations are unchanged by the renderer correction.

The final Full Kaddish is first-day Selichot, never Ten Days of Repentance. Before
its transclusion, declare `asher:selichot/first_day=true` and the standard holiday
aggregate `aseret-ymei-tshuva=false`; close the declaration after the prayer.
This local source context overrides unrelated export defaults and restores them
afterward. A synthetic compilation fixture starts with the Ten Days aggregate
true, confirms the final addition is excluded, and verifies the caller’s setting
is restored. Reverse verification audits the declaration; PDF verification rejects
the Ten Days rubric and includes a deliberately injected failing control.


## Final-book module organization

Treat this work as the foundation of the final book. `index.xml` holds documentary
book metadata and both title pages; `expanded.xml` provides the expanded book view.
Both reference the same first-day service assembly. Independent prayers and piyyutim
live in named files, with source-independent URNs and publication `@project`
suffixes recording the edition. The printed first-day service retains its rubrics and directly transcludes those files. Ashrei and Half Kaddish are independent modules.

`identities.py` maps evidence IDs to semantic filenames and canonical registry
identities. Existing common prayer/part names take precedence; other texts use
incipits without claiming unverified formal titles. Repeated Ashamnu and scriptural
ranges point to reusable prayer identities. Active structured readings use
`refrain-and-prayers.json`; immutable original evidence is retained.

Remove artificial opening, preface, before-piyyut and closing subdivision files,
and the redundant expanded first-day assembly. Delete their obsolete URNs and
prune exactly these known generated files after replacement XML validates.
Internal reading batches do not define source divisions.

Reverse verification follows direct service references in source order, then checks
individual modules against the original reading units. It audits publication
identities, source boundaries and editorial context separately. Regenerate both
views, resolve URNs, and render both PDFs after the reorganization. The full book
and independent Hebrew pointing review remain pending; do not encode temporary
coverage status in canonical text identities.


## Second day and generated contents

Extend the existing book assemblies with the printed second-day range n51–n60,
ending before the third-day heading. Four new canonical incipit modules and one
second-day assembly per language preserve bilingual verse/prose structure and
seven English footnotes. Expand the source-verified opening, repeated verses,
three prayer pairs, closing range and secondary Full Kaddish; omit fulfilled
instructions. Both day headers must be top-level bookmarks above their pizmons.
All four local export settings enable a generated TOC through heading level two.
Reverse verification follows printed order, selects abbreviation branches and
checks footnotes and page boundaries separately from supplied text. The book PDF
checker uses outline destinations to scope legacy first-day checks and checks
second-day stanza alignment, footnote occurrences, expansion branches and
bookmark hierarchy with failing controls.


## Third-day continuation

Extend both book entrypoints through n67/n68, before the fourth-day heading.
Follow verified printed page order 29, 30, 31, 32, 33: the Archive openings for
31 and 32 are swapped. Preserve actual facsimile identities and bilingual
pairing separately. Three new reusable poem modules and `third_day.xml` bring
the projects to 59 files per language (54 independent texts, five assemblies).
Generalize numbered-day authoring and reverse checks, retaining day-two wrappers.
Preserve Hebrew-only verse instructions and all eight English notes. Use six
stanza alignment ranges, four refrain choices and one complete-opening choice
for Shahar qamti. Expanded cues use the verified existing ranges with a separate
third-day Kaddish declaration. Exclude fourth-day material.

Remove the first pizmon's miscategorized English running page header from the
body and contents while retaining source evidence and the Hebrew printed heading.
Synthetic checks exercise reordered page identities, closed day-specific scopes,
Hebrew-only rubric direction, and running-header exclusion. Render checks audit
day-three stanzas, notes, expansions and day boundaries with broken controls.

## Erev Rosh Hashanah continuation

Encode n99–n184 as one real service assembly with 113 source-ordered units,
independent incipit modules, two subordinate pizmon bookmarks, and documentary /
expanded cue branches. Preserve language-specific repeat ranges and Ark positions.
The printed-52 extra-petition milestone has an explicit terminal same-unit marker.
The final Full Kaddish excludes first-day and Ten Days context. Preserve Tamid’s
numbered note markers without inventing targets or presuming explanatory notes exist.

Bound the page-52 repetitions separately under `prayer:kerachem_av` and
`prayer:selichot/ki_lo_al_tzidqoteinu`; their translation differs from pages 9/10.
Choose the version indicated by the cue, including the explicit English
page-58 reference to 52.

Expanded repeat cues can list different petitions in Hebrew and English. Set
them as one paired prose paragraph with inline transclusions and a shared
alignment milestone for the cue; retain bounded prayer targets in the source
modules. Separate external blocks for unequal target lists can shift later
translations. Verify the compiled pairings and the page-52 translation wording
before rendering, in addition to checking passage starts in the PDF.

Run `python -m opensiddur.importer.asher_selichot.erev_rosh_hashanah` on the
compiled expanded XML to verify all 12 repeat-cue pairings and the exact
page-52 translation variant. Compiler fix #231 keeps inline references inside
parallel paragraphs; both synthetic regressions failed before that fix.

## Tzom Gedaliah continuation

The next complete service covers n183/n184–n207/n208 (printed 91–103), in 38
source-ordered bilingual units. Nine independent piyyutim and six scriptural
prayer modules use reusable incipit URNs; the service assembly is the actual
liturgical running order. Hebrew poems are verse; English retains printed prose.
Horita derekh teshuvah has eight shared stanza units, seven verified refrain
expansions, and a cross-page Reuben/Judah unit with different printed cue positions.
The top-level service bookmark contains its subordinate Hebrew pizmon bookmark.

Four unequal repeat lists use one aligned prose block, as on Erev. Hebrew cites
the page-52 reprinted petitions; English cites the earlier page-9/10 ranges.
Closing repetition includes the printed confessions through Mahi umasi, followed
by Makhnise rahamim and the first-day closing prayers. Editorial Full Kaddish
uses the secondary source with first_day=false and Ten Days=true, then restores
scope. Fulfilled cues disappear. The holiday gate encloses the service in the
book's running order, without printing an undecided-occasion instruction. Every
dated service has such a gate; `asher_selichot/occasions.py` derives them, as the
skill reference's *Day gates in the running order* describes.

Preserve the unattached printed-103 Hebrew marginal note as explicitly documented
editorial commentary; its original target remains unknown. Mixed Hebrew within
English body and apparatus receives explicit language spans. Immutable staged and
assembled first readings precede independent English OCR, with separate image
adjudication and hashes. Independent Hebrew proofreading remains pending.

Run `python -m opensiddur.importer.asher_selichot.tzom_gedaliah` against the
compiled expanded XML before rendering. Its four petition checks complement the
book PDF check's eight pizmon starts, apparatus samples and expansion boundaries.
Broken controls must reject duplicate notes and displaced stanza starts.

The supplied Kaddish has an empty editorial override of
`instruction:aseret_yemei_teshuvah/add`, so its fulfilled secondary “add” rubric
is omitted while the Reader cue remains. Compiler PR #232 respects instruction
selection inside a resolved conditional, including intentionally empty wording;
its ordinary/external/inline regressions fail before the fix. The fix is applied
on the Asher branch and tested with the actual expanded book.

Gedaliah's opening ends at Shomea tefillah's “for it is great”; the following
Selah lanu is printed once. The abbreviated Hebrew כי רבו citation is ambiguous;
the source adjudication documents the editorial boundary from the explicit
English cue and adjacent reprint. The PDF check rejects an extra opening Selah
lanu, including a deliberately injected duplicate.
