# Heidenheim–Marmorstein: second day of Rosh ha-Shanah

Read `specs/SCAN_DIGITIZATION_INSTRUCTIONS.md` and
`specs/MARMORSTEIN_ROSH_HASHANAH_2.md` before continuing.

The startup imports the complete 385-leaf inventory and OCR candidates, caches
images separately, and builds **draft front matter only**. It does not yet
assemble the service, provide second-day export settings, or claim full-volume acceptance. Scans1–4 have completed their separate batch acceptance;
the remaining381 scans are unaccepted.
The Hebrew cover emblem and title signature were settled by user adjudications860–861. The blind
review's omissions and effort-report discrepancy are recorded in source evidence.

Use explicit roots for the coordinated standalone source/project worktrees:

```bash
uv run python -m opensiddur.importer.marmorstein_rosh_hashanah_2.download \
  --source-root /path/to/sourcetexts/sources \
  --output-root /path/to/output \
  --pages s1 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 s12

uv run python -m opensiddur.importer.marmorstein_rosh_hashanah_2.build \
  --draft --source-root /path/to/sourcetexts/sources \
  --project-directory /path/to/opensiddur-projects/project
```

The downloader requires the configured reachable contact address and agent model
(`OPENSIDDUR_CONTACT_EMAIL`, `OPENSIDDUR_AGENT_MODEL`, or their CLI options).
It reuses the existing book-profile-based downloader and shared scan/client
operations. OCR and machine labels never become accepted readings automatically.

The builder requires current hash-bound adjudication and explicit title layouts.
It validates both documents before writing `index.xml` in the separate `prayerbook_for_the_new_year_second_day` Hebrew
and English projects. Each entry point contains the volume-two bibliography. It never writes
first-day projects or supplies absent English from the first volume.
The four accepted source readings remain unchanged; project separation requires
an independently reviewed equivalence record and refreshed presentation evidence.

Confirmed excerpts can be generated separately while the larger batch remains in
adjudication:

```bash
uv run python -m opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers \
  --draft --source-root /path/to/sourcetexts/sources \
  --project-directory /path/to/opensiddur-projects/project
```

The versioned `batches/maariv_s5_s24/draft_units.json` recipe binds its source
inputs by hash. This command writes only named excerpt modules, never index.xml;
it removes a previously generated counterpart if its recipe now records an absent
translation, after all current documents validate. These draft modules do not
accept a complete scan or add words to the documentary/expanded service.

Complete ranges within a biblical chapter use a separate hash-bound recipe:

```bash
uv run python -m opensiddur.importer.marmorstein_rosh_hashanah_2.draft_prayers \
  --draft --source-root /path/to/sourcetexts/sources \
  --project-directory /path/to/opensiddur-projects/project \
  --recipe batches/maariv_s5_s24/scripture_ranges.json
```

Each witness supplies its actual verse identities and page breaks. A page break
can occur inside different verses in the two languages; its surrounding text
controls spacing, including a Hebrew maqaf join. A missing translated verse stays
absent. Range documents expose exact verse milestones, retain initial facsimile
provenance, and do not advertise a complete chapter or fabricate printed citations.

The recipe `batches/maariv_s5_s24/shema_remaining_ranges.json` covers the
remaining two Shema paragraphs. Printed citations become
notes targeting the first verse actually present in each witness. Source evidence
keeps the original citation spelling and parentheses; display references use a
chapter:verse separator without enclosing parentheses.

Liturgical modules use `--recipe batches/maariv_s5_s24/emet_veemunah_units.json`.
A witness supplies `parts`: each canonical `urn` starts a prayer-part milestone;
`new_paragraph: true` preserves a printed paragraph boundary independently. A
continuation may omit `urn` to keep the current part across paragraphs. Bounded
`quotation` content supplies `urn`, `chapter`, `verse` and `content`, with explicit
chapter/verse terminators and current-page provenance. Contextual role and ritual
instructions belong in the service spine. Recipes must mark actual Divine Name
words; matching two adjacent yods inside an ordinary word is not sufficient.

The `hashkivenu_kaddish_units.json` recipe keeps Hashkivenu in one printed
paragraph while exposing its opening and existing `hapores_sukkat_shalom`
variant root as reusable ranges. The service spine must use that root or the
whole prayer; this witness does not supply the deeper `/text` identity.
Kaddish uses `text_language: arc` on its witness, which annotates only its
paragraphs and preserves the Hebrew publication language. Contextual role,
calendar and quorum selection remain separate service-review gates.

The complete evening recipe is `batches/maariv_s5_s24/evening_sequence.json`.
Its `prayer_recipes` list is the ownership manifest for all47 modules. Generate
each listed recipe with `draft_prayers`, then assemble the documentary indexes
and shared expanded entry:

```bash
uv run python -m opensiddur.importer.marmorstein_rosh_hashanah_2.evening \
  --draft --source-root /path/to/sourcetexts/sources \
  --project-directory /path/to/opensiddur-projects/project
```

`paragraphs` witnesses expose a whole prayer without inventing child identities.
`quotation.subverse` selects a registered `half-verse` or `verse-part` unit;
repeated/adapted `source_span` content keeps attribution without duplicating the
canonical verse. `marked_variant` uses an existing named optional wording.
Recipe-level `corrections` reuse the shared exact-locator sic/corr helper.

The service recipe owns roles, condition labels, directives and local settings.
Missing counterparts produce neither empty prayer files nor empty scopes. The
expanded entry supplies the unprinted Hebrew Kaddish/Yigdal dependencies and
records their first-day bibliography. A hash-bound, exact Titqabbal source span
is exposed in the expanded project without editing the accepted first-day file.
The three settings files select documentary Hebrew, documentary parallel and
expanded second-night output. Generation alone does not accept the batch.
