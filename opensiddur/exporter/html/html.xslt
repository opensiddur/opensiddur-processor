<?xml version="1.0" encoding="UTF-8"?>
<!--
  Compiled JLPTEI to the body of an electronic book: an HTML fragment, rooted at <main>.

  The input is a compiled document that html/markers.py has prepared: every scope the
  compiler left undecided is numbered (@p:cid on both of its markers), and every element and
  run of text it governs is labelled with its number (@p:scopes, and p:span around text). A
  label becomes a class, c<n>; a scope's markers carry m<n>. The reader's device hides
  whatever carries the class of a scope that does not hold, with one CSS rule per scope, so
  how the scopes nest and cross is settled here once and never again.

  Polyglot output: well-formed, so the same fragment can go into an EPUB.
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
    xmlns:p="http://jewishliturgy.org/ns/processing"
    xmlns:f="http://jewishliturgy.org/ns/functions"
    xmlns="http://www.w3.org/1999/xhtml"
    exclude-result-prefixes="#all">

    <xsl:output method="xhtml" html-version="5" omit-xml-declaration="yes" indent="no"/>

    <!-- typography.markers.conditional: what brackets an undecided run within a paragraph,
         and what delimits an undecided passage of whole blocks: a rule (drawn by CSS),
         the same brackets, or nothing. -->
    <xsl:param name="inline-open" as="xs:string" select="'['"/>
    <xsl:param name="inline-close" as="xs:string" select="']'"/>
    <xsl:param name="block" as="xs:string" select="'rule'"/>
    <!-- A page reference links to its destination. The source's own words ("continued on page")
         surround it, so the link shows a symbol where print shows the number. -->
    <xsl:param name="page-ref-text" as="xs:string" select="'→'"/>
    <xsl:param name="page-ref-label" as="xs:string" select="'Go to the passage'"/>
    <!-- Whether the book carries a distribution notice. html.py sets it where the placeholder
         comment is left: after the first title page, or at the head of a book with none. -->
    <xsl:param name="distribution-notice" as="xs:boolean" select="false()"/>
    <xsl:param name="notes-mark" as="xs:string" select="'numeric'"/>
    <xsl:param name="notes-visible" as="xs:boolean" select="true()"/>

    <!-- The first element to carry a URN gets it as its id, so #urn:x-opensiddur:... links
         to it; the parallel column's copy, and every later one, does not, ids being unique. -->
    <xsl:key name="corresp" match="*[@corresp]" use="tokenize(@corresp)[1]"/>
    <xsl:key name="opener" match="j:conditional[@p:cid]" use="@p:cid"/>

    <!-- The notes the book numbers, the same ones the PDF numbers (reledmac.xslt,
         f:editorial-note-emissions-before): editorial and commentary notes in the text —
         not a header's notes, not standoff ones, not instructions. -->
    <xsl:accumulator name="note-number" as="xs:integer" initial-value="0">
        <xsl:accumulator-rule
            match="tei:note[not(@type = ('instruction', 'description'))][ancestor::tei:text][not(ancestor::tei:standOff)]"
            select="$value + 1"/>
    </xsl:accumulator>
    <xsl:mode use-accumulators="note-number" on-no-match="shallow-skip"/>

    <xsl:function name="f:note-mark" as="xs:string">
        <xsl:param name="serial" as="xs:integer"/>
        <xsl:variable name="symbols" select="('*', '†', '‡', '§', '‖', '¶')"/>
        <xsl:sequence select="
            if ($notes-mark = 'alpha') then format-integer($serial, 'a')
            else if ($notes-mark = 'roman') then format-integer($serial, 'i')
            else if ($notes-mark = 'symbol') then string-join(
                for $repeat in 1 to (($serial - 1) idiv count($symbols) + 1)
                return $symbols[($serial - 1) mod count($symbols) + 1], '')
            else string($serial)"/>
    </xsl:function>

    <!-- Whether a language is written right to left. A script subtag decides: he-Latn is a
         transliteration, set left to right. The PDF follows the same rule
         (tex/common.xsl, f:is-rtl-lang). -->
    <xsl:function name="f:is-rtl" as="xs:boolean">
        <xsl:param name="lang" as="xs:string"/>
        <xsl:variable name="subtags" select="tokenize(lower-case($lang), '-')"/>
        <xsl:variable name="script" select="$subtags[position() gt 1][string-length(.) = 4][1]"/>
        <xsl:sequence select="if ($script) then $script = ('hebr', 'arab', 'syrc')
                              else $subtags[1] = ('he', 'yi', 'arc', 'ar', 'fa', 'jrb', 'lad', 'ji')"/>
    </xsl:function>

    <!-- True when the first thing a scope governs is a rubric: an instruction, or the
         description of the passage (JLPTEI-3, *Kinds of rubric*). It announces the scope
         as the scope's own note would. An annotation anchored at the scope's start is
         passed over, as a milestone is: it is the apparatus, not the text. reledmac.xslt
         asks the same question. -->
    <xsl:function name="f:opens-with-rubric" as="xs:boolean">
        <xsl:param name="start" as="element()"/>
        <xsl:sequence select="exists($start/following-sibling::node()[
            not(self::text()[normalize-space() = '']) and not(self::tei:milestone or self::tei:pb)
            and not(self::tei:note[not(@type = ('instruction', 'description'))])][1]
            [self::tei:note[@type = ('instruction', 'description')]])"/>
    </xsl:function>

    <!-- Whether a node sits in running text, where only phrasing content is allowed. -->
    <xsl:function name="f:in-text" as="xs:boolean">
        <xsl:param name="node" as="node()"/>
        <xsl:sequence select="exists($node/ancestor::*[
            self::tei:p or self::tei:l or self::tei:ab or self::tei:head or self::tei:seg
            or self::tei:hi or self::tei:note or self::tei:label or self::tei:item
            or self::tei:foreign or self::tei:titlePart or self::tei:byline
            or self::tei:docAuthor or self::tei:docImprint or self::tei:docEdition
            or self::tei:docDate or self::tei:publisher or self::tei:pubPlace
            or self::p:transcludeInline])"/>
    </xsl:function>

    <!-- class (the given names, then the scope classes), lang and dir, and id. -->
    <xsl:template name="attributes">
        <xsl:param name="class" as="xs:string*" select="()"/>
        <xsl:variable name="classes" as="xs:string*"
                      select="($class[. ne ''], tokenize(@p:scopes) ! concat('c', .))"/>
        <xsl:if test="exists($classes)">
            <xsl:attribute name="class" select="string-join($classes, ' ')"/>
        </xsl:if>
        <xsl:if test="@xml:lang">
            <xsl:attribute name="lang" select="@xml:lang"/>
            <xsl:attribute name="dir" select="if (f:is-rtl(@xml:lang)) then 'rtl' else 'ltr'"/>
        </xsl:if>
        <xsl:if test="@corresp and key('corresp', tokenize(@corresp)[1])[1] is .">
            <xsl:attribute name="id" select="tokenize(@corresp)[1]"/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="/">
        <main class="os-book">
            <xsl:for-each select="tei:TEI">
                <xsl:call-template name="attributes"/>
                <xsl:apply-templates select="tei:text"/>
            </xsl:for-each>
        </main>
    </xsl:template>

    <xsl:template match="tei:teiHeader | tei:standOff"/>

    <xsl:template match="text()">
        <xsl:value-of select="."/>
    </xsl:template>

    <!-- ── Structure ──────────────────────────────────────────────────────── -->

    <xsl:template match="tei:text">
        <div class="text">
            <xsl:call-template name="attributes"/>
            <xsl:if test="$distribution-notice and empty(//tei:titlePage)">
                <xsl:comment>@@DISTRIBUTION@@</xsl:comment>
            </xsl:if>
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <!-- What the digital editions say about themselves (tei:div type="colophon", gathered by
         cli_common.relocate_colophons). Marked out so that html.py can move it after the
         book's own colophon, in the footer. -->
    <xsl:template match="tei:back[@p:colophon]" priority="2">
        <xsl:comment>@@COLOPHON-START@@</xsl:comment>
        <section>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'colophon'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </section>
        <xsl:comment>@@COLOPHON-END@@</xsl:comment>
    </xsl:template>

    <xsl:template match="tei:front | tei:body | tei:back">
        <section>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="local-name()"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </section>
    </xsl:template>

    <!-- Blocks inside running text — a list in a paragraph, verse in a note — are spans that
         CSS sets as blocks: a block element there would close the paragraph around it, and the
         text after it would escape the paragraph and the scopes that govern it. -->
    <xsl:template match="tei:div">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'section'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="('div', @type ! concat('div-', .), @p:part ! concat('part-', .))"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:head">
        <xsl:variable name="level"
                      select="max((1, min((6, xs:integer((@p:heading-level, 2)[1])))))"/>
        <xsl:element name="{if (f:in-text(.)) then 'span' else concat('h', $level)}">
            <xsl:attribute name="data-heading-level" select="$level"/>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="('head',
                    if (preceding-sibling::tei:head or ancestor::p:parallelItem[@role = 'parallel'])
                    then 'head-translation' else ())"/>
            </xsl:call-template>
            <!-- Which section it heads, for the contents to know whether any of its text shows
                 (markers.py, _sections). -->
            <xsl:if test="@p:section">
                <xsl:attribute name="data-section" select="@p:section"/>
            </xsl:if>
            <xsl:choose>
                <xsl:when test="@p:psalm-title">
                    <xsl:value-of select="@p:psalm-title"/>
                    <xsl:call-template name="psalm-title-annotations"/>
                </xsl:when>
                <xsl:otherwise><xsl:apply-templates/></xsl:otherwise>
            </xsl:choose>
        </xsl:element>
    </xsl:template>

    <!-- A liturgical psalm wrapper owns its bilingual title. The transcluded
         edition may also supply a title or book heading; keep its anchor and
         annotations without printing a second title. -->
    <xsl:template match="tei:head[@p:suppress-psalm-heading = 'true'] |
                        tei:head[ancestor::tei:div[@type = 'psalm']]
                                [not(parent::tei:div[@type = 'psalm'])]
                                [not(ancestor::tei:note)]" priority="2">
        <xsl:if test="@corresp">
            <span><xsl:call-template name="attributes"/></span>
        </xsl:if>
        <xsl:call-template name="psalm-title-annotations"/>
    </xsl:template>

    <xsl:template name="psalm-title-annotations">
        <xsl:apply-templates select="descendant::*[self::tei:note or self::tei:anchor or self::tei:milestone]
                                    [not(ancestor::tei:note)]"/>
    </xsl:template>

    <xsl:template match="tei:p | tei:ab">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'p'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="(if (f:in-text(.)) then 'np' else (),
                                         if (ancestor::tei:titlePage and
                                             not(ancestor::tei:titlePart or ancestor::tei:epigraph))
                                         then 'title-page-block' else (),
                                         @type ! concat('p-', .),
                                         tokenize(@rend) ! concat('rend-', .))"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:lg">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'div'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'lg'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:l">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'div'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'l'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:lb">
        <br>
            <xsl:call-template name="attributes"/>
        </br>
    </xsl:template>

    <xsl:template match="tei:list">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'ul'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="('list', @type ! concat('list-', .))"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="tei:list/tei:item | tei:list/tei:label">
        <xsl:element name="{if (f:in-text(..)) then 'span' else 'li'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="local-name()"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <!-- ── The title page ─────────────────────────────────────────────────── -->

    <xsl:template match="tei:titlePage">
        <header>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'title-page'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </header>
        <xsl:if test="$distribution-notice and . is (//tei:titlePage)[1]">
            <xsl:comment>@@DISTRIBUTION@@</xsl:comment>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tei:docTitle">
        <div>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'doc-title'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <!-- An epigraph holds paragraphs of its own, and a <p> cannot hold a <p>: the
         parser would close the outer one, leaving the epigraph's class on an empty
         paragraph and its text unstyled after it. -->
    <xsl:template match="tei:titlePart | tei:byline | tei:docEdition | tei:docImprint
                         | tei:epigraph | tei:imprimatur">
        <xsl:element name="{if (f:in-text(.)) then 'span'
                            else if (self::tei:epigraph) then 'div' else 'p'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="(local-name(), @type ! concat(local-name(..), '-', .))"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <!-- ── Words ──────────────────────────────────────────────────────────── -->

    <xsl:template match="tei:seg | tei:hi | tei:foreign | tei:label | tei:emph | tei:q
                         | tei:abbr | tei:expan | tei:sic | tei:corr
                         | tei:docAuthor | tei:docDate | tei:publisher | tei:pubPlace
                         | j:divineName | p:transcludeInline | p:span">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="(if (self::p:span) then () else local-name(),
                                         @type ! concat(local-name(..), '-', .),
                                         @p:optional-reference ! concat('oref', .),
                                         tokenize(@rend) ! concat('rend-', .))"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <xsl:template match="tei:ref[matches(@target, '^https?://')]">
        <a href="{@target}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'ref'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </a>
    </xsl:template>

    <!-- Resolved by page_references.resolve_page_references: @target is a page label's @n. -->
    <xsl:template match="tei:ref[@type='page']">
        <a href="#{@target}" aria-label="{$page-ref-label}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'page-ref'"/>
            </xsl:call-template>
            <xsl:value-of select="$page-ref-text"/>
        </a>
    </xsl:template>

    <!-- The first occurrence of a destination owns the id, which works without scripts. The
         reader's script goes to the first occurrence its settings show (data-page-label). -->
    <xsl:template match="tei:anchor[@type='page-label']">
        <span class="page-label" data-page-label="{@n}">
            <xsl:if test="not(@subtype = 'repeat')">
                <xsl:attribute name="id" select="@n"/>
            </xsl:if>
        </span>
        <!-- Notes the compiler set inside it follow it. -->
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="tei:ref">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'ref'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <xsl:template match="tei:pb">
        <span data-n="{@n}" title="{@ed} {@n}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'pb'"/>
            </xsl:call-template>
        </span>
    </xsl:template>

    <!-- The compiler sets a note whose target has no words of its own inside the anchor or
         milestone it targets, so their children are the notes, and are kept. -->
    <xsl:template match="tei:anchor[@corresp] | tei:milestone[@corresp]" priority="-1">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'anchor'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <xsl:template match="tei:anchor | tei:milestone" priority="-1.5">
        <xsl:apply-templates/>
    </xsl:template>

    <!-- Alternate wordings: all are shown, the first plain and the rest in parentheses, as
         the printed book does; a written form is shown after the read one. -->
    <xsl:template match="tei:choice">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'choice'"/>
            </xsl:call-template>
            <xsl:apply-templates mode="choice"/>
        </span>
    </xsl:template>

    <xsl:template match="j:option" mode="choice">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="if (preceding-sibling::j:option) then ('option', 'option-alt')
                                        else 'option'"/>
            </xsl:call-template>
            <xsl:choose>
                <xsl:when test="preceding-sibling::j:option">
                    <xsl:call-template name="reading-form"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates/>
                </xsl:otherwise>
            </xsl:choose>
        </span>
    </xsl:template>

    <xsl:template match="j:read" mode="choice">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'read'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <xsl:template match="j:written" mode="choice">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="if (../j:read) then ('written', 'written-alt') else 'written'"/>
            </xsl:call-template>
            <xsl:call-template name="reading-form"/>
        </span>
    </xsl:template>

    <!-- A second form's words, in a span of their own inside the one reader.css puts the
         parentheses around: the role (styles.alternative_reading, styles.ketiv) styles the
         words and not the parentheses, which are the text's, as in print. The parentheses
         stay on the outer span so that a condition hiding the form hides them too. -->
    <xsl:template name="reading-form">
        <span class="form">
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <!-- Anything else in a choice — a scope's markers, a span of its text — as anywhere. -->
    <xsl:template match="node()" mode="choice">
        <xsl:apply-templates select="."/>
    </xsl:template>

    <xsl:template match="text()[not(normalize-space())]" mode="choice"/>

    <!-- ── Milestones ─────────────────────────────────────────────────────── -->

    <xsl:template match="tei:milestone[@unit = 'verse'][@n]">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'v'"/>
            </xsl:call-template>
            <xsl:value-of select="@n"/>
        </span>
        <!-- Notes the compiler set inside it follow it. -->
        <xsl:apply-templates/>
    </xsl:template>

    <!-- A chapter number is set only in a book of the Bible; a psalm quoted in the liturgy
         is named by its heading. -->
    <xsl:template match="tei:milestone[@unit = 'chapter'][@n][ancestor::tei:div[@type = 'book']]
                                     [not(ancestor::tei:div[@type = 'psalm'])][not(@p:chapter-label = 'hidden')]">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'ch'"/>
            </xsl:call-template>
            <xsl:value-of select="@n"/>
        </span>
        <!-- Notes the compiler set inside it follow it. -->
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="tei:milestone[starts-with(@unit, 'aliyah') or starts-with(@unit, 'maftir')][@n]
                         | tei:milestone[@unit = 'parsha'][@n]">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="if (@unit = 'parsha') then 'parsha' else 'aliyah'"/>
            </xsl:call-template>
            <xsl:value-of select="@n"/>
        </span>
        <!-- Notes the compiler set inside it follow it. -->
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="tei:milestone[@unit = 'citation'][@n]">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'citation'"/>
            </xsl:call-template>
            <xsl:value-of select="@n"/>
        </span>
        <!-- Notes the compiler set inside it follow it. -->
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="tei:milestone[@rend = '****']">
        <span role="separator">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'section-separator'"/>
            </xsl:call-template>
        </span>
        <!-- Notes the compiler set inside it follow it. -->
        <xsl:apply-templates/>
    </xsl:template>

    <!-- ── Notes ──────────────────────────────────────────────────────────── -->

    <xsl:template match="tei:note[@type = ('instruction', 'description')]">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'p'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'rubric'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <!-- Every other note opens as a popover from its numbered mark. -->
    <xsl:template match="tei:note">
        <xsl:if test="$notes-visible">
        <xsl:variable name="number" select="accumulator-before('note-number')"/>
        <xsl:variable name="id" select="concat('note-', $number)"/>
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'note-anchor'"/>
            </xsl:call-template>
            <button type="button" class="note-ref" popovertarget="{$id}"
                    aria-label="Note {$number}">
                <xsl:value-of select="f:note-mark($number)"/>
            </button>
            <span popover="" id="{$id}" role="note"
                  class="note{@type ! concat(' note-', .)}">
                <span class="note-number"><xsl:value-of select="f:note-mark($number)"/></span>
                <xsl:apply-templates/>
            </span>
        </span>
        </xsl:if>
    </xsl:template>

    <!-- ── Conditional scopes ─────────────────────────────────────────────── -->

    <!-- A scope's markers: the rubric that says when to read it, and a bracket (in running
         text) or a rule (around blocks) to show how far it runs. Which of them show depends
         on how the scope resolves; see reader.js. -->
    <xsl:template match="j:conditional[@p:cid] | j:endConditional[@p:cid]">
        <xsl:variable name="in-text" select="f:in-text(.)"/>
        <xsl:variable name="opens" select="exists(self::j:conditional)"/>
        <!-- The book's own marks are on the opener; the closer shares its scope number. -->
        <xsl:variable name="opener" select="if ($opens) then . else key('opener', @p:cid)"/>
        <xsl:element name="{if ($in-text) then 'span' else 'div'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="('cm', if ($opens) then 'cm-open' else 'cm-close',
                                         concat('m', @p:cid),
                                         if ($in-text) then 'cm-inline' else 'cm-block',
                                         if ($opens and not(tei:note[@type = ('instruction', 'description')])
                                             and not(f:opens-with-rubric(.)))
                                         then 'cm-norubric' else (),
                                         if (@p:silent = 'true') then 'cm-silent' else (),
                                         if ($opener/@type = 'marked') then 'cm-marked' else ())"/>
            </xsl:call-template>
            <xsl:if test="$opens">
                <xsl:apply-templates select="tei:note[@type = ('instruction', 'description')]" mode="rubric"/>
                <!-- Notes the compiler set on the rubric: numbered with the others, so shown. -->
                <xsl:apply-templates select="tei:note[not(@type = ('instruction', 'description'))]"/>
            </xsl:if>
            <span class="cm-br" aria-hidden="true">
                <xsl:if test="$in-text or $block = 'brackets'">
                    <xsl:value-of select="if ($opens) then $inline-open else $inline-close"/>
                </xsl:if>
            </span>
        </xsl:element>
    </xsl:template>

    <!-- An unpaired marker governs nothing that can be found; its rubric is still said. -->
    <xsl:template match="j:conditional">
        <xsl:apply-templates select="tei:note"/>
    </xsl:template>

    <xsl:template match="j:endConditional"/>

    <xsl:template match="tei:note" mode="rubric">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'rubric'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <!-- ── Compiler structure ─────────────────────────────────────────────── -->

    <!-- A transclusion is no unit of the text, but it can be governed by a scope, so it
         stays an element (laid out as if absent) to carry the class. -->
    <xsl:template match="p:transclude">
        <xsl:element name="{if (f:in-text(.)) then 'span' else 'div'}">
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="'tr'"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="p:parallel">
        <div>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="('par', @column-order ! concat('par-', .),
                                         @p:row ! concat('r', .))"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <!-- A column with no words (col-empty) stays shown when the reader shows only the other
         column's language: its row has nothing else to show. -->
    <xsl:template match="p:parallelItem">
        <div>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class"
                                select="('col', @role ! concat('col-', .),
                                         if (normalize-space(.) = '') then 'col-empty' else ())"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <!-- Anything not mapped above keeps its words. -->
    <xsl:template match="tei:* | j:* | p:*" priority="-2">
        <span>
            <xsl:call-template name="attributes">
                <xsl:with-param name="class" select="concat('tei-', local-name())"/>
            </xsl:call-template>
            <xsl:apply-templates/>
        </span>
    </xsl:template>

    <xsl:template match="tei:fs | tei:f | j:all | j:any | j:none | j:one | j:condition
                         | tei:ptr" priority="-1.5"/>

</xsl:stylesheet>
