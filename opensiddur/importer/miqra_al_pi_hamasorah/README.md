# Miqra al pi ha-Masorah importer

Imports [*Miqra according to the Masorah*](https://he.wikisource.org/wiki/%D7%9E%D7%A7%D7%A8%D7%90_%D7%A2%D7%9C_%D7%A4%D7%99_%D7%94%D7%9E%D7%A1%D7%95%D7%A8%D7%94) (MAM) into the JLPTEI project `tanakh-miqra_al_pi_hamasorah-he`. The text comes from the JSON files of [MAM-parsed plus](https://bdenckla.github.io/MAM-basics/MAM-parsed/plus/html/mpplus.html) in [MAM-basics](https://github.com/bdenckla/MAM-basics), which are parsed from MAM's text at Hebrew Wikisource. The humash importer reads its aliyah divisions from the same files (`humash/aliyot.py`).

## License

MAM was prepared by Seth (Avi) Kadish from materials that he originally developed at Hebrew Wikisource, and is available under **CC BY-SA 4.0**. The attribution it asks for differs between Hebrew and other languages; see the downloaded `LICENSE.md`, MAM-parsed's own, for its wording. The project's `index.xml` quotes, in English and in Hebrew, the licence's credit to MAM's editors and the attribution it asks for, and names the commit its text was taken from.

## Download

Writes into the `sourcetexts` submodule (`sourcetexts/sources`) by default; pass
`--sourcetexts-root` to use an external clone instead.

```bash
uv run python -m opensiddur.importer.miqra_al_pi_hamasorah.download
```

MAM-basics publishes no releases of the files, so a download is pinned to a commit: `COMMIT` in `download.py`, or `--commit`, which also takes a branch or tag (resolved to its commit through GitHub's API). Use `--dry-run` to print paths without downloading. A run whose commit and files match the manifest downloads nothing and writes nothing. Files are compared byte for byte, so the sourcetexts commit that adds the download needs the `.gitattributes` line `sources/miqra_al_pi_hamasorah/** -text`, which keeps Git for Windows from turning their line ends into CRLF.

Output layout:

```
<sourcetexts-root>/miqra_al_pi_hamasorah/
  manifest.json      the repository, the commit, each file's URL, size and SHA-256, the download time
  LICENSE.md         MAM-parsed/LICENSE.md
  plus/
    A1-Genesis.json
    …
    FC-Chronicles.json
```

Each file is checked against the Git blob SHA GitHub lists for it at the commit. Every file is fetched and checked before any is written, and the manifest is written last, so a download that fails leaves the previous one as it was. A file under `plus/` that the previous manifest recorded and the commit no longer has is deleted.

The first download replaces `manifest.json`, which described the retired Google Sheet export in `sheets/`. The importer no longer reads `sheets/`; the download leaves it for the maintainer to remove in the sourcetexts commit that adds the download.

## Convert

```bash
uv run python -m opensiddur.importer.miqra_al_pi_hamasorah.convert [--only-book genesis] [--check]
```

Each plus file holds one or more books of the 39, each a set of chapters of verses; a verse is `[C, D, E]`: the separator from the previous verse, the verse label and the verse proper, as strings and templates. `miqra_plus.py` walks them with a closed dispatch: every template has a handler naming the role of each of its parameters (rendered text, note, apparatus, alternative), and an unknown template or parameter raises. It writes the intermediate XML that `miqra_to_tei.xslt` turns into TEI; `canonical_verses.py` first moves MAM's verses onto the canonical verse division. Chapter and verse numbers come from the JSON keys. `convert` reads only the files the manifest lists, and refuses one whose SHA-256 differs from the manifest's, or a JSON file in `plus/` that the manifest does not list, so that the text is never credited to a commit it was not taken from. `convert` converts every book before it writes any file: a missing book, or a template or parameter it rejects, stops it before the project directory is touched, and `--only-book` writes the same file as a full run, note ids included. After moving `COMMIT`, run the download and then `convert --check`, which reads and converts the whole download and writes nothing, so that a change in MAM-parsed's format fails there, before any project file is written.

Where MAM offers alternatives the importer keeps: both ketiv and qere of כו״ק, קו״כ and מ:כו״ק מיוחד (`tei:choice`), but only the pointed ketiv of מ:קו״כ-אם-2; both cantillations of a span with two (`j:option`); the form without the stress helper (מ:דחי, מ:צינור); the grammatical qamats (מ:קמץ's `ד`). A word written and not read (כתיב ולא קרי) or read and not written (קרי ולא כתיב) has one form, which is kept in its parentheses or brackets (`tei:hi`). MAM's documentation notes and scroll-difference notes go to the `tei:standOff`: a note in the verse proper (column E) is anchored where it stands, and a note in the separator or the verse label (columns C and D) at the head of the verse. The good endings (`good_ending_plus`) are checked but not imported.
