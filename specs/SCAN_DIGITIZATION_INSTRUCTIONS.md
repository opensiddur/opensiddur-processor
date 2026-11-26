# Instructions for scan digitization and review

Read this guide before transcribing, reviewing, regenerating or exporting a
scanned edition. It collects operational lessons from the complete
Heidenheim–Marmorstein first-day Rosh ha-Shanah volume. Apply the general rules
to other editions; apply the edition-specific decisions below only to this book.

## Required references and durable decisions

- Read [AGENTS.md](../AGENTS.md), the general encoding guidelines in
  [JLPTEI-3.md](../schema/JLPTEI-3.md), the authoritative
  [ODD](../schema/jlptei.odd.xml), and the
  [URN scheme](SIDDUR_URN_SCHEME.md). Schema validation alone does not establish
  adherence to the prose guidelines or fidelity to the scan.
- Consult the book's specification and current source acceptance records before
  continuing. For this book, use
  [MARMORSTEIN_ROSH_HASHANAH_1.md](MARMORSTEIN_ROSH_HASHANAH_1.md) and
  `sourcetexts/sources/marmorstein_rosh_hashanah_1/`. Historical progress entries
  explain decisions; the latest acceptance record determines current coverage.
- Persist readings, corrections, alignment decisions, unresolved questions and
  adjudications in versioned source evidence. Keep large image caches outside
  Git. Do not leave decisions solely in chat or temporary QA scripts.
- Record reusable lessons here, edition rules in the book specification, and
  individual readings in source evidence. Do not generalize a confirmed mark
  from one occurrence to other occurrences of the same word.

## Inventory and documentary fidelity

- Account for every physical scan page, including covers, blanks, front matter
  and appendices. Distinguish inventoried, encoded, independently reviewed and
  accepted coverage. Do not count a partial excerpt as an accepted full page.
- Use the one-based PDF scan number when communicating with the reader. For
  Internet Archive, scan page `sN` corresponds to zero-based leaf `n(N-1)`.
  Keep printed page labels separately: they can repeat or restart.
- Put the unique Archive leaf URL in every source `tei:pb/@facs`; put the printed
  label in `@n` when present. Do not infer labels from arithmetic or mistake a
  numbered citation for a page label. Keep metadata corrections reproducible.
- Images settle readings. OCR, familiar prayer wording and other editions are
  discovery aids, not substitutes for reading the page. Preserve pointing,
  abbreviations, punctuation, defective spelling, language and source order.
- Preflight generated snippets before sending them for review. Fully decode
  image files before parallel cropping, or use independent decoded images;
  shared lazy decoders can corrupt crops. Inspect representative crops and
  their upper/lower margins, and exclude failed image preparations from approval.
  Approximate line coordinates do not establish page coverage. Check the first
  and last actual source lines; before accepting any claim that text is absent,
  inspect the complete page. Preserve rejected crop-based reviews as history.
- Preserve immutable independent readings even after adjudication. Encode clear
  source mistakes with `tei:choice/tei:sic` and `tei:corr`, retaining the printed
  reading and an evidenced correction. Do not silently modernize archaic forms.
- Distinguish an absent printed mark from an editorial normalization required by
  project conventions. Record the latter explicitly; do not describe it as a
  mark seen in the image. Preserve Divine Name semantics through transclusion.
- When an authorized comparison reconstructs illegible pointing, record the
  reconstruction, exact reference passage and witness. Keep the edition's
  independently verified neighboring readings; damage alone is not a sic/corr
  error, and a reconstructed mark must not be described as clearly printed.
- Credit source authorship, translation, scan preparation and digitization
  separately, with their respective bibliography and licences.

## References, alignment and source modules

- Search the canonical registry, aliases and existing projects before assigning
  identities. Differences of edition, pointing or placement alone do not create
  new prayer identities. Reuse the canonical URN in `@corresp`; distinguish the
  publication through edition-qualified URNs.
