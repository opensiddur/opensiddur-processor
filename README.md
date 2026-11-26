# Open Siddur Project (AI aided version)

[![Tests](https://github.com/opensiddur/opensiddur-processor/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/opensiddur/opensiddur-processor/actions/workflows/tests.yml)
[![codecov](https://codecov.io/github/opensiddur/opensiddur-processor/branch/main/graph/badge.svg?token=S4DAU7F6VY)](https://codecov.io/github/opensiddur/opensiddur-processor)

This is a work in progress to convert the Open Siddur Project to use AI to aid in the conversion of the liturgical texts.

## Features:
* A new version of JLPTEI (2) with a simplified schema.
* Less emphasis on UI: This is primarily about converting texts from any input format to JLPTEI, and converting the JLPTEI to useful output formats and combining texts in novel ways.

## Checkout

The source texts and the derived JLPTEI projects live in two other repositories, both attached
here as git submodules — `sourcetexts/` and `opensiddur-projects/`. A release tag of this
repository therefore names the exact commits of both that the code was tested against. The
books are released separately, as monthly date tags (`vYYYYMMDD`) of opensiddur-projects, each
built with the latest release of this repository (see `RELEASE_PROCEDURE.md`).

```bash
git clone git@github.com:opensiddur/opensiddur-processor.git
cd opensiddur-processor
git submodule update --init
uv sync --all-groups
```

A new git worktree starts with empty submodule directories; run `git submodule update --init`
there too.

See [RELEASE_PROCEDURE.md](RELEASE_PROCEDURE.md) for how a version of this repository is tagged
and how it pins `sourcetexts`/`opensiddur-projects` commits, and how the books are released.

## Schema
To compile the schema:

Prerequisites:
You need a working version of podman (open source implementation of docker).

The main schema is in `schema/jlptei.odd.xml`. To compile it, run:
```bash
$ scripts/build-schema.sh
```

The output will be in the `schema` directory as RelaxNG XML (and, eventually, ISO Schematron).

## Sources

Available sources in their original (or close to original) form are in `sourcetexts/sources`,
the [opensiddur/sourcetexts](https://github.com/opensiddur/sourcetexts) submodule. Every importer
reads from there by default; `--sourcetexts-root` overrides it with an external clone.

Input converters for each specific source are in the `importer` directory.

Example: run the WLC importer:

```bash
uv run python -m opensiddur.importer.wlc.wlc
```

Example: run the JPS 1917 importer:

```bash
uv run python -m opensiddur.importer.jps1917.convert_wikisource
```

Example: download Miqra al pi ha-Masorah, as MAM-parsed plus JSON from MAM-basics, into
sourcetexts, then convert it:

```bash
uv run python -m opensiddur.importer.miqra_al_pi_hamasorah.download
uv run python -m opensiddur.importer.miqra_al_pi_hamasorah.convert
```

## JLPTEI sources

JLPTEI sources are compiled into `opensiddur-projects/project`, the
[opensiddur/opensiddur-projects](https://github.com/opensiddur/opensiddur-projects) submodule.
`--project-directory` overrides it with an external clone.

Its `settings/` directory holds the exporter settings for the released books, one subdirectory
per book with a settings file per variant (`settings/chumash-opensiddur-he/annual.yaml`). Every release
builds them into electronic books (HTML) and PDFs, as each one's `formats:` lists, attached to
the GitHub release; see
[`opensiddur/exporter/README.md`](opensiddur/exporter/README.md#released-books).

## Reference database

The exporter resolves `urn:x-opensiddur:` URIs to project files via a SQLite
database at `database/reference.db`. Whenever you add, remove, or rename files
in `opensiddur-projects/project/`,
re-sync the database so the compiler can find them:

```bash
uv run python -m opensiddur.exporter.refdb
```

The command scans every `project/<name>/` subdirectory, updates URN and
cross-reference mappings for changed files, and removes stale entries for
projects or files that no longer exist.  It prints a per-project summary on
completion.

You must re-sync before running the compiler on any newly-added project. 

## Compilation (JLPTEI → compiled linear XML)

The compiler takes an `opensiddur-projects/project/<name>/` file,
resolves transclusions, annotations, and parallel texts,
and outputs a single “compiled” XML file that can be 
converted into a final printable format (eg, PDF).

Example (compile `project/tanakh-wlc-he/ruth.xml` to `compiled.xml`):

```bash
uv run python -m opensiddur.exporter.compiler \
  --project tanakh-wlc-he \
  --file_name ruth.xml \
  --output_file compiled.xml
```

Example with a settings YAML (controls project priorities, annotations, and optional parallel lookup):

```bash
uv run python -m opensiddur.exporter.compiler \
  --project tanakh-wlc-he \
  --file_name ruth.xml \
  --settings doc/exporter-settings.example.yaml \
  --output_file compiled.xml
```

## TeX export (compiled XML → LuaLaTeX)

Convert the compiled XML file to LuaLaTeX using the `reledmac`/`reledpar` pipeline:

```bash
uv run python -m opensiddur.exporter.tex.latex \
  compiled.xml \
  --settings doc/exporter-settings.example.yaml \
  --output compiled.tex
```

## PDF export (compiled XML → PDF)

Export directly to PDF (generates TeX internally, then runs LuaLaTeX and BibTeX):

```bash
uv run python -m opensiddur.exporter.pdf.pdf \
  --settings doc/exporter-settings.example.yaml \
  compiled.xml \
  output.pdf
```

Keep the intermediate TeX (helpful for debugging LaTeX issues):

```bash
uv run python -m opensiddur.exporter.pdf.pdf \
  --settings doc/exporter-settings.example.yaml \
  --keep-tex \
  compiled.xml \
  output.pdf
```

## Licensing

* **Code** in this repository is licensed under the GNU Lesser General Public License v3 or later (LGPL 3+) — see [LICENSE](LICENSE).
* **Project texts** (`opensiddur-projects/` submodule) are each covered by the license declared in that document's own TEI header (`tei:publicationStmt/tei:availability/tei:licence`), which may differ per document.
* **Source texts** (`sourcetexts/` submodule) are each covered by the license accompanying that source in `sourcetexts/sources/`, which may differ per source.
