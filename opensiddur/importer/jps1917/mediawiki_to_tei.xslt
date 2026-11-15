<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:f="urn:opensiddur:jps1917"
    exclude-result-prefixes="#all">

    <xsl:output method="xml" omit-xml-declaration="yes"/>

    <!-- Use on-no-match to raise an error for unhandled elements -->
    <xsl:mode on-no-match="fail"/>

    <xsl:param name="wrapper_div_type" as="xs:string?"/>
    <!-- book file/reference name-->
    <xsl:param name="book_name" as="xs:string?"/>
    <!-- The scan page a page break links to is this followed by its number in the scan,
         which convert_wikisource.py records on each page as @scan. -->
    <xsl:param name="facs_prefix" as="xs:string?"/>

    <!-- is the book section-delimited? -->
    <xsl:param name="is_section" as="xs:boolean?"/>

    <!-- The parshah name table, as JSON, keyed by consonant skeleton. Produced by
    opensiddur.importer.util.parshiyot.skeleton_map_json(); each entry is
    {"n": canonical Hebrew name, "slug": URN path segment}. Passed as a string because
    xslt_transform_string can only marshal atomic values. -->
    <xsl:param name="parsha_names" as="xs:string?"/>

    <!-- The Hebrew name of the parshah a book opens with, for the five books of the Torah.
    Their opening parshiyot have no running head in the source — the book title heading
    occupies that slot — so they have to be supplied rather than read off the page. -->
    <xsl:param name="first_parsha" as="xs:string?"/>

    <xsl:variable name="parshiyot" as="map(*)"
        select="if ($parsha_names) then parse-json($parsha_names) else map{}"/>

    <!-- Reduce a parshah name to its bare consonant skeleton, so that the way a source
    happens to spell it — pointed or not, maqaf written as a maqaf, a space, or nothing —
    does not affect the lookup. Mirrors
    opensiddur.importer.util.hebrew.normalize_hebrew: everything outside the Hebrew letter
    range goes, which covers combining marks as well as separators. -->
    <xsl:function name="f:parsha-skeleton" as="xs:string">
        <xsl:param name="name" as="xs:string"/>
        <xsl:sequence select="replace($name, '[^&#x05D0;-&#x05EA;]', '')"/>
    </xsl:function>

    <!-- The table entry for a parshah named in Hebrew. Terminates rather than guessing:
    a name the table does not know is either a typo or, as with the Psalm 119 acrostic,
    markup that is not a parshah at all. -->
    <xsl:function name="f:parsha" as="map(*)">
        <xsl:param name="name" as="xs:string"/>
        <xsl:variable name="entry" select="$parshiyot(f:parsha-skeleton($name))"/>
        <xsl:if test="empty($entry)">
            <xsl:message terminate="yes">
                <xsl:text>Unknown parshah name: </xsl:text>
                <xsl:value-of select="$name"/>
                <xsl:text> (skeleton: </xsl:text>
                <xsl:value-of select="f:parsha-skeleton($name)"/>
                <xsl:text>) in book </xsl:text>
                <xsl:value-of select="$book_name"/>
            </xsl:message>
        </xsl:if>
        <xsl:sequence select="$entry"/>
    </xsl:function>

    <xsl:function name="f:parsha-milestone" as="element(tei:milestone)">
        <xsl:param name="name" as="xs:string"/>
        <xsl:variable name="entry" select="f:parsha($name)"/>
        <tei:milestone unit="parsha" n="{$entry?n}"
            corresp="urn:x-opensiddur:text:bible:{$book_name}/{$entry?slug}"/>
    </xsl:function>

    <!-- Identity template: copy everything by default -->
    <xsl:template match="text()">
        <xsl:copy/>
    </xsl:template>

    <xsl:template match="mediawikis.wrapper">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="mediawikis">
        <xsl:variable name="sectioned" as="node()*">
            <mediawikis.wrapper>
                <xsl:choose>
                    <xsl:when test="$is_section">
                        <xsl:apply-templates mode="sectioned"/>                    
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:copy-of select="node()"/>
                    </xsl:otherwise>
                </xsl:choose>
            </mediawikis.wrapper>
        </xsl:variable>
        <xsl:variable name="processed" as="node()*">
            <xsl:apply-templates select="$sectioned" />
        </xsl:variable>
        <xsl:variable name="wrapped-content" as="node()*">
            <xsl:for-each-group select="$processed" group-starting-with="p">
                <xsl:choose>
                    <!-- leading group -->
                    <xsl:when test="not(current-group()[1][self::p])">
                        <xsl:apply-templates select="current-group()" mode="copy"/>
                    </xsl:when>
                    <xsl:when test="current-group()/self::tei:head">
                        <!-- group contains a head element - process maintaining order -->
                        <xsl:for-each-group select="current-group()" group-adjacent="boolean(self::tei:head)">
                            <xsl:choose>
                                <xsl:when test="current-grouping-key()">
                                    <!-- This group contains head elements - don't wrap -->
                                    <xsl:apply-templates select="current-group()" mode="copy"/>
                                </xsl:when>
                                <xsl:when test="not(current-group()/self::text()[normalize-space(.)])">
                                    <!-- This group contains no text - do not wrap -->
                                    <xsl:apply-templates select="current-group()" mode="copy"/>
                                </xsl:when>
                                <xsl:otherwise>
                                    <!-- This group contains non-head elements - wrap in p -->
                                    <tei:p>
                                        <xsl:apply-templates select="current-group()" mode="copy"/>
                                    </tei:p>
                                </xsl:otherwise>
                            </xsl:choose>
                        </xsl:for-each-group>
                    </xsl:when>
                    <xsl:when test="current-group()/self::tei:ab">
                        <!-- ab can't appear in p and is already a block -->
                        <xsl:apply-templates select="current-group()" mode="copy"/>
                    </xsl:when>
                    <xsl:when test="
                        not(current-group()[not(self::p)]
                            [self::text()[normalize-space(.)] or (self::* and not(self::tei:milestone))])">
                        <!-- Nothing here but milestones: a parshah running head, a Psalm
                        119 acrostic letter or an asterisk dinkus. A milestone standing
                        alone is not paragraph content — it marks a boundary between
                        paragraphs, and the division it opens contains the chapter and
                        verse milestones that follow — so leave it as a child of the
                        enclosing div rather than inventing a paragraph for it. -->
                        <xsl:apply-templates select="current-group()" mode="copy"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <tei:p>
                            <xsl:apply-templates select="current-group()" mode="copy"/>
                        </tei:p>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:for-each-group>
        </xsl:variable>
        <xsl:choose>
            <xsl:when test="$wrapper_div_type">
                <xsl:choose>
                    <xsl:when test="count($wrapped-content/self::tei:head) &gt; 1">
                        <!-- handle the case of Psalms, which has multiple sub-books -->
                        <tei:div 
                            type="{$wrapper_div_type}" 
                            >
                            <xsl:if test="$book_name">
                                <xsl:attribute name="n" select="$book_name"/>
                                <xsl:attribute name="corresp" select="concat('urn:x-opensiddur:text:bible:', $book_name)"/>
                            </xsl:if>
                            <xsl:for-each-group select="$wrapped-content" group-starting-with="tei:head">
                                <xsl:choose>
                                    <xsl:when test="position() = 1 and not(current-group()[1][self::tei:head])">
                                        <!-- First group doesn't start with head - do not createa div for it -->
                                        <xsl:copy-of select="current-group()"/>
                                    </xsl:when>
                                    <xsl:when test="current-group()[1][self::tei:head]">
                                        <!-- Group starts with head -->
                                        <tei:div type="{$wrapper_div_type}">
                                            <xsl:attribute name="n" select="concat($book_name, '_', position() - 1)"/>
                                            <xsl:attribute name="corresp" select="concat('urn:x-opensiddur:text:bible:', $book_name, '_', position() - 1)"/>
                                            <xsl:copy-of select="current-group()"/>
                                        </tei:div>
                                    </xsl:when>
                                </xsl:choose>
                            </xsl:for-each-group>
                        </tei:div>
                    </xsl:when>
                    <xsl:otherwise>
                        <tei:div 
                            type="{$wrapper_div_type}" 
                            >
                            <xsl:if test="$book_name">
                                <xsl:attribute name="n" select="$book_name"/>
                                <xsl:attribute name="corresp" select="concat('urn:x-opensiddur:text:bible:', $book_name)"/>
                            </xsl:if>
                            <xsl:choose>
                                <xsl:when test="$first_parsha">
                                    <!-- The book's opening parshah, which the source does not
                                    mark, goes after the title heading and before the text, as
                                    a child of the div like every parshah milestone the running
                                    heads produce. -->
                                    <xsl:variable name="head"
                                        select="$wrapped-content/self::tei:head[1]"/>
                                    <xsl:copy-of select="
                                        $wrapped-content[exists($head) and (. &lt;&lt; $head or . is $head)]"/>
                                    <xsl:sequence select="f:parsha-milestone($first_parsha)"/>
                                    <xsl:copy-of select="
                                        $wrapped-content[empty($head) or . &gt;&gt; $head]"/>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:copy-of select="$wrapped-content"/>
                                </xsl:otherwise>
                            </xsl:choose>
                        </tei:div>
                    </xsl:otherwise>
                </xsl:choose>
                
            </xsl:when>
            <xsl:otherwise>
                <xsl:copy-of select="$wrapped-content"/>
            </xsl:otherwise>
        </xsl:choose>
        <xsl:result-document href="file:///output/standoff">
            <tei:standOff type="notes">
                <xsl:copy-of select="$processed/self::tei:note" />
            </tei:standOff>
        </xsl:result-document>
    </xsl:template>

    <xsl:template match="mediawiki">
        <xsl:variable name="page-number" select="(
            noinclude[last()]/c, 
            following-sibling::mediawiki[1]/noinclude[last()]/c/number() - 1,
            preceding-sibling::mediawiki[1]/noinclude[last()]/c/number() + 1)[1]"/>
        <tei:pb n="{$page-number}" ed="1917">
            <xsl:if test="$facs_prefix and @scan">
                <xsl:attribute name="facs" select="concat($facs_prefix, @scan)"/>
            </xsl:if>
        </tei:pb>
        <xsl:apply-templates />  
    </xsl:template>

    <xsl:template match="noinclude"/>

    <xsl:template match="nop"/>

    <xsl:template match="bar">
        <xsl:value-of select="string-join(for $i in 1 to @length return '—', '')"/>
    </xsl:template>

    <xsl:template match="c[larger|x-larger|xx-larger]">
        <tei:head>
            <xsl:apply-templates />
        </tei:head>
    </xsl:template>

    <xsl:template match="larger|x-larger|xx-larger">
        <xsl:apply-templates />
    </xsl:template>

    <xsl:template match="c" priority="-1">
        <xsl:message terminate="yes">
            <xsl:text>c element found in unexpected context</xsl:text>
            <xsl:value-of select="path(.)"/>

            Is section start or end:
            <xsl:value-of select="some $s in ($section-start, $section-end) satisfies ($s is .)"/>
                
            Keep elements that contain section markers:
            <xsl:value-of select="some $s in ($section-start, $section-end) satisfies ($s = descendant::node())"/>
            
            Descendant node is section-start or section-end:
            <xsl:value-of select="descendant::node() = $section-start or descendant::node() = $section-end"/>
                
            Remove everything before section-start:
            <xsl:value-of select=". &lt;&lt; $section-start"/>
            
            Remove everything after section-end:
            <xsl:value-of select=". &gt;&gt; $section-end"/>
                
        </xsl:message>
    </xsl:template>

    <!-- A centered Hebrew word on its own is a parshah running head:
    {{c|{{lang|he|ויצא}}}} -->
    <xsl:template match="c[lang][not(text()[normalize-space()])]">
        <xsl:sequence select="f:parsha-milestone(normalize-space(lang))"/>
    </xsl:template>

    <!-- A centered Hebrew letter followed by its printed Latin name is an acrostic stanza
    heading in Psalm 119: {{c|{{lang|he|א}} ALEPH.}}. These are not parshiyot — they were
    emitted as unit="parsha" until they collided with the real ones — and they are not
    addressable text divisions, so they take no corresp. They must not become tei:head
    either: the multiple-head grouping in the mediawikis template would split Psalms into
    a sub-book div per stanza. -->
    <xsl:template match="c[lang][text()[normalize-space()]]">
        <tei:milestone unit="acrostic" n="{normalize-space(lang)}"/>
    </xsl:template>

    <!-- double height row = double-line break - it's a paragraph... -->
    <xsl:template match="dhr">
        <p/>
    </xsl:template>

    <xsl:template match="float_right">
        <tei:lb type="last"/><xsl:apply-templates />
    </xsl:template>


    <!-- ignore gaps for now... -->
    <xsl:template match="gap"/>

    <!-- overfloat left is used to indicate letters that mark hebrew acrostics,
    for example, in Psalms. They are not actually part of the text 
    If JLPTEI were to support floating elements, we could support it...
    -->
    <xsl:template match="overfloat_left"/>

    <!-- p will be used as a grouping element -->
    <xsl:template match="p">
        <p/>
    </xsl:template>

    <!-- p inside "c" is a line break in a heading, not a paragraph -->
    <xsl:template match="p[ancestor::c]">
        <tei:lb/>
    </xsl:template>

    <!-- reconstructed text with an error and editorial note -->
    <xsl:template match="reconstruct">
        <xsl:variable name="note-id" select="concat('reconstruct-', generate-id())"/>
        <xsl:apply-templates select="reg/node()"/>
        <tei:anchor xml:id="{$note-id}"/>
        <tei:note type="editorial" target="#{$note-id}">
            <xsl:apply-templates select="note/node()"/>
        </tei:note>
    </xsl:template>

    <!-- sic is an empty template and the incorrect word may be before or after the template :-( -->
    <xsl:template match="sic">
        <xsl:variable name="note-id" select="concat('sic-', generate-id())"/>
    
        <tei:anchor xml:id="{$note-id}"/>
        <tei:note type="editorial" target="#{$note-id}">sic</tei:note>
    </xsl:template>


    <xsl:template match="sc">
        <tei:hi rend="small-caps">
            <xsl:apply-templates select="node()"/>
        </tei:hi>
    </xsl:template>

    <xsl:template match="smaller">
        <tei:hi rend="small">
            <xsl:apply-templates select="node()"/>
        </tei:hi>
    </xsl:template>

    <xsl:template match="larger">
        <tei:hi rend="large">
            <xsl:apply-templates select="node()"/>
        </tei:hi>
    </xsl:template>

    <!-- smaller block and span are both used to indicate liturgically repeated verses -->
    <xsl:template match="smaller_block|span">
        <tei:ab rend="small" type="repetition">
            <xsl:apply-templates select="node()"/>
        </tei:ab>
    </xsl:template>

    <!-- A repeated verse is set as the verse is, a line at a time. Its source starts each
         line with {{gap}} and ends it with <br />, which elsewhere in the 1917 JPS mark the
         items of a list (see br[1] below): read that way, each item took only the newline
         after its break, and the repeated lines were lost. Here the gap opens a line, as
         a poetry line's indent does, and the break is only the end of one. -->
    <xsl:template match="(smaller_block|span)/gap" priority="2">
        <tei:lb/>
    </xsl:template>
    <xsl:template match="(smaller_block|span)/br" priority="2"/>
    <xsl:template match="(smaller_block|span)/text()" priority="2">
        <xsl:copy/>
    </xsl:template>

    <xsl:template match="sup">
        <tei:hi rend="superscript">
            <xsl:apply-templates select="node()"/>
        </tei:hi>
    </xsl:template>


    <xsl:template match="__link__">
        <!-- parse out the book, chapter, and verse. @title may name a page
        (book/chapter:verse), be a same-page anchor with no page (#chapter:verse,
        used for footnote cross-references within the book being converted), or
        name a page with no anchor (a table-of-contents link). -->
        <xsl:variable name="has-page" select="contains(@title, '/')"/>
        <xsl:variable name="has-anchor" select="contains(@title, '#')"/>
        <xsl:variable name="page-title" select="if ($has-page) then substring-after(@title, '/') else ()"/>
        <xsl:variable name="anchor" select="if ($has-anchor) then substring-after(@title, '#') else ()"/>

        <!-- a same-page anchor names no book, so fall back to the book being converted -->
        <xsl:variable name="raw-book" select="
            if (not($has-page)) then $book_name
            else if ($has-anchor) then substring-before($page-title, '#')
            else $page-title"/>
        <xsl:variable name="book" select="replace(lower-case($raw-book), ' ', '_')"/>
        <xsl:variable name="book-1" select="replace($book, '^i_(.*)', '$1_1')"/>
        <xsl:variable name="book-2" select="replace($book-1, '^ii_(.*)', '$1_2')"/>

        <xsl:variable name="target" select="
            if ($has-anchor) then
                concat('urn:x-opensiddur:text:bible:', $book-2, '/',
                    substring-before($anchor, ':'), '/', substring-after($anchor, ':'))
            else
                concat('urn:x-opensiddur:text:bible:', $book-2)"/>
        <tei:ref target="{$target}">
            <xsl:apply-templates select="node()"/>
        </tei:ref>
    </xsl:template>

    <!-- hyphenated word handling: put the entire word on one line/one page.
    if it crosses a page break, the entire word will be on the first page.
    -->
    <xsl:template match="hws">
        <xsl:apply-templates select="node()"/><xsl:apply-templates select="following::hwe[1]/node()"/>
    </xsl:template>
    <xsl:template match="hwe"/>

    <!-- this is a reference to an inline footnote that appears at this position.
    the appropriate action is to leave an anchor and the referencing note.
    A second processor will move the note to standoff markup.
    -->
    <xsl:template match="ref">
        <xsl:variable name="n" select="concat('ref-', generate-id())"/>
        <tei:anchor xml:id="ref-{$n}"/>
        <tei:note target="#ref-{$n}">
            <xsl:apply-templates />
        </tei:note>
    </xsl:template>

    <!-- in the 1917 JPS, it looks like br is being used for lists,
    not just typographical line breaks.-->
    <xsl:template match="br[1]">
        <tei:list>
            <xsl:apply-templates select="self::br | following-sibling::br" mode="br-list-item"/>
        </tei:list>
    </xsl:template>
    <xsl:template match="br|text()[preceding-sibling::br]"/>

    <xsl:template match="br" mode="br-list-item">
        <tei:item>
            <xsl:apply-templates select="following::text()[1]" mode="copy"/>
        </tei:item>
    </xsl:template>

    <!-- dropinitial is used as a chapter division-->
    <xsl:template match="dropinitial">
        <xsl:variable name="chapter" select="text()"/>
        <xsl:if test="$chapter = '1' and not(following-sibling::p[1]/preceding-sibling::text()[normalize-space(.)])">
            <!-- add an initial paragraph break -->
            <p/>
        </xsl:if>
        <!-- A chapter is opened either by its dropinitial or by an explicit verse 1 marker,
             never by both: the verse template emits the chapter milestone alongside verse 1,
             so emitting one here as well would give the chapter two identical corresp
             values, and the reference database and the parallel compiler each keep only the
             first of those. Where a verse 1 marker follows, it opens the chapter and this
             dropinitial is decoration. -->
        <xsl:if test="$chapter and not(following-sibling::verse[@chapter=$chapter][@verse='1'])">
            <tei:milestone unit="chapter" n="{$chapter}"
                corresp="urn:x-opensiddur:text:bible:{$book_name}/{$chapter}"/>
            <tei:milestone unit="verse" n="1"
                corresp="urn:x-opensiddur:text:bible:{$book_name}/{$chapter}/1"/>
        </xsl:if>

    </xsl:template>

    <!-- anchor is used inside dropinitial -->
    <xsl:template match="anchor"/>

    <xsl:template match="verse">
        <xsl:if test="@verse='1'">
            <!-- if the verse marker is here, there is no dropinitial or anchor-->
            <tei:milestone unit="chapter" n="{@chapter}"
            corresp="urn:x-opensiddur:text:bible:{$book_name}/{@chapter}"/>
            <xsl:if test="@chapter = '1' and not(following-sibling::p[1]/preceding-sibling::text()[normalize-space(.)])">
                <!-- add an initial paragraph break -->
                <p/>
            </xsl:if>
        </xsl:if>
        <!-- @verse is the canonical number and drives the URN; @editionVerse is JPS's own,
             emitted only where the two differ. It carries no @corresp, so the reference
             database and the parallel compiler — which look only at @corresp — ignore it,
             while a renderer can still show JPS's numbering. A verse continued from a
             merged one has no @editionVerse at all: it is the same JPS verse. -->
        <xsl:if test="@editionVerse and @editionVerse != @verse">
            <tei:milestone unit="edition-verse" n="{@editionVerse}"/>
        </xsl:if>
        <tei:milestone unit="verse" n="{@verse}"
            corresp="urn:x-opensiddur:text:bible:{$book_name}/{@chapter}/{@verse}"/>
    </xsl:template>

    <!-- dd is used as a line break -->
    <xsl:template match="dd">
        <tei:lb/>
    </xsl:template>

    <xsl:template match="i">
        <tei:hi rend="italic">
            <xsl:apply-templates select="node()"/>
        </tei:hi>
    </xsl:template>

    <xsl:template match="lang">
        <tei:foreign xml:lang="{@code}">
            <xsl:apply-templates select="node()"/>
        </tei:foreign>
    </xsl:template>

    <xsl:template match="asterisks">
        <xsl:variable name="rendering" select="string-join(for $i in 1 to @n return '*', '')"/>
        <tei:milestone rend="{$rendering}" unit="section"/>
    </xsl:template>

    <xsl:template match="right">
        <tei:hi rend="align-right">
            <xsl:apply-templates select="node()"/>
        </tei:hi>
    </xsl:template>

    <xsl:template match="section"/>

    <!-- Copy all TEI elements -->
    <xsl:template match="tei:*">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="document-node()">
        <xsl:copy>
            <xsl:apply-templates select="node()"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="@* | node()" mode="copy">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()" mode="copy"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="p" mode="copy"/>
    <xsl:template match="tei:note" mode="copy"/>

    <!-- on the pages with section boundaries, the section marker appears twice;
    we always want to capture the *second* begin marker and the second to last end marker 
    If the book begins on a page with only itself, it may not have a start marker or vice versa
    -->
    <xsl:variable name="section-start" select="(//mediawikis/mediawiki[1]/section[@begin][2], //mediawikis/mediawiki[1]/node()[1])[1]" as="node()?"/>
    <xsl:variable name="section-end" select="(//mediawikis/mediawiki[last()]/section[@end][last()-1], //mediawikis/mediawiki[last()]/node()[last()])[1]" as="node()?"/>

    <xsl:template match="node()" mode="sectioned">
        <xsl:choose>
            <!-- Keep section markers themselves -->
            <xsl:when test="some $s in ($section-start, $section-end) satisfies ($s is .)">
                <xsl:copy>
                    <xsl:copy-of select="@*"/>
                    <xsl:apply-templates mode="sectioned"/>
                </xsl:copy>
            </xsl:when>
            <!-- Keep elements that contain section markers -->
            <xsl:when test="descendant::node()[. is $section-start or . is $section-end]">
                <xsl:copy>
                    <xsl:copy-of select="@*"/>
                    <xsl:apply-templates mode="sectioned"/>
                </xsl:copy>
            </xsl:when>
            <!-- Remove everything before section-start (unless it contains section markers) -->
            <xsl:when test=". &lt;&lt; $section-start">
                <!-- Do nothing - remove content before section -->
            </xsl:when>
            <!-- Remove everything after section-end (unless it contains section markers) -->
            <xsl:when test=". &gt;&gt; $section-end">
                <!-- Do nothing - remove content after section -->
            </xsl:when>
            <!-- Keep content between section-start and section-end -->
            <xsl:otherwise>
                <xsl:copy>
                    <xsl:copy-of select="@*"/>
                    <xsl:apply-templates mode="sectioned"/>
                </xsl:copy>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
</xsl:stylesheet>