- Shared identity does not authorize replacing this edition's wording with
  another edition's text. Record compatible external witnesses when a referenced
  text is not printed in the book.
- Encode repeated prayer parts, stanzas and biblical chapters/verses with
  correspondence milestones, independently of paragraphs, line breaks and page
  breaks. End a scope before unrelated text using a same-unit milestone without
  `corresp`. Preserve quotation semantics and exact transclusion endpoints.
- An excerpt is not a whole-chapter witness. Match its actual verses or
  subverses. Bounded quotations inside a stanza must not consume adjacent words
  or unnecessarily split a coherent bilingual stanza into many display rows.
- Determine translation alignment from layout, Hebrew cues and verified textual
  extent. Omit Hebrew linkage words from English prayer text; use milestones
  for linkage and retain the cues in reading evidence. Split modules at genuine
  omissions so neighboring translations cannot drift into untranslated text.
- Leave missing English absent. Do not supply another translator, placeholder
  prayer text or empty counterpart merely to make parallel output symmetrical.
  When a later batch adds a translation of the same canonical text, recheck earlier
  untranslated occurrences: global URN reuse must not fill their documented gaps.
- Put biblical citations in anchored citation notes, without enclosing
  parentheses in the generated links. Preserve their documentary forms in
  reading evidence. Citation notes are not recited prayer words.
- Identify instructions using wording, position and typography, including Rashi
  script. Do not add `rend` to instructions to imitate the scan: instruction
  styles follow the reader's selections.
- Keep place-specific role directions, variants and settings in the service or
  structural occurrence, rather than embedding them in reusable prayer words.
  Review both an abbreviation and its expansion, including combined speakers.
- Use edition-qualified URNs for transclusions; project/file pointers used in
  bibliography are not transclusion targets. Check actual resolved ranges,
  including the path-depth fallback for units outside the containment table;
  do not infer a prayer-part's endpoint solely from its next same-unit marker.
- Use `half-verse` and `verse-part` for registered subverses, with their own
  terminators. Repeated or adapted quotations may retain bounded `seg/@source`
  attribution without advertising another canonical verse witness. A prayer-part
  identity must retain its established introduction as well as the quoted words.
- Derive or verify bibliographic end pages through nested quotations and optional
  spans. A span beginning with a page marker needs the following page's `facs`,
  even when selected without its preceding source paragraph.
- Put a condition's printed label inside its `j:conditional` note, so a decided
  condition suppresses the label. Combine bilingual labels in that one note.
  Keep speaker/how descriptions distinct from directives. In a shared expanded
  sequence, deduplicate identical same-language facing-page rubrics; preserve
  differing source roles. Omit scopes that have no counterpart content.

## Page directions and expanded recitation

- Preserve original page-direction wording and printed numbers in transcription
  evidence. Follow Birnbaum's encoding conventions: navigational numbers become
  empty `tei:ref type="page"` elements targeting edition-qualified URNs.
- Wrap independently removable navigation clauses in
  `tei:seg type="optional-page-reference"`. Retain ritual actions, speaker
  directions and bibliographic citations even when a rubric also turns a page.
- Resolve each destination by meaning and images, including language and printed
  mistakes. Never assume a fixed Hebrew/English page-number offset. Required
  unresolved references fail validation; missing optional destinations suppress
  their navigation clauses.
- Keep documentary arrangement separate from the expanded structural spine.
  Give an expanded compilation its own canonical structural root so parallel
  selection cannot substitute the source book's whole arrangement.
- Use one shared bilingual sequence, bilingual headings and editorial rubrics.
  Prayer words transclude canonical, edition-independent URNs with explicit
  source priorities. Preserve transcluded credits and licences.
- Expand skips, resumptions, abbreviations and repetitions at their recitation
  positions. Repeated occurrences have unique structural identities but reuse
  the prayer's canonical identity. Confirm a direction's extent; familiar
  continuations or the abbreviation וכו׳ do not prove additional verses belong.
