<?xml version="1.0" encoding="UTF-8"?>
<!--
  Reledmac/Reledpar LuaLaTeX exporter for compiled JLPTEI XML.

  Layout strategy
  ===============
  Each "stream" of body content lives inside one
  `\beginnumbering`...`\endnumbering` block so that `\pstart`/`\pend` and
  `\edtext` work end-to-end. A stream is flattened into a sequence of "leaf"
  nodes (text, milestones, and non-block inline elements) and then walked with
  `xsl:iterate` to emit `\pstart`/`\pend` pairs per verse. Chapter milestones
  break out of the current `\pstart` to emit `\eledsection{N}` headings between
  verses. Editorial notes in the body become reledmac apparatus footnotes (`\Bfootnote` for editorial
  notes) with interlinear serial marks (`\OSInterlinearNotemark`) matching the
  apparatus prefix (`\OSFootnotemark`). The compiler materializes stand-off notes
  into the body; this stylesheet does not resolve `tei:standOff` or `tei:anchor`
  targets into apparatus. Instructional notes are rendered inline via a dedicated macro so they
  can be styled independently without entering the apparatus.

  Parallel mode wraps two such streams in `\begin{pages}` / `\Pages` (facing
  pages) or `\begin{pairs}` / `\Columns` (two columns on one page); the Nth
  `\pstart` on each side is paired by reledpar, giving verse-level alignment
  across page breaks.

  Typography settings (font, paper, layout, font size) are passed in as XSLT
  parameters so that `settings.yaml` can drive them at compile time.
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
    xmlns:p="http://jewishliturgy.org/ns/processing"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:f="urn:opensiddur:reledmac"
    exclude-result-prefixes="tei j p xs f">

    <xsl:output method="text" encoding="UTF-8" omit-xml-declaration="yes" indent="no"/>

    <xsl:include href="common.xsl"/>

    <!-- Optional pre-built additions to the preamble/postamble (license/bib/credits) -->
    <xsl:param name="additional-preamble" as="xs:string?"/>
    <xsl:param name="additional-postamble" as="xs:string?"/>
    <!-- The distribution notice, set on the verso of the title page, and the statement on
         the book's last page, after the colophon: both pre-built by tex/latex.py from the
         settings' `distribution` section, and empty when the book carries none. -->
    <xsl:param name="distribution-notice" as="xs:string" select="''"/>
    <xsl:param name="back-notice" as="xs:string" select="''"/>

    <!-- Typography (driven by settings.yaml `typography` section).

         This stylesheet holds no typography default of its own: every setting,
         whether a settings file wrote it or not, arrives resolved from
         opensiddur/exporter/typography.py, through tex/latex.py's
         typography_parameters. Hence `required`: a caller that forgets one gets an
         error rather than an appearance nobody chose. The settings reach it as

           $documentclass-options   the handful of things the class has to be
                                    told when it is loaded (base font size,
                                    paper, one- or two-sided);
           $typography-preamble     the definition of every macro and length a
                                    setting controls, built by
                                    tex/typography_tex.py;

         and, for the settings that change the *structure* of the emitted document
         rather than its appearance, a parameter each, below. -->
    <xsl:param name="documentclass-options" as="xs:string" required="yes"/>
    <xsl:param name="typography-preamble" as="xs:string" required="yes"/>
    <!-- pages | pairs | interleaved. The first two set a parallel text with reledpar, on
         facing pages or in columns; interleaved sets it in one reledmac stream, each
         block followed by its translation. -->
    <xsl:param name="layout" as="xs:string" required="yes"/>
    <xsl:variable name="interleaved" as="xs:boolean" select="$layout = 'interleaved'"/>
    <xsl:variable name="facing-pages" as="xs:boolean" select="$layout = 'pages'"/>
    <!-- footnote | endnote | none — where the text of an editorial note goes.
         `none` drops notes entirely, anchor and all. -->
    <xsl:param name="notes-placement" as="xs:string" required="yes"/>
    <!-- numeric | alpha | roman | symbol — the series note marks are drawn
         from. The serial is known here, so the conversion is done here. -->
    <xsl:param name="notes-mark" as="xs:string" required="yes"/>

    <!-- Auto-generated table of contents (driven by settings.yaml
         `typography.table_of_contents`). Depth is independent of the PDF
         bookmark depth below, which is always 4 levels deep. -->
    <xsl:param name="table-of-contents" as="xs:boolean" required="yes"/>
    <xsl:param name="table-of-contents-depth" as="xs:integer" required="yes"/>

    <!-- Running heads and feet: a complete fancyhdr block built by
         opensiddur/exporter/tex/running_heads.py from the settings.yaml
         `typography.page_header`/`page_footer` sections. Empty when both are
         empty, which leaves the book class's own page style alone. The mark
         classes it reads are declared and inserted by this stylesheet. -->
    <xsl:param name="page-style-preamble" as="xs:string" required="yes"/>

    <!-- How many parallel blocks one \Pages/\Columns typesets at a time. reledpar holds
         every chunk of a group in memory as a pair of boxes and refuses more than
         \maxchunks (5120) of them, so a whole humash — ~49000 blocks — cannot be one
         group: it dies with "Too many \pstart without printing". Batching bounds the
         memory and the chunk count. Alignment is unaffected, since both sides are cut at
         the same block boundaries; the visible cost is that \Pages starts a fresh page
         pair at each batch, which \Columns (layout=pairs) does not. -->
    <xsl:param name="parallel-batch-size" as="xs:integer" select="500"/>
    <!-- Which language a PDF bookmark carries where a work names a section twice:
         'combined' joins the two titles, 'primary' takes the first column's or the
         division's first head, 'alt' takes the other. See typography.bookmarks.from. -->
    <xsl:param name="bookmarks-from" as="xs:string" required="yes"/>
    <!-- Which column's heading is set on the page where a work titles a section twice.
         'combined' prints one heading where the two columns agree and both where they do
         not; 'primary' and 'alt' always print the one named. Same vocabulary as
         bookmarks-from, and for the same reason: it is the same question about the same
         pair of titles, asked of the page rather than of the outline.
         See typography.headings.from. -->
    <xsl:param name="headings-from" as="xs:string" required="yes"/>
    <!-- The same question asked of a rubric rather than a heading. A rubric is never
         hoisted out of the columns: it stands mid-flow, and a parallel block cannot be
         interrupted partway through, so the one that is kept stays in its column.

         Anything but 'both' therefore requires that every rubric fall on an alignment
         boundary. Where it does not, the column that gave up its copy has no rubric near
         the passage it is about, and a reader of that column loses it — which is why
         'both' is typography.py's default where 'combined' is a heading's. See
         typography.instructions.from, which says so at more length. -->
    <xsl:param name="instructions-from" as="xs:string" required="yes"/>

    <!-- ====================================================================
         Document scaffolding
         ==================================================================== -->

    <xsl:template match="/">
        <xsl:variable name="root-lang" select="string(tei:TEI/@xml:lang)"/>
        <xsl:variable name="has-parallel" select="exists(//p:parallel)"/>
        <!-- Whether the parallel text is set by reledpar. Everything declared under this
             exists only once reledpar is loaded, so an interleaved compile, which does
             not load it, must not see any of it. -->
        <xsl:variable name="uses-reledpar" select="$has-parallel and not($interleaved)"/>

        <xsl:text>\documentclass[</xsl:text>
        <xsl:value-of select="$documentclass-options"/>
        <xsl:text>]{book}&#10;</xsl:text>

        <xsl:text>\usepackage{geometry}&#10;</xsl:text>
        <xsl:text>\usepackage{fontspec}&#10;</xsl:text>
        <xsl:text>\usepackage{polyglossia}&#10;</xsl:text>
        <xsl:text>\setdefaultlanguage{english}&#10;</xsl:text>
        <xsl:text>\setotherlanguage{hebrew}&#10;</xsl:text>

        <!-- The faces, \hebrewfont included, are declared by $typography-preamble. -->

        <!-- reledmac/reledpar provide critical-edition apparatus and parallel-stream
             synchronization. Series A/B/C/D/E are predefined; we use:
               A = textual apparatus (reserved, currently unused)
               B = editorial notes / commentary -->
        <xsl:text>\usepackage{reledmac}&#10;</xsl:text>
        <xsl:if test="$uses-reledpar">
            <xsl:text>\usepackage{reledpar}&#10;</xsl:text>
        </xsl:if>
        <!-- \Pages starts every spread on a verso, inserting a blank recto where the text
             before it ended on one. reledpar sets that filler in \prevpgstyle when it is
             defined, and otherwise in the current style, running head and all: a wholly
             blank page that names a section. -->
        <xsl:if test="$has-parallel and $facing-pages">
            <xsl:text>\def\prevpgstyle{empty}&#10;</xsl:text>
        </xsl:if>
        <!-- Use BibTeX as backend for portability; biber can be unavailable or
             misconfigured on some systems. -->
        <xsl:text>\usepackage[backend=bibtex]{biblatex}&#10;</xsl:text>
        <!-- xurl must follow biblatex so its URL/eprint letter and digit break
             penalties are enabled; Archive identifiers can exceed a full line. -->
        <xsl:text>\usepackage{xurl}&#10;</xsl:text>
        <!-- For the logo in the distribution notice. -->
        <xsl:text>\usepackage{graphicx}&#10;</xsl:text>
        <xsl:text>\usepackage{hyperref}&#10;</xsl:text>
        <!-- Headings go four deep (index > section > haftarah > rite), and f:heading-toc-level
             emits the fourth as \addcontentsline{toc}{paragraph}. The book class stops the
             table of contents at subsection, and hyperref takes its bookmark depth from that,
             so without this the deeper levels are silently missing from the PDF outline. -->
        <xsl:text>\setcounter{tocdepth}{4}&#10;</xsl:text>
        <xsl:text>\hypersetup{bookmarksdepth=4}&#10;</xsl:text>
        <!-- hyperref builds PDF strings for bookmarks/outlines.  Direction and
             language switches (luabidi/polyglossia) are not representable in
             PDF strings and generate warnings (and sometimes broken outlines).
             Disable them *only* for PDF-string construction. -->
        <xsl:text>\pdfstringdefDisableCommands{&#10;</xsl:text>
        <!-- A direction is three letter tokens, not one: \textdir TLT. Gobbling a single
             argument eats only the T and leaves "LT" glued to the front of the title, so
             every non-Hebrew bookmark reads "LTShabbat Shekalim". -->
        <xsl:text>  \def\textdir#1#2#3{}&#10;</xsl:text>
        <xsl:text>  \def\selectlanguage#1{}&#10;</xsl:text>
        <!-- Two arguments, and the title is the second: \def\foreignlanguage#1#2{#1}
             would put the language name in the bookmark and throw the title away. -->
        <xsl:text>  \def\foreignlanguage#1#2{#2}&#10;</xsl:text>
        <!-- Hebrew runs in a contents entry are wrapped for the typeset table of
             contents (see f:format-section-title); the outline wants the text alone. -->
        <xsl:text>  \def\texthebrew#1{#1}&#10;</xsl:text>
        <xsl:text>}&#10;</xsl:text>

        <!-- ================================================================
             Running heads and feet.

             Every heading and chapter milestone records itself in a LaTeX mark
             class, so a page style can ask what was in force on the page it is
             typesetting. Marks inserted inside a reledmac \pstart do reach the
             output routine, in single-text numbering and inside reledpar's
             \Columns alike, so no aux-file round trip is needed.

             The `Alt` classes carry the *second* parallel stream. Without them
             only the first column's headings could ever reach a running head,
             which would make an English running head impossible on a
             Hebrew-primary parallel volume.

             The classes are declared unconditionally — they cost nothing when
             no running head is configured, and it keeps the preamble
             deterministic.
             ================================================================ -->
        <xsl:text>\NewMarkClass{OSheadA}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadB}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadC}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadD}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadAny}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSbook}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSchapter}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadAAlt}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadBAlt}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadCAlt}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadDAlt}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSheadAnyAlt}&#10;</xsl:text>
        <xsl:text>\NewMarkClass{OSbookAlt}&#10;</xsl:text>

        <!-- The document's own title, for the {document-title} code. The TEI
             header is dropped from the output but can still be read here.
             Per-run direction, like the marks: the slot it lands in may run
             either way. -->
        <xsl:text>\newcommand{\OSDocumentTitle}{</xsl:text>
        <xsl:value-of select="f:emit-bidi-mark(normalize-space(string-join((
            /tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title[@type='main'][1],
            //tei:titlePage//tei:titlePart[@type='main'][1])[1]//text()[not(ancestor::tei:note)], '')))"/>
        <xsl:text>}&#10;</xsl:text>

        <xsl:text>\makeatletter&#10;</xsl:text>
        <!-- Render #2 only when #1 expands to something. A slot whose marks are
             not yet set then disappears entirely, literal text included, so
             "Chapter {chapter-number}" leaves no orphaned "Chapter" on a page
             before the first chapter. -->
        <xsl:text>\newcommand{\OSHFIfNonEmpty}[2]{%&#10;</xsl:text>
        <xsl:text>  \protected@edef\OSHF@test{#1}%&#10;</xsl:text>
        <xsl:text>  \ifx\OSHF@test\@empty\else#2\fi}&#10;</xsl:text>
        <!-- Hebrew numerals for a value that is only known at shipout (a chapter
             mark). polyglossia's \hebrewnumeral requires an integer, so anything
             else is passed through unchanged. The test is a Lua pattern using
             [0-9] rather than %d: a percent sign would be a TeX comment and
             would swallow the rest of the chunk. -->
        <xsl:text>\newcommand{\OSHebrewNumber}[1]{%&#10;</xsl:text>
        <xsl:text>  \edef\OSHF@num{#1}%&#10;</xsl:text>
        <xsl:text>  \directlua{&#10;</xsl:text>
        <xsl:text>    local s = "\luaescapestring{\OSHF@num}"&#10;</xsl:text>
        <xsl:text>    if s:match("^[0-9]+$") then tex.sprint("\string\\hebrewnumeral{" .. s .. "}") else tex.sprint(s) end&#10;</xsl:text>
        <xsl:text>  }}&#10;</xsl:text>
        <xsl:text>\makeatother&#10;</xsl:text>

        <!-- fancyhdr must load after hyperref. Empty unless the settings file
             configures a running head or foot. -->
        <xsl:value-of select="$page-style-preamble"/>

        <!-- Everything a typography setting controls is defined in $typography-preamble
             (tex/typography_tex.py), at the value typography.py resolves: the faces, the
             paragraph lengths, every role's macro (\vno, \chno, \OScitation, \OSaliyah,
             \OSParsha, \OSheadA-D, \OSheadTranslation, the title-page macros,
             \instructionnote, \notenote, \OSSectionSeparatorStyle, \OSListLabelStyle, and
             the inline roles' macros listed in typography_tex.INLINE_ROLE_MACROS), the
             note marks, the conditional markers, the line numbering, the column geometry
             and the interleaved layout's macros. None of them has a copy here, so there is
             nothing for the two to disagree about.

             Callers who want a treatment no setting gives redefine the macro through the
             additional-preamble parameter, which follows the typography block. For an
             apparatus entry instead of a visible parsha header, for instance:

               \renewcommand{\OSParsha}[1]{\leavevmode{\OSRTLfalse%
                 \edtext{\mbox{}}{\Bfootnote{Parsha: #1}}}}

             (an empty-lemma \edtext{} is fragile in bidi/RTL contexts and can make
             reledmac drop surrounding text or corrupt its .1 aux file, hence the explicit
             zero-width \mbox{} lemma), or to suppress the boundary entirely:

               \renewcommand{\OSParsha}[1]{}

             Section headings (tei:head) are \OSheadA-D rather than reledmac's
             \eledchapter/\eledsection/\eledsubsection, which typeset their argument as
             ordinary inline text and defer the real heading to a later pass via an aux
             file keyed on the enclosing \pstart number, which is fragile and drags in
             book-class section numbering. The macros are plain paragraph content inside a
             \pstart \skipnumbering, so they are unnumbered, single-pass and fully under
             our control. -->

        <!-- Keeping a heading with what follows it (#198). A heading is a \pstart of its
             own, and nothing ties one \pstart to the next: the \vspace the next one opens
             with is a legal page break, so a heading could end a page. \OSKeepNext asks
             the next \pstart to open with \nobreak instead, which the \AtEveryPstart*
             hook below does with \OSApplyKeep.

             The penalty goes in the next \pstart's hook rather than straight after the
             heading's \pend because \pend leaves \write records for reledmac's line list
             on the page after the lines. A \nobreak ahead of them would keep nothing: the
             \vspace glue after them follows a whatsit, not a penalty, and can still
             break. In the hook it sits directly in front of that glue.

             \Columns runs the hook before the first row of a block too, so a heading set
             across the page above the columns stays with them the same way. -->
        <xsl:text>\newif\ifOSKeepNext&#10;</xsl:text>
        <xsl:text>\newcommand{\OSKeepNext}{\global\OSKeepNexttrue}&#10;</xsl:text>
        <!-- \OSKeepRow is the same for the first row of a \Columns block, which reledpar
             sets after records of its own; see column-keep-preamble. -->
        <xsl:text>\newcommand{\OSKeepRow}{}&#10;</xsl:text>
        <xsl:text>\newcommand{\OSApplyKeep}{\ifOSKeepNext\global\OSKeepNextfalse\nobreak\OSKeepRow\fi}&#10;</xsl:text>
        <!-- Inside a parallel column the heading and the paragraphs around it are all one
             \pstart, so the column's lines say for themselves what they are: a LuaTeX
             attribute on what a line contains, 1 on a heading's lines (title, translation
             or the placeholder for a title the other column sets), 2 on the blank line
             that separates two paragraphs. See column-keep-preamble, which reads them.
             An attribute rather than a \marks: a mark set in a line lands after the
             line's box, and reledpar takes each line back off its column with \lastbox,
             which then finds the mark instead and sets the line a row out of step.
             \OSKeepSep draws its strut as a rule of its own: \strut copies \strutbox,
             and a copy keeps the attributes it was made with, which are none. -->
        <xsl:text>\newattribute\OSKeepAttr&#10;</xsl:text>
        <xsl:text>\newcommand{\OSKeepHeadBegin}{\OSKeepAttr=1\relax}&#10;</xsl:text>
        <xsl:text>\newcommand{\OSKeepHeadEnd}{\unsetattribute\OSKeepAttr}&#10;</xsl:text>
        <xsl:text>\newcommand{\OSKeepSep}{\mbox{\OSKeepAttr=2\relax\vrule width 0pt height\ht\strutbox depth\dp\strutbox}}&#10;</xsl:text>

        <!-- One line of the imprint, inside \OSDocImprint. -->
        <xsl:text>\newcommand{\OSImprintLine}[1]{{\centering #1\par}}&#10;</xsl:text>

        <!-- Notes styling.
             - All notes must force direction/language using the xml:lang-derived wrappers
               emitted by note-content (\texthebrew{...} / \textenglish{...}).
             - Use {{\bfseries ...}} (regular braces) not \begingroup/\endgroup — the latter
               can prematurely close reledmac's internal groups inside \edtext/\Bfootnote. -->
        <!-- An instruction running against the direction of the text it introduces cannot
             share a line with it: the two runs would be laid out from opposite margins and
             read as one jumbled line. Birnbaum sets his English rubrics on their own line
             above the Hebrew, and this is that line. No box, though: a box of any fixed
             width overhangs a rubric wider than it, because an \hbox to \linewidth cannot
             break. \linewidth inside reledpar's parallel setting is the page rather than
             the column, so the box was twice the width it had to fit in and every long
             rubric ran off the paper in a two-column compile. A \parbox of the same width
             fixes only the first half of that. Ordinary text flow between two \newline
             fixes both: it is measured by whatever column it lands in, and it wraps. What
             it gives up is the flush margin the box provided, which is worth less than the
             words being on the page. -->
        <!-- The leading \strut is what keeps the break out of the facing column. Two of
             these in a row put two \newline together, and the empty line between them has
             no height; \Columns cuts each column into slices of \baselineskip, and a
             zero-height line leaves the glue before it inside its own slice rather than at
             the cut, whereupon reledpar \unvbox-es it onto the shared page list and both
             columns move. The \strut gives that line the height of ordinary text, so it
             becomes a row of this column alone. -->
        <!-- \ifhmode, not \leavevmode: end the line the rubric interrupts, but only when
             there is one. At the head of a \pstart nothing has been set yet, and breaking
             there spends a row on nothing. In a parallel compile that row is spent in one
             column alone — the facing column gives the same rubric run-in, because the
             rubric does not cross ITS direction — so the two copies of one rubric land on
             different rows and take four between them where two would do. -->
        <!-- The rubric's own lines are tagged (\OSKeepAttr 3) so that the page-break rules
             keep it with the text it introduces (#198); see keep-preamble. Only the rubric:
             the line ended before it and the \newline after it are not. -->
        <xsl:text>\newcommand{\OSInstructionBlock}[1]{\ifhmode\unskip\strut\newline\fi{\OSKeepAttr=3\relax\bfseries #1}\newline\ignorespaces}&#10;</xsl:text>
        <!-- The same, for an instruction standing inside a paragraph rather than between
             two. A box the width of the line does not fit on a line that is already
             partly set: it overhangs the margin and the instruction runs off the page,
             which is what happened to both seasonal readings of Birkat ha-Shanim and to
             the day-names of Ya'aleh v'Yavo. Ending the line first gives the instruction
             a line of its own, and ordinary text flow lets it wrap once it has one.

             Identical to \OSInstructionBlock now that neither boxes its argument. The two
             are kept apart because their call sites are: one interrupts a paragraph and
             one stands between paragraphs, and a style may yet want to tell them apart. -->
        <!-- The leading \strut is what keeps the break out of the facing column. Two of
             these in a row put two \newline together, and the empty line between them has
             no height; \Columns cuts each column into slices of \baselineskip, and a
             zero-height line leaves the glue before it inside its own slice rather than at
             the cut, whereupon reledpar \unvbox-es it onto the shared page list and both
             columns move. The \strut gives that line the height of ordinary text, so it
             becomes a row of this column alone. -->
        <!-- \ifhmode, not \leavevmode: end the line the rubric interrupts, but only when
             there is one. At the head of a \pstart nothing has been set yet, and breaking
             there spends a row on nothing. In a parallel compile that row is spent in one
             column alone — the facing column gives the same rubric run-in, because the
             rubric does not cross ITS direction — so the two copies of one rubric land on
             different rows and take four between them where two would do. -->
        <xsl:text>\newcommand{\OSInstructionLine}[1]{\ifhmode\unskip\strut\newline\fi{\OSKeepAttr=3\relax\bfseries #1}\newline\ignorespaces}&#10;</xsl:text>
        <!-- The measure of the current line, for a box as wide as the line it sits in,
             such as the conditional marker's rule (\OSCondRule).
             \hsize, not \linewidth, for the reason given above \OSInstructionBlock:
             reledpar sets \hsize to the column width inside a parallel column but leaves
             \linewidth at the page, so a \linewidth box is twice the width it has to fit
             in and the centred rule lands outside its own column.

             And less \leftskip and \rightskip, which narrow the lines of an indented
             paragraph — the interleaved layout's translation, a list item — but not
             \hsize: a box as wide as \hsize there overruns the right margin by the indent. -->
        <xsl:text>\newcommand{\OSMeasure}{\dimexpr\hsize-\leftskip-\rightskip\relax}&#10;</xsl:text>
        <!-- B-series apparatus: no line numbers; lemma text is not repeated in the
             footnote (\Xwraplemma[B]{\@gobble}) — only \OSFootnotemark + \notenote. -->
        <xsl:text>\Xnonumber[B]&#10;</xsl:text>
        <xsl:text>\Xnolemmaseparator[B]&#10;</xsl:text>
        <xsl:text>\Xinplaceofnumber[B]{0pt}&#10;</xsl:text>

        <!-- Line numbers must always be LTR, or an RTL context flips the digits and
             50 reads 05. The LEFT series needs nothing from us: reledmac's own \ledlinenum
             opens with \ifluatex\textdir TLT\fi, so the number is already set left to
             right whatever the column runs in.

             The right series is the asymmetric one — reledpar's \l@dlinenumR carries no
             such switch — which is why the typography preamble always redefines
             \linenumrepR and \sublinenumrepR.

             There was a \renewcommand*{\linenumberstyle} here, and it never did anything.
             \linenumberstyle is a declaration, not a formatter: its argument is a style
             NAME and its only job is to define \linenumrep, which reledmac does once as it
             loads. Redefining it afterwards is never consulted — and had anything called
             it the way reledmac does, it would have set the word "arabic" in the margin.
             reledpar's \linenumberstyle* (which forwards to both series) makes that a live
             trap rather than merely dead code, so it is gone. Settings that choose numerals
             write \linenumrep, the macro actually consulted; see tex/typography_tex.py.

             How lines are counted (\lineation, \linenummargin and the rest, and their
             reledpar R twins) is in the typography preamble too. -->
        <xsl:if test="$uses-reledpar">
            <xsl:if test="$layout = 'pairs'">
                <!-- In \Columns mode reledpar maps \begin{Leftside} to the physical LEFT column
                     and \begin{Rightside} to the physical RIGHT column (regardless of
                     column-order / which language is primary).  Line numbers must sit on the
                     outer page margins: left column → {left}, right column → {right}.  Using
                     {right} for the left column places numbers in the inter-column gap — and
                     for an RTL left column it is worse still, because the \rlap it selects
                     is mirrored too and the number lands inside the column, on the edge that
                     flush-right Hebrew occupies on every line. -->
                <xsl:text>\linenummarginColumns{left}&#10;</xsl:text>
                <xsl:text>\linenummarginColumnsR{right}&#10;</xsl:text>
                <!-- The columns' width and position are typography settings
                     (typography.parallel), in the typography preamble. -->
                <!-- Polyglossia Hebrew uses TRT; if \pardir stays RTL when \Columns runs,
                     LuaTeX lays out the two-column \hbox right-to-left and Leftside (Hebrew)
                     lands in the physical right column.  Force LTR for assembly only. -->
                <xsl:text>\let\OSreledparColumnsOrig\Columns&#10;</xsl:text>
                <xsl:text>\renewcommand{\Columns}{\begingroup\pardir TLT\relax\textdir TLT\relax\OSreledparColumnsOrig\endgroup}&#10;</xsl:text>
            </xsl:if>
            <xsl:if test="$facing-pages">
                <!-- The same fault on facing pages, where an LTR group around \Pages is not
                     enough: \Pages selects each page's language before setting its lines,
                     and a Hebrew page's rows are then built right to left. The left margin
                     is a row's right-hand end, and a Hebrew verso's line numbers — outer,
                     so left — were printed over the first word of their lines.

                     \ledstrutL and \ledstrutR are reledpar's hooks at the head of every row
                     \Pages builds, and only \Pages uses them. Turning the row's direction
                     there puts its margins back where they are on the page. Each line's own
                     text is unaffected: reledpar sets it in a box of its own, in the
                     direction recorded at its \pstart. -->
                <xsl:text>\renewcommand*{\ledstrutL}{\textdir TLT\relax}&#10;</xsl:text>
                <xsl:text>\renewcommand*{\ledstrutR}{\textdir TLT\relax}&#10;</xsl:text>
            </xsl:if>
        </xsl:if>
        <xsl:text>\makeatletter&#10;</xsl:text>
        <!-- reledmac repeats the \edtext lemma in the apparatus; our lemma is the raised
             \OSInterlinearNotemark. Gobble it for series B so apparatus shows only
             \OSFootnotemark + note text (no duplicate serial). -->
        <xsl:text>\Xwraplemma[B]{\@gobble}&#10;</xsl:text>
        <!-- reledmac/reledpar use @ in internal bidi helpers; expose a public wrapper
             so emitted document content doesn't depend on \makeatletter being in scope. -->
        <xsl:text>\newcommand*{\OSRTLfalse}{\@RTLfalse}&#10;</xsl:text>
        <!-- Lap the number outward whichever way the column runs.

             reledmac hangs the number off the measure with \llap (or \rlap), and a lap is
             built in horizontal mode, so it takes the prevailing \textdir. reledpar
             re-selects each column's own language, and with it its direction, around every
             line it sets — inside the \Columns wrapper above, which it therefore overrides.
             In the Hebrew column that mirrors the lap: instead of hanging \linenumsep to the
             left of the measure the number is planted \linenumsep INSIDE it, on top of the
             text, on every page. \ledlinenum already forces \textdir TLT, but that governs
             only the digits within the lap, not which way the lap itself grows.

             A box of zero width sits at the same place in either direction, so put the whole
             lap in one and give it an explicit direction. In an LTR column the result is
             what stock reledmac produced, to the point; measured, an English column does not
             move. reledmac does this for its own section titles and never for lines. -->
        <xsl:text>\renewcommand*{\leftlinenum}{\hbox dir TLT to \z@{\hss\ledlinenum\kern\linenumsep}}&#10;</xsl:text>
        <xsl:text>\renewcommand*{\rightlinenum}{\hbox dir TLT to \z@{\kern\linenumsep\ledlinenum\hss}}&#10;</xsl:text>
        <!-- The same fault one level up, in reledmac's own \print@line, which sets every
             line outside reledpar: the box it hangs the laps on is \linewidth wide and
             also takes the prevailing direction. In a Hebrew stream "left" is then the
             start of an RTL box, which is the right-hand edge, and the left lap planted
             there lands over the first word of every line. Give that box a fixed direction
             too. The line inside it is unaffected: reledmac sets it in a box of its own,
             in the direction recorded at its \pstart. So left and right, inner and outer,
             mean the same margin for a Hebrew line as for an English one, which is what
             lets the interleaved layout number both texts in one margin.

             reledpar sets its columns and pages with \print@lineL and \print@lineR,
             which this does not touch. -->
        <xsl:text>\patchcmd{\print@line}{\hb@xt@ \linewidth}{\hbox dir TLT to\linewidth}{}{\PackageError{opensiddur}{could not patch reledmac's print@line}{}}&#10;</xsl:text>
        <!-- An unnumbered line (\numberlinefalse) still advances the absolute line count
             and runs the actions queued for it, but reledmac writes its \@nl record to the
             line list only when the line is numbered. The records are what \lineation{page}
             reads page changes from, so every unnumbered line puts the page changes a line
             early, and numbering restarts partway down a page. Write the record for every
             line: an unnumbered line is still counted in no series and printed with no
             number, and the line list stays in step with the lines. -->
        <xsl:text>\patchcmd{\new@line}{\ifnumberline}{\iftrue}{}{\PackageError{opensiddur}{could not patch reledmac's new@line}{}}&#10;</xsl:text>
        <xsl:if test="$uses-reledpar">
            <xsl:text>\renewcommand*{\leftlinenumR}{\hbox dir TLT to \z@{\hss\l@dlinenumR\kern\linenumsep}}&#10;</xsl:text>
            <xsl:text>\renewcommand*{\rightlinenumR}{\hbox dir TLT to \z@{\kern\linenumsep\l@dlinenumR\hss}}&#10;</xsl:text>
            <!-- \setRlineflag is reledpar-only; it does not exist when reledpar is not
                 loaded. Empty flag: no "R" prefix on right-side line numbers. The spatial separation
                 of the two column margins already distinguishes left from right numbers. -->
            <xsl:text>\setRlineflag{}&#10;</xsl:text>
        </xsl:if>
        <xsl:text>\makeatother&#10;</xsl:text>

        <!-- Let a line be loose rather than long. A parallel column is around half the
             measure of a single-column page, and at that width TeX regularly finds no break
             it likes and sets an overfull line instead, which sticks out past the measure and
             into the margin the line numbers occupy. \emergencystretch buys it a further
             pass in which it may stretch the spaces instead. Loose word spacing is a
             blemish; a line lying under its own line number is a defect. -->
        <xsl:text>\setlength{\emergencystretch}{3em}&#10;</xsl:text>

        <!-- No widows and no orphans (#198): the first line of a paragraph never ends a
             page, and its last line never begins one. reledmac zeroes these inside a
             \pstart, but puts them back between a paragraph's lines itself when it sets
             them, reading whatever is in force at that point, so set globally they reach
             every numbered paragraph. LaTeX's 150 is a preference, not a rule. -->
        <xsl:text>\clubpenalty=10000 \widowpenalty=10000 &#10;</xsl:text>

        <!-- The space between one \pstart and the next. reledmac \pstart groups do not
             take \parskip between them, so without this there is no space between
             parallel blocks at all and what looks like separation is only the shorter
             column being padded out to the longer one.

             Starred: the unstarred \AtEveryPstart prefixes \noindent, which makes
             reledpar treat the material as column content and set it in a full-width
             two-\parbox row of its own, costing a whole line per \pstart. The starred
             form goes into the shared vertical list, which is what vertical space wants.

             Halved because \Columns runs the hook once for the left \pstart and again
             for the right one (reledpar's \Columns@print@before@pstart), so a paired
             compile would otherwise get twice the skip a single-column one gets. \Pages
             runs it once per page, so facing pages take it whole.

             A macro rather than a length so it is read when a \pstart is set, not here:
             typography.paragraphs.spacing sets \parskip further down the preamble, and
             this has to follow it. -->
        <xsl:text>\newcommand{\OSPstartSkip}{</xsl:text>
        <xsl:value-of select="if ($uses-reledpar and not($facing-pages))
                              then '0.5\parskip' else '\parskip'"/>
        <xsl:text>}&#10;</xsl:text>
        <xsl:choose>
            <xsl:when test="$has-parallel and $interleaved">
                <xsl:call-template name="interleaved-preamble"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:text>\AtEveryPstart*{\OSApplyKeep\vspace{\OSPstartSkip}}&#10;</xsl:text>
            </xsl:otherwise>
        </xsl:choose>
        <xsl:call-template name="keep-preamble"/>
        <xsl:if test="$uses-reledpar">
            <xsl:call-template name="column-keep-preamble"/>
        </xsl:if>

        <!-- Labelled lists (tei:list, tei:label, tei:item). The label's appearance
             (\OSListLabelStyle) and the item's indent (\OSListIndent) are typography
             settings; how they are placed is here.

             The label is set inside a \pstart, so it follows \OSheadA-\OSheadD rather
             than \OSSectionSeparatorStyle: no {\centering ...\par} and no \parbox. See
             tex/typography_tex.py's _INLINE_ALIGNMENT for why a \par inside a group
             escapes reledmac's per-line capture, and \OSCondRule for why a box sized from \linewidth
             overhangs a reledpar column.

             The item's indent is a pair of skips rather than a box or a list
             environment, for the same reason: \leftskip and \rightskip are measured
             against \hsize, which reledpar sets to the column width, so the indent is
             column-correct in a parallel compile and page-correct in a full-width one
             without either being asked for. \leftskip is read at \par time and
             \pstart...\pend is a group, so setting it at the head of the paragraph
             indents the whole of that paragraph and nothing after it. -->
        <xsl:text>\newcommand{\OSListLabel}[1]{\OSListLabelStyle{#1}}&#10;</xsl:text>
        <xsl:text>\newcommand{\OSListItemPar}{\leftskip=\OSListIndent\relax\rightskip=\OSListIndent\relax}&#10;</xsl:text>

        <xsl:if test="$notes-placement = 'endnote'">
            <!-- The endnote apparatus is configured separately from the footnote
                 one above, and needs the same treatment: no line number, and no
                 repetition of the lemma, which is the raised mark itself and
                 would print the serial twice. The notes are printed at the end
                 of the document (see the postamble). -->
            <xsl:text>\Xendnonumber[B]&#10;</xsl:text>
            <xsl:text>\Xendlemmaseparator[B]{}&#10;</xsl:text>
            <xsl:text>\makeatletter&#10;</xsl:text>
            <xsl:text>\Xendwraplemma[B]{\@gobble}&#10;</xsl:text>
            <xsl:text>\makeatother&#10;</xsl:text>
        </xsl:if>

        <!-- Every typography setting, at its resolved value. After the packages it
             configures; before $additional-preamble, which carries the bibliography
             and may redefine what this defines. -->
        <xsl:value-of select="$typography-preamble"/>

        <xsl:value-of select="$additional-preamble"/>
        <xsl:text>&#10;</xsl:text>

        <xsl:text>\begin{document}&#10;</xsl:text>
        <xsl:text>\OSBodyStyle&#10;</xsl:text>

        <xsl:apply-templates select="tei:TEI/tei:text"/>

        <xsl:text>&#10;</xsl:text>
        <xsl:if test="$notes-placement = 'endnote'">
            <!-- Endnotes are collected as the document is typeset and printed
                 here, after the text and before the metadata appendix. -->
            <xsl:text>\section*{Notes}&#10;</xsl:text>
            <xsl:text>\doendnotes{B}&#10;</xsl:text>
        </xsl:if>
        <!-- Metadata appendix (licenses, credits, sources). -->
        <xsl:value-of select="$additional-postamble"/>
        <xsl:text>&#10;</xsl:text>
        <!-- What the digital editions say about themselves (tei:div type="colophon", gathered
             here by cli_common.relocate_colophons), after the book's own colophon and set as
             the body is. -->
        <xsl:if test="tei:TEI/tei:text/tei:back[@p:colophon][normalize-space()]">
            <xsl:text>\clearpage&#10;</xsl:text>
            <xsl:apply-templates select="tei:TEI/tei:text/tei:back[@p:colophon]"/>
        </xsl:if>
        <!-- The last page, after the colophon. -->
        <xsl:value-of select="$back-notice"/>

        <xsl:text>\end{document}&#10;</xsl:text>
    </xsl:template>

    <xsl:template match="tei:teiHeader"/>

    <xsl:template match="tei:text">
        <!-- \frontmatter/\mainmatter are book-class page-numbering switches (roman for the
             front matter, restarting at arabic for the body). Emit them when there is front
             matter to number, or when a table of contents needs the roman-numeral front-matter
             pagination, so a document without either is unaffected. -->
        <xsl:variable name="needs-frontmatter"
                      select="exists(tei:front) or $table-of-contents or $distribution-notice != ''"/>
        <xsl:if test="$needs-frontmatter">
            <xsl:text>\frontmatter&#10;</xsl:text>
            <xsl:apply-templates select="tei:front"/>
            <!-- A book with no front matter has its distribution notice on the first page. -->
            <xsl:if test="empty(tei:front)">
                <xsl:call-template name="distribution-notice-page"/>
            </xsl:if>
            <xsl:if test="$table-of-contents">
                <!-- Scoped in a TeX group so tocdepth reverts afterward and does not affect
                     \hypersetup{bookmarksdepth=4} or the global tocdepth set in the preamble. -->
                <xsl:text>{\setcounter{tocdepth}{</xsl:text>
                <xsl:value-of select="$table-of-contents-depth"/>
                <!-- Polyglossia records language switches in .toc. A Hebrew switch
                     before an entry otherwise mirrors its leaders and reverses a
                     multi-digit page number. Each contents line uses the LTR slot;
                     its title already wraps Hebrew runs independently. -->
                <xsl:text>}\let\OScontentsline\contentsline&#10;</xsl:text>
                <xsl:text>\renewcommand{\contentsline}[4]{{\selectlanguage{english}\OScontentsline{#1}{#2}{#3}{#4}}}&#10;</xsl:text>
                <xsl:text>\tableofcontents}&#10;</xsl:text>
            </xsl:if>
            <xsl:text>\mainmatter&#10;</xsl:text>
        </xsl:if>
        <xsl:apply-templates select="tei:body"/>
        <!-- Back matter (an afterword, an index, or a parallel appendix) is set after the
             body, and as the body is. -->
        <xsl:if test="tei:back[not(@p:colophon)][normalize-space()]">
            <xsl:text>\backmatter&#10;</xsl:text>
            <xsl:apply-templates select="tei:back[not(@p:colophon)]"/>
        </xsl:if>
    </xsl:template>

    <!-- ====================================================================
         Front matter: title pages are set on their own pages outside all
         numbering; everything else is ordinary text run through the same
         numbered stream the body uses.
         ==================================================================== -->

    <xsl:template match="tei:front">
        <xsl:variable name="flow" as="node()*" select="f:flatten-transcludes(node())"/>

        <!-- Prose is grouped by its own language, not the root's. A book's front matter is
             routinely in a language the body is not: Birnbaum's introduction is English in
             a Hebrew-rooted project, and set under the root language every line of it came
             out reversed. Grouping on the language keeps adjacent same-language prose in one
             numbered stream, which is what a stream is for, and starts a new one where the
             language changes. tei:titlePage already resolves its own language and stays a
             group of its own, since it is set outside the numbering entirely. -->
        <xsl:variable name="items" as="node()*"
                      select="$flow[not(self::text() and not(normalize-space(.)))]"/>
        <xsl:variable name="keys" as="xs:string*" select="f:stream-keys($items)"/>
        <!-- The distribution notice is on the verso of the first title page, before any
             other (a source's own copyright page is a second tei:titlePage). A book with no
             title page, or whose title pages are not set, has it on its first page. -->
        <xsl:variable name="first-title-page" as="element(tei:titlePage)?"
                      select="$items[self::tei:titlePage][1]"/>
        <xsl:if test="empty($first-title-page)">
            <xsl:call-template name="distribution-notice-page"/>
        </xsl:if>
        <xsl:for-each-group select="$items" group-adjacent="subsequence($keys, position(), 1)">
            <xsl:choose>
                <xsl:when test="current-grouping-key() = 'titlePage'">
                    <xsl:for-each select="current-group()">
                        <xsl:apply-templates select="."/>
                        <xsl:if test=". is $first-title-page">
                            <xsl:call-template name="distribution-notice-page"/>
                        </xsl:if>
                    </xsl:for-each>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:call-template name="numbered-stream">
                        <xsl:with-param name="nodes" select="current-group()"/>
                        <xsl:with-param name="lang" select="f:stream-lang(current-group())"/>
                        <xsl:with-param name="align-verses" select="false()"/>
                    </xsl:call-template>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:for-each-group>
    </xsl:template>

    <!-- What each node of a flow is set in: a parallel block, a title page, or a numbered
         stream of one direction ('hebrew' or 'other', the distinction numbered-stream makes).
         Adjacent nodes of the same direction share a stream whatever their language tags.
         A page break, a comment or a processing instruction has no direction of its own,
         and stays in the stream it falls in rather than starting one. -->
    <xsl:function name="f:stream-keys" as="xs:string*">
        <xsl:param name="items" as="node()*"/>
        <xsl:iterate select="$items">
            <xsl:param name="previous" as="xs:string" select="''"/>
            <xsl:variable name="key" as="xs:string"
                          select="if (self::p:parallel) then 'parallel'
                                  else if (self::tei:titlePage) then 'titlePage'
                                  else if ((self::tei:pb or self::comment() or self::processing-instruction())
                                           and $previous = ('hebrew', 'other')) then $previous
                                  else if (f:is-hebrew-lang(f:flow-lang(.))) then 'hebrew'
                                  else 'other'"/>
            <xsl:sequence select="$key"/>
            <xsl:next-iteration>
                <xsl:with-param name="previous" select="$key"/>
            </xsl:next-iteration>
        </xsl:iterate>
    </xsl:function>

    <!-- The language a numbered stream is set in: its first node's that has one. -->
    <xsl:function name="f:stream-lang" as="xs:string">
        <xsl:param name="nodes" as="node()*"/>
        <xsl:sequence select="f:flow-lang((
            $nodes[not(self::tei:pb or self::comment() or self::processing-instruction())],
            $nodes)[1])"/>
    </xsl:function>

    <!-- The language a node of the flow is set in. Its text decides, not the tag on its
         container: a division tagged in one language whose every paragraph and line is in a
         language of the other direction is set in theirs. A division whose text is in both
         directions is set in its own, and the text of the other direction runs in it. -->
    <xsl:function name="f:flow-lang" as="xs:string">
        <xsl:param name="node" as="node()?"/>
        <xsl:variable name="own" select="f:in-scope-lang($node)"/>
        <xsl:variable name="text" as="element()*"
                      select="$node/descendant::*[self::tei:p or self::tei:l or self::tei:ab]
                                                 [not(ancestor::tei:note)]"/>
        <xsl:variable name="directions" as="xs:boolean*"
                      select="distinct-values($text ! f:is-hebrew-lang(f:in-scope-lang(.)))"/>
        <xsl:sequence select="if (count($directions) = 1 and $directions != f:is-hebrew-lang($own))
                              then f:in-scope-lang($text[1]) else $own"/>
    </xsl:function>

    <!-- A title page is a transcription of a printed page, not part of the edited text:
         it gets its own page and no line numbers, so it is emitted directly rather than
         through numbered-stream. -->
    <!-- The distribution notice's page, with no running head. It follows the title page's
         own \end{titlepage}, which ends that page and no more, so in a two-sided book it is
         the title page's verso. It is not a titlepage environment itself: that resets the
         page counter to 1, and a verso counted as page 1 is laid out as a recto, with every
         page after it on the wrong side too. -->
    <xsl:template name="distribution-notice-page">
        <xsl:if test="$distribution-notice != ''">
            <xsl:text>\clearpage&#10;</xsl:text>
            <xsl:text>\thispagestyle{empty}&#10;</xsl:text>
            <xsl:value-of select="$distribution-notice"/>
            <xsl:text>\clearpage&#10;</xsl:text>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tei:titlePage">
        <xsl:variable name="is-hebrew" select="f:is-hebrew-lang(f:in-scope-lang(.))"/>

        <xsl:text>\begin{titlepage}&#10;</xsl:text>
        <!-- A title page carries no running head or foot. The titlepage
             environment sets this itself in the book class, but say it
             explicitly: we redefine the `plain` page style, and this guarantee
             should not rest on a class internal. -->
        <xsl:text>\thispagestyle{empty}&#10;</xsl:text>
        <xsl:if test="$is-hebrew">
            <xsl:text>\begin{hebrew}&#10;</xsl:text>
        </xsl:if>
        <xsl:text>\null\vfill&#10;</xsl:text>
        <xsl:apply-templates select="node()" mode="emit"/>
        <xsl:text>&#10;\vfill&#10;</xsl:text>
        <xsl:if test="$is-hebrew">
            <xsl:text>\end{hebrew}&#10;</xsl:text>
        </xsl:if>
        <xsl:text>\end{titlepage}&#10;</xsl:text>
    </xsl:template>

    <!-- ====================================================================
         Body: split into runs of (parallel) and (non-parallel) chunks.
         Each non-parallel run is wrapped in one \beginnumbering...\endnumbering.
         Each parallel block becomes its own \begin{pages}/\Pages.
         ==================================================================== -->

    <xsl:template match="tei:body | tei:back">
        <!-- Expand p:transclude wrapper elements emitted by the compiler: the TeX stage
             should group and typeset the transcluded content, not the wrapper itself.
             Expansion must recurse: parallel blocks end at every external transclusion, so a
             transcluded document that itself transcludes nests wrappers arbitrarily deep. A
             single-level expansion would leave an inner p:transclude in the flow, where
             group-adjacent classifies it 'inline' and splits the surrounding \Pages run.
             Also ignore whitespace-only text nodes for grouping, otherwise pretty-printed
             XML will split runs of adjacent p:parallel blocks. -->
        <xsl:variable name="flow" as="node()*" select="f:flatten-transcludes(node())"/>

        <!-- Text outside the parallel blocks is grouped by its own language, as the front
             matter's is (see tei:front): a section in another language than the root's — an
             English document transcluded into a Hebrew book — is its own numbered stream,
             set in its own direction, not inside the root's. -->
        <xsl:variable name="items" as="node()*"
                      select="$flow[not(self::text() and not(normalize-space(.)))]"/>
        <xsl:variable name="keys" as="xs:string*" select="f:stream-keys($items)"/>
        <xsl:for-each-group select="$items" group-adjacent="subsequence($keys, position(), 1)">
            <xsl:choose>
                <xsl:when test="current-grouping-key() = 'parallel'">
                    <!-- One \Pages/\Columns per batch: see $parallel-batch-size. The
                         batches exist for reledpar's sake alone, so an interleaved run is
                         not cut: a cut would only restart numbering by section and add
                         auxiliary files. -->
                    <xsl:variable name="blocks" as="element(p:parallel)*" select="current-group()"/>
                    <xsl:for-each-group select="$blocks"
                                        group-adjacent="if ($interleaved) then 0
                                                        else (position() - 1) idiv $parallel-batch-size">
                        <xsl:call-template name="parallel-run">
                            <xsl:with-param name="parallels" select="current-group()"/>
                        </xsl:call-template>
                    </xsl:for-each-group>
                </xsl:when>
                <xsl:when test="every $n in current-group() satisfies (
                                  $n/self::text() and not(normalize-space($n)))">
                    <!-- Whitespace-only run: drop it -->
                </xsl:when>
                <xsl:otherwise>
                    <xsl:call-template name="numbered-stream">
                        <xsl:with-param name="nodes" select="current-group()"/>
                        <xsl:with-param name="lang" select="f:stream-lang(current-group())"/>
                        <xsl:with-param name="align-verses" select="false()"/>
                    </xsl:call-template>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:for-each-group>
    </xsl:template>

    <!-- ====================================================================
         Parallel: \begin{pages}/\begin{pairs} with two streams + \Pages/\Columns.
         column-order picks which side renders the primary stream.
         ==================================================================== -->

    <xsl:template match="p:parallel" priority="5">
        <xsl:call-template name="parallel-run">
            <xsl:with-param name="parallels" select="."/>
        </xsl:call-template>
    </xsl:template>

    <!-- The primary title a parallel block opens with, when the heading is to be set
         across the page rather than inside a column. Empty when it is not.

         A heading that is set once is not a heading of either column: it names the
         section, and the section spans the opening. So every mode that sets one heading
         hoists it out of the columns — whichever title it shows. Only 'both' keeps a
         heading inside a column, because then there really are two, and each belongs to
         the column whose language it is in.

         Hoisting is possible only where the block *opens* with the heading: there is no
         interrupting a \Pages once begun. A heading further in stays where it is.

         Facing pages hoist nothing. There is no measure spanning both texts to set a
         heading across, and a heading set before \Pages is stranded: \Pages starts the
         spread on the next verso, leaving the heading alone on the page before it and,
         as often as not, a blank page between. Each page sets its own instead; see
         f:sets-heading. -->
    <xsl:function name="f:spanning-title" as="xs:string">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:param name="mode" as="xs:string"/>
        <xsl:variable name="primary" select="$block/p:parallelItem[@role='primary'][1]"/>
        <xsl:variable name="primary-leaves" as="node()*">
            <xsl:apply-templates select="$primary/node()" mode="leaves"/>
        </xsl:variable>
        <!-- Whitespace between the markup does not count as content, so a head is still
             what the block opens with when pretty-printed XML puts a newline before it. -->
        <xsl:variable name="first"
                      select="$primary-leaves[not(self::text() and not(normalize-space(.)))][1]"/>
        <xsl:sequence
            select="if ($mode != 'both' and not($facing-pages)
                        and exists($first[self::f:head]))
                    then string($first/@title)
                    else ''"/>
    </xsl:function>

    <!-- A heading set across the page, outside the column structure. It carries the
         running-head marks for both columns and the outline entry, because the heading in
         the columns has been suppressed and would carry neither. \phantomsection anchors
         here, which is where the reader will actually land. -->
    <!-- The two headings a spanning heading is made from: the primary text's first and
         the other text's first, as heading sentinels. Both the spanning heading and the
         streams under it need to agree on which divisions these are, since the notes on
         them are set by the one and so must be left out by the other. -->
    <xsl:function name="f:spanning-heads" as="element()*">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:variable name="primary-leaves" as="node()*">
            <xsl:apply-templates select="$block/p:parallelItem[@role='primary'][1]/node()"
                                 mode="leaves"/>
        </xsl:variable>
        <xsl:variable name="secondary-leaves" as="node()*">
            <xsl:apply-templates select="$block/p:parallelItem[@role='parallel'][1]/node()"
                                 mode="leaves"/>
        </xsl:variable>
        <xsl:sequence select="$primary-leaves[self::f:head][1],
                              $secondary-leaves[self::f:head][1]"/>
    </xsl:function>

    <xsl:template name="spanning-heading">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:variable name="primary-leaves" as="node()*">
            <xsl:apply-templates select="$block/p:parallelItem[@role='primary'][1]/node()"
                                 mode="leaves"/>
        </xsl:variable>
        <xsl:variable name="secondary-leaves" as="node()*">
            <xsl:apply-templates select="$block/p:parallelItem[@role='parallel'][1]/node()"
                                 mode="leaves"/>
        </xsl:variable>
        <xsl:variable name="head" select="$primary-leaves[self::f:head][1]"/>
        <xsl:variable name="alt-head" select="$secondary-leaves[self::f:head][1]"/>
        <!-- The notes on each heading's division. The streams below leave them out (see
             f:spanning-heads); each is set here, after the title of its own division. -->
        <xsl:variable name="head-notes" as="element()*">
            <xsl:perform-sort select="$primary-leaves[f:is-head-note(.)]
                                                     [generate-id(f:head-note-div(.)) = $head/@div]">
                <xsl:sort select="f:note-serial(.)" data-type="number"/>
            </xsl:perform-sort>
        </xsl:variable>
        <xsl:variable name="alt-head-notes" as="element()*">
            <xsl:perform-sort select="$secondary-leaves[f:is-head-note(.)]
                                                       [generate-id(f:head-note-div(.)) = $alt-head/@div]">
                <xsl:sort select="f:note-serial(.)" data-type="number"/>
            </xsl:perform-sort>
        </xsl:variable>
        <xsl:if test="exists($head)">
            <!-- Which of the two titles this heading shows. 'combined' shows the other one
                 too where it says something different, set beneath as a translation of the
                 first — the same shape a division titled twice in one column takes. -->
            <xsl:variable name="shown" as="element()"
                          select="if ($headings-from = 'alt' and exists($alt-head))
                                  then $alt-head else $head"/>
            <xsl:variable name="second" as="element()?"
                          select="if ($headings-from = 'combined' and exists($alt-head)
                                      and string($alt-head/@title) != string($head/@title))
                                  then $alt-head else ()"/>
            <xsl:variable name="lang" select="string($shown/@xml:lang)"/>
            <xsl:variable name="is-hebrew"
                          select="f:is-hebrew-lang($lang)"/>
            <xsl:variable name="mark" select="f:emit-bidi-mark(string($shown/@title))"/>
            <!-- A title that is not set lends its notes to the one that is. -->
            <xsl:variable name="second-notes" as="element()*"
                          select="if (exists($second)) then $alt-head-notes else ()"/>
            <xsl:variable name="shown-notes" as="element()*"
                          select="($head-notes, $alt-head-notes) except $second-notes"/>
            <xsl:for-each select="('', 'Alt')">
                <xsl:text>\InsertMark{OShead</xsl:text>
                <xsl:value-of select="f:heading-suffix(xs:integer($head/@level))"/>
                <xsl:value-of select="."/>
                <xsl:text>}{</xsl:text><xsl:value-of select="$mark"/><xsl:text>}</xsl:text>
                <xsl:text>\InsertMark{OSheadAny</xsl:text><xsl:value-of select="."/>
                <xsl:text>}{</xsl:text><xsl:value-of select="$mark"/><xsl:text>}</xsl:text>
            </xsl:for-each>
            <xsl:text>&#10;</xsl:text>
            <xsl:variable name="titles" as="xs:string">
            <xsl:value-of>
            <xsl:text>\OShead</xsl:text>
            <xsl:value-of select="f:heading-suffix(xs:integer($head/@level))"/>
            <xsl:text>{</xsl:text>
            <xsl:if test="not($is-hebrew)">
                <xsl:text>{\textdir TLT\foreignlanguage{english}{</xsl:text>
            </xsl:if>
            <xsl:apply-templates select="$shown/node()[not(self::f:alt-head)]" mode="emit"/>
            <!-- Inside the title's direction; see name="heading". -->
            <xsl:apply-templates select="$shown-notes" mode="emit"/>
            <xsl:if test="not($is-hebrew)">
                <xsl:text>}}</xsl:text>
            </xsl:if>
            <xsl:text>}</xsl:text>
            <xsl:if test="exists($second)">
                <!-- The facing column's title is wrapped against ITS OWN language, not the
                     one this heading is set in. The two can differ: a book may head the
                     same section in Hebrew on one page and in English on the facing one.
                     Left unwrapped, an English title emitted inside the hebrew environment
                     is typeset right to left, and comes out with its letters painted in
                     reverse order. mode="emit" cannot save it: that wraps a run the source
                     marks as foreign, and a head whose whole text is in the other language
                     marks nothing. -->
                <xsl:variable name="second-lang" select="string($second/@xml:lang)"/>
                <xsl:variable name="second-is-hebrew"
                              select="f:is-hebrew-lang($second-lang)"/>
                <xsl:text>\OSheadTranslation{</xsl:text>
                <xsl:choose>
                    <xsl:when test="$second-is-hebrew">
                        <xsl:text>\texthebrew{</xsl:text>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:text>{\textdir TLT\foreignlanguage{english}{</xsl:text>
                    </xsl:otherwise>
                </xsl:choose>
                <xsl:apply-templates select="$second/node()[not(self::f:alt-head)]"
                                     mode="emit"/>
                <xsl:apply-templates select="$second-notes" mode="emit"/>
                <xsl:choose>
                    <xsl:when test="$second-is-hebrew">
                        <xsl:text>}</xsl:text>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:text>}}</xsl:text>
                    </xsl:otherwise>
                </xsl:choose>
                <xsl:text>}</xsl:text>
            </xsl:if>
            </xsl:value-of>
            </xsl:variable>
            <xsl:choose>
                <xsl:when test="exists($head-notes) or exists($alt-head-notes)">
                    <!-- A note mark is an \edtext, which reledmac sets only inside numbered
                         text, and this heading stands between the columns, outside any. So
                         a heading that carries notes is given a numbered section of its
                         own, with numbering switched off around its one paragraph so that
                         neither of its lines takes a number. Headings without notes are
                         left as they were. -->
                    <xsl:text>\beginnumbering&#10;{\numberlinefalse\interlinepenalty=10000\relax&#10;</xsl:text>
                    <xsl:if test="$is-hebrew">
                        <xsl:text>\begin{hebrew}&#10;</xsl:text>
                    </xsl:if>
                    <xsl:call-template name="pstart"/>
                    <xsl:value-of select="$titles"/>
                    <xsl:text>\pend&#10;</xsl:text>
                    <xsl:if test="$is-hebrew">
                        <xsl:text>\end{hebrew}&#10;</xsl:text>
                    </xsl:if>
                    <xsl:text>}&#10;\endnumbering&#10;</xsl:text>
                </xsl:when>
                <xsl:otherwise>
                    <!-- \parfillskip is 0pt plus 1fil on an ordinary paragraph, and the
                         heading macros centre with an \hfill at each end. Three infinite
                         glues put the title a third of the way across instead of half.
                         reledmac zeroes \parfillskip inside a \pstart, which is why a
                         heading set in a column looks right and this one, set between
                         columns, did not. -->
                    <xsl:text>{\parfillskip=0pt\interlinepenalty=10000\relax </xsl:text>
                    <xsl:if test="$is-hebrew">
                        <xsl:text>\begin{hebrew}</xsl:text>
                    </xsl:if>
                    <!-- A rubric that ended the columns above may be waiting to be kept
                         with this title. Its \nobreak goes after \begin{hebrew}, which
                         writes a language record to the page, and a skip after a \write
                         can break whatever penalty came before it. -->
                    <xsl:text>\OSApplyKeep </xsl:text>
                    <xsl:value-of select="$titles"/>
                    <xsl:if test="$is-hebrew">
                        <xsl:text>\end{hebrew}</xsl:text>
                    </xsl:if>
                    <xsl:text>\par}&#10;</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
            <xsl:text>\phantomsection\addcontentsline{toc}{</xsl:text>
            <xsl:value-of select="f:heading-toc-level(xs:integer($head/@level))"/>
            <xsl:text>}{</xsl:text>
            <xsl:value-of select="f:format-section-title(
                if ($bookmarks-from = 'combined' and exists($second))
                then concat(string($head/@title), ' &#xB7; ', string($second/@title))
                else if ($bookmarks-from = 'alt' and exists($alt-head))
                then string($alt-head/@title)
                else string($head/@title))"/>
            <!-- Not stranded above the columns it titles: \Columns opens the block with
                 the \AtEveryPstart* hook, which keeps it with this. -->
            <xsl:text>}\OSKeepNext&#10;</xsl:text>
        </xsl:if>
    </xsl:template>

    <xsl:template name="parallel-run">
        <xsl:param name="parallels" as="element(p:parallel)+"/>

        <!-- Filter out empty blocks (structural wrappers that contain no real content). -->
        <xsl:variable name="usable" as="element(p:parallel)*">
            <xsl:for-each select="$parallels">
                <xsl:variable name="primary" select="p:parallelItem[@role='primary'][1]"/>
                <xsl:variable name="secondary" select="p:parallelItem[@role='parallel'][1]"/>
                <xsl:variable name="left" select="if (@column-order='primary_last') then $secondary else $primary"/>
                <xsl:variable name="right" select="if (@column-order='primary_last') then $primary else $secondary"/>

                <xsl:variable name="left-leaves" as="node()*">
                    <xsl:apply-templates select="$left/node()" mode="leaves"/>
                </xsl:variable>
                <xsl:variable name="right-leaves" as="node()*">
                    <xsl:apply-templates select="$right/node()" mode="leaves"/>
                </xsl:variable>
                <xsl:variable name="left-has-content" as="xs:boolean"
                              select="exists($left-leaves[not(self::text() and not(normalize-space(.))) and not(self::f:para-break) and not(self::f:block-break)])"/>
                <xsl:variable name="right-has-content" as="xs:boolean"
                              select="exists($right-leaves[not(self::text() and not(normalize-space(.))) and not(self::f:para-break) and not(self::f:block-break)])"/>

                <xsl:if test="$left-has-content or $right-has-content">
                    <xsl:sequence select="."/>
                </xsl:if>
            </xsl:for-each>
        </xsl:variable>

        <!-- A block with text in one language only has nothing to face, so it is set
             across the whole page rather than beside an empty column, and the columns
             resume at the next block both languages set. Interleaving never reserves a
             column, so it keeps every block in one run; see f:interleaved-nodes for
             what it does with a block like this. -->
        <xsl:for-each-group select="$usable"
                            group-adjacent="if ($interleaved) then 'columns' else f:parallel-row-kind(.)">
            <xsl:choose>
                <xsl:when test="current-grouping-key() = 'columns'">
                    <xsl:call-template name="parallel-column-run">
                        <xsl:with-param name="usable" select="current-group()"/>
                    </xsl:call-template>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:call-template name="parallel-single-run">
                        <xsl:with-param name="usable" select="current-group()"/>
                        <xsl:with-param name="lang"
                                        select="substring-after(current-grouping-key(), 'single:')"/>
                    </xsl:call-template>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:for-each-group>
    </xsl:template>

    <xsl:template name="parallel-column-run">
        <xsl:param name="usable" as="element(p:parallel)*"/>
        <!-- A block opening with a heading both columns share starts a new column block,
             so the heading can be set across the page between them. -->
        <xsl:for-each-group select="$usable"
                            group-starting-with="*[f:spanning-title(., $headings-from) != '']">
            <xsl:choose>
                <xsl:when test="$interleaved">
                    <xsl:call-template name="parallel-interleaved">
                        <xsl:with-param name="usable" select="current-group()"/>
                        <xsl:with-param name="spanning"
                                        select="f:spanning-title(current-group()[1], $headings-from)"/>
                    </xsl:call-template>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:call-template name="parallel-columns">
                        <xsl:with-param name="usable" select="current-group()"/>
                        <xsl:with-param name="spanning"
                                        select="f:spanning-title(current-group()[1], $headings-from)"/>
                    </xsl:call-template>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:for-each-group>
    </xsl:template>

    <!-- 'columns' for a block both of whose items set text, else 'single:' and the
         language of the one item that does. An item holding only apparatus — an empty
         correspondence anchor, a note, a reference marker — sets no text, so it is not
         a translation to face. A block neither item sets text in still carries something
         that puts ink, or parallel-run would have dropped it; it is set in its primary
         language. -->
    <xsl:function name="f:parallel-row-kind" as="xs:string">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:variable name="primary" select="$block/p:parallelItem[@role='primary'][1]"/>
        <xsl:variable name="secondary" select="$block/p:parallelItem[@role='parallel'][1]"/>
        <xsl:variable name="primary-text" as="xs:boolean" select="f:sets-text($primary)"/>
        <xsl:variable name="secondary-text" as="xs:boolean" select="f:sets-text($secondary)"/>
        <xsl:sequence select="
            if ($primary-text and $secondary-text) then 'columns'
            else concat('single:', string(
                (if ($secondary-text) then $secondary else $primary)/@xml:lang))"/>
    </xsl:function>

    <!-- The item of a block that is set in a 'single:' run: the one that sets text, or
         the primary when neither does. -->
    <xsl:function name="f:single-item" as="element()?">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:variable name="primary" select="$block/p:parallelItem[@role='primary'][1]"/>
        <xsl:variable name="secondary" select="$block/p:parallelItem[@role='parallel'][1]"/>
        <xsl:sequence select="if (not(f:sets-text($primary)) and f:sets-text($secondary))
                              then $secondary else $primary"/>
    </xsl:function>

    <!-- The leaves of a block with text in one language: that item's, with the other
         item's editorial notes and page labels put among them. Birnbaum's Hoshanot
         have no English translation, but his English notes on them are compiled onto empty anchors in
         the English document; they belong to the Hebrew, not to a column or paragraph
         of their own. A rubric is not among them: it is words of its own, and a block
         whose other item sets one has text on both sides, so never comes here.

         Page labels belong to their source edition even when neither side sets words:
         Birnbaum's long Tachanun boundaries are milestone-only blocks. Keep both
         editions' labels in the surviving stream so neither edition's page references
         point to labels that disappear when the block is collapsed.

         Flattened here rather than by the stream, so the notes can go inside the text's
         paragraph and not after its closing break. Flattening is idempotent: the leaves
         are the source nodes themselves, so the stream's own pass finds them unchanged,
         with their ancestors (and so their serials) intact. -->
    <xsl:function name="f:single-row-leaves" as="node()*">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:variable name="item" select="f:single-item($block)"/>
        <xsl:variable name="leaves" as="node()*">
            <xsl:apply-templates select="$item/node()" mode="leaves"/>
        </xsl:variable>
        <xsl:variable name="other-content" as="element()*"
                      select="($block/p:parallelItem except $item)
                              /(.//tei:note[not(@type = ('instruction', 'description'))]
                                | .//tei:anchor[@type = 'page-label'
                                               or .//tei:note[not(@type = ('instruction', 'description'))]])
                              [not(ancestor::tei:note or ancestor::tei:anchor[.//tei:note])]"/>
        <xsl:variable name="ink" as="xs:integer*"
                      select="index-of($leaves ! (f:puts-ink(.) and not(self::f:head)), true())"/>
        <!-- After the text when the other item follows it in the document, before it
             when the other item comes first, so the marks keep the order their serials
             were counted in. -->
        <xsl:variable name="at" as="xs:integer"
                      select="if (empty($other-content) or empty($ink)) then count($leaves)
                              else if ($other-content[1] &lt;&lt; $item) then $ink[1] - 1
                              else $ink[last()]"/>
        <xsl:sequence select="subsequence($leaves, 1, $at), $other-content,
                              subsequence($leaves, $at + 1)"/>
    </xsl:function>

    <!-- Blocks with text in one language, set across the whole page between column
         blocks. -->
    <xsl:template name="parallel-single-run">
        <xsl:param name="usable" as="element(p:parallel)+"/>
        <xsl:param name="lang" as="xs:string"/>
        <xsl:variable name="nodes" as="node()*">
            <xsl:for-each select="$usable">
                <xsl:sequence select="f:single-row-leaves(.)"/>
                <xsl:if test="position() != last()">
                    <f:block-break/>
                </xsl:if>
            </xsl:for-each>
        </xsl:variable>
        <xsl:variable name="first" select="$usable[1]"/>
        <!-- The column the text would have stood in names the running-head marks it
             records into, so a running head keeps one language per side. -->
        <xsl:variable name="in-left-column" as="xs:boolean"
                      select="(f:single-item($first)/@role = 'primary')
                              = not($first/@column-order = 'primary_last')"/>
        <xsl:choose>
            <!-- A title-only primary block belongs above the following columns.
                 A numbered stream would finish its section (and write language/line
                 records) between the title and those columns, introducing another
                 page-break opportunity after the title's keep penalty. Reuse the
                 spanning-title path, which closes its language before requesting the
                 keep. Restrict this to a single bare title: apparatus, page labels,
                 extra headings and body text retain the complete stream path. -->
            <xsl:when test="count($usable) = 1
                            and f:spanning-title($first, $headings-from) != ''
                            and count($nodes[self::f:head]) = 1
                            and empty($nodes[not(self::f:head or self::f:para-break
                                               or self::text()[not(normalize-space(.))])])">
                <xsl:call-template name="spanning-heading">
                    <xsl:with-param name="block" select="$first"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:otherwise>
        <xsl:call-template name="numbered-stream">
            <xsl:with-param name="nodes" select="$nodes"/>
            <xsl:with-param name="lang" select="$lang"/>
            <xsl:with-param name="align-verses" select="false()"/>
            <xsl:with-param name="stream" select="if ($in-left-column) then 'primary' else 'alt'"/>
        </xsl:call-template>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- One \Pages (or \Columns) block, optionally preceded by a heading set across the
         whole page rather than inside either column. -->
    <xsl:template name="parallel-columns">
        <xsl:param name="usable" as="element(p:parallel)*"/>
        <xsl:param name="spanning" as="xs:string" select="''"/>

        <xsl:if test="$spanning != ''">
            <xsl:call-template name="spanning-heading">
                <xsl:with-param name="block" select="$usable[1]"/>
            </xsl:call-template>
        </xsl:if>

        <xsl:if test="exists($usable)">
        <xsl:variable name="hoisted-divs" as="xs:string*"
                      select="if ($spanning != '') then f:spanning-heads($usable[1])/@div else ()"/>
        <xsl:variable name="env" select="if ($layout='pairs') then 'pairs' else 'pages'"/>
        <xsl:variable name="typeset" select="if ($layout='pairs') then '\Columns' else '\Pages'"/>

            <!-- Build a single continuous stream per side; insert a block-break between
                 adjacent parallel blocks so each block becomes its own alignment unit
                 (one \pstart...\pend per block), while intra-block paragraphs remain
                 plain \par breaks. -->
            <xsl:variable name="left-nodes" as="node()*">
                <xsl:for-each select="$usable">
                    <xsl:variable name="primary" select="p:parallelItem[@role='primary'][1]"/>
                    <xsl:variable name="secondary" select="p:parallelItem[@role='parallel'][1]"/>
                    <xsl:variable name="left" select="if (@column-order='primary_last') then $secondary else $primary"/>
                    <xsl:sequence select="$left/node()"/>
                    <xsl:if test="position() != last()">
                        <f:block-break/>
                    </xsl:if>
                </xsl:for-each>
            </xsl:variable>

            <xsl:variable name="right-nodes" as="node()*">
                <xsl:for-each select="$usable">
                    <xsl:variable name="primary" select="p:parallelItem[@role='primary'][1]"/>
                    <xsl:variable name="secondary" select="p:parallelItem[@role='parallel'][1]"/>
                    <xsl:variable name="right" select="if (@column-order='primary_last') then $primary else $secondary"/>
                    <xsl:sequence select="$right/node()"/>
                    <xsl:if test="position() != last()">
                        <f:block-break/>
                    </xsl:if>
                </xsl:for-each>
            </xsl:variable>

            <xsl:variable name="first-primary" select="$usable[1]/p:parallelItem[@role='primary'][1]"/>
            <xsl:variable name="first-secondary" select="$usable[1]/p:parallelItem[@role='parallel'][1]"/>
            <xsl:variable name="left-lang"
                          select="string((if ($usable[1]/@column-order='primary_last') then $first-secondary else $first-primary)/@xml:lang)"/>
            <xsl:variable name="right-lang"
                          select="string((if ($usable[1]/@column-order='primary_last') then $first-primary else $first-secondary)/@xml:lang)"/>

            <xsl:text>\begin{</xsl:text><xsl:value-of select="$env"/><xsl:text>}&#10;</xsl:text>

            <xsl:text>\begin{Leftside}&#10;</xsl:text>
            <xsl:call-template name="column-glue-reset"/>
                <xsl:call-template name="numbered-stream">
                <xsl:with-param name="nodes" select="$left-nodes"/>
                <xsl:with-param name="lang" select="$left-lang"/>
                <xsl:with-param name="align-verses" select="false()"/>
                <xsl:with-param name="single-pstart" select="true()"/>
                <xsl:with-param name="stream" select="'primary'"/>
                <!-- Both columns are in scope here and nowhere else, which is what makes
                     joining their headings possible at all. -->
                <xsl:with-param name="alt-nodes" select="$right-nodes"/>
                <xsl:with-param name="hoisted-heading" select="$spanning"/>
                <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
            </xsl:call-template>
            <xsl:text>\end{Leftside}&#10;</xsl:text>

            <xsl:text>\begin{Rightside}&#10;</xsl:text>
            <xsl:call-template name="column-glue-reset"/>
                <xsl:call-template name="numbered-stream">
                <xsl:with-param name="nodes" select="$right-nodes"/>
                <xsl:with-param name="lang" select="$right-lang"/>
                <xsl:with-param name="align-verses" select="false()"/>
                <xsl:with-param name="single-pstart" select="true()"/>
                <!-- The second column records into the `Alt` mark classes so a
                     running head can name either language's heading. -->
                <xsl:with-param name="stream" select="'alt'"/>
                <!-- The other column, so this one can tell whether its heading says the
                     same thing. The primary side is given the same in reverse. -->
                <xsl:with-param name="alt-nodes" select="$left-nodes"/>
                <xsl:with-param name="hoisted-heading" select="$spanning"/>
                <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
            </xsl:call-template>
            <xsl:text>\end{Rightside}&#10;</xsl:text>

            <xsl:text>\end{</xsl:text><xsl:value-of select="$env"/><xsl:text>}&#10;</xsl:text>
            <xsl:value-of select="$typeset"/><xsl:text>&#10;</xsl:text>
        </xsl:if>
    </xsl:template>

    <!-- Lines that must not be parted by a page break (#198), and the rules that read them.

         reledmac and reledpar both set numbered text a line at a time, \vsplit-ting each
         line off the box its \pstart was collected in. Before a line is set, OSkeep reads
         the lines still waiting in that box: what each is (see \OSKeepAttr: a heading
         line H, a paragraph separator S, a rubric line R, or text N), and whether the box
         ends after it (E). A line with no text at all is a separator too: the \newline
         that ends a rubric leaves one when the rubric ends its \pstart. A line cannot be broken after when it is:
           * a heading line, so a heading is never split or left at the foot of a page;
           * one of a rubric's last five lines, so a rubric of up to five lines stays
             whole and with the text below it, and a longer one keeps at least its end
             with it; or the first line of a rubric (orphan);
           * a separator after a rubric, so the rubric is not left above a blank line;
           * the first line of a paragraph, unless the paragraph is one line (orphan);
           * the line before the last of a paragraph (widow).
         A heading, a separator, a rubric or the start of a \pstart begins a paragraph;
         any of them or the end of the box ends one.

         Here, single-stream text: reledmac's own club and widow penalties already cover
         its paragraphs, so what this adds is the rubric. reledmac puts a line's penalty
         after it in \add@penalties; a bound line adds 10000 to it, and the last line of
         a \pstart, which gets none, hands the keep on to the next one (\OSKeepNext).
         reledpar's columns use the same rules; see column-keep-preamble.

         Lua because TeX cannot look inside a box without taking it apart; it is written
         without % or ~, which TeX would read first. -->
    <xsl:template name="keep-preamble">
        <xsl:text>\makeatletter&#10;</xsl:text>
        <xsl:text>\newcount\OS@linebound&#10;</xsl:text>
        <xsl:text>\directlua{&#10;</xsl:text>
        <xsl:text>  OSkeep = {attr = luatexbase.attributes.OSKeepAttr, prev = {L = "start", R = "start", M = "start"}, held = {}, begun = {}, done = {}, cap = 10, tail = 5};&#10;</xsl:text>
        <xsl:text>  local HLIST = node.id("hlist")&#10;</xsl:text>
        <xsl:text>  local VLIST = node.id("vlist")&#10;</xsl:text>
        <xsl:text>  local KIND = {[1] = "H", [2] = "S", [3] = "R"};&#10;</xsl:text>
        <xsl:text>  local GLYPH = node.id("glyph")&#10;</xsl:text>
        <xsl:text>  local function inked(head)&#10;</xsl:text>
        <xsl:text>    for n in node.traverse(head) do&#10;</xsl:text>
        <xsl:text>      if n.id == GLYPH then return true end&#10;</xsl:text>
        <xsl:text>      if (n.id == HLIST or n.id == VLIST) and n.head and inked(n.head) then return true end&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    return false&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  local function tag(head)&#10;</xsl:text>
        <xsl:text>    local found = 0&#10;</xsl:text>
        <xsl:text>    for n in node.traverse(head) do&#10;</xsl:text>
        <xsl:text>      local v = node.has_attribute(n, OSkeep.attr)&#10;</xsl:text>
        <xsl:text>      if v and v > found then found = v end&#10;</xsl:text>
        <xsl:text>      if (n.id == HLIST or n.id == VLIST) and n.head then&#10;</xsl:text>
        <xsl:text>        local w = tag(n.head)&#10;</xsl:text>
        <xsl:text>        if w > found then found = w end&#10;</xsl:text>
        <xsl:text>      end&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    return found&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  function OSkeep.lines(boxnum, count)&#10;</xsl:text>
        <xsl:text>    local kinds, heights, n = {}, {}, 0&#10;</xsl:text>
        <xsl:text>    local box = boxnum >= 0 and tex.box[boxnum]&#10;</xsl:text>
        <xsl:text>    if box and box.head then&#10;</xsl:text>
        <xsl:text>      for item in node.traverse_id(HLIST, box.head) do&#10;</xsl:text>
        <xsl:text>        if n >= count then return kinds, heights end&#10;</xsl:text>
        <xsl:text>        n = n + 1&#10;</xsl:text>
        <xsl:text>        local t = item.head and tag(item.head) or 0&#10;</xsl:text>
        <xsl:text>        kinds[n] = KIND[t] or ((item.head and inked(item.head)) and "N" or "S")&#10;</xsl:text>
        <xsl:text>        heights[n] = item.height + item.depth&#10;</xsl:text>
        <xsl:text>      end&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    kinds[n + 1] = "E"&#10;</xsl:text>
        <xsl:text>    return kinds, heights&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  local function edge(x)&#10;</xsl:text>
        <xsl:text>    return x == "start" or x == "S" or x == "H" or x == "R"&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  function OSkeep.bound(k, j, prev)&#10;</xsl:text>
        <xsl:text>    local a, b, c = k[j], k[j + 1], k[j + 2]&#10;</xsl:text>
        <xsl:text>    local before = (j == 1) and prev or k[j - 1]&#10;</xsl:text>
        <xsl:text>    if a == "H" then return true end&#10;</xsl:text>
        <xsl:text>    if a == "S" then return before == "R" end&#10;</xsl:text>
        <xsl:text>    if a == "R" then&#10;</xsl:text>
        <xsl:text>      if b == "R" and not (before == "R") then return true end&#10;</xsl:text>
        <xsl:text>      local r = 1&#10;</xsl:text>
        <xsl:text>      while k[j + r] == "R" do r = r + 1 end&#10;</xsl:text>
        <xsl:text>      return not (k[j + r] == nil) and r &lt;= OSkeep.tail&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    if not (a == "N" and b == "N") then return false end&#10;</xsl:text>
        <xsl:text>    if edge(before) then return true end&#10;</xsl:text>
        <xsl:text>    return c == "E" or c == "S" or c == "H" or c == "R"&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  function OSkeep.single(boxnum)&#10;</xsl:text>
        <xsl:text>    local k = OSkeep.lines(boxnum, OSkeep.tail + 3)&#10;</xsl:text>
        <xsl:text>    local held = OSkeep.bound(k, 1, OSkeep.prev.M)&#10;</xsl:text>
        <xsl:text>    OSkeep.prev.M = (k[2] == "E") and "start" or k[1]&#10;</xsl:text>
        <xsl:text>    tex.setcount("global", "OS@linebound", held and ((k[2] == "E") and 2 or 1) or 0)&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>}&#10;</xsl:text>
        <xsl:text>\appto\do@linehook{\directlua{OSkeep.single(\number\raw@text)}}&#10;</xsl:text>
        <xsl:text>\patchcmd{\add@penalties}{\@l@dtempcnta=\ballast@count}{\@l@dtempcnta=\ballast@count\ifnum\OS@linebound>\z@\advance\@l@dtempcnta 10000 \fi}{}{\PackageError{opensiddur}{could not patch reledmac's add@penalties}{}}&#10;</xsl:text>
        <xsl:text>\apptocmd{\add@penalties}{\ifnum\OS@linebound>\@ne\OSKeepNext\fi}{}{\PackageError{opensiddur}{could not patch reledmac's add@penalties}{}}&#10;</xsl:text>
        <xsl:text>\makeatother&#10;</xsl:text>
    </xsl:template>

    <!-- The same rules inside reledpar's columns (#198); see keep-preamble for the rules.

         Neither column layout honours a penalty between lines: \Columns runs with every
         penalty zeroed and stacks rows that can break between any two, and \Pages ignores
         penalties altogether and decides each page itself, ending it when \pagetotal
         reaches its goal. And every paragraph, heading and rubric of a column is one
         \pstart, so reledmac's own club and widow penalties, which work per \pstart,
         never see them either.

         \Columns: if either column's line in a row must not be broken after, the row is
         followed by \nobreak. A heading or rubric that ends its block also asks the next
         block to keep with it, as a heading set between \pstarts does.
         \Pages: before each line, the run of lines that must stay together from it is
         measured, and if the last of them would not fit, reledpar is told the page is
         full, so the whole run starts the next one. A run that reaches the end of its
         block continues into the next block only when the facing page ends the block no
         lower: otherwise reledpar pads this page with blank lines until the facing page
         catches up, and the rubric is parted from its text by them anyway. The verso is
         set before its recto, so for the verso that is a projection from the lines the
         recto has left; the recto knows where the verso ended (OSkeep.done), or that it
         has not, in which case the verso runs on past this spread and the recto pads.

         Either way at most ten lines are bound together, so a column made of nothing
         else still breaks somewhere. -->
    <xsl:template name="column-keep-preamble">
        <xsl:text>\makeatletter&#10;</xsl:text>
        <xsl:text>\newcount\OS@rowkeep&#10;</xsl:text>
        <xsl:text>\newcount\OS@keeprun&#10;</xsl:text>
        <xsl:text>\newdimen\OS@chainht&#10;</xsl:text>
        <xsl:text>\newcount\OS@chainlines&#10;</xsl:text>
        <xsl:text>\newcount\OS@pagelines&#10;</xsl:text>
        <xsl:text>\directlua{&#10;</xsl:text>
        <xsl:text>  local function spread() return math.floor(tex.count["c@page"] / 2) end&#10;</xsl:text>
        <xsl:text>  local function height(k, h, upto)&#10;</xsl:text>
        <xsl:text>    local line, gap, total = tex.getglue("baselineskip"), tex.getglue("lineskip"), 0&#10;</xsl:text>
        <xsl:text>    for i = 1, upto do total = total + math.max(line, h[i] + gap) end&#10;</xsl:text>
        <xsl:text>    return total&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  function OSkeep.line(side, boxnum)&#10;</xsl:text>
        <xsl:text>    local k, h = OSkeep.lines(boxnum, OSkeep.tail + 3)&#10;</xsl:text>
        <xsl:text>    OSkeep.held[side] = OSkeep.bound(k, 1, OSkeep.prev[side])&#10;</xsl:text>
        <xsl:text>    if OSkeep.held[side] then tex.setcount("global", "OS@rowkeep", 1) end&#10;</xsl:text>
        <xsl:text>    if OSkeep.prev[side] == "start" then&#10;</xsl:text>
        <xsl:text>      OSkeep.begun[side] = {spread = spread(), pt = tex.pagetotal};&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    if k[2] == "E" then&#10;</xsl:text>
        <xsl:text>      OSkeep.done[side] = {spread = spread(), pt = tex.pagetotal + height(k, h, 1)};&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    OSkeep.prev[side] = (k[2] == "E") and "start" or k[1]&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  local function clear(side, facing, finish)&#10;</xsl:text>
        <xsl:text>    local other = (side == "L") and "R" or "L"&#10;</xsl:text>
        <xsl:text>    local slack = 2 * 65536&#10;</xsl:text>
        <xsl:text>    local fk, fh = OSkeep.lines(facing, 60)&#10;</xsl:text>
        <xsl:text>    local n = 0&#10;</xsl:text>
        <xsl:text>    while fk[n + 1] and not (fk[n + 1] == "E") do n = n + 1 end&#10;</xsl:text>
        <xsl:text>    if not fk[n + 1] then return false end&#10;</xsl:text>
        <xsl:text>    if n == 0 then&#10;</xsl:text>
        <xsl:text>      local d = OSkeep.done[other]&#10;</xsl:text>
        <xsl:text>      if not d or d.spread &lt; spread() then return true end&#10;</xsl:text>
        <xsl:text>      return d.pt &lt;= finish + slack&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    if side == "R" then return false end&#10;</xsl:text>
        <xsl:text>    local b = OSkeep.begun[side]&#10;</xsl:text>
        <xsl:text>    local start = (b and b.spread == spread()) and b.pt or 0&#10;</xsl:text>
        <xsl:text>    return start + height(fk, fh, n) &lt;= finish + slack&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>  function OSkeep.chain(side, boxnum, nextnum, facing)&#10;</xsl:text>
        <xsl:text>    tex.setcount("global", "OS@chainlines", 1)&#10;</xsl:text>
        <xsl:text>    if OSkeep.held[side] then return end&#10;</xsl:text>
        <xsl:text>    local line = tex.getglue("baselineskip")&#10;</xsl:text>
        <xsl:text>    local gap = tex.getglue("lineskip")&#10;</xsl:text>
        <xsl:text>    local skip = tex.getglue("parskip")&#10;</xsl:text>
        <xsl:text>    local prev = OSkeep.prev[side]&#10;</xsl:text>
        <xsl:text>    local total = (prev == "start") and skip or 0&#10;</xsl:text>
        <xsl:text>    local k, h = OSkeep.lines(boxnum, OSkeep.cap + OSkeep.tail + 2)&#10;</xsl:text>
        <xsl:text>    local j, count = 1, 1&#10;</xsl:text>
        <xsl:text>    while count &lt; OSkeep.cap and k[j] and not (k[j] == "E") and OSkeep.bound(k, j, prev) do&#10;</xsl:text>
        <xsl:text>      if k[j + 1] == "E" then&#10;</xsl:text>
        <xsl:text>        local finish = tex.pagetotal + total + math.max(line, h[j] + gap)&#10;</xsl:text>
        <xsl:text>        if nextnum &lt; 0 or not clear(side, facing, finish) then break end&#10;</xsl:text>
        <xsl:text>        local k2, h2 = OSkeep.lines(nextnum, OSkeep.cap + OSkeep.tail + 2)&#10;</xsl:text>
        <xsl:text>        if k2[1] == "E" then break end&#10;</xsl:text>
        <xsl:text>        total = total + math.max(line, h[j] + gap) + skip&#10;</xsl:text>
        <xsl:text>        k, h, j, prev, nextnum = k2, h2, 1, "start", -1&#10;</xsl:text>
        <xsl:text>      else&#10;</xsl:text>
        <xsl:text>        total = total + math.max(line, h[j] + gap)&#10;</xsl:text>
        <xsl:text>        j = j + 1&#10;</xsl:text>
        <xsl:text>      end&#10;</xsl:text>
        <xsl:text>      count = count + 1&#10;</xsl:text>
        <xsl:text>    end&#10;</xsl:text>
        <xsl:text>    tex.setcount("global", "OS@chainlines", count)&#10;</xsl:text>
        <xsl:text>    tex.setdimen("global", "OS@chainht", total)&#10;</xsl:text>
        <xsl:text>  end&#10;</xsl:text>
        <xsl:text>}&#10;</xsl:text>
        <xsl:text>\appto\do@lineLhook{\directlua{OSkeep.line("L", \number\namebox{l@dLcolrawbox\the\l@dpscL})}}&#10;</xsl:text>
        <xsl:text>\appto\do@lineRhook{\directlua{OSkeep.line("R", \number\namebox{l@dRcolrawbox\the\l@dpscR})}}&#10;</xsl:text>
        <xsl:choose>
            <xsl:when test="$facing-pages">
                <!-- The register number of a side's raw box for the \pstart numbered #2,
                     or -1 if there is none yet. OSkeep.chain is given this side's box, the
                     next one, and the facing side's box for the same \pstart.

                     The next box is read only by a run that reaches the end of this one,
                     never while this side is being padded: its own box is empty then and
                     there is no run. Measuring the next \pstart from padding ended padded
                     pages early and put that \pstart lower on one side than the other.
                     Otherwise the next \pstart is measured once it is current, before its
                     first line, with the skip that opens it (see \OSPstartSkip). -->
                <xsl:text>\newcommand*{\OS@rawbox}[2]{\ifcsname l@d#1colrawbox\the\numexpr#2\relax\endcsname\number\csname l@d#1colrawbox\the\numexpr#2\relax\endcsname\else -1\fi}&#10;</xsl:text>
                <!-- \OS@chainlines is the number of lines in the run and \OS@chainht the
                     height of all but its last. reledpar sets a line whenever \pagetotal is
                     still short of its goal, so the run fits if its last line would still be
                     allowed. It also stops a page at the number of lines the facing page
                     held on the last pass (\l@dminpagelines), so the run must fit under
                     that count too.

                     The page is ended the way reledpar ends one at that count, not as a
                     full page: a full page's count is what the facing page is held to on
                     the next pass, and recording these early ends there would cut the
                     facing page short at a line of its own that may be bound, which moves
                     the next pass's breaks, and so on, every pass undoing the last.

                     Never after a line that is itself bound to the next: by then it is too
                     late to move the run, and ending the page there would make the very
                     break the run exists to prevent. The run is measured before its first
                     line for that reason, including the first line of a \pstart. -->
                <xsl:for-each select="'L', 'R'">
                    <xsl:text>\apptocmd{\checkpage</xsl:text><xsl:value-of select="."/>
                    <xsl:text>}{\ifl@dsamepage\ifnum\numpagelines</xsl:text><xsl:value-of select="."/>
                    <xsl:text>>\z@\directlua{OSkeep.chain("</xsl:text><xsl:value-of select="."/>
                    <xsl:text>", \OS@rawbox{</xsl:text><xsl:value-of select="."/>
                    <xsl:text>}{\l@dpsc</xsl:text><xsl:value-of select="."/>
                    <xsl:text>}, \OS@rawbox{</xsl:text><xsl:value-of select="."/>
                    <xsl:text>}{\l@dpsc</xsl:text><xsl:value-of select="."/>
                    <xsl:text>+1}, \OS@rawbox{</xsl:text><xsl:value-of select="if (. = 'L') then 'R' else 'L'"/>
                    <xsl:text>}{\l@dpsc</xsl:text><xsl:value-of select="."/>
                    <xsl:text>})}\ifnum\OS@chainlines>\@ne\dimen@=\pagetotal\advance\dimen@\OS@chainht\OS@pagelines=\numpagelines</xsl:text><xsl:value-of select="."/>
                    <xsl:text>\advance\OS@pagelines\OS@chainlines\ifdim\dimen@&lt;\ledthegoal\ifnomaxlines\else\ifnum\OS@pagelines>\l@dminpagelines\l@dsamepagefalse\l@dpagefullfalse\fi\fi\else\l@dsamepagefalse\l@dpagefullfalse\fi\fi\fi\fi}{}{\PackageError{opensiddur}{could not patch reledpar's checkpage</xsl:text>
                    <xsl:value-of select="."/>
                    <xsl:text>}{}}&#10;</xsl:text>
                </xsl:for-each>
            </xsl:when>
            <xsl:otherwise>
                <!-- \checkpb@columns runs after every row: it settles whether the row
                     just set may be broken after, and the last row of a block hands that
                     on to the next block (\OSKeepNext). The \nobreak itself goes in front
                     of the next row's box, where that row's interline glue follows it
                     directly; a penalty only stops glue breaking when nothing stands
                     between them.

                     Taking a line off its column also puts what came with it on the page:
                     a language record (a \write) and the empty \splittopskip glue \vsplit
                     starts each piece with. That glue follows a \write and is therefore a
                     legal break whatever penalties surround it. It is empty, so it goes. -->
                <xsl:for-each select="'L', 'R'">
                    <xsl:text>\patchcmd{\do@line</xsl:text><xsl:value-of select="."/>
                    <xsl:text>}{\global\setbox\one@line</xsl:text><xsl:value-of select="if (. = 'R') then 'R' else ''"/>
                    <xsl:text>=\lastbox}{\global\setbox\one@line</xsl:text><xsl:value-of select="if (. = 'R') then 'R' else ''"/>
                    <xsl:text>=\lastbox\unskip}{}{\PackageError{opensiddur}{could not patch reledpar's do@line</xsl:text>
                    <xsl:value-of select="."/>
                    <xsl:text>}{}}&#10;</xsl:text>
                </xsl:for-each>
                <xsl:text>\newcount\OS@rowbound&#10;</xsl:text>
                <xsl:text>\renewcommand{\OSKeepRow}{\global\OS@rowbound\@ne}&#10;</xsl:text>
                <xsl:text>\apptocmd{\checkpb@columns}{\global\OS@rowbound\z@\ifnum\OS@rowkeep>\z@\global\OS@rowkeep\z@\global\advance\OS@keeprun\@ne\ifnum\OS@keeprun&lt;10 \ifaraw@text\global\OS@rowbound\@ne\else\OSKeepNext\fi\else\global\OS@keeprun\z@\fi\else\global\OS@keeprun\z@\fi}{}{\PackageError{opensiddur}{could not patch reledpar's checkpb@columns}{}}&#10;</xsl:text>
                <xsl:text>\patchcmd{\OSreledparColumnsOrig}{\hb@xt@ \hsize}{\ifnum\OS@rowbound>\z@\nobreak\fi\hb@xt@ \hsize}{}{\PackageError{opensiddur}{could not patch reledpar's Columns}{}}&#10;</xsl:text>
                <xsl:text>\pretocmd{\OSreledparColumnsOrig}{\global\OS@rowbound\z@\global\OS@keeprun\z@}{}{\PackageError{opensiddur}{could not patch reledpar's Columns}{}}&#10;</xsl:text>
            </xsl:otherwise>
        </xsl:choose>
        <xsl:text>\makeatother&#10;</xsl:text>
    </xsl:template>

    <!-- ====================================================================
         Interleaved: one numbered stream, each block followed by its translation.
         ==================================================================== -->

    <!-- The preamble the interleaved layout adds. \OSInterleavedSize, \OSInterleavedIndent,
         \OSInterleavedSpacing and \OSInterleavedNumbering are typography settings
         (InterleavedConfig in typography.py), defined by tex/typography_tex.py.

         The translation goes in an environment, i.e. a group, and that is where its
         settings take effect. It has to be outside the \pstart: \pstart gathers the
         paragraph in a group of its own and \pend closes it before the lines are set, so
         a \numberlinefalse inside would be gone by the time a line is counted. Inside the
         group \skipnumbering must be disarmed as well, or the heading or citation it
         precedes would pull back the count of the numbered text around it, which is why
         \OSInterleavedNumbering does both.

         \leftskip and \rightskip are advanced rather than set, keeping the stretch
         \raggedright puts in \rightskip.

         The seam is the one place the spacing between two paragraphs is not \parskip:
         the \pstart after it is the second half of a pair, and takes the closer
         \OSInterleavedSpacing instead. A flag rather than a skip emitted in place, so
         the hook still runs exactly once per \pstart. -->
    <xsl:template name="interleaved-preamble">
        <xsl:text>\newenvironment{OSInterleavedTranslation}{\OSInterleavedNumbering\OSInterleavedSize\advance\leftskip\OSInterleavedIndent\relax\advance\rightskip\OSInterleavedIndent\relax}{}&#10;</xsl:text>
        <xsl:text>\newif\ifOSInterleavedSeam&#10;</xsl:text>
        <xsl:text>\newcommand{\OSInterleavedSeam}{\global\OSInterleavedSeamtrue}&#10;</xsl:text>
        <xsl:text>\AtEveryPstart*{\OSApplyKeep\ifOSInterleavedSeam\global\OSInterleavedSeamfalse\vspace{\OSInterleavedSpacing}\else\vspace{\OSPstartSkip}\fi}&#10;</xsl:text>
    </xsl:template>

    <!-- A run of parallel blocks set one after another in a single numbered section:
         each block's first text, then its second, in the order @column-order gives.

         The unit is the block, the same unit the column layouts pair side by side, so a
         translation follows exactly the passage a column layout would set beside it.

         The two texts are prepared as whole streams, each with the other as its facing
         stream, exactly as the columns are. That keeps headings-from, instructions-from,
         bookmarks-from and the -alt running heads meaning what they mean in columns: the
         first text records into the primary mark classes and the second into the Alt
         ones. Only then is each stream cut back into its blocks, to be emitted in turn.

         One numbered section for the whole run, rather than one per block: reledmac
         writes auxiliary files for every section, and a book has thousands of blocks.
         Direction therefore changes between paragraphs inside the section, with each
         Hebrew segment in its own hebrew environment. -->
    <xsl:template name="parallel-interleaved">
        <xsl:param name="usable" as="element(p:parallel)*"/>
        <xsl:param name="spanning" as="xs:string" select="''"/>

        <xsl:if test="$spanning != ''">
            <xsl:call-template name="spanning-heading">
                <xsl:with-param name="block" select="$usable[1]"/>
            </xsl:call-template>
        </xsl:if>

        <xsl:if test="exists($usable)">
            <xsl:variable name="hoisted-divs" as="xs:string*"
                          select="if ($spanning != '') then f:spanning-heads($usable[1])/@div else ()"/>
            <xsl:variable name="first-nodes" as="node()*">
                <xsl:for-each select="$usable">
                    <xsl:sequence select="f:interleaved-nodes(., 1)"/>
                    <xsl:if test="position() != last()">
                        <f:block-break/>
                    </xsl:if>
                </xsl:for-each>
            </xsl:variable>
            <xsl:variable name="second-nodes" as="node()*">
                <xsl:for-each select="$usable">
                    <xsl:sequence select="f:interleaved-nodes(., 2)"/>
                    <xsl:if test="position() != last()">
                        <f:block-break/>
                    </xsl:if>
                </xsl:for-each>
            </xsl:variable>
            <xsl:variable name="first-leaves" as="node()*"
                          select="f:stream-leaves($first-nodes, $second-nodes, 'primary', false())"/>
            <xsl:variable name="second-leaves" as="node()*"
                          select="f:stream-leaves($second-nodes, $first-nodes, 'alt', false())"/>
            <xsl:variable name="first-breaks" as="xs:integer*"
                          select="index-of($first-leaves ! exists(self::f:block-break), true())"/>
            <xsl:variable name="second-breaks" as="xs:integer*"
                          select="index-of($second-leaves ! exists(self::f:block-break), true())"/>
            <xsl:if test="count($first-breaks) + 1 != count($usable)
                          or count($second-breaks) + 1 != count($usable)">
                <xsl:message terminate="yes">
                    <xsl:text>interleaved layout: block boundaries were lost preparing the streams</xsl:text>
                </xsl:message>
            </xsl:if>

            <xsl:variable name="body" as="xs:string*">
                <xsl:for-each select="1 to count($usable)">
                    <xsl:variable name="i" as="xs:integer" select="."/>
                    <xsl:variable name="block" as="element(p:parallel)" select="$usable[$i]"/>
                    <xsl:variable name="first-tex" as="xs:string">
                        <xsl:call-template name="interleaved-segment">
                            <xsl:with-param name="leaves"
                                            select="f:segment($first-leaves, $first-breaks, $i)"/>
                            <xsl:with-param name="item" select="f:interleaved-item($block, 1)"/>
                            <xsl:with-param name="stream" select="'primary'"/>
                            <xsl:with-param name="hoisted-heading" select="$spanning"/>
                            <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
                        </xsl:call-template>
                    </xsl:variable>
                    <xsl:variable name="second-tex" as="xs:string">
                        <xsl:call-template name="interleaved-segment">
                            <xsl:with-param name="leaves"
                                            select="f:segment($second-leaves, $second-breaks, $i)"/>
                            <xsl:with-param name="item" select="f:interleaved-item($block, 2)"/>
                            <xsl:with-param name="stream" select="'alt'"/>
                            <xsl:with-param name="hoisted-heading" select="$spanning"/>
                            <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
                        </xsl:call-template>
                    </xsl:variable>
                    <xsl:sequence select="$first-tex"/>
                    <!-- Only between two texts that each set a paragraph: a seam with no
                         paragraph after it would carry its spacing into the next block. -->
                    <xsl:if test="contains($first-tex, '\pstart') and contains($second-tex, '\pstart')">
                        <xsl:sequence select="'\OSInterleavedSeam&#10;'"/>
                    </xsl:if>
                    <xsl:sequence select="$second-tex"/>
                </xsl:for-each>
            </xsl:variable>
            <xsl:variable name="tex" as="xs:string" select="string-join($body, '')"/>
            <!-- reledmac refuses a numbered section with no \pstart in it, and a group that
                 is only a hoisted heading's marks has none. -->
            <xsl:value-of select="f:collapse-blank-lines(
                                      if (contains($tex, '\pstart'))
                                      then concat('\beginnumbering&#10;', $tex, '\endnumbering&#10;')
                                      else $tex)"/>
        </xsl:if>
    </xsl:template>

    <!-- The parallelItem a block sets first (1) or second (2), by its @column-order. -->
    <xsl:function name="f:interleaved-item" as="element()?">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:param name="which" as="xs:integer"/>
        <xsl:variable name="primary" select="$block/p:parallelItem[@role='primary'][1]"/>
        <xsl:variable name="secondary" select="$block/p:parallelItem[@role='parallel'][1]"/>
        <xsl:sequence select="if (($which = 1) = ($block/@column-order = 'primary_last'))
                              then $secondary else $primary"/>
    </xsl:function>

    <!-- What a block sets first (1) or second (2). A block with text in one language
         gives that text, with the other item's notes in it, and nothing for the other:
         an item of notes alone would otherwise be set as a translation paragraph holding
         nothing but their marks. -->
    <xsl:function name="f:interleaved-nodes" as="node()*">
        <xsl:param name="block" as="element(p:parallel)"/>
        <xsl:param name="which" as="xs:integer"/>
        <xsl:variable name="item" select="f:interleaved-item($block, $which)"/>
        <xsl:sequence select="if (f:parallel-row-kind($block) = 'columns') then $item/node()
                              else if ($item is f:single-item($block))
                              then f:single-row-leaves($block)
                              else ()"/>
    </xsl:function>

    <!-- The $i-th of the segments $leaves is cut into at the positions $breaks. -->
    <xsl:function name="f:segment" as="node()*">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:param name="breaks" as="xs:integer*"/>
        <xsl:param name="i" as="xs:integer"/>
        <xsl:variable name="from" select="if ($i = 1) then 1 else $breaks[$i - 1] + 1"/>
        <xsl:variable name="to"
                      select="if ($i le count($breaks)) then $breaks[$i] - 1 else count($leaves)"/>
        <xsl:sequence select="subsequence($leaves, $from, $to - $from + 1)"/>
    </xsl:function>

    <!-- One block's text in one language, as the paragraphs of a single stream. A
         translation is wrapped in OSInterleavedTranslation, which sets it apart and
         decides whether its lines are numbered; a Hebrew text in the hebrew environment,
         inside that, since the direction belongs to the paragraphs themselves. -->
    <xsl:template name="interleaved-segment" as="xs:string">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:param name="item" as="element()?"/>
        <xsl:param name="stream" as="xs:string"/>
        <xsl:param name="hoisted-heading" as="xs:string"/>
        <xsl:param name="hoisted-divs" as="xs:string*"/>
        <xsl:variable name="inner" as="xs:string">
            <xsl:value-of>
                <xsl:call-template name="emit-leaves">
                    <xsl:with-param name="leaves" select="$leaves"/>
                    <xsl:with-param name="stream" select="$stream"/>
                    <xsl:with-param name="has-alt-column" select="true()"/>
                    <xsl:with-param name="hoisted-heading" select="$hoisted-heading"/>
                    <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
                    <xsl:with-param name="interleaved" select="true()"/>
                </xsl:call-template>
            </xsl:value-of>
        </xsl:variable>
        <xsl:variable name="translation" as="xs:boolean" select="$item/@role = 'parallel'"/>
        <xsl:variable name="hebrew" as="xs:boolean"
                      select="f:is-hebrew-lang(string($item/@xml:lang))"/>
        <xsl:variable name="sets-text" as="xs:boolean" select="contains($inner, '\pstart')"/>
        <xsl:value-of>
            <xsl:if test="$sets-text and $translation">
                <xsl:text>\begin{OSInterleavedTranslation}&#10;</xsl:text>
            </xsl:if>
            <xsl:if test="$sets-text and $hebrew">
                <xsl:text>\begin{hebrew}&#10;</xsl:text>
            </xsl:if>
            <xsl:value-of select="$inner"/>
            <xsl:if test="$sets-text and $hebrew">
                <xsl:text>\end{hebrew}&#10;</xsl:text>
            </xsl:if>
            <xsl:if test="$sets-text and $translation">
                <xsl:text>\end{OSInterleavedTranslation}&#10;</xsl:text>
            </xsl:if>
        </xsl:value-of>
    </xsl:template>

    <!-- No vertical glue may survive inside a parallel \pstart.

         \Columns takes each side one slice at a time (\vsplit ... to\baselineskip) and
         then \unvbox-es that slice onto the enclosing vertical list — which is the
         full-width page list — keeping only its \lastbox as the column's line. Glue in
         the slice is left behind there, between two full-width rows, so it displaces
         BOTH columns. A \parskip after a paragraph inside one column therefore opened a
         gap in the middle of the facing column's paragraph.

         Zeroing it here is enough because a \par with no \parskip contributes only
         interline glue, which the \vsplit consumes exactly. Leftside and Rightside are
         LaTeX environments, hence groups, so this reaches the raw-box construction and
         nothing else — the single-column body and the bibliography keep \parskip. -->
    <xsl:template name="column-glue-reset">
        <xsl:text>\setlength{\parskip}{0pt}&#10;</xsl:text>
    </xsl:template>

    <xsl:template name="parallel-side">
        <xsl:param name="item" as="element()?"/>
        <xsl:variable name="lang" select="string($item/@xml:lang)"/>

        <xsl:call-template name="numbered-stream">
            <xsl:with-param name="nodes" select="$item/node()"/>
            <xsl:with-param name="lang" select="$lang"/>
            <xsl:with-param name="align-verses" select="false()"/>
            <xsl:with-param name="single-pstart" select="false()"/>
        </xsl:call-template>
    </xsl:template>

    <!-- ====================================================================
         Numbered stream: emit \beginnumbering...\endnumbering with verse-level
         \pstart/\pend pairs, derived from a flattened leaf sequence.
         For Hebrew streams, wrap the whole numbering block in \begin{hebrew}
         so polyglossia handles direction and font for everything inside.
         ==================================================================== -->

    <!-- Every \pstart in the emitted document goes through here.

         reledmac declares \newcommandx*{\pstart}[2][1,2,usedefault] — two optional,
         bracket-delimited arguments — and TeX skips spaces and newlines while scanning
         for one. So a paragraph whose first character is "[" is read as \pstart's
         argument and *executed* rather than typeset. Birnbaum's "[We pray] for Israel"
         came out as a bare "We pray" set in the gutter outside the column, with the
         brackets consumed as delimiters and the paragraph beginning at "for"; the
         Feinstein haggadah's "[This verse can be explained as follows:]" is the same.

         Nothing downstream catches it: the \pstart counts still pair side for side, so
         every alignment assertion stays green while the words are set outside the column.

         \relax is not "[", so the scan stops at it, and it typesets nothing. It has to be
         emitted unconditionally rather than only for paragraphs that happen to start with
         a bracket — the emission sites below do not all know what follows them, and the
         one that forgot would reopen this. -->
    <xsl:template name="pstart">
        <xsl:text>\pstart\relax </xsl:text>
    </xsl:template>

    <!-- Source whitespace must never reach the output as a blank line. This stylesheet
         separates paragraphs with an explicit \par (the f:para-break branch below) or a
         \newline, and never with a blank line: there is not one &#10;&#10; in the file.
         But pretty-printed source puts a newline between two siblings and another at the
         head of the second, and the two meet in the output. A note that annotates the
         block after it —

             </tei:note>&#10;<tei:p>&#10;Exalt the Lord with me...

         — is one whitespace leaf followed by a content leaf opening with a newline, and
         together they are a blank line, i.e. \par. The anchor has already begun the
         paragraph with \leavevmode, so that \par spends a row on the mark alone and
         starts the text on the next one. In a parallel block the facing column, where the
         same whitespace lands in vertical mode and is discarded, does not spend that row,
         and the two columns drift apart by one line.

         The two newlines belong to different leaves, so no per-leaf template can see both,
         and rewriting the content leaf is not open to us: the emit templates read the
         ancestor and preceding axes of the original node — note serials off
         f:editorial-note-emissions-before, in-scope language, list membership — so a leaf
         has to reach them as itself, which is the constraint f:resolve-markers is written
         to. The join is only visible once the leaves are text, which is here.

         One newline, not none. A newline is a space in TeX, and between two leaves it is
         often the only thing separating two words; collapsing keeps that space and drops
         only the break. It also keeps a \par out of \Bfootnote content, which breaks
         reledmac's apparatus grouping.

         Scoped to a stream on purpose: $additional-preamble and $additional-postamble are
         written elsewhere and do use blank lines deliberately — the embedded bibliography
         ends every record with one, and the licence block sets paragraphs with them — so the
         invariant is this stylesheet's own, not theirs. -->
    <xsl:template name="numbered-stream">
        <xsl:param name="nodes" as="node()*"/>
        <xsl:param name="lang" as="xs:string?" select="''"/>
        <xsl:param name="align-verses" as="xs:boolean" select="false()"/>
        <xsl:param name="single-pstart" as="xs:boolean" select="false()"/>
        <xsl:param name="stream" as="xs:string" select="'primary'"/>
        <xsl:param name="alt-nodes" as="node()*" select="()"/>
        <xsl:param name="hoisted-heading" as="xs:string" select="''"/>
        <!-- The divisions whose headings are set across the page above this stream, by
             @div. Their notes are set there too. See spanning-heading. -->
        <xsl:param name="hoisted-divs" as="xs:string*" select="()"/>

        <!-- The whole body, not just its xsl:iterate: a partial capture would leave a seam
             (\beginnumbering&#10; against a leading whitespace leaf) across which a blank
             line could still form. -->
        <xsl:variable name="tex">
            <xsl:call-template name="numbered-stream-body">
                <xsl:with-param name="nodes" select="$nodes"/>
                <xsl:with-param name="lang" select="$lang"/>
                <xsl:with-param name="align-verses" select="$align-verses"/>
                <xsl:with-param name="single-pstart" select="$single-pstart"/>
                <xsl:with-param name="stream" select="$stream"/>
                <xsl:with-param name="alt-nodes" select="$alt-nodes"/>
                <xsl:with-param name="hoisted-heading" select="$hoisted-heading"/>
                <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
            </xsl:call-template>
        </xsl:variable>
        <xsl:value-of select="f:collapse-blank-lines(string($tex))"/>
    </xsl:template>

    <xsl:template name="numbered-stream-body">
        <xsl:param name="nodes" as="node()*"/>
        <xsl:param name="lang" as="xs:string?" select="''"/>
        <!-- When true, emit one \pstart...\pend per verse (required for reledpar
             alignment across two streams). When false, emit paragraph-level
             \pstart blocks and render verse numbers inline with \vno{n}. -->
        <xsl:param name="align-verses" as="xs:boolean" select="false()"/>
        <!-- When true, force exactly one \pstart...\pend for the entire stream
             (used for parallel blocks where verse-level pstart pairing is not desired). -->
        <xsl:param name="single-pstart" as="xs:boolean" select="false()"/>
        <!-- Which family of running-head mark classes this stream records into:
             'primary' for a single text or the first parallel column, 'alt' for
             the second column. See the mark declarations in the preamble. -->
        <xsl:param name="stream" as="xs:string" select="'primary'"/>
        <!-- The other column's nodes, when this stream is one side of a parallel block.
             Only their headings are read, and only to give this stream's headings the
             title of the same section in the other language. -->
        <xsl:param name="alt-nodes" as="node()*" select="()"/>
        <!-- A title already set across the page, above these columns. The first heading
             carrying it is suppressed here so it is not set a second time inside one. -->
        <xsl:param name="hoisted-heading" as="xs:string" select="''"/>
        <!-- The divisions whose headings are set across the page above this stream, by
             @div. Their notes are set there too. See spanning-heading. -->
        <xsl:param name="hoisted-divs" as="xs:string*" select="()"/>

        <xsl:variable name="leaves" as="node()*"
                      select="f:stream-leaves($nodes, $alt-nodes, $stream, $single-pstart)"/>

        <xsl:if test="exists($leaves)">
            <xsl:variable name="inner">
                <xsl:if test="$single-pstart">
                    <!-- reledpar requires at least one \pstart...\pend in each side.
                         When single-pstart is requested, open it up-front so even
                         chapter-only or whitespace-leading blocks satisfy this. -->
                    <xsl:call-template name="pstart"/>
                </xsl:if>

                <xsl:call-template name="emit-leaves">
                    <xsl:with-param name="leaves" select="$leaves"/>
                    <xsl:with-param name="align-verses" select="$align-verses"/>
                    <xsl:with-param name="single-pstart" select="$single-pstart"/>
                    <xsl:with-param name="stream" select="$stream"/>
                    <xsl:with-param name="has-alt-column" select="exists($alt-nodes)"/>
                    <xsl:with-param name="hoisted-heading" select="$hoisted-heading"/>
                    <xsl:with-param name="hoisted-divs" select="$hoisted-divs"/>
                </xsl:call-template>
            </xsl:variable>

            <!-- XML leaves can be only structural whitespace, paragraph breaks or
                 silent milestones, as between transclusions in Birnbaum's full index.
                 reledmac rejects numbering with no paragraph. Test the rendered stream,
                 retaining any out-of-paragraph output (separators, heading marks).
                 single-pstart still guarantees a paragraph for each parallel side. -->
            <xsl:variable name="has-paragraph" as="xs:boolean"
                          select="contains($inner, '\pstart')"/>
            <xsl:if test="f:is-hebrew-lang(string($lang))">
                <xsl:text>\begin{hebrew}&#10;</xsl:text>
            </xsl:if>
            <xsl:if test="$has-paragraph">
                <xsl:text>\beginnumbering&#10;</xsl:text>
            </xsl:if>
            <xsl:value-of select="$inner"/>
            <xsl:if test="$has-paragraph">
                <xsl:text>\endnumbering&#10;</xsl:text>
            </xsl:if>

            <xsl:if test="f:is-hebrew-lang(string($lang))">
                <xsl:text>\end{hebrew}&#10;</xsl:text>
            </xsl:if>
        </xsl:if>
    </xsl:template>

    <!-- Set a prepared leaf sequence (see f:stream-leaves) as \pstart...\pend paragraphs.
         The caller supplies the surrounding \beginnumbering, and the opening \pstart
         when $single-pstart asks for one to be open already. -->
    <xsl:template name="emit-leaves">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:param name="align-verses" as="xs:boolean" select="false()"/>
        <xsl:param name="single-pstart" as="xs:boolean" select="false()"/>
        <xsl:param name="stream" as="xs:string" select="'primary'"/>
        <!-- Whether there is a facing stream. See name="heading". -->
        <xsl:param name="has-alt-column" as="xs:boolean" select="false()"/>
        <xsl:param name="hoisted-heading" as="xs:string" select="''"/>
        <!-- The divisions whose headings are set across the page above this stream, by
             @div. Their notes are set there too. See spanning-heading. -->
        <xsl:param name="hoisted-divs" as="xs:string*" select="()"/>
        <!-- Whether this is one text of an interleaved block. See parallel-interleaved. -->
        <xsl:param name="interleaved" as="xs:boolean" select="false()"/>

        <!-- Notes on a whole headed division, by the division they are on. They are held
             back from the flow and set with the division's heading instead, after its
             title: in the flow they stood between the heading and the text, a mark on a
             line of its own. Only for a heading that is in this stream; anything else
             keeps its place. -->
        <xsl:variable name="head-divs" as="xs:string*"
                      select="distinct-values($leaves[self::f:head]/@div)"/>
        <xsl:variable name="notes-by-div" as="map(xs:string, element()*)">
            <xsl:map>
                <xsl:for-each-group select="$leaves[f:is-head-note(.)]"
                                    group-by="generate-id(f:head-note-div(.))">
                    <xsl:if test="current-grouping-key() = $head-divs">
                        <!-- In the order they are numbered: a note on the division can stand
                             before its heading, and the heading's own notes come after it. -->
                        <xsl:map-entry key="current-grouping-key()">
                            <xsl:perform-sort select="current-group()">
                                <xsl:sort select="f:note-serial(.)" data-type="number"/>
                            </xsl:perform-sort>
                        </xsl:map-entry>
                    </xsl:if>
                </xsl:for-each-group>
            </xsl:map>
        </xsl:variable>
        <xsl:iterate select="$leaves">
            <xsl:param name="in-pstart" as="xs:boolean" select="$single-pstart"/>
            <xsl:on-completion>
                <xsl:if test="$in-pstart">
                    <xsl:text>\pend&#10;</xsl:text>
                </xsl:if>
            </xsl:on-completion>
            <xsl:choose>
                <xsl:when test="self::text() and not(normalize-space(.)) and not($in-pstart)">
                    <!-- Whitespace-only text outside a pstart is structural whitespace
                         between sections/paragraphs; TeX handles its own spacing. -->
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="false()"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::tei:milestone[@unit='chapter']">
                    <!-- A chapter milestone is not a heading. Inside a Bible book the
                         chapter has no other representation, so mark it inline; elsewhere
                         (e.g. a psalm quoted in a liturgical text) the surrounding
                         tei:head already names the section and a chapter number would be
                         noise, so render nothing. -->
                    <!-- The running-head mark is recorded either way: a header
                         asking for the chapter number wants it even where the
                         number itself is deliberately not printed. It must not
                         open a \pstart of its own — that would desync the two
                         sides' \pstart counts under reledpar — but a mark
                         between \pend and \pstart is harmless. -->
                    <!-- One class for both streams, unsuffixed: parallel columns
                         carry the same chapter numbers, so there is nothing for a
                         per-stream class to distinguish.

                         The digits go through f:emit-bidi-mark for the same
                         reason \chno wraps them below: a slot that declares
                         Hebrew forces RTL, and bare digits are laid out in
                         that direction, so chapter 50 reads "05". -->
                    <xsl:text>\InsertMark{OSchapter}{</xsl:text>
                    <xsl:value-of select="f:emit-bidi-mark(string(@n))"/>
                    <xsl:text>}</xsl:text>
                    <xsl:choose>
                        <xsl:when test="ancestor::tei:div[@type='book']">
                            <xsl:if test="not($in-pstart)">
                                <xsl:call-template name="pstart"/>
                            </xsl:if>
                            <xsl:text>\chno{</xsl:text>
                            <xsl:choose>
                                <xsl:when test="matches(string(@n), '^[0-9]+$')">
                                    <!-- Force LTR digits in Hebrew RTL contexts -->
                                    <xsl:text>{\textdir TLT\foreignlanguage{english}{</xsl:text>
                                    <xsl:value-of select="f:escape-tex(string(@n))"/>
                                    <xsl:text>}}</xsl:text>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:value-of select="f:escape-tex(string(@n))"/>
                                </xsl:otherwise>
                            </xsl:choose>
                            <xsl:text>}</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="$in-pstart"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::tei:milestone[@unit='citation']">
                    <!-- A scriptural citation the humash generator inserts to state a
                         haftarah/festival reading's source, or to mark where it resumes
                         after a backward jump or a skip (build._citation). It is not a
                         tei:head — it earns no bookmark entry, being a caption on a
                         reading already headed by its own tei:head — but it is treated
                         the way a heading is for reledpar column-pairing: only the
                         Hebrew source carries this milestone (an English/JPS column has
                         no matching one), so closing and reopening the pstart here would
                         desync the two sides' \pstart counts. Stay inside whatever is
                         already open in single-pstart (parallel) mode, the way f:head
                         does above. -->
                    <xsl:choose>
                        <xsl:when test="$single-pstart">
                            <xsl:choose>
                                <xsl:when test="$in-pstart">
                                    <xsl:text>\par&#10;</xsl:text>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:call-template name="pstart"/>
                                </xsl:otherwise>
                            </xsl:choose>
                            <xsl:text>\OScitation{</xsl:text>
                            <xsl:value-of select="f:emit-bidi-text(string(@n))"/>
                            <xsl:text>}</xsl:text>
                            <xsl:text>\par&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <xsl:call-template name="pstart"/><xsl:text>\skipnumbering&#10;</xsl:text>
                            <xsl:text>\OScitation{</xsl:text>
                            <xsl:value-of select="f:emit-bidi-text(string(@n))"/>
                            <xsl:text>}</xsl:text>
                            <xsl:text>&#10;\pend&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="false()"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::tei:milestone[@unit='verse']">
                    <xsl:choose>
                        <xsl:when test="$align-verses">
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <xsl:call-template name="pstart"/><xsl:text>\vno{</xsl:text>
                            <xsl:value-of select="f:verse-number-label(string(@n))"/>
                            <xsl:text>}</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <!-- Non-parallel flow: keep verse numbers inline so
                                 prose/paragraph formatting is preserved. -->
                            <xsl:if test="not($in-pstart)">
                                <xsl:call-template name="pstart"/>
                            </xsl:if>
                            <xsl:text>\vno{</xsl:text>
                            <xsl:value-of select="f:verse-number-label(string(@n))"/>
                            <xsl:text>}</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::tei:milestone[
                        starts-with(@unit, 'aliyah') or starts-with(@unit, 'maftir')]">
                    <!-- Aliyah, maftir, weekday and triennial markers, inline at the
                         verse the division begins on. See \OSaliyah in the preamble for
                         why these are inline and not breaks. -->
                    <xsl:if test="not($in-pstart)">
                        <xsl:call-template name="pstart"/>
                    </xsl:if>
                    <xsl:text>\OSaliyah{</xsl:text>
                    <xsl:value-of select="f:escape-tex(string(@n))"/>
                    <xsl:text>}</xsl:text>
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="true()"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::tei:milestone[starts-with(@unit, 'parsha.')]">
                    <!-- A qualified parsha unit (parsha.annual) comes from the humash,
                         where every parshah is a tei:div with a tei:head carrying its
                         name. Rendering the milestone too would print the name twice, so
                         it is left to the heading. The unqualified @unit='parsha' below
                         is the wlc/jps1917 case, where there is no such heading. -->
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="$in-pstart"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::tei:milestone[@unit='parsha']">
                    <!-- Parsha boundary: a division that contains the chapters and
                         verses following it, so it legitimately sits *between*
                         paragraphs. Open a pstart when none is open, the way the
                         chapter and verse branches do — a boundary outside a pstart
                         would otherwise be silently dropped. Leaving in-pstart true
                         is what makes the name run in: the following paragraph's
                         chapter/verse milestones join this pstart rather than opening
                         their own, so the name shares a line with the parsha's first
                         verse. -->
                    <xsl:if test="not($in-pstart)">
                        <xsl:call-template name="pstart"/>
                    </xsl:if>
                    <xsl:text>\OSParsha{</xsl:text>
                    <xsl:choose>
                        <!-- Parsha names are Hebrew in an otherwise LTR stream (the
                             JPS 1917 translation), so give them the same direction
                             wrapper tei:foreign[@xml:lang='he'] gets. Wrapping here
                             rather than inside the macro keeps it in place for a
                             caller's \renewcommand. -->
                        <xsl:when test="matches(string(@n), '\p{IsHebrew}')">
                            <xsl:text>\texthebrew{</xsl:text>
                            <xsl:value-of select="f:escape-tex(string(@n))"/>
                            <xsl:text>}</xsl:text>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="f:escape-tex(string(@n))"/>
                        </xsl:otherwise>
                    </xsl:choose>
                    <xsl:text>}</xsl:text>
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="true()"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::tei:milestone[@rend='****']">
                    <xsl:if test="$in-pstart">
                        <xsl:text>\pend&#10;</xsl:text>
                    </xsl:if>
                    <xsl:text>\OSSectionSeparator&#10;</xsl:text>
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="false()"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::tei:milestone">
                    <!-- A milestone this stylesheet does not set: unit="edition-verse",
                         which records an edition's own verse numbering beside the
                         canonical one, and anything else a source marks but a printed
                         page does not show. Falling through to the generic branch would
                         open a \pstart that then receives no text, and reledmac cannot
                         set an empty paragraph — it dies with "You can't use \lastbox in
                         vertical mode". Skip it, leaving any open pstart as it is. -->
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="$in-pstart"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::f:head">
                    <xsl:choose>
                        <xsl:when test="$single-pstart">
                            <!-- reledpar pairs the two sides by \pstart count. Closing and
                                 reopening here would desync the columns whenever only one
                                 side carries a head, so stay inside the open pstart. -->
                            <xsl:choose>
                                <xsl:when test="$in-pstart">
                                    <!-- End the paragraph the heading interrupts. When the
                                         pstart was only just opened there is nothing to end,
                                         and a leading \par would leave an empty first
                                         paragraph that throws off the column layout. -->
                                    <xsl:text>\par&#10;</xsl:text>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:call-template name="pstart"/>
                                </xsl:otherwise>
                            </xsl:choose>
                            <!-- Tagged as a heading, every line of it, so that the
                                 column keeps it whole and with what follows; see
                                 column-keep-preamble. -->
                            <xsl:text>\OSKeepHeadBegin </xsl:text>
                            <xsl:call-template name="heading">
                                <xsl:with-param name="stream" select="$stream"/>
                                <xsl:with-param name="has-alt-column"
                                                select="$has-alt-column"/>
                                <xsl:with-param name="hoisted-heading"
                                                select="$hoisted-heading"/>
                                <xsl:with-param name="notes"
                                                select="f:own-head-notes(., $notes-by-div, $hoisted-divs)"/>
                            </xsl:call-template>
                            <xsl:text>\OSKeepHeadEnd\par&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:when test="$interleaved and not(f:alt-head)
                                        and not(f:sets-heading(., $stream, $hoisted-heading))
                                        and empty(f:own-head-notes(., $notes-by-div, $hoisted-divs))">
                            <!-- A heading this text does not set, because the other text
                                 of the block already does. Columns keep a placeholder
                                 paragraph so reledpar's \pstart counts stay paired; one
                                 stream has no pairing to keep, and a placeholder would only
                                 open a blank line between the original and its
                                 translation. Only the marks and the outline entry remain,
                                 set between paragraphs as the chapter marks are. -->
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <xsl:call-template name="heading">
                                <xsl:with-param name="stream" select="$stream"/>
                                <xsl:with-param name="has-alt-column" select="$has-alt-column"/>
                                <xsl:with-param name="hoisted-heading" select="$hoisted-heading"/>
                                <xsl:with-param name="marks-only" select="true()"/>
                            </xsl:call-template>
                            <xsl:text>&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="false()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <!-- The heading gets its own paragraph in the numbered stream,
                                 excluded from line numbering. It is kept whole, however
                                 many lines its title and translation run to, and kept
                                 with the paragraph after it; see \OSKeepNext. -->
                            <xsl:text>\begingroup\interlinepenalty=10000\relax&#10;</xsl:text>
                            <xsl:call-template name="pstart"/><xsl:text>\skipnumbering&#10;</xsl:text>
                            <xsl:call-template name="heading">
                                <xsl:with-param name="stream" select="$stream"/>
                                <xsl:with-param name="has-alt-column"
                                                select="$has-alt-column"/>
                                <xsl:with-param name="hoisted-heading"
                                                select="$hoisted-heading"/>
                                <xsl:with-param name="notes"
                                                select="f:own-head-notes(., $notes-by-div, $hoisted-divs)"/>
                            </xsl:call-template>
                            <xsl:text>&#10;\pend\endgroup\OSKeepNext&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="false()"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::f:list-label">
                    <!-- The label naming a list item. Placed the way f:head is — it is
                         the same problem, a short phrase that must have a line of its
                         own — but it is not a heading and must not be mistaken for
                         one: no \InsertMark, so it never reaches a running head, and
                         no \addcontentsline, so it claims no place in the PDF outline.
                         A list label names an alternative inside a section; it does not
                         open a section. -->
                    <xsl:choose>
                        <xsl:when test="$single-pstart">
                            <!-- reledpar pairs the two sides by \pstart count, and a
                                 list is exactly the kind of thing only one side
                                 carries, so closing and reopening here would desync
                                 the columns. Stay inside whatever is open, as f:head
                                 does above. -->
                            <xsl:choose>
                                <xsl:when test="$in-pstart">
                                    <xsl:text>\par&#10;</xsl:text>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:call-template name="pstart"/>
                                </xsl:otherwise>
                            </xsl:choose>
                            <xsl:call-template name="list-label"/>
                            <xsl:text>\par&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <!-- Its own paragraph, out of the line numbering: the
                                 label is apparatus for the item, and numbering it
                                 would cite it as a line of the text. -->
                            <xsl:call-template name="pstart"/><xsl:text>\skipnumbering&#10;</xsl:text>
                            <xsl:call-template name="list-label"/>
                            <xsl:text>&#10;\pend&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="false()"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::f:para-break">
                    <!-- Paragraph boundary: end current pstart, but don't open a new
                         one until we see actual content. -->
                    <xsl:choose>
                        <xsl:when test="$align-verses">
                            <!-- Verse-aligned mode: paragraph breaks must not affect \pstart counts,
                                 otherwise the two sides can desync. -->
                            <xsl:text>\par&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="$in-pstart"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:when test="$single-pstart and $in-pstart">
                            <!-- Keep the single block open; just start a new paragraph.

                                 The separation is a blank line rather than a skip
                                 because a skip would not stay in this column — see
                                 the column-glue-reset template. One line is also the
                                 smallest column-local vertical unit reledpar has:
                                 \Columns advances both sides a row at a time, so
                                 anything shorter is either discarded at the slice
                                 boundary or leaks onto the shared page list. The two
                                 columns drift by these lines within a block and come
                                 back together at the next \pstart, which is the only
                                 alignment the encoder actually declared.

                                 \skipnumbering keeps the blank line out of the margin
                                 numbering, and \mbox{} keeps it non-empty: reledmac
                                 cannot set an empty paragraph and dies on the whole
                                 build when asked to.

                                 The \strut is what makes it a line rather than a leak.
                                 \Columns cuts each column into slices of \baselineskip;
                                 a box of no height leaves the interline glue before it
                                 inside its own slice instead of at the cut, and that
                                 glue is then \unvbox-ed onto the shared page list — the
                                 very displacement this is meant to avoid. A strut gives
                                 the line the height and depth of ordinary text, so the
                                 slice ends where the machinery expects.

                                 \OSKeepSep is that \mbox{\strut}, tagged as a separator
                                 so the column's widow and orphan rules can see where its
                                 paragraphs end; see column-keep-preamble. -->
                            <xsl:text>\par\skipnumbering\OSKeepSep\par&#10;</xsl:text>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="false()"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="self::f:block-break">
                    <!-- Parallel-block boundary: close and reopen so reledpar can pair
                         one \pstart...\pend per parallel block across sides. -->
                    <xsl:choose>
                        <xsl:when test="$align-verses">
                            <!-- Verse-aligned mode: ignore block boundaries; verses define alignment units. -->
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="$in-pstart"/>
                            </xsl:next-iteration>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:if test="$in-pstart">
                                <xsl:text>\pend&#10;</xsl:text>
                            </xsl:if>
                            <xsl:call-template name="pstart"/>
                            <xsl:next-iteration>
                                <xsl:with-param name="in-pstart" select="true()"/>
                            </xsl:next-iteration>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="f:is-head-note(.)
                                and generate-id(f:head-note-div(.)) = $head-divs">
                    <!-- Set with its division's heading; see $notes-by-div. -->
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="$in-pstart"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:if test="not($in-pstart)">
                        <xsl:call-template name="pstart"/>
                        <!-- Indent the paragraphs of a list item, so an item reads as
                             a block set off from the prose around it rather than as
                             more of the same prose. Pass 1 emits leaves as the source
                             nodes themselves (xsl:sequence, not a copy), so a leaf
                             still knows whether it came from inside a tei:item.
                             Only this branch needs it: an item holds text and inline
                             markup, never the chapter or verse milestones that open a
                             \pstart in the branches above.

                             Single-column streams only, which is where labelled lists
                             are used: front matter is never parallel. Under
                             $single-pstart the whole side is one \pstart that is
                             already open, so there is no paragraph head to set the
                             skip at, and setting it mid-block would leak past the end
                             of the item — \leftskip would stay in force for the rest
                             of the \pstart, indenting the prose after the list too.
                             A parallel item is set flush; its label still separates
                             it. -->
                        <xsl:if test="ancestor::tei:item">
                            <xsl:text>\OSListItemPar </xsl:text>
                        </xsl:if>
                    </xsl:if>
                    <xsl:apply-templates select="." mode="emit"/>
                    <xsl:next-iteration>
                        <xsl:with-param name="in-pstart" select="true()"/>
                    </xsl:next-iteration>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:iterate>
    </xsl:template>

    <!-- The leaves one stream sets, ready for emit-leaves: flattened, with its markers
         resolved and, when a facing stream is given, its headings and rubrics paired with
         that stream's. $trim drops paragraph breaks that separate nothing, which only a
         single-\pstart stream needs. -->
    <xsl:function name="f:stream-leaves" as="node()*">
        <xsl:param name="nodes" as="node()*"/>
        <xsl:param name="alt-nodes" as="node()*"/>
        <xsl:param name="stream" as="xs:string"/>
        <xsl:param name="trim" as="xs:boolean"/>
        <xsl:variable name="flattened" as="node()*">
            <xsl:apply-templates select="$nodes" mode="leaves"/>
        </xsl:variable>
        <!-- Silent conditional delimiters and repeated labels are decided here, where the
             leaves either side of a marker are in view. See f:resolve-markers. -->
        <xsl:variable name="resolved" as="node()*" select="f:resolve-markers($flattened)"/>
        <xsl:variable name="alt-flattened" as="node()*">
            <xsl:if test="exists($alt-nodes)">
                <xsl:apply-templates select="$alt-nodes" mode="leaves"/>
            </xsl:if>
        </xsl:variable>
        <xsl:variable name="alt-heads" as="element()*"
                      select="$alt-flattened[self::f:head]"/>
        <!-- A rubric is as often inside a j:conditional as beside one — the marker and
             the sentence it explains travel together — and a conditional reaches the leaf
             stream whole. So rubrics are gathered from within the leaves, not only from
             among them. -->
        <xsl:variable name="alt-instructions" as="xs:string*"
                      select="for $n in $alt-flattened
                                        /descendant-or-self::tei:note[@type = ('instruction', 'description')]
                              return normalize-space(string($n))"/>
        <!-- 'both' keeps every rubric where it is. 'combined' drops from the second
             column only what the first already says in the same words, so two rubrics
             that differ are both kept. 'primary' and 'alt' name a column and mean it:
             the other column's rubric goes whether or not it says something different,
             which is what naming one column asks for. -->
        <xsl:variable name="drop-rubrics" as="xs:string"
                      select="if ($instructions-from = 'both') then 'none'
                              else if ($instructions-from = 'combined')
                              then (if ($stream = 'alt') then 'matching' else 'none')
                              else if ($instructions-from = 'primary')
                              then (if ($stream = 'alt') then 'all' else 'none')
                              else (if ($stream = 'primary') then 'all' else 'none')"/>
        <xsl:variable name="paired" as="node()*"
                      select="if (exists($alt-flattened))
                              then f:pair-heads($resolved, $alt-heads, $alt-instructions,
                                                $drop-rubrics)
                              else $resolved"/>
        <!-- A paragraph break is a terminator, so the last paragraph of a block carries
             one with nothing after it. Inside a single \pstart that break now sets a
             blank line, and a blank line before \pend is a row of empty column. Drop the
             ones that separate nothing. -->
        <xsl:variable name="unbroken" as="node()*" select="f:drop-trailing-lbs($paired)"/>
        <xsl:sequence
                      select="if ($trim) then f:trim-trailing-breaks($unbroken)
                              else $unbroken"/>

    </xsl:function>

    <!-- Drop a line break that ends its paragraph.

         Verse is encoded line by line, and a source commonly closes the last line of a
         paragraph with a tei:lb like every other. A forced break with nothing after it
         does not end a line: it starts an empty one, which then takes a line number and
         sets a blank row before the paragraph's end — once per verse, where a text is
         aligned verse by verse. The break is dropped when nothing that prints follows it
         before the paragraph ends: layout whitespace, a silent milestone, the terminating
         verse milestone that carries no number, or another such break. Anything else
         after it, a note mark included, keeps it, as a line of its own.

         A rubric counts as an end of paragraph here because its macro breaks the line
         itself before setting the rubric, so a break in front of it also sets an empty
         line. -->
    <xsl:function name="f:drop-trailing-lbs" as="node()*">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:sequence select="for $i in 1 to count($leaves)
                              return if (exists($leaves[$i]/self::tei:lb)
                                         and f:only-silence-follows($leaves, $i + 1))
                                     then ()
                                     else $leaves[$i]"/>
    </xsl:function>

    <xsl:function name="f:only-silence-follows" as="xs:boolean">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:param name="from" as="xs:integer"/>
        <xsl:variable name="next" as="node()?" select="$leaves[$from]"/>
        <xsl:sequence
            select="if (empty($next)) then true()
                    else if ($next/self::f:para-break or $next/self::f:block-break
                             or $next/self::f:head or $next/self::f:list-label
                             or $next/self::tei:milestone[@rend = '****']
                             or $next/self::tei:note[@type = ('instruction', 'description')])
                    then true()
                    else if (f:is-structural-space($next) or f:renders-nothing($next)
                             or $next/self::tei:lb
                             or $next/self::tei:milestone[@unit = 'verse'][not(normalize-space(@n))])
                    then f:only-silence-follows($leaves, $from + 1)
                    else false()"/>
    </xsl:function>


    <!-- Render one f:head sentinel (the context node) as a heading macro plus its PDF
         outline entry. Caller is responsible for the surrounding \pstart/\pend. -->
    <xsl:template name="heading">
        <xsl:param name="stream" as="xs:string" select="'primary'"/>
        <!-- Whether a facing column exists at all. Without it, 'alt' cannot mean the other
             column and has to mean the division's own second head instead. -->
        <xsl:param name="has-alt-column" as="xs:boolean" select="false()"/>
        <xsl:param name="hoisted-heading" as="xs:string" select="''"/>
        <!-- Record the heading for the running heads and the outline without setting
             anything on the page. For a heading f:sets-heading says is not set, where the
             caller has no paragraph to hold a placeholder. -->
        <xsl:param name="marks-only" as="xs:boolean" select="false()"/>
        <!-- Notes on the division this heads, set after its title. See emit-leaves. -->
        <xsl:param name="notes" as="element()*" select="()"/>
        <xsl:variable name="lang" select="string(@xml:lang)"/>
        <xsl:variable name="is-hebrew" select="f:is-hebrew-lang($lang)"/>

        <!-- Record the heading for the running heads before setting it, so a
             head at the very top of a page is already in force there. The
             payload is the flattened title with per-run direction applied, so a
             mixed title like "רות RUTH" reads correctly in a slot of either
             direction; see f:emit-bidi-mark. -->
        <xsl:variable name="mark-suffix" select="if ($stream = 'alt') then 'Alt' else ''"/>
        <xsl:variable name="mark-title" select="f:emit-bidi-mark(string(@title))"/>
        <xsl:text>\InsertMark{OShead</xsl:text>
        <xsl:value-of select="f:heading-suffix(xs:integer(@level))"/>
        <xsl:value-of select="$mark-suffix"/>
        <xsl:text>}{</xsl:text><xsl:value-of select="$mark-title"/><xsl:text>}</xsl:text>
        <xsl:text>\InsertMark{OSheadAny</xsl:text><xsl:value-of select="$mark-suffix"/>
        <xsl:text>}{</xsl:text><xsl:value-of select="$mark-title"/><xsl:text>}</xsl:text>
        <xsl:if test="@is-book = 'true'">
            <xsl:text>\InsertMark{OSbook</xsl:text><xsl:value-of select="$mark-suffix"/>
            <xsl:text>}{</xsl:text><xsl:value-of select="$mark-title"/><xsl:text>}</xsl:text>
        </xsl:if>

        <!-- Whether this column sets the heading on the page: see f:sets-heading.
             Suppressing one is not the same as dropping it: reledpar pairs the columns by
             counting \pstart...\pend, so the paragraph has to stay and be non-empty.
             \mbox{} is both — reledmac cannot typeset an empty \pstart at all, and fails
             the whole build when asked to. -->
        <xsl:variable name="hoisted" as="xs:boolean"
                      select="f:is-hoisted(., $hoisted-heading)"/>
        <xsl:variable name="sets-heading" as="xs:boolean"
                      select="f:sets-heading(., $stream, $hoisted-heading)"/>
        <xsl:choose>
            <xsl:when test="$marks-only"/>
            <xsl:when test="$sets-heading">
        <xsl:text>\OShead</xsl:text>
        <xsl:value-of select="f:heading-suffix(xs:integer(@level))"/>
        <xsl:text>{</xsl:text>
        <!-- Hebrew titles stay in the stream direction; other languages need an explicit
             LTR wrapper so Latin text is not reversed in RTL blocks. Runs marked
             tei:foreign[@xml:lang='he'] inside such a title get their own \texthebrew
             wrapper from mode="emit". -->
        <xsl:if test="not($is-hebrew)">
            <xsl:text>{\textdir TLT\foreignlanguage{english}{</xsl:text>
        </xsl:if>
        <xsl:apply-templates select="node()[not(self::f:alt-head)]" mode="emit"/>
        <!-- Inside the macro's argument, so the mark is centred with the title, and
             inside the title's direction, so it follows the title's last word: outside an
             LTR title in an RTL paragraph, "after" is its left-hand end. -->
        <xsl:apply-templates select="$notes" mode="emit"/>
        <xsl:if test="not($is-hebrew)">
            <xsl:text>}}</xsl:text>
        </xsl:if>
        <xsl:text>}</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:text>\mbox{\strut}</xsl:text>
                <!-- The other column sets the title; the mark stays in this column, on
                     the row the placeholder already holds, rather than a row of its own. -->
                <xsl:apply-templates select="$notes" mode="emit"/>
            </xsl:otherwise>
        </xsl:choose>

        <!-- A second head on the same division is the translated title. It is set under
             the first rather than beside it, so that it reads as naming the same section
             again and not as a section of its own. -->
        <xsl:if test="f:alt-head and not($marks-only)">
            <!-- No direction wrapper here: mode="emit" already wraps each run against the
                 stream it lands in, and adding one on top nests a second \textdir around
                 the first for no gain. -->
            <xsl:text>\OSheadTranslation{</xsl:text>
            <xsl:apply-templates select="f:alt-head/node()" mode="emit"/>
            <xsl:text>}</xsl:text>
        </xsl:if>

        <!-- PDF outline entry. No \tableofcontents is emitted, so the .toc drives
             hyperref's bookmarks only. It takes the flattened @title: \addcontentsline
             builds a PDF string, which cannot carry markup.

             Exactly one stream may write it. Both used to, which is why a parallel
             compile produced two entries per heading, interleaved out of document order
             because the columns reach the .toc at different points. -->
        <!-- Exactly one stream writes the entry. Under 'alt' that is the facing column
             where there is one; where there is none, the primary stream still writes it,
             taking the division's second head as the other title. Tying 'alt' to the
             column alone emitted no outline at all for a single text titled twice. -->
        <xsl:variable name="writes-outline" as="xs:boolean"
                      select="if ($hoisted) then false()
                              else if ($stream = 'alt')
                              then $bookmarks-from = 'alt'
                              else not($bookmarks-from = 'alt' and $has-alt-column)"/>
        <xsl:if test="$writes-outline">
            <!-- @alt-title is the title of the same section in the other language,
                 whether that came from a second head on the division or from the other
                 column; f:pair-heads has already settled which. Combined, they are one
                 entry, because they name one section.

                 Under 'alt' it is read only in the primary stream, and only because a
                 single text titled twice has no other column to take the title from.
                 The alt stream's own @title is already the alt title; reading @alt-title
                 there would hand back the primary's. -->
            <xsl:variable name="other" as="xs:string" select="string(@alt-title)"/>
            <xsl:variable name="outline-title" as="xs:string"
                          select="if ($bookmarks-from = 'combined' and $other != ''
                                      and $other != string(@title))
                                  then concat(string(@title), ' &#xB7; ', $other)
                                  else if ($bookmarks-from = 'alt' and $stream = 'primary'
                                           and $other != '')
                                  then $other
                                  else string(@title)"/>
            <xsl:text>\phantomsection\addcontentsline{toc}{</xsl:text>
            <xsl:value-of select="f:heading-toc-level(xs:integer(@level))"/>
            <xsl:text>}{</xsl:text>
            <xsl:value-of select="f:format-section-title($outline-title)"/>
            <xsl:text>}</xsl:text>
        </xsl:if>
    </xsl:template>

    <!-- Whether a heading is the one already set across the page above the columns, so
         that neither column sets it. The hoisted title is the primary column's. In the alt
         column the sentinel's own @title is the other language, and @alt-title is the
         primary's — so both columns recognise the heading that was lifted out above them. -->
    <!-- A note on a whole division that has a heading: the compiler sets such a note as
         one of the division's own children, beside the tei:head, rather than in any of
         its paragraphs. It is about what the heading names, so it is set with the heading:
         after its title. A division may hold nothing but a heading and rubrics (the
         haggadah has such sections), so the heading, not the first text after it, is the
         one thing such a note can always be set with. -->
    <xsl:function name="f:is-head-note" as="xs:boolean">
        <xsl:param name="node" as="node()?"/>
        <xsl:sequence select="exists(f:head-note-div($node))"/>
    </xsl:function>

    <!-- The headed division whose heading a note is set with: the division it is on, where
         the compiler anchored a note on the whole division, or the division whose heading
         it stands in. -->
    <xsl:function name="f:head-note-div" as="element(tei:div)?">
        <xsl:param name="node" as="node()?"/>
        <xsl:variable name="note" select="$node/self::tei:note[not(@type = ('instruction', 'description'))]
                                                              [not(ancestor::tei:standOff)]"/>
        <xsl:sequence select="($note/parent::tei:div[tei:head],
                               $note/ancestor::tei:head[1]/parent::tei:div)[1]"/>
    </xsl:function>

    <!-- The notes a heading sets itself: its division's, unless that heading is set
         across the page above the stream, which sets them there. -->
    <xsl:function name="f:own-head-notes" as="element()*">
        <xsl:param name="head" as="element()"/>
        <xsl:param name="notes-by-div" as="map(xs:string, element()*)"/>
        <xsl:param name="hoisted-divs" as="xs:string*"/>
        <xsl:sequence select="if (string($head/@div) = ('', $hoisted-divs)) then ()
                              else $notes-by-div(string($head/@div))"/>
    </xsl:function>

    <xsl:function name="f:is-hoisted" as="xs:boolean">
        <xsl:param name="head" as="element()"/>
        <xsl:param name="hoisted-heading" as="xs:string"/>
        <xsl:sequence select="$hoisted-heading != ''
                              and ($hoisted-heading = string($head/@title)
                                   or $hoisted-heading = string($head/@alt-title))"/>
    </xsl:function>

    <!-- Whether the stream $stream sets heading $head on the page. Where the two columns
         title a section identically, printing both says the same thing twice, once per
         column; where they differ, each column needs its own. Beyond the hoisted heading,
         reached only by a heading that was not hoisted: one further into a block than its
         opening, or any heading at all under 'both'.

         On facing pages the reader cannot take a title from across the opening the way
         they can from the next column, and each page is a full measure of its own, so
         'combined' sets the heading on both pages even where they agree. 'primary' and
         'alt' still name one side and mean it. -->
    <xsl:function name="f:sets-heading" as="xs:boolean">
        <xsl:param name="head" as="element()"/>
        <xsl:param name="stream" as="xs:string"/>
        <xsl:param name="hoisted-heading" as="xs:string"/>
        <xsl:variable name="agrees" as="xs:boolean"
                      select="string($head/@alt-title) != ''
                              and string($head/@alt-title) = string($head/@title)"/>
        <xsl:sequence select="if (f:is-hoisted($head, $hoisted-heading)) then false()
                              else if ($headings-from = 'both') then true()
                              else if ($headings-from = 'primary') then $stream = 'primary'
                              else if ($headings-from = 'alt') then $stream = 'alt'
                              else $facing-pages or $stream = 'primary' or not($agrees)"/>
    </xsl:function>

    <!-- Render one f:list-label sentinel (the context node). Caller is responsible for the
         surrounding \pstart/\pend, as with name="heading". -->
    <xsl:template name="list-label">
        <xsl:variable name="lang" select="string(@xml:lang)"/>
        <xsl:text>\OSListLabel{</xsl:text>
        <!-- The same direction wrapper a heading gets, and for the same reason: the label
             is Latin text that may land in a Hebrew-rooted stream. Birnbaum's introduction
             is exactly that — English front matter realised by the English project and
             transcluded into a Hebrew index — so without this the label reads backwards.
             A Hebrew label stays in the stream direction; any Latin run inside it takes
             its own wrapper from mode="emit". -->
        <xsl:if test="not(f:is-hebrew-lang($lang))">
            <xsl:text>{\textdir TLT\foreignlanguage{english}{</xsl:text>
        </xsl:if>
        <xsl:apply-templates select="node()" mode="emit"/>
        <xsl:if test="not(f:is-hebrew-lang($lang))">
            <xsl:text>}}</xsl:text>
        </xsl:if>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <!-- The heading in the other column that names the same section as $head.

         Paired on (@corresp, @part): one authored division becomes several pieces under
         marker_reconstruct, all carrying the same @corresp, so the URN alone would match
         the wrong piece. Where the division carries no URN — which happens; a head-bearing
         div need not have one — fall back to the heading at the same ordinal among those
         the other column offers.

         Position alone would not do. A project's realisation of a URN need not cover every
         branch, so one column may hold a heading the other lacks, and everything after the
         gap would pair with the wrong title. An unmatched heading gets no counterpart and
         is bookmarked under its own title, which is the honest answer; it is never dropped. -->
    <xsl:function name="f:counterpart" as="element()?">
        <xsl:param name="head" as="element()"/>
        <xsl:param name="alt-heads" as="element()*"/>
        <xsl:param name="ordinal" as="xs:integer"/>
        <xsl:variable name="by-urn" as="element()*"
                      select="if (string($head/@corresp) != '')
                              then $alt-heads[string(@corresp) = string($head/@corresp)
                                              and string(@part) = string($head/@part)]
                              else ()"/>
        <xsl:sequence
            select="if (exists($by-urn)) then $by-urn[1]
                    else if (string($head/@corresp) = '') then $alt-heads[$ordinal]
                    else ()"/>
    </xsl:function>

    <!-- Copy a flattened leaf sequence, giving every f:head sentinel the title of its
         counterpart in the other column. Done here rather than in the heading template
         because a heading's ordinal among headings is knowable only with the whole
         sequence in hand: the template is called from inside an iterate, one leaf at a
         time. A sentinel that already carries @alt-title got it from a second head on its
         own division, and that wins — it is the same division's own translation. -->
    <xsl:function name="f:pair-heads" as="node()*">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:param name="alt-heads" as="element()*"/>
        <!-- The other column's rubrics, in order. A rubric carries no URN to pair on, so
             it is matched by its words, scanning forward and never back: each of the
             other column's rubrics is spent at most once, and in order.

             Counted, not positioned. One column routinely carries rubrics the other has
             none of — Birnbaum's Hebrew page labels the Reader where his English page
             translates the words instead — and matching by position puts every rubric
             after such a label out of step. Matching forward from a moving pointer fixes
             that only until one pair matches out of order, and then strands the rest.

             So the test is a count: the nth rubric saying this in this column is echoed if
             the other column says it n times or more. The columns are two renderings of
             one document aligned paragraph by paragraph, which is what makes a rubric
             present in both overwhelmingly likely to be present at the same place; and a
             rubric the other column does not have, or has fewer of, is kept. -->
        <xsl:param name="alt-instructions" as="xs:string*"/>
        <!-- What this stream gives up: 'none', 'matching' (only a rubric the other
             column gives in the same words) or 'all' (every rubric, because the settings
             named the other column). Decided by the caller, which knows which column it
             is; mode="emit" does not. -->
        <xsl:param name="drop-rubrics" as="xs:string"/>
        <xsl:iterate select="$leaves">
            <xsl:param name="seen" as="xs:integer" select="0"/>
            <!-- The rubrics already met in this column, so that the nth of a repeated one
                 is matched against the other column's nth. -->
            <xsl:param name="rubrics-seen" as="xs:string*" select="()"/>
            <xsl:choose>
                <xsl:when test="self::f:head">
                    <xsl:variable name="ordinal" as="xs:integer" select="$seen + 1"/>
                    <xsl:variable name="mate" as="element()?"
                                  select="f:counterpart(., $alt-heads, $ordinal)"/>
                    <xsl:copy>
                        <xsl:copy-of select="@*"/>
                        <xsl:if test="not(@alt-title) and exists($mate)">
                            <xsl:attribute name="alt-title" select="string($mate/@title)"/>
                        </xsl:if>
                        <xsl:copy-of select="node()"/>
                    </xsl:copy>
                    <xsl:next-iteration>
                        <xsl:with-param name="seen" select="$ordinal"/>
                        <xsl:with-param name="rubrics-seen" select="$rubrics-seen"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="descendant-or-self::tei:note[@type = ('instruction', 'description')]">
                    <!-- One rubric per leaf in practice: either the note itself, or a
                         conditional carrying the rubric that explains it. -->
                    <xsl:variable name="note"
                                  select="descendant-or-self::tei:note[@type = ('instruction', 'description')][1]"/>
                    <xsl:variable name="text" as="xs:string"
                                  select="normalize-space(string($note))"/>
                    <!-- How many times this column has said it, counting this one. -->
                    <xsl:variable name="nth" as="xs:integer"
                                  select="count($rubrics-seen[. = $text]) + 1"/>
                    <xsl:variable name="echoed" as="xs:boolean"
                                  select="$drop-rubrics = 'all'
                                          or ($drop-rubrics = 'matching'
                                              and count($alt-instructions[. = $text]) ge $nth)"/>
                    <xsl:apply-templates select="." mode="stamp-rubric">
                        <xsl:with-param name="echoed" select="$echoed" tunnel="yes"/>
                        <xsl:with-param name="note-lang" tunnel="yes"
                                        select="string(($note/ancestor-or-self::*[@xml:lang][1])/@xml:lang)"/>
                        <xsl:with-param name="text-lang" tunnel="yes"
                                        select="string(($note/ancestor::*[@xml:lang][1])/@xml:lang)"/>
                    </xsl:apply-templates>
                    <xsl:next-iteration>
                        <xsl:with-param name="seen" select="$seen"/>
                        <xsl:with-param name="rubrics-seen"
                                        select="($rubrics-seen, $text)"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:sequence select="."/>
                    <xsl:next-iteration>
                        <xsl:with-param name="seen" select="$seen"/>
                        <xsl:with-param name="rubrics-seen" select="$rubrics-seen"/>
                    </xsl:next-iteration>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:iterate>
    </xsl:function>

    <!-- Copy a leaf, recording on every rubric inside it what pairing decided and the
         languages its direction is read from. Copying detaches a node from its ancestors,
         and those two languages are read off them, so an English rubric in a Hebrew column
         would otherwise stop looking like one and be set inline instead of on its own
         line. -->
    <xsl:mode name="stamp-rubric" on-no-match="shallow-copy"/>

    <!-- Preserve scope classification before copying detaches the conditional from
         its paragraph and matching end marker in a parallel stream. -->
    <xsl:template match="j:conditional" mode="stamp-rubric">
        <xsl:copy>
            <xsl:copy-of select="@*"/>
            <xsl:attribute name="f:inline" select="f:is-inline-conditional(.)"/>
            <xsl:attribute name="f:in-paragraph" select="exists(ancestor::tei:p | ancestor::tei:l)"/>
            <xsl:apply-templates mode="stamp-rubric"/>
        </xsl:copy>
    </xsl:template>

    <!-- A note copied with its leaf keeps the serial of the note it was copied from: the copy
         has no ancestors, and f:editorial-note-emissions-before counts from where a note
         stands in the document. -->
    <xsl:template match="tei:note[not(@type = ('instruction', 'description'))]" mode="stamp-rubric stamp-serial">
        <xsl:copy>
            <xsl:copy-of select="@*"/>
            <xsl:attribute name="f:serial" select="f:note-serial(.)"/>
            <xsl:apply-templates mode="#current"/>
        </xsl:copy>
    </xsl:template>

    <!-- Copies that carry no rubrics, only notes to keep the serials of. -->
    <xsl:mode name="stamp-serial" on-no-match="shallow-copy"/>

    <!-- A heading's copy (head-sentinel): its words and rubrics, without its annotations at
         any depth. Those are set with the heading from where they stand (f:is-head-note);
         copied as well, a note inside a tei:hi or a tei:foreign was set twice. -->
    <xsl:mode name="head-copy" on-no-match="shallow-copy"/>
    <xsl:template match="tei:note[not(@type = ('instruction', 'description'))][not(ancestor::tei:note)]"
                  mode="head-copy"/>

    <xsl:template match="tei:note[@type = ('instruction', 'description')]" mode="stamp-rubric">
        <xsl:param name="echoed" as="xs:boolean" tunnel="yes"/>
        <xsl:param name="note-lang" as="xs:string" tunnel="yes"/>
        <xsl:param name="text-lang" as="xs:string" tunnel="yes"/>
        <xsl:copy>
            <xsl:copy-of select="@*"/>
            <xsl:attribute name="f:note-lang" select="$note-lang"/>
            <xsl:attribute name="f:text-lang" select="$text-lang"/>
            <!-- A block rubric introduces a new paragraph in both parallel
                 columns, even when its language matches one column. Otherwise
                 the translation runs onto the rubric's last line while the
                 facing Hebrew starts below it. Preserve this before copying. -->
            <xsl:attribute name="f:parallel-block"
                           select="exists(ancestor::p:parallelItem)
                                   and not(ancestor::tei:p or ancestor::tei:l)"/>
            <xsl:if test="$echoed">
                <xsl:attribute name="f:echoed" select="'true'"/>
            </xsl:if>
            <xsl:copy-of select="node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- ====================================================================
         Pass 1 (mode="leaves"): walk the tree, emit a flat sequence of
         leaf-like nodes in document order. Inline formatting elements are
         emitted whole (with text content); block elements are transparent.
         Paragraph boundaries become f:para-break sentinels so we can close
         pstart between paragraphs. A div with a head emits an f:head sentinel
         carrying the title, its language and its heading level.
         ==================================================================== -->

    <xsl:template match="text()" mode="leaves">
        <xsl:sequence select="."/>
    </xsl:template>

    <!-- A milestone is set by the stream itself (a verse number, a chapter, a rule), which
         looks only at its attributes. Notes the compiler set inside it follow it as leaves of
         their own, so that they are set where the milestone is. -->
    <xsl:template match="tei:milestone" mode="leaves">
        <xsl:sequence select="."/>
        <xsl:apply-templates select="tei:note" mode="leaves"/>
    </xsl:template>

    <xsl:template match="tei:hi | tei:emph | tei:foreign | tei:choice | tei:note | tei:ref | tei:lb | tei:anchor"
                  mode="leaves">
        <xsl:sequence select="."/>
    </xsl:template>

    <!-- Retained conditional markers must survive flattening to be rendered; see
         \OSCondStartInline and friends in the preamble. -->
    <xsl:template match="j:conditional | j:endConditional" mode="leaves">
        <xsl:sequence select="."/>
    </xsl:template>

    <xsl:template match="tei:pb" mode="leaves"/>

    <xsl:template match="tei:standOff" mode="leaves"/>

    <!-- A title page is never part of a numbered stream. tei:front handles it directly;
         should one turn up inside the body, the match="*" fallback would otherwise
         flatten its parts into running text. -->
    <xsl:template match="tei:titlePage" mode="leaves"/>

    <!-- Internal sentinels produced by this stylesheet must survive flattening. -->
    <xsl:template match="f:para-break | f:block-break | f:head | f:list-label" mode="leaves">
        <xsl:sequence select="."/>
    </xsl:template>

    <!-- Heading level is the count of *headed* div ancestors, not of all div ancestors:
         transclusion interposes an arbitrary number of headless container divs (in the
         compiled haggadah, index.xml's div wraps seder.xml's div wraps each section), so
         raw nesting depth does not correspond to logical heading level. -->
    <xsl:template match="tei:div" mode="leaves">
        <xsl:if test="tei:head">
            <xsl:call-template name="head-sentinel">
                <xsl:with-param name="head" select="tei:head[1]"/>
                <!-- A multilingual work titles one division twice, and every head after the
                     first used to be dropped here: the recursion below excludes them all,
                     so only tei:head[1] survived. It bit at random rather than always,
                     because marker_reconstruct splits a division across parallel columns
                     and each piece gets its own tei:head[1] — so two heads were lost only
                     when the splitter happened not to cut between them. -->
                <xsl:with-param name="alt-head" select="tei:head[2]"/>
                <xsl:with-param name="level"
                                select="if (tei:head[1]/@p:heading-level)
                                        then min((xs:integer(tei:head[1]/@p:heading-level), 4))
                                        else min((count(ancestor::tei:div[tei:head]) + 1, 4))"/>
            </xsl:call-template>
            <!-- A note in a heading, which the heading's copy cannot carry (see
                 head-sentinel): set from where it stands, with the heading, as a note on the
                 division is. -->
            <xsl:apply-templates select="tei:head//tei:note[not(@type = ('instruction', 'description'))]
                                                            [not(ancestor::tei:note)]" mode="leaves"/>
        </xsl:if>
        <xsl:apply-templates select="node()[not(self::tei:head)]" mode="leaves"/>
    </xsl:template>

    <!-- A tei:head outside a tei:div — front matter titles a section without dividing it,
         as in "PREFACE" at the head of tei:front. Without this it would fall through to the
         match="*" fallback and its text would run straight into the following paragraph. -->
    <xsl:template match="tei:head[not(parent::tei:div)]" mode="leaves">
        <xsl:call-template name="head-sentinel">
            <xsl:with-param name="head" select="."/>
            <xsl:with-param name="level" select="1"/>
        </xsl:call-template>
        <!-- Its notes follow it in the text, there being no division to set them with. -->
        <xsl:apply-templates select=".//tei:note[not(@type = ('instruction', 'description'))]
                                                [not(ancestor::tei:note)]" mode="leaves"/>
    </xsl:template>

    <xsl:template name="head-sentinel">
        <xsl:param name="head" as="element(tei:head)"/>
        <xsl:param name="level" as="xs:integer"/>
        <!-- The same division's heading in the other language, where the source titles it
             twice in one div. The other way a work carries two languages — two projects
             compiled in parallel — is joined later, in the parallel block, where both
             columns are in scope; see $alt-heads. -->
        <xsl:param name="alt-head" as="element(tei:head)?" select="()"/>
        <xsl:element name="f:head" namespace="urn:opensiddur:reledmac">
            <!-- @title is the flattened plain-text form, used only for the PDF
                 bookmark (\addcontentsline takes no markup). -->
            <xsl:attribute name="title"
                           select="normalize-space(string-join(
                               $head//text()[not(ancestor::tei:note)], ''))"/>
            <xsl:attribute name="xml:lang" select="f:section-title-lang($head)"/>
            <xsl:attribute name="level" select="$level"/>
            <!-- Drives the {book-title} running-head code: in a Bible export the
                 book is a div[@type='book'] whose head names it. -->
            <xsl:attribute name="is-book" select="$head/parent::tei:div/@type = 'book'"/>
            <!-- Identity, for pairing this heading with its counterpart in the other
                 column. @corresp alone is not enough: marker_reconstruct splits one
                 authored division into several pieces that all carry it, so the piece is
                 named by the pair. Either may be absent — a head-bearing div need not
                 carry a URN at all — which is why the pairing falls back to position. -->
            <xsl:attribute name="corresp" select="string($head/parent::tei:div/@corresp)"/>
            <xsl:attribute name="part" select="string($head/parent::tei:div/@p:part)"/>
            <!-- The division itself, so the notes it carries can be found again and set
                 with its heading. See f:is-head-note. -->
            <xsl:if test="exists($head/parent::tei:div)">
                <xsl:attribute name="div" select="generate-id($head/parent::tei:div)"/>
            </xsl:if>
            <xsl:if test="exists($alt-head)">
                <xsl:attribute name="alt-title"
                               select="normalize-space(string-join(
                                   $alt-head//text()[not(ancestor::tei:note)], ''))"/>
                <xsl:attribute name="alt-lang" select="f:section-title-lang($alt-head)"/>
            </xsl:if>
            <!-- The head's own content is carried through so it can be rendered in
                 mode="emit" rather than flattened: a title like
                 <foreign xml:lang="he">רות</foreign><lb/>RUTH needs its Hebrew run
                 wrapped in \texthebrew (otherwise it renders reversed inside the
                 surrounding LTR heading) and its line break preserved.
                 Notes inside the head are left out of the copy: a note's serial is counted
                 from where it stands in the document. They are set with the heading from
                 their own place, as a note on the whole division is; see f:is-head-note. -->
            <xsl:apply-templates select="$head/node()" mode="head-copy"/>
            <!-- The counterpart's content, kept in a child element so that the primary
                 head's nodes stay direct children and mode="emit" renders them exactly as
                 before. The heading template picks this out and excludes it. -->
            <xsl:if test="exists($alt-head)">
                <xsl:element name="f:alt-head" namespace="urn:opensiddur:reledmac">
                    <xsl:apply-templates select="$alt-head/node()" mode="head-copy"/>
                </xsl:element>
            </xsl:if>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:p | tei:ab" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
        <!-- Don't drop pstart on (first|middle) split fragments — they carry
             logical-id continuation across parallel boundaries. -->
        <xsl:if test="not(@p:part = ('first', 'middle'))">
            <xsl:element name="f:para-break" namespace="urn:opensiddur:reledmac"/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tei:lg" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
        <xsl:if test="not(@p:part = ('first', 'middle'))">
            <xsl:element name="f:para-break" namespace="urn:opensiddur:reledmac"/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tei:l" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
        <xsl:if test="not(@p:part = ('first', 'middle'))">
            <!-- Hard line break inside the current pstart -->
            <xsl:element name="tei:lb" namespace="http://www.tei-c.org/ns/1.0"/>
        </xsl:if>
    </xsl:template>

    <!-- A labelled list. Without these three templates all of tei:list, tei:label and
         tei:item fall through to the match="*" fallback below, which descends without
         emitting a sentinel of any kind: the label's text runs into the head of the
         paragraph it labels, and the items lose every boundary between them, so a
         comparison of two translations set as two labelled blocks comes out as one
         continuous run of prose. -->
    <xsl:template match="tei:label[parent::tei:list]" mode="leaves">
        <!-- tei:label is macro.phraseSeq — phrase content only, never a tei:p — so this
             is head-sentinel's shape without the block handling, the heading levels or
             the parallel-column pairing. tei:note is dropped: unlike a heading's, a
             label's notes are not set from where they stand.
             Restricted to a label inside a list: the other use of tei:label is naming
             a standoff note (see JLPTEI-3.md), which is not text on the page. -->
        <xsl:element name="f:list-label" namespace="urn:opensiddur:reledmac">
            <xsl:attribute name="xml:lang" select="f:in-scope-lang(.)"/>
            <xsl:apply-templates select="node()[not(self::tei:note)]" mode="stamp-serial"/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:item" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
        <!-- An item whose content is block-level has already been closed off by the
             f:para-break its last tei:p emitted; emitting a second one here would be a
             no-op in a single-column stream but would spend a blank strut line in a
             parallel one (see the f:para-break branch of numbered-stream). Only an item
             of inline content — the plain, label-less lists in the JPS 1917 books —
             needs a break of its own. -->
        <xsl:if test="not(tei:p | tei:ab | tei:lg)">
            <xsl:element name="f:para-break" namespace="urn:opensiddur:reledmac"/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tei:list" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
        <!-- Same guard, one level up: separate the list from the prose that follows it,
             unless its items have already done so. -->
        <xsl:if test="not(tei:item[tei:p | tei:ab | tei:lg])">
            <xsl:element name="f:para-break" namespace="urn:opensiddur:reledmac"/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="p:transclude | p:transcludeInline" mode="leaves" priority="5">
        <xsl:apply-templates select="node()" mode="leaves"/>
    </xsl:template>

    <!-- Safety net only. The compiler guarantees a p:parallel never has a p:parallel ancestor
         (see the parallel invariants in specs/COMPILER_SPECIFICATION.md): parallel blocks end at
         every external transclusion. If one ever slips through, flattening it into the enclosing
         column is wrong but survivable â it renders the inner text in the outer column's
         direction rather than aborting the build. -->
    <xsl:template match="p:parallel | p:parallelItem" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
    </xsl:template>

    <!-- Pass-through fallback for unknown elements: descend. -->
    <xsl:template match="*" mode="leaves">
        <xsl:apply-templates select="node()" mode="leaves"/>
    </xsl:template>

    <!-- ====================================================================
         Pass 2 (mode="emit"): render leaves as TeX text inside a \pstart.
         ==================================================================== -->

    <!-- Text is set by f:emit-bidi-text, which wraps Latin runs left to right, when it is in
         Hebrew script, or in a Latin-script form of a Hebrew-script language (he-Latn): a
         transliteration stands in Hebrew-script surroundings, which would otherwise lay it out
         right to left. -->
    <xsl:template match="text()" mode="emit">
        <xsl:variable name="lang" select="f:in-scope-lang(.)"/>
        <xsl:choose>
            <xsl:when test="f:is-hebrew-lang($lang)
                            or (tokenize(lower-case($lang), '-')[1] = ('he', 'yi', 'arc')
                                and tokenize(lower-case($lang), '-') = 'latn')">
                <xsl:value-of select="f:emit-bidi-text(string(.))"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="f:escape-tex(.)"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- Headings are centered with symmetric fill glue, which only exists on the first
         line of the box; a \\ would leave the remainder flush-left. Titles that mark a
         break between a Hebrew and a Latin form (JPS book heads do this) read fine as one
         centered line, so separate the runs horizontally instead. -->
    <xsl:template match="tei:lb[ancestor::f:head]" mode="emit" priority="20">
        <xsl:text>\quad </xsl:text>
    </xsl:template>

    <xsl:template match="tei:lb" mode="emit">
        <!-- Ensure we're in horizontal mode before forcing a linebreak.
             This avoids \"There's no line here to end\" when lb occurs at the
             start of a paragraph/block. -->
        <!-- Add an empty brace group so a following `[` at the start of the next
             line is not parsed as the optional length argument to `\\`. -->
        <xsl:text>\leavevmode\\{}&#10;</xsl:text>
    </xsl:template>

    <!-- tei:anchor carries no text of its own, but the compiler inserts a standoff note
         it is the target of as its child. Descend, or that note is built and then
         silently dropped: the mark never appears and the apparatus is short by one. -->
    <xsl:template match="tei:anchor" mode="emit">
        <xsl:apply-templates mode="emit"/>
    </xsl:template>

    <!-- tei:hi/@rend is a list of tokens, each wrapped around the content in order: "small
         superscript" is small and raised. A token that changes the look of the text is set
         with its role's macro (styles.highlight_*, defined in the typography preamble); the
         raise of a superscript is fixed, and the role styles the raised text. A token with
         no styling of its own (a layout or reading mark such as centered, ketiv-only) sets
         the text plain; an unknown one does too, with a warning, rather than in bold as
         everything unrecognised once was. The electronic book styles the same tokens as
         rend-* classes (css.py). -->
    <xsl:variable name="hi-rend-tex" as="map(xs:string, xs:string+)" select="map {
        'small-caps': ('\OSHighlightSmallCaps{', '}'),
        'smallcaps': ('\OSHighlightSmallCaps{', '}'),
        'italic': ('\OSHighlightItalic{', '}'),
        'bold': ('\OSHighlightBold{', '}'),
        'sup': ('\textsuperscript{\OSHighlightSuperscript{', '}}'),
        'superscript': ('\textsuperscript{\OSHighlightSuperscript{', '}}'),
        'suspended': ('\textsuperscript{\OSHighlightSuperscript{', '}}'),
        'raised': ('\textsuperscript{\OSHighlightSuperscript{', '}}'),
        'large': ('\OSHighlightLarge{', '}'),
        'small': ('\OSHighlightSmall{', '}'),
        'align-right': ('\hspace*{\fill}', '')
    }"/>

    <!-- The role of the line or list item a word is set in (styles.poetry_line,
         styles.list_item), as the macro that sets it: the nearest tei:l or tei:item, unless
         a note is nearer, since a note's words are the apparatus's. Empty when an inline
         element between the two (a highlight, a foreign phrase, a reading, a reference)
         already carries the line's style around the word, so that the line's style is
         always the outer one and the word's own role overrides it. -->
    <xsl:function name="f:container-macro" as="xs:string">
        <xsl:param name="node" as="node()"/>
        <xsl:variable name="container" as="element()?"
                      select="($node/ancestor::*[self::tei:l or self::tei:item or self::tei:note])[last()]"/>
        <xsl:sequence select="
            if (empty($container) or $container/self::tei:note
                or exists($node/ancestor::*[self::tei:hi or self::tei:emph or self::tei:foreign
                                            or self::tei:choice or self::tei:ref]
                                           [. >> $container]))
            then ''
            else if ($container/self::tei:l) then 'OSPoetryLine' else 'OSListItem'"/>
    </xsl:function>

    <!-- The words of a poetry line or a list item, in its role. Matched at the outermost
         inline node in the line, above every template that sets one, so that the role
         wraps whatever those emit. Whitespace is left bare: a group around it gains
         nothing, and the stream tests leaves for whitespace by their being text. -->
    <xsl:template match="(text()[normalize-space(.)] | tei:hi | tei:emph | tei:foreign
                          | tei:choice | tei:ref)[f:container-macro(.) ne '']"
                  mode="emit" priority="30">
        <xsl:value-of select="concat('\', f:container-macro(.), '{')"/>
        <xsl:next-match/>
        <xsl:text>}</xsl:text>
    </xsl:template>
    <xsl:variable name="hi-rend-plain" as="xs:string*"
                  select="('centered', 'centred', 'center', 'ketiv-only', 'qeri-only')"/>

    <xsl:template match="tei:hi" mode="emit">
        <xsl:call-template name="hi-wrap">
            <xsl:with-param name="tokens" select="tokenize(normalize-space(@rend))"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template name="hi-wrap">
        <xsl:param name="tokens" as="xs:string*"/>
        <xsl:choose>
            <xsl:when test="empty($tokens)">
                <xsl:apply-templates mode="emit"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:variable name="wrap" select="$hi-rend-tex($tokens[1])"/>
                <xsl:if test="empty($wrap) and not($tokens[1] = $hi-rend-plain)">
                    <xsl:message select="concat('reledmac.xslt: tei:hi/@rend token &quot;',
                                                $tokens[1], '&quot; has no styling; set plain')"/>
                </xsl:if>
                <xsl:value-of select="$wrap[1]"/>
                <xsl:call-template name="hi-wrap">
                    <xsl:with-param name="tokens" select="subsequence($tokens, 2)"/>
                </xsl:call-template>
                <xsl:value-of select="$wrap[2]"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="tei:emph" mode="emit">
        <xsl:text>\emph{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <!-- A foreign phrase is set in its role (styles.foreign) inside whatever selects its
         language and direction, so that the role's face, if it names one, wins. -->
    <xsl:template match="tei:foreign[@xml:lang][f:is-hebrew-lang(string(@xml:lang))]"
                  mode="emit" priority="10">
        <xsl:text>\texthebrew{\OSForeign{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}}</xsl:text>
    </xsl:template>

    <!-- An apparatus catchword, which is a quotation of the text and therefore a
         tei:label rather than a tei:foreign.

         `note-content` forces a direction on the whole note: an English commentary note
         is set inside \textdir TLT. A Hebrew run left bare inside that is laid out left
         to right and comes out reversed, which is what happened to the catchword of every
         lemma-keyed note in Birnbaum's apparatus — forty-seven of them, `אהליך` reading
         backwards at the head of its note.

         tei:foreign already had the wrapper and the catchword missed it because it is not
         a foreign phrase. Matched on direction rather than on `he` alone, for the reason
         f:is-rtl-lang exists: Yiddish is written in the same script and has the same
         problem. Priority 12 so it also takes precedence over the list-label template
         below, whose \OSListLabelStyle is applied here too rather than lost. -->
    <xsl:template match="tei:label[@xml:lang][f:is-rtl-lang(string(@xml:lang))]"
                  mode="emit" priority="12">
        <xsl:if test="parent::tei:list">
            <xsl:text>\OSListLabelStyle{</xsl:text>
        </xsl:if>
        <xsl:text>\texthebrew{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}</xsl:text>
        <xsl:if test="parent::tei:list">
            <xsl:text>}\ </xsl:text>
        </xsl:if>
    </xsl:template>

    <!-- English citations embedded in a Hebrew paragraph need a scoped LTR
         direction even when they contain no digits (e.g. Ps. cxlv.). Start the
         surrounding paragraph before switching direction so a citation-only
         span does not change the paragraph direction. -->
    <xsl:template match="tei:foreign[@xml:lang='en']" mode="emit" priority="10">
        <xsl:text>\leavevmode{\textdir TLT\foreignlanguage{english}{\OSForeign{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}}}</xsl:text>
    </xsl:template>

    <xsl:template match="tei:foreign" mode="emit">
        <xsl:text>\OSForeign{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <!-- ====================================================================
         Title page parts (mode="emit").
         Each part is wrapped in its own \OS* macro so all title page styling
         lives in the preamble. Direction is handled once per part, the same
         way the `heading` template handles it: Hebrew stays in the stream
         direction, anything else gets an explicit LTR wrapper so Latin text
         is not reversed on a Hebrew title page.
         ==================================================================== -->

    <xsl:template name="title-page-part">
        <xsl:param name="macro" as="xs:string"/>
        <xsl:variable name="page-hebrew"
                      select="f:is-hebrew-lang(f:in-scope-lang(ancestor::tei:titlePage[1]))"/>
        <xsl:variable name="part-hebrew" select="f:is-hebrew-lang(f:in-scope-lang(.))"/>
        <!-- Only wrap when the part runs against the direction of the page it sits on: an
             English part on an English page needs nothing. Both directions matter — a
             Hebrew line on a Latin title page renders reversed without \texthebrew, and
             Latin text on a Hebrew one renders reversed without an explicit LTR group. -->
        <xsl:variable name="needs-ltr" select="$page-hebrew and not($part-hebrew)"/>
        <xsl:variable name="needs-rtl" select="$part-hebrew and not($page-hebrew)"/>
        <xsl:text>\</xsl:text>
        <xsl:value-of select="$macro"/>
        <xsl:text>{</xsl:text>
        <xsl:if test="$needs-ltr">
            <xsl:text>{\textdir TLT\foreignlanguage{english}{</xsl:text>
        </xsl:if>
        <xsl:if test="$needs-rtl">
            <xsl:text>\texthebrew{</xsl:text>
        </xsl:if>
        <xsl:apply-templates select="node()" mode="emit"/>
        <!-- The LTR branch opens two groups, the RTL one \texthebrew's single group. -->
        <xsl:if test="$needs-ltr">
            <xsl:text>}}</xsl:text>
        </xsl:if>
        <xsl:if test="$needs-rtl">
            <xsl:text>}</xsl:text>
        </xsl:if>
        <xsl:text>}&#10;</xsl:text>
    </xsl:template>

    <!-- tei:docTitle is a container; its tei:titlePart children carry the styling. -->
    <xsl:template match="tei:docTitle" mode="emit">
        <xsl:apply-templates select="node()" mode="emit"/>
    </xsl:template>

    <xsl:template match="tei:titlePart[@type = ('sub', 'desc')]" mode="emit" priority="10">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSTitleSub'"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="tei:titlePart[@type = ('alt', 'short')]" mode="emit" priority="10">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSTitleAlt'"/>
        </xsl:call-template>
    </xsl:template>

    <!-- @type='main' and untyped titleParts both read as the title proper. -->
    <xsl:template match="tei:titlePart" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSTitleMain'"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="tei:byline" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSByline'"/>
        </xsl:call-template>
    </xsl:template>

    <!-- Inside a byline the wrapper already supplied the styling; standing alone,
         a docAuthor is the byline. -->
    <xsl:template match="tei:docAuthor[parent::tei:byline]" mode="emit" priority="10">
        <xsl:apply-templates select="node()" mode="emit"/>
    </xsl:template>

    <xsl:template match="tei:docAuthor" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSByline'"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="tei:docEdition" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSDocEdition'"/>
        </xsl:call-template>
    </xsl:template>

    <!-- An imprint listing place, publisher and date as elements is a container: each part
         sets its own line and supplies its own direction wrapper, so wrapping the container
         too would only nest a redundant \textdir group around them. An imprint written as a
         running phrase ("Copyright, 1917, By The Jewish Publication Society of America") is
         styled as one block instead, and its parts stay inline — see f:is-imprint-list. -->
    <xsl:template match="tei:docImprint[f:is-imprint-list(.)]" mode="emit" priority="10">
        <xsl:text>\OSDocImprint{</xsl:text>
        <xsl:apply-templates select="node()" mode="emit"/>
        <xsl:text>}&#10;</xsl:text>
    </xsl:template>

    <xsl:template match="tei:docImprint" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSDocImprint'"/>
        </xsl:call-template>
    </xsl:template>

    <!-- Each imprint element prints on its own line, but only where the imprint is a list of
         them; breaking the line at a publisher named mid-sentence would split the sentence. -->
    <xsl:template match="tei:pubPlace[f:is-imprint-list(..)] |
                         tei:publisher[f:is-imprint-list(..)] |
                         tei:docDate[f:is-imprint-list(..)]" mode="emit" priority="10">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSImprintLine'"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="tei:epigraph" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSEpigraph'"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="tei:imprimatur" mode="emit">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSImprimatur'"/>
        </xsl:call-template>
    </xsl:template>

    <!-- Block content elsewhere on a title page (a loose paragraph, an epigraph's
         paragraphs) still needs to break as a paragraph rather than run on. -->
    <xsl:template match="tei:p[ancestor::tei:titlePage] |
                         tei:ab[ancestor::tei:titlePage] |
                         tei:lg[ancestor::tei:titlePage]" mode="emit" priority="10">
        <xsl:call-template name="title-page-part">
            <xsl:with-param name="macro" select="'OSTitlePageBlock'"/>
        </xsl:call-template>
    </xsl:template>

    <xsl:template match="tei:l[ancestor::tei:titlePage]" mode="emit" priority="10">
        <xsl:apply-templates select="node()" mode="emit"/>
        <xsl:text>\\&#10;</xsl:text>
    </xsl:template>

    <!-- A page break inside front matter records the source foliation only; the
         typeset page breaks are produced by the titlepage environment itself. -->
    <xsl:template match="tei:pb[ancestor::tei:titlePage]" mode="emit"/>

    <!-- Every title page part already ends its own paragraph, so the pretty-printing
         whitespace between them would only add stray blank lines (= \par) and
         unwanted vertical space. -->
    <xsl:template match="text()[not(normalize-space(.))][ancestor::tei:titlePage]"
                  mode="emit" priority="10"/>

    <xsl:template match="tei:anchor[@type='page-label']" mode="emit" priority="10">
        <xsl:text>\label{</xsl:text><xsl:value-of select="@n"/><xsl:text>}</xsl:text>
        <xsl:apply-templates select="node()" mode="emit"/>
    </xsl:template>

    <xsl:template match="tei:ref[@type='page']" mode="emit" priority="10">
        <xsl:text>\pageref{</xsl:text><xsl:value-of select="@target"/><xsl:text>}</xsl:text>
    </xsl:template>

    <!-- A reference's words are set in its role (styles.reference); a page reference's are
         generated, and are not. -->
    <xsl:template match="tei:ref[@target]" mode="emit">
        <xsl:text>\href{</xsl:text>
        <xsl:value-of select="f:escape-url(@target)"/>
        <xsl:text>}{\OSReference{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}}</xsl:text>
    </xsl:template>

    <xsl:template match="tei:ref" mode="emit">
        <xsl:text>\OSReference{</xsl:text>
        <xsl:apply-templates mode="emit"/>
        <xsl:text>}</xsl:text>
    </xsl:template>

    <!-- A conditional whose condition was decided is resolved away by the compiler, so any
         marker reaching here is one that could not be decided, and was not silenced by
         f:resolve-markers. Bracket it, so the passage it governs is visibly set off from
         the text around it. Within running text that means brackets; around whole blocks,
         a rule, because brackets several lines apart do not read as a pair. -->
    <xsl:template match="j:conditional" mode="emit">
        <xsl:choose>
            <!-- Marker-only instructions announce their own labels. Within a paragraph
                 or verse, however, the instruction cannot show where an addition ends. -->
            <xsl:when test="f:is-announced(.)
                            and f:is-inline-conditional(.)
                            and not(ancestor::tei:p or ancestor::tei:l or @f:in-paragraph = 'true')"/>
            <xsl:when test="f:is-inline-conditional(.)">
                <xsl:apply-templates select="tei:note" mode="emit"/>
                <xsl:text>\OSCondStartInline{}</xsl:text>
            </xsl:when>
            <!-- A block that announces itself needs no rule to open it: the instruction
                 says which passage this is and on what it depends, and a rule above it
                 only reads as a stray line. The closing rule stays, since nothing else
                 shows where the passage stops. A scope the book marks off takes its rule
                 all the same. -->
            <xsl:when test="f:is-announced(.)"/>
            <xsl:otherwise>
                <xsl:text>\OSCondStartBlock{}</xsl:text>
            </xsl:otherwise>
        </xsl:choose>
        <!-- The note, when there is one, explains the condition the reader must judge. -->
        <xsl:if test="not(f:is-inline-conditional(.))
                      or (tei:note[@type = ('instruction', 'description')] and not(@type = 'marked')
                          and not(ancestor::tei:p or ancestor::tei:l or @f:in-paragraph = 'true'))">
            <xsl:apply-templates select="tei:note" mode="emit"/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="j:endConditional" mode="emit">
        <xsl:variable name="start" select="f:matching-start(.)"/>
        <xsl:choose>
            <!-- Matching the opening: a scope whose instruction stands in for its
                 opening bracket takes no closing one. -->
            <xsl:when test="exists($start) and f:is-announced($start)
                            and f:is-inline-conditional($start)
                            and not($start/ancestor::tei:p or $start/ancestor::tei:l)"/>
            <xsl:when test="if (exists($start))
                            then f:is-inline-conditional($start)
                            else (ancestor::tei:p or ancestor::tei:l)">
                <xsl:text>\OSCondEndInline{}</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <xsl:text>\OSCondEndBlock{}</xsl:text>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- Each reading is emitted, not flattened to a string: it can hold markup (a divine
         name, a highlighted letter) and the anchor of a note, whose mark belongs where the
         anchor is. string() spliced the note's text into the middle of the word. -->
    <!-- Each form is set in its role (styles.abbreviation, styles.expansion,
         styles.printed_error, styles.correction, styles.qere, styles.ketiv,
         styles.alternative_reading). The parentheses around a second form are the
         text's, outside the role. -->
    <xsl:template match="tei:choice" mode="emit">
        <xsl:choose>
            <xsl:when test="tei:abbr or tei:expan">
                <!-- Compiled choices contain one selected form. Uncompiled input defaults
                     to the printed abbreviation, rather than concatenating both. -->
                <xsl:call-template name="reading-form">
                    <xsl:with-param name="form" select="(tei:abbr, tei:expan)[1]"/>
                    <xsl:with-param name="macro"
                                    select="if (tei:abbr) then 'OSAbbreviation' else 'OSExpansion'"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:when test="tei:sic or tei:corr">
                <!-- Likewise one form of an edition error; uncompiled input reads the
                     correction, as the exporter's default does. -->
                <xsl:call-template name="reading-form">
                    <xsl:with-param name="form" select="(tei:corr, tei:sic)[1]"/>
                    <xsl:with-param name="macro"
                                    select="if (tei:corr) then 'OSCorrection' else 'OSPrintedError'"/>
                </xsl:call-template>
            </xsl:when>
            <xsl:when test="j:option">
                <!-- Alternate wordings: exactly one is read, but nothing here has chosen
                     between them, so all are shown, the first plain and the rest bracketed
                     as the 1822 print does. -->
                <xsl:for-each select="j:option">
                    <xsl:choose>
                        <xsl:when test="position() gt 1">
                            <xsl:text> (</xsl:text>
                            <xsl:call-template name="reading-form">
                                <xsl:with-param name="form" select="."/>
                                <xsl:with-param name="macro" select="'OSAlternativeReading'"/>
                            </xsl:call-template>
                            <xsl:text>)</xsl:text>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:apply-templates select="node()" mode="emit"/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:for-each>
            </xsl:when>
            <xsl:otherwise>
                <xsl:call-template name="reading-form">
                    <xsl:with-param name="form" select="j:read"/>
                    <xsl:with-param name="macro" select="'OSQere'"/>
                </xsl:call-template>
                <xsl:if test="j:read and j:written">
                    <xsl:text> (</xsl:text>
                </xsl:if>
                <xsl:call-template name="reading-form">
                    <xsl:with-param name="form" select="j:written"/>
                    <xsl:with-param name="macro" select="'OSKetiv'"/>
                </xsl:call-template>
                <xsl:if test="j:read and j:written">
                    <xsl:text>)</xsl:text>
                </xsl:if>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template name="reading-form">
        <xsl:param name="form" as="element()?"/>
        <xsl:param name="macro" as="xs:string"/>
        <xsl:if test="exists($form)">
            <xsl:value-of select="concat('\', $macro, '{')"/>
            <xsl:apply-templates select="$form/node()" mode="emit"/>
            <xsl:text>}</xsl:text>
        </xsl:if>
    </xsl:template>

    <!-- Notes become reledmac apparatus footnotes. Editorial/commentary notes
         go to the B-series; instructional notes go to the C-series. They
         attach to a zero-width lemma so the apparatus mark sits at the
         note's textual anchor point. -->
    <xsl:template match="tei:note[@type = ('instruction', 'description')]" mode="emit" priority="10">
        <!-- A rubric the other column gives in the same words is one rubric printed twice,
             once per column. f:pair-heads has marked it; which column keeps it is the
             settings' business. Nothing is emitted for the one that does not, and nothing
             needs to be: a rubric is inline, so unlike a heading it opens no paragraph
             that reledpar would be counting. -->
        <xsl:if test="not(@f:echoed = 'true')">
        <!-- Whose direction the instruction runs in, against the text around it. Read
             off the ancestors, except where pairing has copied the note out of its tree
             and recorded them on it. -->
        <xsl:variable name="note-lang"
                      select="if (@f:note-lang) then string(@f:note-lang)
                              else string((ancestor-or-self::*[@xml:lang][1])/@xml:lang)"/>
        <xsl:variable name="text-lang"
                      select="if (@f:text-lang) then string(@f:text-lang)
                              else string((ancestor::*[@xml:lang][1])/@xml:lang)"/>
        <xsl:variable name="crosses"
                      select="f:is-rtl-lang($note-lang) ne f:is-rtl-lang($text-lang)"/>
        <xsl:variable name="within" select="exists(ancestor::tei:p | ancestor::tei:l)"/>
        <xsl:text>\</xsl:text>
        <xsl:value-of select="if (@f:parallel-block = 'true') then 'OSInstructionBlock'
                              else if (not($crosses)) then 'instructionnote'
                              else if ($within) then 'OSInstructionLine'
                              else 'OSInstructionBlock'"/>
        <xsl:text>{</xsl:text>
        <xsl:call-template name="note-content"/>
        <xsl:text>}</xsl:text>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tei:note[not(ancestor::tei:standOff)][not(@type = ('instruction', 'description'))]" mode="emit">
        <xsl:variable name="serial" as="xs:integer" select="f:note-serial(.)"/>
        <xsl:call-template name="os-b-footnote">
            <xsl:with-param name="serial" select="$serial"/>
        </xsl:call-template>
    </xsl:template>

    <!-- A note on the title page. The title page is set outside \beginnumbering, where
         reledmac's \edtext is an error that ends the run, so the note is LaTeX's own
         footnote, which the titlepage environment prints at the foot of that page. It
         keeps its serial and mark, so the numbering of the notes after it is unchanged;
         under endnote placement it is still a footnote, since the endnotes are printed
         from reledmac's apparatus, which the title page is not part of. -->
    <xsl:template match="tei:note[ancestor::tei:titlePage][not(ancestor::tei:standOff)]
                                 [not(@type = ('instruction', 'description'))]" mode="emit" priority="5">
        <xsl:if test="$notes-placement != 'none'">
            <xsl:text>\begingroup\renewcommand{\thefootnote}{</xsl:text>
            <xsl:value-of select="f:note-mark(f:note-serial(.))"/>
            <xsl:text>}\footnote{\notenote{</xsl:text>
            <xsl:call-template name="note-content"/>
            <xsl:text>}}\endgroup{}</xsl:text>
        </xsl:if>
    </xsl:template>

    <!-- The mark that anchors a note, in the series $notes-mark asks for.
         format-integer handles alpha and roman for any serial; the traditional
         symbol series has only six members, so past the sixth the symbol is
         repeated, which is how a printed apparatus has always done it. -->
    <xsl:variable name="note-symbols" as="xs:string+"
                  select="('\textasteriskcentered', '\textdagger', '\textdaggerdbl',
                           '\textsection', '\textbardbl', '\textparagraph')"/>

    <xsl:function name="f:note-mark" as="xs:string">
        <xsl:param name="serial" as="xs:integer"/>
        <xsl:choose>
            <xsl:when test="$notes-mark = 'alpha'">
                <xsl:sequence select="format-integer($serial, 'a')"/>
            </xsl:when>
            <xsl:when test="$notes-mark = 'roman'">
                <xsl:sequence select="format-integer($serial, 'i')"/>
            </xsl:when>
            <xsl:when test="$notes-mark = 'symbol'">
                <xsl:variable name="symbol"
                              select="$note-symbols[($serial - 1) mod count($note-symbols) + 1]"/>
                <xsl:sequence select="string-join(
                    for $repeat in 1 to ($serial - 1) idiv count($note-symbols) + 1
                    return $symbol, '')"/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:sequence select="string($serial)"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:function>

    <xsl:template name="os-b-footnote">
        <xsl:param name="serial" as="xs:integer"/>
        <xsl:if test="$notes-placement != 'none'">
            <xsl:call-template name="os-b-footnote-emit">
                <xsl:with-param name="serial" select="$serial"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>

    <xsl:template name="os-b-footnote-emit">
        <xsl:param name="serial" as="xs:integer"/>
        <!-- In bidi/RTL contexts, empty-lemma \edtext{} can be fragile with reledmac's
             aux-file writes. Use an explicit visible-but-zero-width lemma via
             \OSInterlinearNotemark. \Bfootnote routes content to the B-series apparatus.
             Plain \footnote inside \pstart...\pend is flushed by reledmac after \pend.
             \OSRTLfalse forces reledmac's LTR code path for .1-file writes: in RTL
             mode reledmac writes ] before \@ref[N][ for single-line lemmas, which
             corrupts the catcode-group that controls [ ] delimiters when the .1
             file is re-read on the next pass. -->
        <xsl:text>\leavevmode{\OSRTLfalse\edtext{\OSInterlinearNotemark{</xsl:text>
        <xsl:value-of select="f:note-mark($serial)"/>
        <xsl:text>}}{\</xsl:text>
        <!-- A colophon division is set after the endnotes have been printed (see the root
             template), so its notes are footnotes whatever the placement. -->
        <xsl:value-of select="if ($notes-placement = 'endnote' and not(ancestor::tei:back[@p:colophon]))
                              then 'Bendnote' else 'Bfootnote'"/>
        <xsl:text>{\OSFootnotemark{</xsl:text>
        <xsl:value-of select="f:note-mark($serial)"/>
        <xsl:text>}\notenote{</xsl:text>
        <xsl:call-template name="note-content"/>
        <xsl:text>}}}}</xsl:text>
    </xsl:template>

    <!-- A paragraph inside apparatus is emitted directly rather than through the
         body paragraph pipeline. Honor its explicit language before inheriting the
         surrounding note's forced direction. Keep ordinary groups, not paragraph
         environments, inside reledmac's auxiliary-file writes. -->
    <xsl:template match="tei:p[ancestor::tei:note][@xml:lang]" mode="emit" priority="10">
        <xsl:call-template name="note-paragraph-break"/>
        <xsl:call-template name="note-content"/>
    </xsl:template>

    <xsl:template match="tei:p[ancestor::tei:note]" mode="emit" priority="9">
        <xsl:call-template name="note-paragraph-break"/>
        <xsl:apply-templates mode="emit"/>
    </xsl:template>

    <!-- A note's second and later paragraphs start a new line, as the print sets them: an
         English instruction followed by the Hebrew verses it introduces otherwise share a
         line. \newline rather than \par, for the reason given at tei:item below. -->
    <xsl:template name="note-paragraph-break">
        <xsl:if test="preceding-sibling::tei:p">
            <xsl:text>\newline </xsl:text>
        </xsl:if>
    </xsl:template>

    <xsl:template name="note-content">
        <!-- The same language the macro was chosen by, computed the same way, so the two
             cannot disagree about one note. @f:note-lang because pairing the columns copies
             a rubric out of its tree to stamp it, and a rubric written in the language
             around it — which is most of them — states no language of its own and had
             nothing left to inherit from: every such rubric came out reversed. Tested by
             direction rather than for `he`, for the reason f:is-rtl-lang exists. -->
        <xsl:variable name="note-lang"
                      select="if (@f:note-lang) then string(@f:note-lang)
                              else string((ancestor-or-self::*[@xml:lang][1])/@xml:lang)"/>
        <xsl:choose>
            <xsl:when test="f:is-rtl-lang($note-lang)">
                <!-- Force explicit RTL direction inside notes even when nested
                     in an LTR context.
                     Use {{\textdir TRT ...}} (regular braces) to avoid leaking
                     \begingroup/\endgroup into reledmac's aux-file write machinery. -->
                <xsl:text>{{\textdir TRT\foreignlanguage{hebrew}{</xsl:text>
                <xsl:apply-templates mode="emit"/>
                <xsl:text>}}}</xsl:text>
            </xsl:when>
            <xsl:otherwise>
                <!-- Force explicit LTR direction inside notes even when nested
                     in an RTL (Hebrew) context. This avoids visual reversal of
                     LTR runs like \"note\" rendering backwards. -->
                <xsl:text>{{\textdir TLT\foreignlanguage{english}{</xsl:text>
                <xsl:apply-templates mode="emit"/>
                <xsl:text>}}}</xsl:text>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- A list inside a note. tei:note is emitted whole by pass 1 (xsl:sequence, so its
         children never reach mode="leaves"), which means a list nested in one — the JPS
         1917 index carries a 23-item list in a standoff note — is rendered here instead,
         where the sentinel machinery is not available. \newline rather than \par: the
         note is set inside \Bfootnote, and a \par there breaks reledmac's apparatus
         grouping. That is the same constraint \OSInstructionBlock is written to. -->
    <xsl:template match="tei:label[parent::tei:list]" mode="emit">
        <xsl:text>\OSListLabelStyle{</xsl:text>
        <xsl:apply-templates select="node()" mode="emit"/>
        <xsl:text>}\ </xsl:text>
    </xsl:template>

    <xsl:template match="tei:item" mode="emit">
        <xsl:apply-templates select="node()" mode="emit"/>
        <!-- Nothing after the last item: a trailing \newline would set a blank line
             against the end of the note. -->
        <xsl:if test="following-sibling::tei:item">
            <xsl:text>\newline </xsl:text>
        </xsl:if>
    </xsl:template>

    <!-- Default: shouldn't be reachable after pass 1, but be defensive. -->
    <xsl:template match="*" mode="emit">
        <xsl:apply-templates mode="emit"/>
    </xsl:template>

    <!-- ====================================================================
         TeX escaping helpers
         ==================================================================== -->

    <!-- The notes the book numbers before this one, the same ones the electronic book numbers
         (html.xslt, note-number): editorial and commentary notes in the text — not a
         header's notes, not standoff ones, not instructions. A note that holds this one comes
         before it, though the preceding axis leaves it out. -->
    <!-- A note's serial: the one stamped on it when it was copied, else counted where it stands. -->
    <xsl:function name="f:note-serial" as="xs:integer">
        <xsl:param name="note" as="element(tei:note)"/>
        <xsl:sequence select="if ($note/@f:serial) then xs:integer($note/@f:serial)
                              else f:editorial-note-emissions-before($note) + 1"/>
    </xsl:function>

    <xsl:function name="f:editorial-note-emissions-before" as="xs:integer">
        <xsl:param name="ctx" as="element()"/>
        <xsl:sequence select="count(($ctx/preceding::tei:note | $ctx/ancestor::tei:note)
            [not(@type = ('instruction', 'description'))][ancestor::tei:text][not(ancestor::tei:standOff)])"/>
    </xsl:function>

    <!-- Heading level (1-4) to the \OSheadA/B/C/D macro suffix. -->
    <xsl:function name="f:heading-suffix" as="xs:string">
        <xsl:param name="level" as="xs:integer"/>
        <xsl:sequence select="('A', 'B', 'C', 'D')[min((max(($level, 1)), 4))]"/>
    </xsl:function>

    <!-- Heading level (1-4) to the \addcontentsline level driving hyperref bookmarks. -->
    <xsl:function name="f:heading-toc-level" as="xs:string">
        <xsl:param name="level" as="xs:integer"/>
        <xsl:sequence select="('section', 'subsection', 'subsubsection', 'paragraph')[
            min((max(($level, 1)), 4))]"/>
    </xsl:function>

    <!-- ====================================================================
         Marker resolution over the flattened leaf sequence
         ==================================================================== -->

    <!-- An aliyah, maftir, weekday or triennial marker: auto-generated label text that
         \OSaliyah already sets off in brackets of its own. -->
    <xsl:function name="f:is-aliyah-marker" as="xs:boolean">
        <xsl:param name="node" as="node()?"/>
        <xsl:sequence select="exists($node/self::tei:milestone[
            starts-with(@unit, 'aliyah') or starts-with(@unit, 'maftir')])"/>
    </xsl:function>

    <xsl:function name="f:is-structural-space" as="xs:boolean">
        <xsl:param name="node" as="node()?"/>
        <xsl:sequence select="exists($node/self::text()) and not(normalize-space($node))"/>
    </xsl:function>

    <!-- True when the stream loop sets nothing for this leaf. Milestones are the only
         leaves that can be silent: a qualified parsha unit is left to the div's heading,
         and an unrecognised unit (edition-verse and friends) is skipped rather than given
         a \pstart it would leave empty. A silent leaf is invisible in the output, so it
         neither ends a run of markers nor separates the layout whitespace around it:
         two such whitespace leaves meeting would be a blank line, i.e. a \par. Keep this
         in step with the milestone branches of the stream loop. -->
    <xsl:function name="f:renders-nothing" as="xs:boolean">
        <xsl:param name="node" as="node()?"/>
        <xsl:variable name="unit" select="string($node/@unit)"/>
        <xsl:sequence select="exists($node/self::tei:milestone) and (
            starts-with($unit, 'parsha.')
            or not($unit = ('chapter', 'citation', 'verse', 'parsha')
                   or starts-with($unit, 'aliyah')
                   or starts-with($unit, 'maftir')
                   or $node/@rend = '****'))"/>
    </xsl:function>

    <!-- True when a leaf puts something on the page, so a paragraph break before it has
         something to separate. Everything a stream can carry that does not: the breaks
         themselves, the layout whitespace between them, and the silent milestones. -->
    <xsl:function name="f:puts-ink" as="xs:boolean">
        <xsl:param name="node" as="node()?"/>
        <xsl:sequence select="not(exists($node/self::f:para-break)
                                  or exists($node/self::f:block-break)
                                  or f:is-structural-space($node)
                                  or f:renders-nothing($node))"/>
    </xsl:function>

    <!-- True when an item sets words of its own: text, a heading, a list label, or a
         rubric. Apparatus does not count — an editorial note, the anchor carrying one, a
         reference marker (milestone), a line break or a condition marker — since an item
         holding only these is not a text the other column could face. -->
    <xsl:function name="f:sets-text" as="xs:boolean">
        <xsl:param name="item" as="element()?"/>
        <xsl:variable name="leaves" as="node()*">
            <xsl:apply-templates select="$item/node()" mode="leaves"/>
        </xsl:variable>
        <!-- A rubric is looked for within the leaves, not only among them: one inside a
             j:conditional reaches the leaf stream inside its marker. -->
        <xsl:sequence select="exists($leaves[
            (self::text() and normalize-space(.))
            or ((self::tei:hi | self::tei:emph | self::tei:foreign | self::tei:choice
                 | self::tei:ref)
                and normalize-space(string(.)))
            or descendant-or-self::tei:note[@type = ('instruction', 'description')][normalize-space(.)]
            or self::f:head or self::f:list-label])"/>
    </xsl:function>

    <!-- Drop the paragraph breaks that trail the end of a block, where they would set a
         blank line against \pend rather than separate two paragraphs. Grouped by block so
         a break at the end of one block is judged against that block, not the next one. -->
    <xsl:function name="f:trim-trailing-breaks" as="node()*">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:for-each-group select="$leaves" group-ending-with="self::f:block-break">
            <xsl:variable name="group" as="node()*" select="current-group()"/>
            <xsl:variable name="last-ink" as="xs:integer"
                          select="(0,
                                   for $i in 1 to count($group)
                                   return if (f:puts-ink($group[$i])) then $i else ()
                                  )[last()]"/>
            <xsl:sequence select="$group[position() le $last-ink
                                         or exists(self::f:block-break)]"/>
        </xsl:for-each-group>
    </xsl:function>

    <!-- A run of newlines, with whatever indentation the source pretty-printer left
         between them, reduced to the one newline that carries the inter-word space.
         The indentation of the surviving line goes with it: TeX discards spaces at the
         start of a line, so it was never anything but noise. A run of exactly one
         newline is left alone, so every separation that is already right is untouched.
         See the comment on numbered-stream for why this is done on the emitted text. -->
    <xsl:function name="f:collapse-blank-lines" as="xs:string">
        <xsl:param name="tex" as="xs:string"/>
        <xsl:sequence select="replace($tex, '\n[ \t]*(\n[ \t]*)+', '&#10;')"/>
    </xsl:function>

    <!-- The endConditional that closes a conditional, and the nodes between the two.
         An unmatched conditional (no xml:id, or no matching end) governs nothing, and
         every test below then falls back to the conservative answer. -->
    <xsl:function name="f:matching-end" as="element()?">
        <xsl:param name="start" as="element()"/>
        <xsl:sequence select="if ($start/@xml:id)
            then $start/following::j:endConditional[@target = '#' || $start/@xml:id][1]
            else ()"/>
    </xsl:function>

    <xsl:function name="f:matching-start" as="element()?">
        <xsl:param name="end" as="element()"/>
        <xsl:sequence select="$end/preceding::j:conditional[
            @xml:id and '#' || @xml:id = string($end/@target)][1]"/>
    </xsl:function>

    <xsl:function name="f:governed-nodes" as="node()*">
        <xsl:param name="start" as="element()"/>
        <xsl:variable name="end" select="f:matching-end($start)"/>
        <xsl:sequence select="if (exists($end))
            then ($start/following::node() intersect $end/preceding::node())
            else ()"/>
    </xsl:function>

    <!-- True when an undecided conditional is printed without delimiters. How a scope is
         set off follows the book. A scope the book itself marks off — with brackets,
         parentheses or a line — is @type="marked", and takes the standard delimiters. One
         that carries an instruction is set off by it. One with neither is a direction to the
         processor, not to the reader: an occasion's gate around a whole service, or the
         reading divisions of a cycle, whose markers \OSaliyah already brackets. Delimiters
         there would only crowd the page — and a block delimiter is a full-measure box,
         which broke each aliyah label onto a line of its own. -->
    <!-- latex.py records on both markers whether a scope is silent beforehand (p:silent),
         since the two are often met apart; the test here is for a document that was not.
         A rubric the scope opens with announces it as its own note would. -->
    <xsl:function name="f:is-silent" as="xs:boolean">
        <xsl:param name="start" as="element()"/>
        <xsl:sequence select="if ($start/@p:silent) then $start/@p:silent = 'true' else
            not($start/@type = 'marked')
            and empty($start/tei:note)
            and not(f:opens-with-rubric($start))
            and exists(f:matching-end($start))"/>
    </xsl:function>

    <!-- True when the first thing a scope governs is a rubric: an instruction, or the
         description of the passage (JLPTEI-3, *Kinds of rubric*). It announces the scope
         as the scope's own note would. An annotation anchored at the scope's start
         is passed over, as a milestone is: it is the apparatus, not the text. -->
    <xsl:function name="f:opens-with-rubric" as="xs:boolean">
        <xsl:param name="start" as="element()"/>
        <xsl:variable name="first-governed" select="$start/following-sibling::node()[
            not(self::text()[normalize-space() = '']) and not(self::tei:milestone or self::tei:pb)
            and not(self::tei:note[not(@type = ('instruction', 'description'))])][1]"/>
        <xsl:sequence select="exists($first-governed[self::tei:note[@type = ('instruction', 'description')]])"/>
    </xsl:function>

    <!-- True when an undecided scope is announced by a rubric, its own or the one it
         opens with, so that the rubric stands in for its opening delimiter. -->
    <xsl:function name="f:is-announced" as="xs:boolean">
        <xsl:param name="start" as="element()"/>
        <xsl:sequence select="(exists($start/tei:note[@type = ('instruction', 'description')])
                               or f:opens-with-rubric($start))
                              and not($start/@type = 'marked')"/>
    </xsl:function>

    <!-- True when a conditional governs no block content, so its delimiters can be the
         inline brackets rather than a rule. The stylesheet's older test — is there a
         tei:p or tei:l ancestor — answers this for prose, but not for a text whose verse
         structure is milestone-based and whose divisions therefore sit directly in a
         tei:div, as the humash's do. -->
    <xsl:function name="f:is-inline-conditional" as="xs:boolean">
        <xsl:param name="start" as="element()"/>
        <xsl:sequence select="if ($start/@f:inline) then $start/@f:inline = 'true' else
            exists($start/ancestor::tei:p) or exists($start/ancestor::tei:l)
            or (exists(f:matching-end($start))
                and empty(f:governed-nodes($start)[
                    self::tei:p or self::tei:ab or self::tei:l or self::tei:lg
                    or self::tei:div or self::tei:head]))"/>
    </xsl:function>

    <!-- One pass over the flattened leaves, dropping two kinds of noise that only become
         visible once a text carries many overlapping reading divisions:

         (1) the delimiters of a silent conditional (f:is-silent), and
         (2) a marker repeating a label already shown at the same point.

         (2) arises for the combined parshiyot, where the same triennial aliyah is reached
         under several patterns: the conditions differ, so the compiled TEI rightly keeps
         every marker, but they all print the same label and the reader needs it once.
         A "point" is a run of consecutive markers, so identical labels separated by text
         are both kept.

         Node identity is preserved throughout: what survives is the original leaf, not a
         copy, because the emit templates read the ancestor and preceding axes. -->
    <xsl:function name="f:resolve-markers" as="node()*">
        <xsl:param name="leaves" as="node()*"/>
        <xsl:iterate select="$leaves">
            <!-- Labels already shown in the run of markers currently being emitted. -->
            <xsl:param name="run-labels" as="xs:string*" select="()"/>
            <!-- xml:ids of conditionals dropped by (1), so their ends go with them. -->
            <xsl:param name="silent-ids" as="xs:string*" select="()"/>
            <!-- Whether the last leaf emitted was layout whitespace. Dropping a leaf
                 leaves the whitespace that surrounded it back to back, and two of those
                 in the output are a blank line, which TeX reads as \par: inside a
                 \pstart, the very break these markers were making. -->
            <xsl:param name="after-space" as="xs:boolean" select="false()"/>
            <xsl:choose>
                <xsl:when test="self::j:conditional">
                    <xsl:variable name="silent" select="f:is-silent(.)"/>
                    <xsl:if test="not($silent)">
                        <xsl:sequence select="."/>
                    </xsl:if>
                    <xsl:next-iteration>
                        <!-- A silent conditional is invisible, so it does not interrupt the
                             run of markers it sits among; a visible one does. -->
                        <xsl:with-param name="run-labels" select="if ($silent) then $run-labels else ()"/>
                        <xsl:with-param name="silent-ids"
                                        select="if ($silent) then ($silent-ids, string(@xml:id)) else $silent-ids"/>
                        <xsl:with-param name="after-space" select="$silent and $after-space"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="self::j:endConditional">
                    <!-- A closer is often met in a different stream from its opener: a gate
                         around a section of parallel columns closes in the full-width stream
                         after them. So it carries its scope's silence itself (p:silent). -->
                    <xsl:variable name="silent" select="@p:silent = 'true'
                        or substring(string(@target), 2) = $silent-ids"/>
                    <xsl:if test="not($silent)">
                        <xsl:sequence select="."/>
                    </xsl:if>
                    <xsl:next-iteration>
                        <xsl:with-param name="run-labels" select="if ($silent) then $run-labels else ()"/>
                        <xsl:with-param name="silent-ids" select="$silent-ids"/>
                        <xsl:with-param name="after-space" select="$silent and $after-space"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="f:is-aliyah-marker(.)">
                    <xsl:variable name="label" select="string(@n)"/>
                    <xsl:variable name="duplicate" select="$label = $run-labels"/>
                    <xsl:if test="not($duplicate)">
                        <xsl:sequence select="."/>
                    </xsl:if>
                    <xsl:next-iteration>
                        <xsl:with-param name="run-labels" select="distinct-values(($run-labels, $label))"/>
                        <xsl:with-param name="silent-ids" select="$silent-ids"/>
                        <xsl:with-param name="after-space" select="$duplicate and $after-space"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:when test="f:is-structural-space(.)">
                    <!-- Layout whitespace between markers; it does not end the run. Only
                         the first of a run of it is kept, so that what a dropped leaf
                         used to separate does not become a blank line. -->
                    <xsl:if test="not($after-space)">
                        <xsl:sequence select="."/>
                    </xsl:if>
                    <xsl:next-iteration>
                        <xsl:with-param name="run-labels" select="$run-labels"/>
                        <xsl:with-param name="silent-ids" select="$silent-ids"/>
                        <xsl:with-param name="after-space" select="true()"/>
                    </xsl:next-iteration>
                </xsl:when>
                <xsl:otherwise>
                    <!-- A leaf the stream loop sets nothing for is invisible, so it can
                         neither end a run of markers nor keep whitespace apart. -->
                    <xsl:variable name="invisible" select="f:renders-nothing(.)"/>
                    <xsl:sequence select="."/>
                    <xsl:next-iteration>
                        <xsl:with-param name="run-labels" select="if ($invisible) then $run-labels else ()"/>
                        <xsl:with-param name="silent-ids" select="$silent-ids"/>
                        <xsl:with-param name="after-space" select="$invisible and $after-space"/>
                    </xsl:next-iteration>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:iterate>
    </xsl:function>

    <!-- Nearest xml:lang in scope for any element, falling back to the document language. -->
    <xsl:function name="f:in-scope-lang" as="xs:string">
        <xsl:param name="node" as="node()?"/>
        <xsl:sequence select="string((
            $node/ancestor-or-self::*[@xml:lang][1]/@xml:lang,
            $node/root()/tei:TEI/@xml:lang,
            ''
        )[1])"/>
    </xsl:function>

    <!-- True when a tei:docImprint sets its parts out as a list — place, publisher and date
         each on a line of its own — rather than running them into a sentence. The test is
         that the imprint carries imprint-part elements and no prose of its own. -->
    <xsl:function name="f:is-imprint-list" as="xs:boolean">
        <xsl:param name="imprint" as="node()?"/>
        <xsl:sequence select="exists($imprint/self::tei:docImprint)
            and exists($imprint/(tei:pubPlace | tei:publisher | tei:docDate))
            and not($imprint/text()[normalize-space(.)])"/>
    </xsl:function>


    <!-- Language for the tei:head used in \OSheadA/B/C titles. -->
    <!-- The nearest declaration of any kind, rather than the head's own, then a tei:div,
         then the tei:TEI. A unit file states its language once on its own tei:TEI and
         titles its divisions without repeating it, so most heads declare nothing; compiling
         two projects in parallel puts both under one root, which can carry only the primary
         project's language, and records each column's on its p:parallelItem. Naming the
         element types skipped that, and every English title in a Hebrew book was taken for
         Hebrew — set \texthebrew, its words each wrapped against the Hebrew around them,
         and so laid out right to left. -->
    <xsl:function name="f:section-title-lang" as="xs:string">
        <xsl:param name="head" as="element(tei:head)"/>
        <xsl:sequence select="string($head/ancestor-or-self::*[@xml:lang][1]/@xml:lang)"/>
    </xsl:function>

    <!-- A \addcontentsline entry, which is written once and read in two places: hyperref
         builds a PDF string from it for the outline, and \tableofcontents typesets it on
         a page. The typeset one is the constraint. Its slot is the table of contents,
         whose direction is the document class's, not the heading's, so the heading's own
         language may not be assumed — exactly the running-head problem, and answered the
         same way, by f:emit-bidi-mark: every Hebrew run takes \texthebrew and every other
         run an LTR wrap, so neither reverses whichever way the slot runs.

         Keying on the heading's language instead left Hebrew titles bare, correct in a
         Hebrew stream and back-to-front in an LTR table of contents — a whole Hebrew
         contents page read in reverse. The outline is unaffected either way:
         \pdfstringdefDisableCommands strips both wrappers. -->
    <xsl:function name="f:format-section-title" as="xs:string">
        <xsl:param name="title" as="xs:string"/>
        <xsl:sequence select="f:emit-bidi-mark($title)"/>
    </xsl:function>

    <!-- Recursively replace p:transclude / p:transcludeInline wrappers with their children.
         The wrappers are display no-ops that carry provenance only. -->
    <xsl:function name="f:flatten-transcludes" as="node()*">
        <xsl:param name="nodes" as="node()*"/>
        <xsl:sequence select="for $n in $nodes
                              return if ($n/self::p:transclude or $n/self::p:transcludeInline)
                                     then f:flatten-transcludes($n/node())
                                     else $n"/>
    </xsl:function>


    <!-- Sources like the MAM apparatus notes are Hebrew prose that embeds short Latin
         tokens (manuscript sigla such as "EVR-II-B-8", "BHS") and citation ranges (build.
         _citation, e.g. "42:5-43:10"). \textdir TRT forces the whole Hebrew note/heading
         into strict RTL layout, which has no per-run bidi detection, so an embedded Latin
         or digit token renders with its characters back-to-front unless explicitly
         switched back to LTR. Wrap each such token the same way \vno/\chno already wrap
         other LTR content in RTL context, leaving a hyphen that merely touches Hebrew
         (e.g. "פטרבורג-EVR-II-B-8") outside the wrap so its direction still resolves
         normally.

         A citation's separators (":", ";", the en dash) join a whole run into ONE
         embedding rather than one per token, because two separate LTR embeds sitting side
         by side in RTL text, with nothing but a colon or dash between them, do not
         reliably keep their *relative* order — the bidi algorithm has no strong character
         between them to anchor on, so wrapping "42" and "5" and "43" and "10" separately
         can come out as "43:10-42:5". A Hebrew book name, not in this character class,
         still ends a run and starts a fresh one, so "18:46; מלאכי 3:4" wraps its two
         ranges separately, each still safe on its own. -->
    <xsl:function name="f:emit-bidi-text" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <xsl:variable name="parts" as="xs:string*">
            <xsl:analyze-string select="$s" regex="[A-Za-z0-9]+([-'.:;–]\s?[A-Za-z0-9]+)*">
                <xsl:matching-substring>
                    <xsl:sequence select="concat('{{\textdir TLT\foreignlanguage{english}{', f:escape-tex(.), '}}}')"/>
                </xsl:matching-substring>
                <xsl:non-matching-substring>
                    <xsl:sequence select="f:escape-tex(.)"/>
                </xsl:non-matching-substring>
            </xsl:analyze-string>
        </xsl:variable>
        <xsl:sequence select="string-join($parts, '')"/>
    </xsl:function>

    <!-- Decimal verse numbers keep the macro's LTR default. Hebrew labels need
         their own direction and font, including when typography overrides vno.
         Wrap at the call site, just as for named parsha milestones. -->
    <xsl:function name="f:verse-number-label" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <xsl:sequence select="if (matches($s, '\p{IsHebrew}'))
                              then f:emit-bidi-mark($s) else f:escape-tex($s)"/>
    </xsl:function>

    <!-- A running-head mark, which the settings file can place in a slot of
         either direction, so neither direction may be assumed.

         \textdir forces a direction rather than running the bidi algorithm, so
         a run left bare is reversed whenever the slot runs the other way: a
         Hebrew book title reversed in an English header, "RUTH" reversed in a
         Hebrew one. Hebrew runs therefore take \texthebrew — which also selects
         the Hebrew font, without which a Latin-font slot has no glyphs for them
         at all — and every other run is wrapped LTR.

         Each run is wrapped whole. f:emit-bidi-text is not reused for the Latin
         side because it joins only the words of a siglum, so "A Section" would
         become two separate embeddings and read "Section A" in an RTL slot.

         A table-of-contents entry is the same problem in another slot, so
         f:format-section-title calls this too. -->
    <xsl:function name="f:emit-bidi-mark" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <xsl:variable name="parts" as="xs:string*">
            <!-- Hebrew segments joined by whitespace or connecting punctuation are
                 one run. A paired parsha name is written with an en-dash —
                 תַזְרִיעַ–מְצֹרָע — which is outside the Hebrew block, so splitting on it
                 would make the dash its own LTR embedding and let a neighbouring
                 chapter number reorder into the middle of the name. (The maqaf of
                 לֶךְ־לְךָ is inside the block and was never at risk.) -->
            <xsl:analyze-string select="$s"
                                regex="[&#x0590;-&#x05FF;&#xFB1D;-&#xFB4F;]+([\s&#x2010;-&#x2015;/,.:;-]*[&#x0590;-&#x05FF;&#xFB1D;-&#xFB4F;]+)*">
                <xsl:matching-substring>
                    <xsl:sequence select="concat('\texthebrew{', f:escape-tex(.), '}')"/>
                </xsl:matching-substring>
                <xsl:non-matching-substring>
                    <!-- Whitespace separating two runs carries no direction of
                         its own; wrapping it would only add empty groups. -->
                    <xsl:if test="normalize-space(.)">
                        <xsl:sequence select="concat('{\textdir TLT\foreignlanguage{english}{',
                                                     f:escape-tex(.), '}}')"/>
                    </xsl:if>
                </xsl:non-matching-substring>
            </xsl:analyze-string>
        </xsl:variable>
        <xsl:sequence select="string-join($parts, '')"/>
    </xsl:function>

    <xsl:function name="f:escape-url" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <!-- Inside \href targets, only `%`, `#`, and `\` need escaping. -->
        <xsl:variable name="t1" select="replace($s, '\\', '\\textbackslash{}')"/>
        <xsl:variable name="t2" select="replace($t1, '%', '\\%')"/>
        <xsl:variable name="t3" select="replace($t2, '#', '\\#')"/>
        <xsl:sequence select="$t3"/>
    </xsl:function>

</xsl:stylesheet>
