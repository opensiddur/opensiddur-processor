<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  xmlns:j="http://jewishliturgy.org/ns/jlptei/2"
  xmlns:miqra="urn:x-opensiddur:miqra:intermediate"
  xmlns:mw="urn:x-opensiddur:mw:intermediate"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  exclude-result-prefixes="miqra mw xs">

  <xsl:output method="xml" omit-xml-declaration="yes" indent="no"/>

  <xsl:function name="miqra:parashah-p-type" as="xs:string">
    <xsl:param name="type" as="xs:string?"/>
    <xsl:variable name="t" select="normalize-space($type)"/>
    <xsl:choose>
      <xsl:when test="$t = 'open-line'">
        <xsl:sequence select="'open-3'"/>
      </xsl:when>
      <xsl:when test="$t = ('close', 'close-inline', 'close-narrow', 'shirah')">
        <xsl:sequence select="'closed-1'"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:sequence select="'open-1'"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:function>

  <!-- True when a מ:כפול carries nothing but a parashah break in each of its strands, i.e. the
       two readings agree on where the break falls and differ only in whether it lands mid-verse. -->
  <xsl:function name="miqra:parashah-only" as="xs:boolean">
    <xsl:param name="dual" as="element(miqra:dual-accent)"/>
    <xsl:sequence select="
      exists($dual/miqra:strand/miqra:parashah)
      and (every $n in $dual/miqra:strand/node() satisfies (
        $n instance of element(miqra:parashah)
        or ($n instance of text() and normalize-space($n) = '')
      ))
    "/>
  </xsl:function>

  <xsl:function name="miqra:has-verse-ref" as="xs:boolean">
    <xsl:param name="chapter" as="xs:string"/>
    <xsl:param name="verse" as="xs:string"/>
    <xsl:sequence select="
      $chapter != '' and $verse != ''
      and matches($chapter, '^[0-9]+$')
      and matches($verse, '^[0-9]+$')
    "/>
  </xsl:function>

  <xsl:template match="/">
    <xsl:result-document href="body">
      <tei:body>
        <tei:div type="book">
          <xsl:attribute name="corresp">
            <xsl:text>urn:x-opensiddur:text:bible:</xsl:text>
            <xsl:value-of select="/miqra:book/@fileName"/>
          </xsl:attribute>
          <tei:head xml:lang="en">
            <xsl:value-of select="/miqra:book/@bookNameEn"/>
          </tei:head>
          <xsl:variable name="blocks" as="node()*">
            <xsl:apply-templates select="/miqra:book/miqra:row" mode="flatten"/>
          </xsl:variable>
          <xsl:for-each-group select="$blocks" group-starting-with="miqra:parashah">
            <tei:p>
              <xsl:attribute name="type">
                <xsl:choose>
                  <xsl:when test="current-group()[1] instance of element(miqra:parashah)">
                    <xsl:sequence select="miqra:parashah-p-type(string((current-group()[1]/@type)))"/>
                  </xsl:when>
                  <xsl:otherwise>open-1</xsl:otherwise>
                </xsl:choose>
              </xsl:attribute>
              <xsl:apply-templates select="current-group()[not(self::miqra:parashah)]" mode="block"/>
            </tei:p>
          </xsl:for-each-group>
        </tei:div>
      </tei:body>
    </xsl:result-document>
    <xsl:if test="/miqra:book//miqra:note">
      <xsl:result-document href="standoff">
        <tei:standOff type="notes" xml:lang="he">
          <xsl:apply-templates select="/miqra:book//miqra:note" mode="standoff"/>
        </tei:standOff>
      </xsl:result-document>
    </xsl:if>
  </xsl:template>

  <!-- Flatten each row (one verse of MAM-parsed plus: its columns C, D and E) into nav markers +
       verse runs. -->
  <xsl:template match="miqra:row" mode="flatten">
    <!-- Column C: only parashah markers structure paragraphs; // line breaks are cosmetic.
         A break the source wrapped in {{נוסח}} — because another witness reads it
         differently — is still MAM's own break and must reach the body. -->
    <xsl:apply-templates
        select="miqra:nav/(miqra:parashah | miqra:variant[miqra:display/miqra:parashah])"
        mode="flatten"/>
    <!-- The row's own identity, bound before any grouping: inside xsl:for-each-group the
         context item is a member of the group, not the row. -->
    <xsl:variable name="chapter" select="string(@chapter)"/>
    <xsl:variable name="verse" select="string(@verse)"/>
    <xsl:variable name="editionVerse" select="string(@editionVerse)"/>
    <xsl:variable name="editionVerseStart" select="string(@editionVerseStart)"/>
    <xsl:variable name="fileName" select="string(ancestor::miqra:book/@fileName)"/>
    <!-- Whether this row opens a new chapter, decided here against the real source tree
         (preceding-sibling::miqra:row) rather than downstream against the constructed
         miqra:verse elements: those are built by independent element constructors inside
         the $blocks variable in the calling template, so they are not one tree and
         preceding:: cannot see across them there. -->
    <xsl:variable name="opens-chapter" select="
        not(preceding-sibling::miqra:row[1])
        or preceding-sibling::miqra:row[1]/normalize-space(@chapter) != $chapter"/>
    <!-- The rest of the column C/D notes annotate the row — a break another witness has
         but MAM does not, a seder marker, a free {{מ:הערה}} — rather than a point in the
         verse, so they anchor at the head of the verse. Without this the standOff note
         survives and its target does not resolve. -->
    <xsl:variable name="row-anchors" as="element()*">
      <xsl:for-each select="
        (miqra:nav | miqra:scaffold)/miqra:variant[@noteId][not(miqra:display/miqra:parashah)]">
        <miqra:anchor xml:id="{@noteId}-ref"/>
      </xsl:for-each>
      <xsl:copy-of select="(miqra:nav | miqra:scaffold)//miqra:anchor"/>
    </xsl:variable>
    <xsl:variable name="text-nodes" as="node()*">
      <xsl:sequence select="$row-anchors"/>
      <xsl:apply-templates select="miqra:text/node()" mode="hoist"/>
    </xsl:variable>
    <xsl:choose>
      <xsl:when test="$text-nodes[self::miqra:parashah]">
        <!-- A parashah break in the middle of a verse splits the verse across paragraphs, but
             the verse is still one verse: only the first group that carries content opens it,
             and the rest continue it. Emitting a milestone per group is what previously gave
             MAM's לא תחמד two identical corresp values. -->
        <xsl:variable name="group-has-content" as="xs:boolean*">
          <xsl:for-each-group select="$text-nodes" group-starting-with="miqra:parashah">
            <xsl:sequence select="
              exists(current-group()[not(self::miqra:parashah)][not(self::miqra:note)])"/>
          </xsl:for-each-group>
        </xsl:variable>
        <xsl:variable name="first-group" select="index-of($group-has-content, true())[1]"/>
        <xsl:for-each-group select="$text-nodes" group-starting-with="miqra:parashah">
          <xsl:variable name="position" select="position()"/>
          <xsl:apply-templates select="current-group()[self::miqra:parashah]" mode="flatten"/>
          <xsl:variable name="content"
                        select="current-group()[not(self::miqra:parashah)][not(self::miqra:note)]"/>
          <xsl:if test="exists($content)">
            <miqra:verse chapter="{$chapter}" verse="{$verse}" fileName="{$fileName}"
                         editionVerse="{$editionVerse}"
                         editionVerseStart="{$editionVerseStart}"
                         opensVerse="{if ($position = $first-group) then 'true' else 'false'}"
                         opensChapter="{if ($opens-chapter) then 'true' else 'false'}">
              <xsl:copy-of select="$content"/>
            </miqra:verse>
          </xsl:if>
        </xsl:for-each-group>
      </xsl:when>
      <xsl:otherwise>
        <miqra:verse chapter="{$chapter}" verse="{$verse}" fileName="{$fileName}"
                     editionVerse="{$editionVerse}"
                     editionVerseStart="{$editionVerseStart}"
                     opensVerse="true"
                     opensChapter="{if ($opens-chapter) then 'true' else 'false'}">
          <xsl:copy-of select="$text-nodes[not(self::miqra:note)]"/>
        </miqra:verse>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Lift parashah breaks out of מ:כפול so the paragraph grouping above can see them. -->
  <xsl:mode name="hoist" on-no-match="shallow-copy"/>

  <xsl:template match="miqra:dual-accent[miqra:parashah-only(.)]" mode="hoist">
    <!-- Keep the apparatus anchors from the merged text, which is not itself rendered. -->
    <xsl:for-each select="miqra:merged//miqra:variant[@noteId]">
      <miqra:anchor xml:id="{@noteId}-ref"/>
    </xsl:for-each>
    <xsl:copy-of select="miqra:merged//miqra:anchor"/>
    <!-- Both readings break in the same place; keep the ta'am tachton marker, which is the
         reading MAM's own verse division follows. -->
    <xsl:copy-of select="miqra:strand[@role = 'א']/miqra:parashah"/>
  </xsl:template>

  <xsl:template match="miqra:parashah" mode="flatten">
    <xsl:copy-of select="."/>
  </xsl:template>

  <!-- The anchor follows the break so it becomes the first member of the new group, which
       puts it at the head of the paragraph the break opens. -->
  <xsl:template match="miqra:variant[miqra:display/miqra:parashah]" mode="flatten">
    <xsl:copy-of select="miqra:display/miqra:parashah"/>
    <xsl:if test="@noteId">
      <miqra:anchor xml:id="{@noteId}-ref"/>
    </xsl:if>
  </xsl:template>

  <xsl:template match="miqra:lb" mode="flatten">
    <xsl:copy-of select="."/>
  </xsl:template>

  <xsl:template match="text()[normalize-space(.) = '']" mode="flatten"/>

  <xsl:template match="node()" mode="flatten">
    <xsl:copy-of select="."/>
  </xsl:template>

  <!-- Verse milestones + text (no tei:ab wrapper).

       Two units are emitted. @unit='verse' carries the canonical URN and is the join key for
       alignment and transclusion; there is exactly one per canonical verse. @unit='edition-verse'
       carries MAM's own number and no @corresp, so the reference database and the parallel
       compiler — which both look only at @corresp — ignore it, while a renderer can still show
       MAM's numbering. The two coincide everywhere except the chapters the editions divide
       differently, where one MAM verse opens several canonical ones. -->
  <xsl:template match="miqra:verse" mode="block">
    <xsl:variable name="chapter" select="normalize-space(@chapter)"/>
    <xsl:variable name="verse" select="normalize-space(@verse)"/>
    <xsl:variable name="editionVerse" select="normalize-space(@editionVerse)"/>
    <xsl:if test="miqra:has-verse-ref($chapter, $verse)">
      <xsl:if test="@opensVerse = 'true' and @opensChapter = 'true'">
        <!-- A chapter milestone has no representation of its own in MAM's source; @opensChapter
             is computed in mode="flatten", against the real miqra:row source tree, because by
             the time verses reach this template they are independent nodes built by separate
             element constructors and so cannot be compared by document order (preceding::)
             against one another. wlc emits the same unit from its own explicit c/@n; see
             transform_book.xslt. -->
        <tei:milestone unit="chapter" n="{$chapter}">
          <xsl:attribute name="corresp">
            <xsl:text>urn:x-opensiddur:text:bible:</xsl:text>
            <xsl:value-of select="@fileName"/>
            <xsl:text>/</xsl:text>
            <xsl:value-of select="$chapter"/>
          </xsl:attribute>
        </tei:milestone>
      </xsl:if>
      <xsl:if test="@editionVerseStart = 'true' and @opensVerse = 'true'
                    and $editionVerse != '' and $editionVerse != $verse">
        <tei:milestone unit="edition-verse" n="{$editionVerse}"/>
      </xsl:if>
      <xsl:if test="@opensVerse = 'true'">
        <tei:milestone unit="verse" n="{$verse}">
          <xsl:attribute name="corresp">
            <xsl:text>urn:x-opensiddur:text:bible:</xsl:text>
            <xsl:value-of select="@fileName"/>
            <xsl:text>/</xsl:text>
            <xsl:value-of select="$chapter"/>
            <xsl:text>/</xsl:text>
            <xsl:value-of select="$verse"/>
          </xsl:attribute>
        </tei:milestone>
      </xsl:if>
    </xsl:if>
    <xsl:apply-templates select="node()" mode="inline"/>
  </xsl:template>

  <xsl:template match="miqra:lb" mode="block">
    <tei:lb/>
  </xsl:template>

  <!-- Strip nav/scaffold from direct processing -->
  <xsl:template match="miqra:nav | miqra:scaffold | miqra:row"/>

  <!-- Variant documentation (נוסח) -->
  <xsl:template match="miqra:variant" mode="inline">
    <xsl:if test="@noteId">
      <tei:anchor xml:id="{concat(@noteId, '-ref')}"/>
    </xsl:if>
    <xsl:apply-templates select="miqra:display" mode="inline"/>
  </xsl:template>

  <xsl:template match="miqra:display" mode="inline">
    <xsl:apply-templates mode="inline"/>
  </xsl:template>

  <xsl:template match="miqra:note" mode="standoff">
    <tei:note>
      <xsl:copy-of select="@xml:id"/>
      <!-- Link this standOff note to the in-text marker so the reference database
           can index it and the compiler can inline it at the correct point. -->
      <xsl:attribute name="target" select="concat('#', string(@xml:id), '-ref')"/>
      <xsl:apply-templates mode="inline"/>
    </tei:note>
  </xsl:template>

  <xsl:template match="miqra:note" mode="inline"/>
  <xsl:template match="miqra:note"/>

  <!-- Ketiv/qeri -->
  <xsl:template match="miqra:kq" mode="inline">
    <tei:choice>
      <xsl:choose>
        <xsl:when test="@order = 'qeri-first'">
          <j:read>
            <xsl:apply-templates select="miqra:qeri/node() | miqra:bracketed/node()" mode="inline"/>
          </j:read>
          <j:written>
            <xsl:apply-templates select="miqra:ketiv/node()" mode="inline"/>
          </j:written>
        </xsl:when>
        <xsl:otherwise>
          <j:written>
            <xsl:apply-templates select="miqra:ketiv/node()" mode="inline"/>
          </j:written>
          <j:read>
            <xsl:apply-templates select="miqra:qeri/node() | miqra:bracketed/node()" mode="inline"/>
          </j:read>
        </xsl:otherwise>
      </xsl:choose>
    </tei:choice>
  </xsl:template>

  <xsl:template match="miqra:bracketed" mode="inline">
    <xsl:text>[</xsl:text>
    <xsl:apply-templates mode="inline"/>
    <xsl:text>]</xsl:text>
  </xsl:template>

  <xsl:template match="miqra:kq-matres" mode="inline"/>

  <xsl:template match="miqra:ketiv-only" mode="inline">
    <tei:hi rend="ketiv-only">
      <xsl:text>(</xsl:text>
      <xsl:apply-templates mode="inline"/>
      <xsl:text>)</xsl:text>
    </tei:hi>
  </xsl:template>

  <xsl:template match="miqra:qeri-only" mode="inline">
    <tei:hi rend="qeri-only">
      <xsl:text>[</xsl:text>
      <xsl:apply-templates mode="inline"/>
      <xsl:text>]</xsl:text>
    </tei:hi>
  </xsl:template>

  <!-- Poetic layout (within a paragraph) -->
  <xsl:template match="miqra:poetic" mode="inline">
    <tei:lb>
      <xsl:if test="@level != '0'">
        <xsl:attribute name="type">indent</xsl:attribute>
      </xsl:if>
    </tei:lb>
  </xsl:template>

  <xsl:template match="miqra:centered" mode="inline">
    <tei:hi rend="centered">
      <xsl:apply-templates mode="inline"/>
    </tei:hi>
  </xsl:template>

  <xsl:template match="miqra:hi" mode="inline">
    <tei:hi>
      <xsl:attribute name="rend" select="@rend"/>
      <xsl:apply-templates mode="inline"/>
    </tei:hi>
  </xsl:template>

  <xsl:template match="miqra:dotted | miqra:inverted-nun" mode="inline">
    <xsl:apply-templates mode="inline"/>
  </xsl:template>

  <xsl:template match="miqra:yerushalem | miqra:yerushalema" mode="inline">
    <xsl:value-of select="@vowel"/>
    <xsl:value-of select="@accent"/>
    <xsl:text>&#x034F;ִ</xsl:text>
  </xsl:template>

  <xsl:template match="miqra:accent" mode="inline">
    <xsl:text> </xsl:text>
  </xsl:template>

  <xsl:template match="miqra:qupo-accent" mode="inline"/>

  <xsl:template match="miqra:punct | miqra:maqaf" mode="inline">
    <xsl:value-of select="."/>
  </xsl:template>

  <xsl:template match="miqra:fn-mark" mode="inline">
    <tei:hi rend="sup">*</tei:hi>
  </xsl:template>

  <xsl:template match="miqra:anchor" mode="inline">
    <tei:anchor>
      <xsl:copy-of select="@xml:id"/>
    </tei:anchor>
  </xsl:template>

  <!-- An anchor lifted out of column C sits beside the parashah breaks, not inside a verse,
       so it reaches mode="block"; without this rule the built-in one would discard it. -->
  <xsl:template match="miqra:anchor" mode="block">
    <tei:anchor>
      <xsl:copy-of select="@xml:id"/>
    </tei:anchor>
  </xsl:template>

  <!-- Dual cantillation (מ:כפול): the two readings are alternate wordings of the same text,
       exactly one of which is read, which is what j:option is for. MAM-parsed documents the
       strand labels (mpplus_dualcant.html): א is ta'am tachton (פשוטה at Gen 35:22), ב is ta'am
       elyon (מדרשית).
       The corresp URNs are fixed rather than per-passage, so one setting picks the reading
       everywhere it occurs. Parashah-only spans never reach here; see mode="hoist". -->
  <xsl:template match="miqra:dual-accent" mode="inline">
    <xsl:apply-templates select="miqra:merged" mode="inline"/>
    <tei:choice>
      <j:option corresp="urn:x-opensiddur:condition:bible:taam-tachton">
        <xsl:apply-templates select="miqra:strand[@role = 'א']/node()" mode="inline"/>
      </j:option>
      <j:option corresp="urn:x-opensiddur:condition:bible:taam-elyon">
        <xsl:apply-templates select="miqra:strand[@role = 'ב']/node()" mode="inline"/>
      </j:option>
    </tei:choice>
  </xsl:template>

  <!-- The merged doubly-accented text is not rendered — the strands carry it — but the
       manuscript apparatus hangs off it, so its anchors must still exist in the body. -->
  <xsl:template match="miqra:merged" mode="inline">
    <xsl:apply-templates select=".//miqra:variant[@noteId] | .//miqra:anchor" mode="anchor-only"/>
  </xsl:template>

  <xsl:template match="miqra:variant[@noteId]" mode="anchor-only">
    <tei:anchor xml:id="{@noteId}-ref"/>
  </xsl:template>

  <xsl:template match="miqra:anchor" mode="anchor-only">
    <tei:anchor>
      <xsl:copy-of select="@xml:id"/>
    </tei:anchor>
  </xsl:template>

  <!-- A strand is only ever reached through miqra:dual-accent, which selects its children
       directly; the empty rule keeps a stray one from leaking text through the built-in rule. -->
  <xsl:template match="miqra:line-anchor | miqra:segment | miqra:good-ending | miqra:dual-trope-link | miqra:strand" mode="inline"/>

  <xsl:template match="miqra:parashah" mode="block"/>
  <xsl:template match="miqra:parashah" mode="inline"/>

  <!-- Legacy mw elements -->
  <xsl:template match="mw:hi" mode="inline">
    <tei:hi>
      <xsl:attribute name="rend" select="@rend"/>
      <xsl:apply-templates mode="inline"/>
    </tei:hi>
  </xsl:template>

  <xsl:template match="mw:link" mode="inline">
    <xsl:choose>
      <xsl:when test="normalize-space(.) != ''">
        <tei:ref>
          <xsl:attribute name="target" select="@target"/>
          <xsl:apply-templates mode="inline"/>
        </tei:ref>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="@target"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="mw:template" mode="inline">
    <xsl:apply-templates select="mw:param/node()" mode="inline"/>
  </xsl:template>

  <xsl:template match="mw:param" mode="inline">
    <xsl:value-of select="."/>
  </xsl:template>

  <xsl:template match="text()" mode="inline">
    <xsl:value-of select="."/>
  </xsl:template>

  <xsl:template match="text()" mode="block">
    <xsl:value-of select="."/>
  </xsl:template>

</xsl:stylesheet>
