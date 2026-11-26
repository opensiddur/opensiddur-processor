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

The builder requires current hash-bound adjudication and explicit title layouts, and validates both documents before writing `day_two.xml` in the existing
Hebrew and English edition projects. It does not write `index.xml`, day-one
modules, settings or the expanded maḥzor. Add those integrations only after
reading and reviewing the corresponding new material. The synthetic startup test
checks that the accepted index/shared modules survive and each language receives
the complete multilingual paratext with correct language tags and per-page paratext gates.

Use `--update-bibliography` explicitly to add/update only the volume-two bibliography in the edition indexes. The default build leaves indexes unchanged; the explicit update preserves all existing index content.