- Use the smallest coherent source ranges that exclude obsolete navigation.
  Preserve documentary text while exposing boundaries needed by the expansion.
- Encode complete alternative piyyutim continuously, one file per work, even
  when the print alternates their fragments across page bottoms. Select the
  complete alternatives conditionally instead of interleaving their fragments.
- Reuse calendar, rite, service, quorum and recitation settings. Close local
  declarations. Test true, false and undecided states: a resolved Shabbat
  insertion is included without selection brackets on Shabbat and excluded
  when definitely not Shabbat; an undecided choice retains its semantics.
- Do not declare a false calendar date or kind of day merely to select wording.
  Check preparation before sunset, twilight and the incoming festival separately.
  Headings and common rubrics must share the union of their content's gates.
- Check the entire selected service, including Torah service and Musaf. Avoid
  duplicate passages when a rite condition moves a block to another position.
- Treat parentheses by their evidenced function: variants, optional additions
  and calendar conditions differ. Do not make every parenthesis an alternative.

## Independent review and questions

- Have a second reader read the images independently before seeing the first
  transcription, OCR or suggested replacement from another edition. Record the
  actual model, effort, image scope and raw response. If a required reviewer is
  unavailable, request a replacement rather than silently substituting one.
- After blind reading, review encoding-guideline adherence, canonical identities,
  alignment and expanded order independently as well. Provide the applicable
  guidelines and record their versions. A confident second reading does not
  settle a disagreement without image evidence.
- Compare consonants, vowels, cantillation, dageshes, mappiq, metegs, punctuation,
  omissions, repetitions and reading order. Separate textual, pointing and
  whitespace differences; distinguish printing blemishes from actual marks.
- For every pointing question, put the numbered question immediately before an
  enlarged source-image snippet. Include the entire word, all lower/upper marks
  and enough adjacent context. Do not ask from a crop that cuts off the vowels.
- If an image fails to display, redisplay it using a working inline method,
  individually and at a readable size. Do not repeatedly send the same broken
  image reference. On request, redisplay all still-open numbered snippets.
- Persist answers against their question IDs and exact occurrences immediately.
  Consult that record before asking again. A corrected answer supersedes its
  earlier value without erasing the history.
- When applying a reading, bind the occurrence to its verse or surrounding words
  as well as its word index. A search for a bare word can skip an earlier
  maqaf-linked occurrence and silently select a later one. Verify the indexed
  context against the source crop before recording the application.
- Give read-only reviewers the exact paths of adjudication records and complete,
  tightly enlarged source crops. Do not rely on directory discovery or assume a
  full-page image will display large enough to distinguish fine marks.
- For defective Jerusalem with two vowels under lamed, encode the source patah
  or qamatz, then meteg U+05BD, CGJ U+034F, hiriq U+05B4. If a printed yod carries
  the hiriq, encode lamed + its vowel/meteg, then yod + hiriq, without that CGJ.
  Read patah versus qamatz from each occurrence.
