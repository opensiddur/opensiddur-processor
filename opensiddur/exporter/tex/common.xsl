<?xml version="1.0" encoding="UTF-8"?>
<!-- Functions the TeX stylesheet (reledmac.xslt) shares across its templates. One copy of each, so
     that a fix reaches every caller: the escaping below once existed three times, and the copy
     the book's text went through escaped the braces of its own \textbackslash{}. -->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:f="urn:opensiddur:reledmac"
    exclude-result-prefixes="xs f">

    <!-- The string without its bidi formatting characters, as escape_tex drops them
         (opensiddur/common/bidi.py): \textdir ignores them, and a font without a glyph for
         them prints a box. LRM, RLM, ALM, the embeddings and overrides, the isolates. -->
    <xsl:function name="f:strip-bidi" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <xsl:sequence select="replace($s, '[&#x200E;&#x200F;&#x061C;&#x202A;-&#x202E;&#x2066;-&#x2069;]', '')"/>
    </xsl:function>

    <!-- Escape the characters that have special meaning in LaTeX. A sentinel (a private-use
         character) stands in for the backslash while the others are escaped, so that the braces
         of its own \textbackslash{} are not escaped in turn. opensiddur/exporter/tex/escape.py
         does the same for strings that reach TeX from Python. -->
    <xsl:function name="f:escape-tex" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <xsl:variable name="t1" select="replace(f:strip-bidi($s), '\\', '&#xE000;')"/>
        <xsl:variable name="t2" select="replace($t1, '([&amp;%$#_{}])', '\\$1')"/>
        <xsl:variable name="t3" select="replace($t2, '~', '\\textasciitilde{}')"/>
        <xsl:variable name="t4" select="replace($t3, '\^', '\\textasciicircum{}')"/>
        <xsl:sequence select="replace($t4, '&#xE000;', '\\textbackslash{}')"/>
    </xsl:function>

    <!-- Whether text in a language is in the Hebrew script, and so set in Polyglossia's Hebrew
         environment. A script subtag decides: he-Latn is a transliteration, arc-Hebr Aramaic
         in Hebrew letters. Without one, Hebrew, Yiddish and Aramaic are written in Hebrew
         letters. The electronic book (html.xslt f:is-rtl) and the running heads
         (running_heads.is_hebrew_language) follow the same rule. -->
    <xsl:function name="f:is-hebrew-lang" as="xs:boolean">
        <xsl:param name="lang" as="xs:string"/>
        <xsl:variable name="subtags" select="tokenize(lower-case($lang), '-')"/>
        <xsl:variable name="script" select="$subtags[position() gt 1][string-length(.) = 4][1]"/>
        <xsl:sequence select="if ($script) then $script = 'hebr'
                              else $subtags[1] = ('he', 'yi', 'arc')"/>
    </xsl:function>

    <!-- Whether a language is written right to left, for deciding whether two runs can share
         a line. Compared by direction rather than by language, so English beside Yiddish is one
         line and Hebrew beside Yiddish is another. The script subtag decides here too. -->
    <xsl:function name="f:is-rtl-lang" as="xs:boolean">
        <xsl:param name="lang" as="xs:string"/>
        <xsl:variable name="subtags" select="tokenize(lower-case($lang), '-')"/>
        <xsl:variable name="script" select="$subtags[position() gt 1][string-length(.) = 4][1]"/>
        <xsl:sequence select="if ($script) then $script = ('hebr', 'arab', 'syrc')
                              else $subtags[1] = ('he', 'yi', 'arc', 'ar', 'fa', 'jrb', 'lad', 'ji')"/>
    </xsl:function>

</xsl:stylesheet>
