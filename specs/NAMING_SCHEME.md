# Naming projects, settings, files and URNs

This document defines how projects, book settings, project files and the path components of
`urn:x-opensiddur:` names are spelled. It supplements [JLPTEI-3.md](../schema/JLPTEI-3.md),
which holds the transliteration table, and [SIDDUR_URN_SCHEME.md](SIDDUR_URN_SCHEME.md),
which says what a URN names. Check a corpus against it with:

```bash
uv run python -m opensiddur.common.validate_names
```

## Project identifiers

A project identifier is the name of its directory under `opensiddur-projects/project/`, and the
`@project` suffix of every URN that names it (`urn:x-opensiddur:text:bible:genesis/1/1@tanakh-wlc-he`).
So it has to be a valid URN part, a safe file name on every filesystem, and a safe word in a
shell loop and a TeX job name. It is lowercase ASCII:

```
<title>-<author>-<date>-<lang>
```

Fields are joined by `-`; the words within a field are joined by `_`. Formally,
`^[a-z0-9]+(_[a-z0-9]+)*(-[a-z0-9]+(_[a-z0-9]+)*)+$`: at least two fields.

| Field | What it holds | Required |
|---|---|---|
| `title` | The work's title: its common English name where it has one (`tanakh`, `siddur_expanded`); else the source's own romanization of its name, if it gives one ([below](#a-source-that-romanizes-its-own-name)); else the title page's Hebrew romanized by the [table](#transliteration). Leading articles and prepositions join their word (`hasiddur_hashalem`, `haggadah_leleil_shimmurim`). | yes |
| `author` | The surname of the author, editor or translator who makes this edition what it is (`birnbaum`, `asher`, `jps`, `wlc`). `opensiddur` for an Open Siddur compilation. | when there is one |
| `date` | The year of the edition. Left out for an undated or continuously revised work. | when there is one |
| `lang` | The `xml:lang` of the project's `index.xml`, lowercased: a BCP 47 tag, so `he-latn` is two fields. Always last. | yes |

A translation and the original it translates share a `title`, as the Hebrew and English of one
book do, so a pair reads as a pair: `hasiddur_hashalem-birnbaum-1949-he` and
`hasiddur_hashalem-birnbaum-1949-en`.

`title (author, publisher, date)`, the form used for uploads to opensiddur.org and the
Internet Archive, carries the same information but cannot be an identifier: spaces are not legal
in a URN, a romanized title carries diacritics, mixed case collides on case-insensitive
filesystems, and parentheses, commas and spaces break the tooling. The publisher is left out
because it rarely tells two editions apart that the author and date do not.

### Former names

The projects took these identifiers in one change (issue #266, phase 2), as did their
books' settings directories. An older processor, or text written before then, may still use
the former name.

| Former name | Identifier |
|---|---|
| `asher_selichot_he_1912` | `selichoth-asher-1912-he` |
| `asher_selichot_en_1912` | `selichoth-asher-1912-en` |
| `birnbaum_ashkenaz_he_1949` | `hasiddur_hashalem-birnbaum-1949-he` |
| `birnbaum_ashkenaz_en_1949` | `hasiddur_hashalem-birnbaum-1949-en` |
| `heidenheim_haggadah_1822` | `haggadah_leleil_shimmurim-heidenheim-1822-he` |
| `feinstein_haggadah_translation_2009` | `haggadah_leleil_shimmurim-feinstein-2009-en` |
| `humash` | `chumash-opensiddur-he` |
| `siddur_expanded` | `siddur_expanded-opensiddur-he` |
| `jps1917` | `tanakh-jps-1917-en` |
| `miqra_al_pi_hamasorah` | `tanakh-miqra_al_pi_hamasorah-he` |
| `wlc` | `tanakh-wlc-he` |
| `original-example` | `example_original-he` |
| `translation-example` | `example_translation-en` |

### A source that romanizes its own name

When a source gives its own name in Latin letters, that romanization is the title, not the
table's: the name is the source's, and a reader looking for the book looks for it as printed. It
is folded to the identifier's alphabet and nothing more: lowercased, diacritics stripped, hyphens
and apostrophes dropped with the parts joined, and spaces made `_`.

| The source prints | Title field |
|---|---|
| *Selichoth for the Propitiatory and Penitential Days* (Asher, 1912) | `selichoth` (the table gives `selichot`) |
| *ha-Siddur ha-Shalem* (Birnbaum, 1949) | `hasiddur_hashalem` |
| *Miqra al pi ha-Masorah* | `miqra_al_pi_hamasorah` |

The exception is for the project's title only. The texts inside the book, its file names and
URNs follow the table, so that one prayer is spelled one way in every book.

The 1822 Heidenheim haggadah prints its title only in Hebrew, so the table applies. The title
page reads סדר ההגדה לליל שמורים, which our `index.xml` gives as *Haggadah le-Leil Shimurim*: "the haggadah *for* the night of vigil", not the construct
*haggadat leil*. The mem of שִׁמֻּרִים carries a dagesh, so it doubles: `shimmurim`.

### Projects imported from opensiddur.org

Projects imported from the opensiddur.org export follow the same format; they are not named
after the post that carried them.

- `title`: the Latin-script part of the post's title, up to its first comma or "by", with
  anything in brackets left out: *Maoz Tsur (Rock of Ages), singing translation by…* is
  `maoz_tsur`. A post that romanizes its own name keeps its romanization, folded to ASCII: the
  style guide's letters are mapped onto the table's (`ḥ`→`ch`, `ẓ`→`tz`, `ƙ`→`kh`, `š`→`sh`,
  `ḳ`→`q`), `ʼ` and `ȝ` are dropped and any other diacritic is stripped. Cut at a word
  boundary to at most 60 characters. A title with no Latin part is taken from the post's slug.
- `author`: a translation's translator, or none when the translator is unknown; for any
  other column, the original author. The title's "by" settles which credited name is which
  (*…a hymn by Penina Moïse*, *trans. by Frederick de Sola Mendes*), since the site's credits
  do not always say. A name with a patronymic or a place is given by its first name
  (`mordekhai` for Mordekhai ben Yitsḥaq ha-Levi), any other by its surname.
- `date`: for any column but a translation, the year of the original work, else of the post;
  `515bce` for a year before the common era. A translation has none: when it was made is
  rarely recorded.
- Should two posts produce the same identifier, the newer post, by ID, adds its post ID as a
  field before `lang`, so adding a post never renames an older one. The importer assigns
  identifiers across the whole export, whichever posts a run converts.

The post ID stays recorded in `index.xml`, and is how the importer finds a post's projects
again. Retitling a post renames its project, and the importer removes the old one and says so.

A post that matches no text in the collection is given a URN named the same way as the
project's title, but with each word respelled by the spelling list (`maoz_tzur`, where the
project keeps the post's `maoz_tsur`), and followed by the original author's name
(`rock_of_ages_gottheil`). The text file of such a project is named from the post's
URN, its path components joined by `_`.

## Settings files and book names

A book's settings live at `opensiddur-projects/settings/<project>/<variant>.yaml`, where
`<project>` is the settings file's `book.project`. The release names its files
`<project>-<variant>[-<tag>].<pdf|html>`, so a book is named after the project it is built from.
A book with a translation in parallel is named after its primary project.

## File names

A project file's stem is lowercase ASCII words joined by `_`:
`^[a-z0-9]+(_[a-z0-9]+)*$`. Its Hebrew words follow the [table](#transliteration).

A file name and a URN that name the same text spell its words the same way. Where a file holds
one URN-named text, the stem is that URN's path components joined by `_`, with a section prefix
where the project needs one (`haftarat_`, `shabbat_`).

## URN path components

A URN path component is lowercase ASCII, digits and `_`
(`opensiddur.common.urn_registry.COMPONENT_RE`): no `-`, which marks a range, and none of `@`,
`#`, `:`, `/`, `(`, `)` or `,`. Its Hebrew words follow the [table](#transliteration).

A URN that is respelled is recorded in `specs/urn_registry/aliases.jsonl` as an alias of its new
spelling; the registry check reports any project still emitting it.

## Transliteration

Hebrew words in identifiers, file names and URNs are romanized by the table in
[JLPTEI-3.md](../schema/JLPTEI-3.md#transliteration). It is ASCII-only: digraphs, never
diacritics. Where the opensiddur.org style guide's simple forms differ, this table wins: het is
`ch`, never `h`, so that it stays distinct from heh; tsadi is `tz`, not `ts`.

### Common spellings and known variants

`specs/naming/spellings.yaml` holds two lists:

- `exceptions`: words with a common spelling that wins over the table (`kaddish`, `chanukah`,
  `chumash`). Only words with a spelling of their own in English belong here, not every word a
  book happens to print in English.
- `variants`: a non-standard spelling, mapped to its standard one (`hanukkah: chanukah`,
  `kedushah: qedushah`). `validate_names` reports every variant it finds in a file name, a URN
  path component or the registry. It does not check a project identifier's spelling: its title
  may be the source's own romanization, and its author is a person's name.

An importer that names something from a source's own words -- hebcal's reading names, the
reading IDs of a transcription -- respells those words by the list as it names it
(`opensiddur.common.validate_names.respell` and `respell_urns`), and keeps the source's own
spelling in the source. A word added to the list is then respelled everywhere by regenerating.
Until then the projects that use the old spelling fail the check, so a change to the list comes
with an opensiddur-projects PR of the same branch name that regenerates them.

The variant list catches known misspellings, not every one. A word is only a variant if it
cannot be another word: `selah` (סֶלָה) and `selach` (סְלַח) are both correct, so neither is
listed. Where one book's reading IDs use such a word wrongly, its importer keeps a list of its
own, applied after the shared one to that book alone: Asher's `selah` is סְלַח, so
`opensiddur/importer/asher_selichot/spellings.yaml` respells it `selach` in Asher's names only.
That list also renames the few reading IDs that did not spell the printed words, and has whole
names to rename where a word is right in the book's other names (`renames`).

Spellings are settled from the Hebrew, a family of books at a time, and each new decision is
added here so the next book is held to it.
