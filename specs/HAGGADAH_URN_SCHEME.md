# Haggadah canonical URN scheme

This document defines canonical reference URNs for Passover haggadah projects in the
Open Siddur JLPTEI corpus. It supplements [JLPTEI-3.md](../schema/JLPTEI-3.md).

## Namespace overview

| Content | URN prefix | Example |
|---------|------------|---------|
| Haggadah-specific sections | `urn:x-opensiddur:text:haggadah:` | `…/maggid/ha_lachma_anya` |
| Shared liturgy (kiddush, birkat hamazon, etc.) | `urn:x-opensiddur:text:prayer:` | `…/kiddush/…` |
| Biblical quotations | `urn:x-opensiddur:text:bible:` | `…/genesis/1/31` |

A `@corresp` carries the URN alone, with no project: the Hebrew and the English carry the
same URNs, which is what aligns them. A project suffix — `@haggadah_leleil_shimmurim-heidenheim-1822-he`
(Hebrew) or `@haggadah_leleil_shimmurim-feinstein-2009-en` (English) — belongs only on a
`j:transclude` target that must name the project it takes the text from.

## Haggadah namespace

Top-level URN:

```
urn:x-opensiddur:text:haggadah:haggadah
```

Index/outline files use the index slug as the final path component:

```
urn:x-opensiddur:text:haggadah:pre_seder
urn:x-opensiddur:text:haggadah:seder
urn:x-opensiddur:text:haggadah:maggid
```

Leaf section files use the section slug:

```
urn:x-opensiddur:text:haggadah:bediqat_chametz
urn:x-opensiddur:text:haggadah:maggid/ha_lachma_anya
urn:x-opensiddur:text:haggadah:nirtzah/chasal_siddur_pesach
```

Nested maggid and nirtzah subsections use a two-level path under `haggadah:`.

### Sub-paragraph markers

Within a section file, each body paragraph is marked with a `tei:milestone` whose
`corresp` URN appends a sequence number after `/`, analogous to chapter/verse paths in
biblical texts:

```
urn:x-opensiddur:text:haggadah:qaddesh/1
urn:x-opensiddur:text:haggadah:qaddesh/2
urn:x-opensiddur:text:haggadah:maggid/ha_lachma_anya/1
```

```xml
<tei:milestone unit="paragraph" n="1" corresp="urn:x-opensiddur:text:haggadah:qaddesh/1"/>
<tei:p>…</tei:p>
```

These numbered URNs align the Hebrew with its translation, which were divided together. A
number is a poor key across editions, though, since the count is each edition's own (see
*Sub-division numbering* in SIDDUR_URN_SCHEME.md): another haggadah should share a numbered
URN only where it divides the passage the same way, and prefers a named subdivision where the
passage has a name.

Index files (such as `maggid.xml` or `nirtzah.xml`) may contain `tei:head` and body
content for the section title and any text that belongs to the index division itself,
followed by `j:transclude` elements for child sections.

## Prayer namespace (shared liturgy)

Sections that are not haggadah-specific—such as kiddush in `qaddesh.xml` or birkat
hamazon in `barech.xml`—use the existing `prayer` namespace per JLPTEI-3 transliteration
rules. The containing file remains a `haggadah:` URN on its root `tei:div`; inner
`tei:div` or `tei:milestone` elements carry `prayer:` URNs where appropriate.

## Bible namespace

When a passage is biblical (per OSP compilation footnotes), use standard bible URNs on
`tei:milestone` or annotation `corresp` values, e.g.:

```
urn:x-opensiddur:text:bible:exodus/12/26
```

Biblical alignment uses WLC paths where the Open Siddur transcription followed WLC.

## Parallel alignment

Hebrew and English projects share identical `corresp` URNs (without relying on matching
`@project` suffixes) so the compiler can align parallel streams. Project layout is flat:
all `.xml` files are siblings; hierarchy is expressed only through `j:transclude` in
index files.

## Page breaks

`tei:pb/@n` records the foliation printed in the 1822 Heidenheim edition itself — folios
`2r` through `40v`, each folio numbered once as a Hebrew numeral on the recto and once as
an Arabic numeral on the verso. It is deliberately not the 10–88 sequence the HebrewBooks
scan adds at the foot of each page, and not the index of the page within the scanned PDF.

The curated table of breaks lives in
`opensiddur/importer/feinstein_haggadah/page_breaks_1822.json`, which is the source of
truth; each entry anchors a break to the words on either side of the turn rather than to a
page number, and every one was verified by hand against the facsimile.
`align_page_breaks` is a developer aid that produces a rough draft only — nothing in the
conversion path imports it, and its output is not authoritative.

```xml
<tei:pb n="3v" ed="1822" facs="https://www.hebrewbooks.org/pdfpager.aspx?req=4909&amp;pgnum=6"/>
```

`@facs` deep-links the same page in the facsimile, so `@n` stays citable as the printed
foliation while the digital edition remains linkable. The mapping is exact and regular:
`pgnum=1` is the title page, folio `2r` is `pgnum=3` where the text begins, and the
recto/verso alternation runs unbroken to folio `40v` at `pgnum=80`, the last page of the
scan. It is implemented by `facsimile_page()` and `facsimile_url()` in `page_breaks.py` —
do not recompute it inline.

The reference copy is `sources/heidenheim_haggadah_1822/Hebrewbooks_org_4909.pdf`, 80 pages,
paginated identically to `pgnum`. Other copies of this scan circulate with a copyright page
inserted as page 2 and so run one page ahead; checking a link against one of those makes a
correct mapping look off by one.

When verifying, check a page in the middle of the book, not only the ends. The viewer clamps
an out-of-range `pgnum` to the last page, so an off-by-one mapping still resolves the final
folio correctly while every page before it is wrong.

The converter emits `tei:pb` only in the Hebrew (`haggadah_leleil_shimmurim-heidenheim-1822-he`) project. The
English translation project has no 1822 pagination and omits `tei:pb` milestones.

`@facs` reaches the schema through `<classRef key="att.global.facs"/>` in
`schema/jlptei.odd.xml`; the TEI `transcr` module is *not* included, so `tei:facsimile`,
`tei:surface` and `tei:graphic` remain unavailable and `@facs` always holds an absolute
URL rather than a local pointer.
