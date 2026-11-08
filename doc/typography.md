# Typography settings

Everything about how an exported document looks. This is the `typography:` section of a
settings file, read by the output stage only; the linear-XML compiler ignores it.

**Every setting is optional and every default reproduces the output this exporter has always
produced.** A settings file with no `typography:` section, or one that sets a single key, gets
the same document it always got in every other respect.

**Invalid settings fail before anything is rendered.** Unknown keys, values outside a closed
list, malformed lengths and font chains with nothing installed are all errors naming the
offending key and its path, and so is a setting the PDF stage would accept and do nothing
with — an `align` on a role set mid-line, a column too wide to have a neighbour. Nothing
silently falls back: a setting that was quietly dropped would leave a document missing what
was asked for, with nothing to say why. The electronic book reflows, and honours only the few
settings [listed at the end](#how-this-reaches-the-renderer); it ignores the rest.

Settings are renderer-agnostic: they describe the document, not the commands that typeset it.
There is no TeX in a settings file, and there is no place to put any.

```yaml
typography:
  page:
    paper: a5paper
    margins: {inner: 25mm, outer: 18mm}
  paragraphs:
    line_spacing: 1.3
  styles:
    heading1: {size: x-large, weight: bold, align: center}
    note: {size: 9pt, weight: normal}
  line_numbers:
    enabled: false
```

## Value types

| Type | Written as | Notes |
| --- | --- | --- |
| length | `12pt`, `1.5em`, `25mm`, `0.75in` | Units: `pt`, `bp`, `mm`, `cm`, `in`, `pc`, `em`, `ex`. `em` and `ex` are relative to the font in force where the length is used. Only `paragraphs.indent` (a hanging indent) and a style's `space_before`/`space_after` may be negative; a negative margin, page, rule, spacing or indent is an error. |
| absolute length | `12pt`, `25mm` | The same without `em`/`ex`. Required where the length is itself defining a font size. |
| percentage | `43%` | Of the enclosing measure. |
| size | `x-large` or `10pt` | See the ladder below. |

### The size ladder

A named size follows the selected font’s `normal_size`, or `page.base_font_size` when
that is omitted. Named sizes preserve the document class’s size ladder proportions relative
to normal. An absolute length pins a role to an exact size regardless of the selected font. Each
step of the ladder is roughly 1.2 times the one below it.

| Name | Relative size | | Name | Relative size |
| --- | --- | --- | --- | --- |
| `xxx-small` | smallest | | `large` | one step up |
| `xx-small` | | | `x-large` | |
| `x-small` | | | `xx-large` | |
| `small` | one step down | | `xxx-large` | |
| `normal` | the base size | | `xxxx-large` | largest |

## `fonts`

Named font families. Each is a **chain of names tried in order**; the first one installed on
the machine building the document is used. If none of them is installed, that is an error —
falling back to whatever the renderer would have picked produces a document that is quietly
not the one that was asked for, and for Hebrew it is usually one with no vowels or
cantillation. A bare string is shorthand for a one-name chain.

Two families always exist, because the exporter refers to them by role rather than by name:
`latin` for Latin-script text and `hebrew` for Hebrew-script text. Declaring one **replaces**
its default chain rather than extending it. You may declare families of your own and point a
style at them by name. A family's name is lower-case words joined by single hyphens
(`note-sans`), because it becomes the name of a TeX command, which is letters only. A font's
own name may not contain any of `{ } \ % # & $ ^ _ ~`.

```yaml
typography:
  fonts:
    hebrew: ["Frank Ruehl CLM", "Ezra SIL", "SBL Hebrew", "FreeSerif"]   # the default chain
    latin: "Linux Libertine O"                                           # the default
    note-sans: ["DejaVu Sans"]                                           # your own
```

Each entry can instead specify `name` and `normal_size`, a positive finite number in
points (without a `pt` suffix). The first installed entry supplies **both** the font and
its normal size, so different fallback fonts can have different sizes:

```yaml
typography:
  fonts:
    hebrew:
      - {name: "Frank Ruehl CLM", normal_size: 12}
      - {name: "Ezra SIL", normal_size: 12}
      - {name: "SBL Hebrew", normal_size: 13}
      - {name: "FreeSerif", normal_size: 12}
    latin:
      - {name: "Linux Libertine O", normal_size: 11}
```

String entries and entries without `normal_size` retain the document class’s sizes.
They may be mixed with sized entries in the same list. These settings work for custom
families too. Font switches preserve the surrounding role’s relative size; explicit
style sizes such as `9pt` remain exact even across font switches. Line spacing scales
with relative sizes. Omitting all per-font sizes preserves existing output. The book
class’s `11pt` option actually uses 10.95pt normal text; an explicit `normal_size: 11`
means exactly 11pt.

**Only a chain you write is checked.** The two defaults are not: a document that asked for
nothing must still export on a machine that does not have this project's house fonts, so the
renderer falls back for them on its own: the PDF stage chooses among them when the document is
typeset, and with none of the `latin` defaults installed keeps the document class's own face. Writing a chain down — even one whose names happen to
be the defaults — opts it into the check.

That makes a one-name chain a deliberate assertion: name a single font and a machine without it
fails the build rather than quietly substituting another. Give the chain a widely available last
resort, as the default `hebrew` chain ends in `FreeSerif`, if you would rather it degrade.

The check needs `fontconfig` (`fc-list`). On a machine without it the check is skipped and the
chain is handed to the renderer to resolve at build time instead. The check belongs to the PDF
stage. The compiler, which typesets nothing, does not make it, and neither does the electronic
book: the reader's device chooses the face, so what the building machine has installed is beside
the point. `books --check` asks the stricter question of whether a PDF could be built here, and
checks every chain, defaults included.

## `page`

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `page.paper` | `a4paper` \| `letterpaper` \| `legalpaper` \| `a5paper` \| `b5paper` \| `executivepaper` \| `custom` | `letterpaper` | Sheet size. |
| `page.width` | absolute length | — | Sheet width. Required with `paper: custom`, an error otherwise. |
| `page.height` | absolute length | — | Sheet height. Same. |
| `page.orientation` | `portrait` \| `landscape` | `portrait` | |
| `page.sides` | `one` \| `two` | `two` | `two` mirrors margins and running heads between recto and verso. |
| `page.binding` | `right` \| `left` | `right` | The edge the book is bound at. A PDF viewer reads its spreads in that direction (Acrobat's "Binding: Right Edge"), and with `sides: two` the inner margins, the `inner`/`outer` line-number margins and the default running head move to match. Under `right` the recto is the left-hand page of a spread. A two-sided book opens as a cover page and then spreads ("Two Up (Cover Page)"), and a one-sided one a page at a time. |
| `page.chapter_start` | `recto` \| `any` | `recto` | `recto` opens each book on a recto (odd) page, inserting a blank if needed. Under `binding: right` that is the left-hand page. |
| `page.base_font_size` | `10pt` \| `11pt` \| `12pt` | `11pt` | The size named sizes are relative to. Only these three exist; anything else would silently become one of them. |

### `page.margins`

Every margin defaults to the document class's own, which is what the exporter produced before
margins were configurable. Margins are named for the **binding**, not for the page edge, so
`inner` and `outer` mean the same thing on a recto and a verso, whichever edge `page.binding`
puts the binding at. On a one-sided document `inner` is the left margin and `outer` the right.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `page.margins.top` | length | class default | Space above the text block. |
| `page.margins.bottom` | length | class default | Space below the text block. |
| `page.margins.inner` | length | class default | Margin at the binding edge. |
| `page.margins.outer` | length | class default | Margin at the fore edge. |
| `page.margins.binding_offset` | length | class default | Added at the binding edge and taken off the fore edge, for the part of the page a binding swallows. On a one-sided document it is added at the left, like `inner`. |

## `paragraphs`

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `paragraphs.indent` | length | `0pt` | First-line indent. |
| `paragraphs.spacing` | length | `0.5em` | Vertical space between paragraphs, in addition to normal line spacing. |
| `paragraphs.line_spacing` | number, 0.5–3.0 | `1.0` | Multiple of single spacing. Hebrew with vowels and cantillation needs more leading than unpointed text. |
| `paragraphs.alignment` | `justify` \| `left` \| `right` \| `center` | `justify` | |

`paragraphs.spacing` sets the space between one aligned unit and the next. Inside a unit, in a
`pairs` or `pages` compile, a paragraph break is a blank line instead — reledpar advances the
two sides a line at a time, so a skip in one column would displace the facing one, and one
line is the smallest separation that stays in the column it belongs to. On facing pages it
also keeps the count of lines, which is what reledpar pairs the two pages by, true. To get the configured
spacing part-way through a prayer, split it into two units by giving the two halves their own
`@corresp` URNs; that also aligns the columns there. The `interleaved` layout sets one
column, so its paragraphs take the configured spacing throughout.

## `styles`

The appearance of each kind of text the exporter distinguishes. Setting one changes only that
role; the rest keep their defaults. A role you write **replaces** its default whole rather
than amending it: `heading1: {size: large}` gives a heading that is large and nothing else —
not bold, not centred — so restate whatever of the default you want to keep.

### Style attributes

Every role takes the same eight keys. All are optional, and an omitted one leaves that aspect
as the surrounding text has it.

| Key | Type | Effect |
| --- | --- | --- |
| `font` | a family declared in `fonts` | Omit to let the text keep the font its script selects. |
| `size` | size | See the ladder above. |
| `weight` | `normal` \| `bold` | |
| `style` | `normal` \| `italic` | |
| `variant` | `normal` \| `small-caps` | |
| `align` | `left` \| `right` \| `center` \| `justify` | Physical positions on the page, so they mean the same in a Hebrew and an English stream. Only on the roles set on a line of their own — the headings, `heading_translation`, `citation`, `list_label`, the title-page roles, `distribution_notice`, `back_notice` and `section_separator`; an error on any other. |
| `space_before` | length | Vertical space above. Only on the title-page roles (`title_main` through `title_page_block`), `distribution_notice`, `back_notice` and `section_separator`, which are paragraphs of their own; an error on any other. |
| `space_after` | length | Vertical space below. The same roles as `space_before`. |

### Roles

| Role | Default | What it sets |
| --- | --- | --- |
| `styles.body` | inherits | Ordinary running text. |
| `styles.heading1` | `xx-large`, bold, centered | Top-level section heading. |
| `styles.heading2` | `x-large`, bold, centered | Second-level heading. |
| `styles.heading3` | `large`, bold, centered | Third-level heading. |
| `styles.heading4` | `normal`, bold, centered | Fourth-level heading; the deepest there is. |
| `styles.heading_translation` | `normal`, italic, centered | A heading's translated title, where a division is titled twice. Set on its own line under the title it translates, at whichever of the four levels that title is — so it takes one style rather than four. See [`bookmarks`](#bookmarks) for how the two titles reach the outline. |
| `styles.title_main` | `xxxx-large`, bold, centered, `1.5ex` after | The main title on the title page. |
| `styles.title_sub` | `x-large`, centered, `1.5ex` before | The subtitle. |
| `styles.title_alt` | `large`, centered, `1ex` after | An alternative title, usually the title in the other language. |
| `styles.byline` | `large`, centered, `3ex` before | The author/editor line. |
| `styles.edition` | `normal`, centered, `2ex` before | The edition statement. |
| `styles.imprint` | `normal`, centered, `4ex` before | The publisher/place/date block at the foot of the title page. |
| `styles.epigraph` | `small`, italic, centered, `2ex` before | An epigraph on the title page. |
| `styles.imprimatur` | `small`, italic, centered, `2ex` before | An imprimatur or approbation. |
| `styles.title_page_block` | `normal`, centered | Any other paragraph on the title page. |
| `styles.distribution_notice` | `small`, centered | The distribution notice on the verso of the title page (see the settings file's `distribution.notice`). |
| `styles.back_notice` | `small`, `2ex` before | The statement on the book's last page, after the colophon (see the settings file's `distribution.back_notice`). |
| `styles.citation` | `normal`, italic, centered | A scriptural citation on a line of its own, naming where a reading begins or resumes. |
| `styles.parsha` | `large`, bold | A parsha name, run in at the head of the text it opens. |
| `styles.aliyah` | bold | An aliyah or maftir marker, inline at the verse it begins on. |
| `styles.verse_number` | inherits | The verse number at the start of each verse. |
| `styles.chapter_number` | `large`, bold | The chapter number, inline at the start of a chapter. |
| `styles.instruction` | bold | An instruction to the reader, in the note apparatus. |
| `styles.note` | bold | The text of an editorial note. |
| `styles.note_mark` | `xx-small` | The mark that anchors a note, in the text and where the note is printed. |
| `styles.line_number` | inherits | Marginal line numbers. |
| `styles.section_separator` | centered | The separator between unheaded sections. |
| `styles.list_label` | small-caps | The label naming an item of a labelled list, set on a line of its own above the item. Like the headings, it is set inside an aligned unit rather than as a block, so `space_before` and `space_after` do nothing here; the space above it is the space between one aligned unit and the next. See [`lists`](#lists) for the item's indent. |
| `styles.highlight_italic` | italic | Text the source highlights in italics (`tei:hi` with `rend="italic"`). Each look-changing `rend` token has a role of its own, and a highlight with several tokens nests them in order. Layout and reading tokens (`centered`, `align-right`, `ketiv-only`, `qeri-only`) have none. |
| `styles.highlight_bold` | bold | Text the source highlights in bold (`rend="bold"`). |
| `styles.highlight_small_caps` | small-caps | Text the source sets in small capitals (`rend="small-caps"`). |
| `styles.highlight_superscript` | inherits | Text the source raises above the line (`rend` `sup`, `superscript`, `raised` or `suspended`). It is always raised and reduced; the style sets its face and size. |
| `styles.highlight_large` | `x-large` | Text the source sets larger (`rend="large"`). |
| `styles.highlight_small` | `small` | Text the source sets smaller (`rend="small"`). |
| `styles.foreign` | inherits | A phrase in another language than the text around it (`tei:foreign`), such as Hebrew quoted in English. Its script's font is selected either way. |
| `styles.reference` | inherits | The words of a reference or link (`tei:ref`). A page reference's text is generated and does not take it. |
| `styles.poetry_line` | inherits | A line of poetry (`tei:l`). |
| `styles.list_item` | inherits | The text of an item in a list. See [`lists`](#lists) for its indent. |
| `styles.abbreviation` | inherits | An abbreviation, where `readings.abbreviations` reads them as printed. |
| `styles.expansion` | inherits | An abbreviation's expansion, where `readings.abbreviations` reads them expanded. |
| `styles.printed_error` | inherits | A misprint as printed, where `readings.errors` reads them so. |
| `styles.correction` | inherits | A misprint's correction, where `readings.errors` reads them corrected (the default). |
| `styles.qere` | italic | The qere: a word as it is read, where that differs from how it is written. |
| `styles.ketiv` | inherits | The ketiv: a word as it is written, in parentheses after the qere when both are given. |
| `styles.alternative_reading` | inherits | A second or later wording, in parentheses after the first, where a text gives more than one (`j:option`). |

## `line_numbers`

Marginal line numbers, as a critical edition uses to cite a passage.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `line_numbers.enabled` | boolean | `true` | When false no number is printed. The numbering machinery still runs, so cross-references and the apparatus are unaffected. |
| `line_numbers.unit` | `page` \| `section` | `page` | What numbering restarts at. |
| `line_numbers.increment` | integer ≥ 1 | `5` | Print a number every nth line. |
| `line_numbers.first` | integer ≥ 1 | `5` | The first line number printed, so the numbers run 5, 10, 15 rather than 1, 5, 10. |
| `line_numbers.margin` | `inner` \| `outer` \| `left` \| `right` | `outer` | `inner`/`outer` are relative to the binding; `left`/`right` are fixed. The default applies to every layout, a single text included. In a `pairs` parallel layout each column takes the nearer outer margin regardless, since the alternative is numbers in the gutter between the columns. In an `interleaved` layout both texts are numbered in the one margin chosen here, whichever direction each runs in. |
| `line_numbers.separation` | length | `1em` | Space between the number and the text block. |
| `line_numbers.numerals` | `arabic` \| `hebrew` | `arabic` | Arabic numerals with no `styles.line_number` are set in the face of the text they number; a style sets them in the Latin face. |

## `notes`

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `notes.placement` | `footnote` \| `endnote` \| `none` | `footnote` | Where the text of a note is printed. `none` drops notes entirely, anchor and all, and is an error if a note style is also set — the two cannot both hold and the one that silently wins deletes the notes. |
| `notes.anchor` | `interlinear` \| `superscript` \| `inline` | `interlinear` | How the mark that points at a note is set. `interlinear` raises it above the line and gives it no width, so the text it annotates is not respaced — which is what keeps two columns of a parallel text aligned. |
| `notes.mark` | `numeric` \| `alpha` \| `roman` \| `symbol` | `numeric` | The series marks are drawn from. The symbol series has six members and repeats the symbol past the sixth, as a printed apparatus does. |

There is deliberately no setting for showing the *lemma* — the words a note is attached to,
repeated where the note is printed. A note anchors at a point rather than over a range, so
there are no such words: the apparatus entry's lemma is the mark itself, and printing it would
give "∗ ] ∗ the note text".

## `markers`

The small marks that structure a text without being part of it.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `markers.section_separator` | text | `* * * *` | Printed between sections that carry no heading. An empty string leaves nothing but the space. |
| `markers.verse_numbers` | `shown` \| `hidden` | `shown` | |
| `markers.chapter_numbers` | `shown` \| `hidden` | `shown` | |

### `markers.conditional`

Only conditions the compiler could not decide survive into the output, so a marker means "say
this only if …", and the reader has to be able to see where the passage starts and stops.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `markers.conditional.inline_open` | text | `[` | Opens a conditional run inside a paragraph. |
| `markers.conditional.inline_close` | text | `]` | Closes it. |
| `markers.conditional.block` | `rule` \| `brackets` \| `none` | `rule` | How a whole conditional paragraph is delimited. Brackets several lines apart do not read as a pair, hence the rule. |
| `markers.conditional.rule_width` | percentage | `25%` | Width of the rule, as a percentage of the measure. |
| `markers.conditional.rule_thickness` | length | `0.4pt` | |

## `lists`

A labelled list sets out alternatives among the paragraphs of a prose passage — Birnbaum's
introduction compares his new translation against the old one this way. The label is styled by
[`styles.list_label`](#roles); this is how the item under it is set off from the prose around
it.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `lists.item_indent` | length | `2em` | Indent applied to both margins of an item's paragraphs, so the item reads as a block of its own. `0pt` sets items flush with the surrounding text and leaves the label alone to distinguish them. |

The indent is measured against the column, not the page, so an item inside a parallel block is
indented within its own column. In the `interleaved` layout it adds to the translation's own
indent.

## `parallel`

The geometry of a parallel-text layout.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `parallel.layout` | `pairs` \| `pages` \| `interleaved` | `pairs` | `pairs` puts two columns on the same page; `pages` sets the texts on facing pages, which gives each a full measure and suits a long work; `interleaved` sets one column, each block followed by its translation, for a measure too narrow to split. |
| `parallel.column_width` | percentage | `43%` | Width of each column as a percentage of the text block. Only in `pairs` layout; naming it under another is an error. The two columns and the gap share 100%, so it must be under 50%, and well under — the remainder leaves the outer margins room for line numbers. |
| `parallel.column_position` | `left` \| `center` \| `right` | `center` | Where the pair of columns sits in the text block. Only in `pairs` layout; naming it under another is an error. |
| `parallel.interleaved` | table | | How the translation is set apart, in `interleaved` layout. See [below](#interleaved). |
| `parallel.interleaved.translation_size` | size | `small` | Font size of the translation. |
| `parallel.interleaved.translation_indent` | length | `1em` | Indent applied to both margins of the translation's paragraphs. `0pt` sets it to the full measure. |
| `parallel.interleaved.spacing` | length | `0.25em` | Vertical space between a block and its translation. The space between one pair and the next is `paragraphs.spacing`, so keeping this smaller is what makes each original and its translation read as a pair. |
| `parallel.interleaved.line_numbers` | `primary` \| `both` | `primary` | `primary` numbers only the primary text's lines, so a line number cites the text being translated; `both` counts every line in one series. |

**Which text goes on which side is not set here.** It is `parallel.column_order` in the
compiler section of the settings file. `primary_first` puts the primary stream first, in the
left column or, on facing pages, on the verso. `primary_last` swaps them. The order is set there because the compiler is what decides the order the streams are
emitted in. In the `interleaved` layout the same setting decides which text comes first.

**A passage with no counterpart is set across the whole page.** Where an aligned unit has text
in one language only, there is nothing for the other column to face, so the columns stop, the
passage is set at the full measure in its own language, and the columns resume at the next unit
both languages set. A side holding only apparatus (an empty correspondence anchor, a
reference marker, or a note on the other text) does not count as a translation: its notes are
set with the text they annotate. In `pages` layout, each return to the columns starts a new
spread.

### Facing pages

`layout: pages` sets the first text on a verso and the second on the recto facing it,
each with the full measure. Every aligned unit starts at the same height on both pages: where
one side runs longer, the other is left blank alongside it until both are done, a page at a
time if need be. Each run of parallel text starts on a fresh spread, so a recto left over
before it is left blank — with no running head.

Which physical side the verso is on depends on [`page.binding`](#page). A book bound on the
right (the default, as for a Hebrew book) has its verso on the right of the spread, and the
reader meets that page first. So with `parallel.column_order: primary_first` and Hebrew as
the primary text, the Hebrew is on the right-hand page. Under `binding: left` the verso is on
the left, and the same order puts the Hebrew there.

Line numbers go in each page's outer margin, whichever language the page is in. Under a right
binding that is the right of a verso and the left of a recto.

Headings are set on the pages themselves, never across the spread; see
[`headings`](#headings). A running head names a page's own text with `{section-title}` on
the verso and `{section-title-alt}` on the recto; see [running heads](#page_header-and-page_footer).

### `interleaved`

```yaml
typography:
  parallel:
    layout: interleaved
    interleaved:
      translation_size: small
      translation_indent: 1em
      spacing: 0.25em
      line_numbers: primary
```

Each block the compiler aligns — the unit a column layout sets side by side — is followed by
its translation: original, translation, next original. The translation is set apart by its
size and indent, and by `spacing`, which is smaller than the space between one pair and the
next. A Hebrew original and an English translation change direction from one paragraph to the
next; line numbers stay in the one margin `line_numbers.margin` names for both.

Headings, rubrics, bookmarks and running heads behave as they do in columns, with "first
column" meaning the text that comes first. A heading that opens a block is still set once
above it under `headings.from: combined`, `instructions.from: combined` drops a rubric from the
translation where the original already says it, and `{head1-alt}` and the other `-alt` running
heads name the text that comes second. `column_width` and `column_position` do not apply.

## `table_of_contents`

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `table_of_contents.enabled` | boolean | `false` | Print a table of contents. |
| `table_of_contents.depth` | integer 1–4 | `4` | Heading levels shown. Independent of the PDF bookmark depth, which is always four levels deep. |

## `bookmarks`

The PDF outline of a work that names a section in two languages — a division carrying two
`tei:head`, or two projects compiled in parallel. One setting governs both, because to a
reader they are the same question asked twice.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `bookmarks.from` | `combined` \| `primary` \| `alt` | `combined` | Which title an outline entry carries. `combined` joins both with a middle dot; `primary` takes the first column's title, or the division's first head; `alt` takes the other — the facing column where there is one, otherwise the division's second head. |

Depth is not settable here: the outline is always four levels deep. `table_of_contents.depth`
governs the printed table only.

This is the one default that does **not** reproduce earlier output. Before it, both columns
of a parallel compile wrote to the outline, so every heading appeared twice and out of
document order. Set `from: primary` for one title per entry.

## `headings`

The heading a section carries **on the page**, where a work titles it twice — the same
question [`bookmarks`](#bookmarks) asks of the outline, so it takes the same vocabulary.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `headings.from` | `combined` \| `primary` \| `alt` \| `both` | `combined` | Which heading a section carries. The first three set **one** heading, spanning the page above both columns; `both` sets one in each column. |

| Value | What is set |
| --- | --- |
| `combined` | One heading, spanning. Both titles where the columns differ, the second beneath the first as a translation of it; one title where they agree. |
| `primary` | The first column's title, spanning. |
| `alt` | The other column's title, spanning. |
| `both` | Each column keeps its own heading, inside its own column. Nothing is deduplicated and nothing spans. |

**A heading that is set once spans the page.** It is not a heading of either column: it
names the section, and the section spans the opening. Setting it inside a column would
centre it over half the page. Only `both` keeps a heading in a column, because then there
really are two and each belongs to the column whose language it is in.

Spanning is possible only where a parallel block **opens** with the heading — there is no
interrupting a `\Pages` once begun — so a heading further into a block stays where it is,
deduplicated but not spanning.

**Facing pages span nothing.** Two pages have no measure in common, and a heading set before
the spread would be left on a page of its own. Each page sets its own heading instead:
`combined` sets it on both pages even where the titles agree, since the reader cannot take
it from across the opening the way they can from the next column; `primary` and `alt` set it
on the one page they name, and `both` on both.

`bookmarks` has no `both`: an outline entry is one line and cannot show two titles in two
places. A page can, which is why this setting has a value that one does not.

A suppressed heading still keeps its paragraph and its running-head mark: reledpar pairs
the columns by counting them, and a page style should still be able to name either
language. In the `interleaved` layout there is nothing to pair, so only the mark is kept.

## `instructions`

The rubric a passage carries, where a work prints it in both columns — [`headings`](#headings)'
question asked of a rubric, with the same vocabulary.

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `instructions.from` | `combined` \| `primary` \| `alt` \| `both` | `both` | Which column's rubric is set. `combined` sets one where the two columns give it in the same words and both where they differ; `primary` and `alt` set the one named whether or not they differ; `both` keeps each column's. |

> **Anything but `both` requires that every rubric fall on an alignment boundary.**
> Read the rest of this section before setting it.

**A rubric is not hoisted the way a heading is.** A heading is lifted out of the columns and
set across the page; a rubric cannot be, because it stands mid-flow and a parallel block
cannot be interrupted partway through. So the rubric that is kept stays *in its column* —
the primary one under `combined` and `primary`.

That is only readable where the two columns are aligned at the rubric's own position. Where
they are, a reader of either column sees it on the row it governs. Where they are not, the
column that gave up its copy has no rubric anywhere near the passage the rubric is about,
and a reader of that column simply loses it. The Birnbaum siddur is the worked example:
its rubrics sit mid-passage rather than at paragraph boundaries, so it sets
`instructions.from: both`.

**`both` has no such requirement, and is the default** — the one setting in this document
whose default is the conservative value rather than the tidy one, because getting it wrong
loses a rubric rather than merely repeating one. Set `combined` where a document's rubrics
are known to sit at alignment boundaries.

[`headings`](#headings) defaults the other way, and the asymmetry is deliberate: a heading
is lifted clear of the columns and set across the page, so deduplicating one costs nothing.

Rubrics are matched by count, not position: the *n*th rubric saying this in one column is
echoed if the other says it *n* times or more. Position does not survive contact with a real
document, where one column routinely carries rubrics the other has none of. A rubric the
other column does not have, or has fewer of, is always kept.

## `page_header` and `page_footer`

Running heads and feet. `page_header` defaults to the current section title on the inner edge
and the page number on the outer — the marks it reads are recorded at every heading whether or
not anything asks for them, so this costs nothing a document was not already paying. Write
`page_header: {}` for no head at all. `page_footer` is empty unless asked for.

Each takes either `all` — the same content on every page — or `odd` and/or `even` to
differentiate them; combining `all` with either is an error.

```yaml
typography:
  page_header:
    odd:
      left: "{book-title}"                                    # bare string = just text
      right: {text: "Page {page}", language: en}
    even:
      left: {text: "{page-hebrew}", language: he}
      center: {text: "Chapter {chapter-number}", language: en, if: "{chapter-number}"}
  page_footer:
    all:
      center: "{page}"
```

`left`, `center` and `right` are *physical* positions on the page, not logical ones: `left` is
the left edge whichever way the text runs. Each is either a bare string or a mapping with:

- `text` — the template.
- `language` — the slot's base direction, which decides the order its runs are laid out in,
  and the font for content that declares nothing else. A language tag, as in `xml:lang`
  (`he`, `en-US`, `he-Latn`); anything else is an error. Defaults to the document's own
  `xml:lang`; only the Hebrew script versus everything else is distinguished. A script subtag
  decides (`he-Latn` is a transliteration, `arc-Hebr` Aramaic in Hebrew letters); without one,
  `he`, `yi` and `arc` are Hebrew script. Every run
  carries its own direction inside that, so a mixed title like "רות RUTH" reads correctly in a
  slot of either direction and digits are never reversed.
- `if` — a second template. When it expands to nothing the whole position is dropped, literal
  text included, so `"Chapter {chapter-number}"` leaves no orphaned "Chapter" on a page before
  the first chapter.

Anything outside braces is literal text; `{{` and `}}` are literal braces. The codes are a
closed list, and an unrecognized one is a settings error:

| Code | Expands to |
| --- | --- |
| `{page}` | the page number as the document numbers it (roman in front matter) |
| `{page-hebrew}` | the page number in Hebrew numerals |
| `{document-title}` | the title from the TEI header, fixed for the whole document |
| `{book-title}` | the head of the enclosing `tei:div[@type='book']` |
| `{chapter-number}` | the `n` of the last `tei:milestone[@unit='chapter']` |
| `{chapter-number-hebrew}` | the same, in Hebrew numerals |
| `{head1}` … `{head4}` | the last heading at that level |
| `{section-title}` | the last heading at any level |
| `{book-title-alt}`, `{head1-alt}` … `{head4-alt}`, `{section-title-alt}` | the same, from the *second* parallel column — in the `interleaved` layout, the text that comes second |

Everything but `{page}`, `{page-hebrew}` and `{document-title}` names whatever was in force at
the *end* of the page, so a heading starting partway down a page names that page. The `-alt`
codes are what let a running head name the second language of a parallel volume; in a
non-parallel document they expand to nothing. On facing pages only the verso records the plain
codes and only the recto the `-alt` ones, so a verso heads its own text with
`{section-title}` and a recto with `{section-title-alt}`; the other code on either page names
whatever the facing side last set, which may be a page or more behind.

Title pages never carry a running head or foot, nor do the blank pages inserted to keep a
title page on a recto.

## How this reaches the renderer

The electronic book (`opensiddur/exporter/html/`) reflows. These settings reach its
HTML, CSS, and reader controls:

| Setting | HTML behavior |
|---|---|
| `fonts` | Latin, Hebrew and custom families become CSS font stacks. Per-face `normal_size` supplies the normal size for that family. The hosted Builder embeds installed faces in both previews and downloaded HTML books, including custom families, and uses the first embedded face's size. A standalone exporter names fonts for the reader's device to supply. |
| `page.base_font_size` | Supplies the normal size for a family without an explicit `normal_size`. |
| `styles` | Every text role except `line_number` has an HTML selector. Font, size, weight, italic style, small caps, alignment and applicable vertical spacing are emitted. Named sizes scale with the chosen family's normal size. Absolute sizes remain exact across language changes. |
| `paragraphs` | Indent, spacing, line spacing and alignment apply to running text. |
| `lists.item_indent` | Applies to both margins of list items. |
| `markers` | Verse/chapter visibility, section separators, conditional brackets and rule dimensions apply. |
| `notes` | Numeric, alphabetic, Roman and symbol marks apply, as do inline, superscript and interlinear anchors. `placement: none` omits notes. Both physical-page placements use accessible popovers on screen. |
| `parallel` | Wide-screen pairs use the configured column width and position. Interleaved output uses its translation size, indent and spacing. Narrow screens and the reader's one-column choice continue to reflow. Facing-page layout uses responsive columns on screen. |
| `table_of_contents.depth` | Limits the reader's Contents dialog to the configured heading depth, including level four. |

English inside a Hebrew work resets to the Latin family. Hebrew transliteration
tagged `he-Latn` also uses Latin. Repeated language tags do not multiply font
sizes. Explicit role font overrides are inherited within that role.

Paper dimensions, binding, margins, page numbering, running heads/feet, marginal
line numbering and the PDF outline have physical-page meanings. They do not
change the reflowing book. The printed table-of-contents `enabled` switch does
not remove the reader's Contents control. `headings.from` and `instructions.from`
govern print deduplication; the HTML reader retains both streams and lets the
reader choose which columns to display. Interleaved line numbering likewise
belongs to print.

`html/css.py` translates visual settings and `html.xslt` renders text roles and
note marks. The reader applies the contents depth at runtime.

`opensiddur/exporter/typography.py` holds the models above and knows nothing about any
renderer. `opensiddur/exporter/tex/typography_tex.py` turns a validated settings tree into a
block of LuaLaTeX, which `tex/reledmac.xslt` emits before `\begin{document}`. **The models are
the only place a default is stated.** Every setting is emitted at its resolved value, whether
the file wrote it or not, and the stylesheet defines none of the macros or lengths a setting
controls; the electronic book's `html/css.py` likewise writes every value its stylesheet
uses. So the defaults in the tables above are the ones a book is printed with.

Adding a setting means adding a field to the model, a case to the emitter, a row to this
document, and a test. `opensiddur/tests/exporter/test_typography_doc.py` fails if the row is
missing, and `test_typography_defaults.py` fails if its default is not the model's or does not
reach the stylesheet.