- Choose cantillation codepoints by the printed sign and placement, not only
  Unicode character names. Postpositive zarqa uses U+05AE (named ZINOR);
  U+0598 (named ZARQA) is used for above-letter tsinnorit. See
  [Unicode's character-name anomaly note](https://www.unicode.org/notes/tn27/tn27-1.html#appA).
- Bind approvals to the exact reading, realization, structure, settings and
  artifact hashes they cover. Changed text invalidates its previous approval.
  A mechanically proven unchanged payload may retain its approval only with an
  explicit, reviewed record of what changed and what remained equivalent.
- Work in substantial batches when requested, but finish each batch's reading,
  encoding, order and presentation review before calling it accepted. Preserve
  unresolved uncertainty explicitly; do not turn low confidence into certainty
  to satisfy an acceptance counter.

## Export checks and acceptance

- Number notes in emitted reading order, including repeated transclusions and
  bilingual columns, rather than file creation order or source storage order.
- Preserve word boundaries across line breaks, except `break="no"`; do not add
  spaces inside a word or after a source maqaf. Verify quotation and verse
  boundaries without destroying coherent stanza alignment.
- Carry page-marker-only fragments into the next non-empty fragment in the
  same column while preserving order, facsimile identity and conditional scope.
  Do not discard leading markers or manufacture empty parallel rows. A marker
  inside a visible instruction must survive as part of that instruction.
- Emit scan backlinks when the source page changes, not at every paragraph or
  module boundary. Track the unique facsimile URL per edition/column, not the
  printed label. Returning to an earlier page must produce a link again; hidden
  conditional content must not suppress the next visible link.
- Use `typography.markers.scan_links.placement: margin` for marginal backlinks
  when desired. Check both PDF outer margins and HTML gutters, including RTL,
  LTR, narrow displays, link targets and annotation bounds. Preserve source
  markers even when a renderer suppresses a redundant link.
  Link counts alone cannot show that links are usable: distinct source pages
  can occupy identical clickable rectangles on one generated line. Check
  nonoverlap, full click-target size and page bounds in both output formats.
- Check a canonical range's opening provenance as well as internal page breaks:
  its source page marker may live on a documentary heading outside the selected
  range. Do not reset backlink state at every file to conceal that problem.
  An ancestor's facs alone can be lost during extraction. Preserve the opening
  source on each reusable verse span, and probe an interior verse after a page
  break separately in each language.
- Keep related subsections under a structural parent for bookmarks, contents
  and electronic navigation. Editorial wrappers need proper credit; preserve
  source headings and canonical text identities inside them.
- Run schema, naming, feature, registry and reference-database checks, and
  synthetic regressions for reusable changes. Cover repeated page labels,
  missing/partial counterparts, conditional destinations, repeated transclusions
  and mixed ritual/navigation clauses. Test shared algorithms with invented data.
- After creating or renaming projects, refresh the reference database before
  exporting. Assert actual counterpart discovery and parallel output mode; a
  warning about fallback to per-transclusion parallels can hide missing English
  while a front-matter-only preview still looks correct.
- Inspect documentary Hebrew, documentary parallel and expanded PDF/HTML.
  Verify actual links, direction, columns, notes, bookmarks and conditional
  alternatives. Record visual sampling separately from mechanical all-page QA.
- Freeze complete reports and artifact hashes before final independent export
  review. A still-running test log or screenshots from an earlier artifact do
  not certify the current output. Re-render after relevant changes.
- After interrupted LaTeX builds, restore or rebuild a consistent auxiliary
  cache and rerun until references settle. PDF existence alone proves nothing.
- Report accepted coverage from current evidence, including blanks. Distinguish
  accepted explicit critical uncertainty from an unresolved reading dispute,
  and document any nonblocking rendering limitation honestly.

## Heidenheim–Marmorstein decisions to retain

These decisions describe this edition, not every Ashkenaz maḥzor. The book
specification and source records retain their detailed evidence and exceptions.

- Keep the first-day projects' shared title `prayerbook_for_the_new_year`, with edition
  fields `heidenheim-1965-he` and `marmorstein-1965-en`. Use the actual book title
  in presentation, never a historical “pilot installment” label. Volume two uses
  `prayerbook_for_the_new_year_second_day` for both languages, by user decision.
  Separate physical-volume projects keep scan provenance and missing translations
  distinct while reusing canonical prayer identities.
- The expanded project is `machzor_expanded-opensiddur-he`; its structural root
  is `urn:x-opensiddur:text:siddur:machzor_expanded`.
- Numeric-only biblical citations such as Ashrei's קמה refer to Psalms.
- Kedushah's קו״ח / קו׳ means קהל וחזן. Other occurrences include חו״ק
  (חזן וקהל), ח׳ (חזן) and ק׳ (קהל); read the actual printed abbreviation.
- Birnbaum supplies encoding examples, not authority to replace this edition's
  rite. Retain full Qabbalat Shabbat and Lekhah Dodi on festival Shabbat, gated
  at the higher transclusion level. The leading לכה cue repeats the opening
  refrain: this source's ten cues yield eleven full refrain recitations.
- Move Torah blessings through Eilu Dvarim conditionally on German rite. In that
  rite Elohai Neshamah follows Asher Yatzar directly; in other rites the Torah
  blessings block intervenes. Do not impose one sequence on every rite.
- Keep preparatory Minchah's actual seasonal context local. Do not import an
  unprinted Ten Days variant merely because the volume is for Rosh ha-Shanah.
- Preserve Frankfurt, Metz and Fürth distinctions. Transcribe Hebrew-script
  German with its printed vowels and rafe; translate as a sanity check without
  replacing uncertain letters with expected German. Keep low-certainty sigla
  explicitly critical rather than repeatedly guessing them.
- The post-shofar “אשרי העם וכו׳” directs only the printed Psalm 89:16. The
  cantor's “הוא אלהינו וכו׳” continues through the paragraph's end, including
  וידעת היום. These are separate adjudicated extents, not a general וכו׳ rule.
- Unsigned parenthesized appendix additions are independently optional in source
  order. The confirmed missing opening parenthesis on כנשר ירחף does not make
  that line ordinary mandatory text.
- Avinu Malkenu belongs under Shacharit, with its non-Shabbat condition. Group
  all seven Shir ha-Yichud day sections under one file/bookmark parent; keep
  Shir ha-Kavod a sibling rather than another day of that hymn.

## Engineering and closeout

- Reuse the shared scan utilities and Archive client. Keep reusable algorithms
  tested separately from edition recipes and data. Read/write text as UTF-8.
- Keep exporter fixes in separate focused PRs. For dependent registry/schema
  and project changes, follow the paired-branch merge order in AGENTS.md and
  rerun project validation after the processor dependency reaches main.
- Keep release submodule pins out of unrelated changes. Before archiving a
  managed worktree, preserve untracked QA scripts, needed ignored outputs and
  any unique submodule commits; distinguish changed pointers from changed files.
- Verify merge state, update the continuing checkout, and refresh the accepted
  artifact manifest before closeout. Use the managed archive operation and
  report remaining limitations without reopening settled source readings.

### Citation marker attachment

Inspect the position of every note marker beside its intended text anchor,
including full-width RTL paragraphs. Correct numbering and note order alone
do not prove attachment. When the default interlinear placement drifts, test
the existing `typography.notes.anchor: superscript` setting and independently
review the rebuilt configured outputs before accepting them. Record the chosen
book setting and preserve the rejected-output evidence.

### Dedicated readers before human pointing questions

For each unresolved pointing question, give its own dedicated agent reader the
preflighted enlarged source snippet and a neutral question. Do not supply the
proposed answer or other readers' conclusions. Record the reader identity,
image hash, answer, confidence and visible evidence for that occurrence.
Resolve confident image-supported answers without asking the user; return only
cases the dedicated reader cannot confidently settle, with the question before
its enlarged image. Offer an open reading when candidate choices may be wrong.
This question-level adjudication does not replace full-page independent reading,
guideline/alignment/order review or the remaining acceptance gates.

### Divine Name word boundaries

Check the semantic markup as well as concatenated text. A substring search for
two yods can wrongly mark an ordinary word such as בחיים without changing its
visible letters. Identify actual Divine Name tokens, inspect surrounding words
and legitimate attached prefixes, and review every generated `j:divineName`.
Exact-text comparison alone cannot catch this error.

### Small Rashi-script glyphs

Inspect the complete letterform and surrounding type before treating a detached
lower stroke as a vowel. A Rashi alef's detached lower limb can resemble a patah;
a tight crop alone can conceal that distinction. Give a dedicated reader the
enlarged word and wider font context. Resolve each occurrence independently and
keep genuinely uncertain marks for human review.
