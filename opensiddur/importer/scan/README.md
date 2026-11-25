# Shared scan code and edition recipes

Before working on a scanned edition, read the required
[scan digitization instructions](../../../specs/SCAN_DIGITIZATION_INSTRUCTIONS.md).
They cover transcription, review, alignment, recitation structure and export QA;
this README describes the shared code contracts.

Reusable behavior lives here and is included in coverage:

| Module | Contract tested with synthetic inputs |
|---|---|
| `pages.py` | Book isolation, scan identity, ambiguous labels, cache reuse, verified downloads, failure cleanup and image bands |
| `metadata.py` | Machine page candidates, image evidence, unknown labels and reciprocal translation pairing |
| `compare.py` | Text/pointing/whitespace differences, opt-in settlement policy and stale adjudications |
| `reverse.py` | XML source order, printed abbreviation branches, language scopes and documentary stream comparisons |
| `authoring.py` | XML namespaces, mixed-language spans, anchored notes, continuing verse, refrain structure, boolean scopes and validation before writes |
| `pdf.py` | Glyph geometry, caller-supplied mirrored columns, body/apparatus separation, bookmarks, contents destinations and section clipping |
| `pdf_direction.py` | Direction from glyph positions against source n-grams, including reversed controls |

Tests must describe behavior using invented text, temporary files and synthetic
XML/glyph coordinates. Do not copy an edition's words, page inventory or prayer
sequence into expected test results. Source fidelity is established by scan
proofreading and documentary/PDF verification, rather than a unit-test snapshot.

The `asher_selichot` package retains the edition's assembly/layout recipes,
identity tables, fixed Archive download selection and fixed-text inspection
commands. These are one-book tooling, not supported generic APIs. Their existing
CLI/import paths still work; reusable operations are imported from this package.
`codecov.yml` explicitly ignores those recipes, and `.coveragerc` omits the same
paths so local and CI totals use the same scope. Existing edition regression
fixtures still run; this change does not add transcription-data tests.

Coverage exclusions do not disable a recipe or its validation commands. Adding
an algorithm to an ignored recipe is not a shortcut around testing: extract any
reusable behavior here and add synthetic tests. Keep edition identifiers,
fingerprints, thresholds and geometry in the edition recipe or source data, and
pass them to shared code explicitly. New shared modules must not be added to the
ignore list merely because coverage is low. Compiler/exporter logic remains
covered, as do its behavioral regressions. Both Codecov targets remain 85%.
