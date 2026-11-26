"""
MediaWiki/Wikitext to intermediate XML processor.

Reusable framework originally built for the JPS1917 importer. Other importers
(e.g. Miqra al pi ha-Masorah) subclass ``MediaWikiProcessor`` and register their
own template/tag handlers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import mwparserfromhell


class ProcessingStage(Enum):
    """Stages of MediaWiki processing"""
    PREPROCESS = "preprocess"
    TEMPLATES = "templates"
    TAGS = "tags"
    POSTPROCESS = "postprocess"


@dataclass
class ConversionResult:
    """Result of a conversion operation"""
    xml_content: str
    metadata: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    wikilinks: list[dict[str, Any]]


class MediaWikiProcessor:
    """
    Modular MediaWiki to XML processor for JPS1917 content.
    
    This processor handles the conversion of MediaWiki syntax to XML,
    with separate modules for different types of templates and tags.
    """
    
    def __init__(self):
        self.template_handlers = {}
        self.tag_handlers = {}
        self.preprocessors = []
        self.postprocessors = []
        self.wikilinks = []  # Store captured wikilinks
        self._initialize_handlers()
    
    def _initialize_handlers(self):
        """Initialize all template and tag handlers"""
        self._initialize_template_handlers()
        self._initialize_tag_handlers()
        self._initialize_preprocessors()
        self._initialize_postprocessors()
        self._initialize_wikilink_handlers()
    
    def _initialize_template_handlers(self):
        """Initialize handlers for MediaWiki templates"""
        
        # Text Formatting Templates
        self.template_handlers['sc'] = self._handle_small_caps
        self.template_handlers['larger'] = self._handle_larger_text
        self.template_handlers['x-larger'] = self._handle_x_larger_text
        self.template_handlers['xx-larger'] = self._handle_xx_larger_text
        self.template_handlers['xxx-larger'] = self._handle_xxx_larger_text
        self.template_handlers['smaller'] = self._handle_smaller_text
        
        # Layout Templates
        self.template_handlers['c'] = self._handle_center
        self.template_handlers['right'] = self._handle_right_align
        self.template_handlers['rule'] = self._handle_horizontal_rule
        self.template_handlers['nop'] = self._handle_no_paragraph
        
        # Biblical Content Templates
        self.template_handlers['verse'] = self._handle_verse
        self.template_handlers['rh'] = self._handle_right_header
        self.template_handlers['dropinitial'] = self._handle_drop_initial
        self.template_handlers['dhr'] = self._handle_double_horizontal_rule
        
        # Navigation Templates
        self.template_handlers['anchor'] = self._handle_anchor
        self.template_handlers['anchor+'] = self._handle_anchor_plus
        
        # Language Templates
        self.template_handlers['lang'] = self._handle_language
        
        # Reference Templates
        self.template_handlers['smallrefs'] = self._handle_small_refs
        
        # Special Templates
        self.template_handlers['hws'] = self._handle_hws
        self.template_handlers['hwe'] = self._handle_hwe
        self.template_handlers['***'] = self._handle_asterisks
        self.template_handlers['reconstruct'] = self._handle_reconstruct
        self.template_handlers['SIC'] = self._handle_sic
        self.template_handlers['sic'] = self._handle_sic
        self.template_handlers['sup'] = self._handle_superscript
        self.template_handlers['bar'] = self._handle_bar
        self.template_handlers['gap'] = self._handle_gap
        self.template_handlers['overfloat left'] = self._handle_overfloat_left
        self.template_handlers['float right'] = self._handle_float_right
        self.template_handlers['smaller block/s'] = self._handle_smaller_block_start
        self.template_handlers['smaller block/e'] = self._handle_smaller_block_end
    
    def _initialize_tag_handlers(self):
        """Initialize handlers for HTML/XML tags"""
        
        # Structural Tags
        self.tag_handlers['section'] = self._handle_section
        self.tag_handlers['table'] = self._handle_table
        self.tag_handlers['tr'] = self._handle_table_row
        self.tag_handlers['td'] = self._handle_table_cell
        
        # Text Formatting Tags
        self.tag_handlers['i'] = self._handle_italic
        self.tag_handlers['br'] = self._handle_line_break
        self.tag_handlers['span'] = self._handle_span
        
        # Content Tags
        self.tag_handlers['dd'] = self._handle_definition_description
        self.tag_handlers['ref'] = self._handle_reference
        
        # MediaWiki Specific Tags
        self.tag_handlers['noinclude'] = self._handle_noinclude
        self.tag_handlers['pagequality'] = self._handle_pagequality
    
    def _initialize_preprocessors(self):
        """Initialize preprocessing functions"""
        self.preprocessors = [
            self._fix_noinclude_line_breaks,
            self._convert_paragraph_breaks,
            self._normalize_whitespace,
            self._handle_special_characters,  # Enable special character processing
            self._extract_metadata
        ]
    
    def _initialize_postprocessors(self):
        """Initialize postprocessing functions"""
        self.postprocessors = [
            self._validate_xml_structure,
            self._finalize_metadata
        ]
    
    def _initialize_wikilink_handlers(self):
        """Initialize wikilink processing"""
        # Wikilinks are processed during the main parsing loop
        pass
    
    def _process_nested_content(self, content: str, depth: int = 0) -> str:
        """Recursively process nested templates and other elements"""
        # Prevent infinite recursion
        if depth > 10:
            return content
            
        # Parse the content to handle nested elements
        parsed = mwparserfromhell.parse(content)
        nodes_to_replace = []
        
        # Process nodes recursively
        for node in parsed.nodes:
            if hasattr(node, 'name'):  # Template
                template_name = str(node.name).strip()
                if template_name in self.template_handlers:
                    try:
                        # Process nested content within the template
                        processed_node = self._process_template_with_nesting(node, depth + 1)
                        replacement = self.template_handlers[template_name](processed_node)
                        nodes_to_replace.append((node, replacement))
                    except Exception:
                        # If nested processing fails, try without nesting
                        replacement = self.template_handlers[template_name](node)
                        nodes_to_replace.append((node, replacement))
                else:
                    # Unknown template - process its content for nested elements
                    processed_content = self._process_nested_content(str(node), depth + 1)
                    nodes_to_replace.append((node, processed_content))
            
            elif hasattr(node, 'tag'):  # Tag
                tag_name = str(node.tag).strip().lower()
                if tag_name in self.tag_handlers:
                    try:
                        # Process nested content within the tag
                        processed_node = self._process_tag_with_nesting(node, depth + 1)
                        replacement = self.tag_handlers[tag_name](processed_node)
                        nodes_to_replace.append((node, replacement))
                    except Exception:
                        # If nested processing fails, try without nesting
                        replacement = self.tag_handlers[tag_name](node)
                        nodes_to_replace.append((node, replacement))
                else:
                    # Unknown tag - process its content for nested elements
                    processed_content = self._process_nested_content(str(node), depth + 1)
                    nodes_to_replace.append((node, processed_content))
            
            elif hasattr(node, '__class__') and 'Wikilink' in str(node.__class__):  # Wikilink
                try:
                    replacement = self._handle_wikilink(node)
                    nodes_to_replace.append((node, replacement))
                except Exception:
                    # If wikilink processing fails, keep original
                    nodes_to_replace.append((node, str(node)))
        
        # Replace all nodes
        for node, replacement in nodes_to_replace:
            parsed.replace(node, replacement)
        
        return str(parsed)
    
    def _process_template_with_nesting(self, template, depth: int = 0) -> object:
        """Process a template and its nested content"""
        # Create a copy of the template to avoid modifying the original
        import copy
        processed_template = copy.deepcopy(template)
        
        # Process each parameter of the template
        for param in processed_template.params:
            if hasattr(param, 'value'):
                # Process nested content in parameter values
                processed_value = self._process_nested_content(str(param.value), depth + 1)
                param.value = processed_value
        
        return processed_template
    
    def _process_tag_with_nesting(self, tag, depth: int = 0) -> object:
        """Process a tag and its nested content"""
        # Create a copy of the tag to avoid modifying the original
        import copy
        processed_tag = copy.deepcopy(tag)
        
        # Process nested content within the tag
        if hasattr(processed_tag, 'contents') and processed_tag.contents:
            processed_contents = self._process_nested_content(str(processed_tag.contents), depth + 1)
            processed_tag.contents = processed_contents
        
        return processed_tag
    
    # ============================================================================
    # TEMPLATE HANDLERS
    # ============================================================================
    
    def _handle_small_caps(self, template) -> str:
        """Convert {{sc|text}} to <sc>text</sc>"""
        content = str(template.get(1, ''))
        return f'<sc>{content}</sc>'
    
    def _handle_larger_text(self, template) -> str:
        """Convert {{larger|text}} to <larger>text</larger>"""
        content = str(template.get(1, ''))
        return f'<larger>{content}</larger>'
    
    def _handle_x_larger_text(self, template) -> str:
        """Convert {{x-larger|text}} to <x-larger>text</x-larger>"""
        content = str(template.get(1, ''))
        return f'<x-larger>{content}</x-larger>'
    
    def _handle_xx_larger_text(self, template) -> str:
        """Convert {{xx-larger|text}} to <xx-larger>text</xx-larger>"""
        content = str(template.get(1, ''))
        return f'<xx-larger>{content}</xx-larger>'
    
    def _handle_xxx_larger_text(self, template) -> str:
        """Convert {{xxx-larger|text}} to <xxx-larger>text</xxx-larger>"""
        content = str(template.get(1, ''))
        return f'<xxx-larger>{content}</xxx-larger>'
    
    def _handle_smaller_text(self, template) -> str:
        """Convert {{smaller|text}} to <smaller>text</smaller>"""
        content = str(template.get(1, ''))
        return f'<smaller>{content}</smaller>'
    
    def _handle_center(self, template) -> str:
        """Convert {{c|text}} to <c>text</c>"""
        content = str(template.get(1, ''))
        return f'<c>{content}</c>'
    
    def _handle_right_align(self, template) -> str:
        """Convert {{right|text}} to <right>text</right>"""
        content = str(template.get(1, ''))
        return f'<right>{content}</right>'
    
    def _handle_horizontal_rule(self, template) -> str:
        """Convert {{rule}} to <rule/>"""
        return '<rule/>'
    
    def _handle_no_paragraph(self, template) -> str:
        """Convert {{nop}} to <nop/>"""
        return '<nop/>'
    
    def _handle_verse(self, template) -> str:
        """Convert {{verse|chapter|verse|text}} to <verse chapter="..." verse="...">text</verse>"""
        chapter = str(template.get('chapter', template.get(1, ''))).replace("chapter=", "")
        verse = str(template.get('verse', template.get(2, ''))).replace("verse=", "")
        text = str(template.get(3, template.get('text', '')))
        chapter_attr = f' chapter="{chapter}"' if chapter else ''
        verse_attr = f' verse="{verse}"' if verse else ''
        if not chapter or not verse:
            print(f"Invalid verse template: {template} {template.get(1, '')=} {template.get(2, '')=} {template.get(3, '')=}")
            
        return f'<verse{chapter_attr}{verse_attr}>{text}</verse>'
    
    def _handle_right_header(self, template) -> str:
        """Convert {{rh|text}} to <rh>text</rh>"""
        content = str(template.get(1, ''))
        return f'<rh>{content}</rh>'
    
    def _handle_drop_initial(self, template) -> str:
        """Convert {{dropinitial|letter}} to <dropinitial>letter</dropinitial>"""
        letter = str(template.get(1, ''))
        return f'<dropinitial>{letter}</dropinitial>'
    
    def _handle_double_horizontal_rule(self, template) -> str:
        """Convert {{dhr}} to <dhr/>"""
        value = str(template.get(1, ''))
        if value:
            value=f' value="{value}"'
        else:
            value=""
        return f'<dhr{value}/>'
    
    def _handle_anchor(self, template) -> str:
        """Convert {{anchor|name}} to <anchor name="name"/>"""
        name = str(template.get(1, ''))
        return f'<anchor name="{name}"/>'
    
    def _handle_anchor_plus(self, template) -> str:
        """Convert {{anchor+|name|text}} to <anchor name="name">text</anchor>"""
        name = str(template.get(1, ''))
        text = str(template.get(2, ''))
        return f'<anchor name="{name}">{text}</anchor>'
    
    def _handle_language(self, template) -> str:
        """Convert {{lang|code|text}} to <lang code="code">text</lang>"""
        code = str(template.get(1, ''))
        text = str(template.get(2, ''))
        return f'<lang code="{code}">{text}</lang>'
    
    def _handle_small_refs(self, template) -> str:
        """Convert {{smallrefs}} to <smallrefs/>"""
        return '<smallrefs/>'
    
    def _handle_hws(self, template) -> str:
        """Convert {{hws|text}} to <hws>text</hws>"""
        content = str(template.get(1, ''))
        return f'<hws>{content}</hws>'
    
    def _handle_hwe(self, template) -> str:
        """Convert {{hwe|text}} to <hwe>text</hwe>"""
        content = str(template.get(1, ''))
        return f'<hwe>{content}</hwe>'
    
    def _handle_asterisks(self, template) -> str:
        """Convert {{***}} to <asterisks>***</asterisks>"""
        n = str(template.get(1, '3'))
        return f'<asterisks n="{n}">***</asterisks>'
    
    def _handle_reconstruct(self, template) -> str:
        """Convert {{reconstruct|content|text}} to <reconstruct>text</reconstruct>"""
        content = str(template.get(1, ''))
        text = str(template.get(2, ''))
        return f'<reconstruct><reg>{content}</reg><note>{text}</note></reconstruct>'
    
    def _handle_sic(self, template) -> str:
        """Convert {{SIC|text}} to <sic>text</sic>"""
        content = str(template.get(1, ''))
        return f'<sic>{content}</sic>'
    
    def _handle_superscript(self, template) -> str:
        """Convert {{sup|text}} to <sup>text</sup>"""
        content = str(template.get(1, ''))
        return f'<sup>{content}</sup>'
    
    def _handle_bar(self, template) -> str:
        """Convert {{bar|length}} to <bar length="length"/>"""
        length = str(template.get(1, '6'))
        return f'<bar length="{length}"/>'
    
    def _handle_gap(self, template) -> str:
        """Convert {{gap|length}} to <gap length="length"/>"""
        length = str(template.get(1, ''))
        if length:
            return f'<gap length="{length}"/>'
        else:
            return '<gap/>'
    
    def _handle_overfloat_left(self, template) -> str:
        """Convert {{overfloat left|align|padding|text}} to <overfloat_left align="..." padding="...">text</overfloat_left>"""
        # Get parameters - can be positional or named
        align = str(template.get('align', template.get(1, '')))
        padding = str(template.get('padding', template.get(2, '')))
        text = str(template.get('text', template.get(3, '')))
        
        # Clean up named parameters (remove parameter name prefixes)
        align = align.replace('align=', '') if align.startswith('align=') else align
        padding = padding.replace('padding=', '') if padding.startswith('padding=') else padding
        text = text.replace('text=', '') if text.startswith('text=') else text
        
        # Build attributes
        attributes = []
        if align:
            attributes.append(f'align="{align}"')
        if padding:
            attributes.append(f'padding="{padding}"')
        
        attr_str = ' ' + ' '.join(attributes) if attributes else ''
        
        return f'<overfloat_left{attr_str}>{text}</overfloat_left>'
    
    def _handle_float_right(self, template) -> str:
        """Convert {{float right|text}} to <float_right>text</float_right>"""
        text = str(template.get(1, ''))
        return f'<float_right>{text}</float_right>'
    
    def _handle_smaller_block_start(self, template) -> str:
        """Convert {{smaller block/s}} to <smaller_block>"""
        return '<smaller_block>'
    
    def _handle_smaller_block_end(self, template) -> str:
        """Convert {{smaller block/e}} to </smaller_block>"""
        return '</smaller_block>'
    
    # ============================================================================
    # WIKILINK HANDLERS
    # ============================================================================
    
    def _handle_wikilink(self, wikilink) -> str:
        """Process and capture wikilinks"""
        # Extract wikilink information
        title = str(wikilink.title) if hasattr(wikilink, 'title') and wikilink.title else ''
        text = str(wikilink.text) if hasattr(wikilink, 'text') and wikilink.text else title
        
        # Process templates within the wikilink text
        processed_text = self._process_nested_content(text)
        
        # Store wikilink information
        wikilink_info = {
            'title': title,
            'text': processed_text,
            'namespace': str(wikilink.namespace) if hasattr(wikilink, 'namespace') and wikilink.namespace else None,
            'section': str(wikilink.section) if hasattr(wikilink, 'section') and wikilink.section else None,
            'fragment': str(wikilink.fragment) if hasattr(wikilink, 'fragment') and wikilink.fragment else None
        }
        self.wikilinks.append(wikilink_info)
        
        # Convert to XML - use __link__ tag with attributes
        attributes = []
        if title:
            attributes.append(f'title="{title}"')
        if wikilink_info['namespace']:
            attributes.append(f'namespace="{wikilink_info["namespace"]}"')
        if wikilink_info['section']:
            attributes.append(f'section="{wikilink_info["section"]}"')
        if wikilink_info['fragment']:
            attributes.append(f'fragment="{wikilink_info["fragment"]}"')
        
        attr_str = ' ' + ' '.join(attributes) if attributes else ''
        return f'<__link__{attr_str}>{processed_text}</__link__>'
    
    # ============================================================================
    # TAG HANDLERS
    # ============================================================================
    
    def _handle_section(self, tag) -> str:
        """Convert <section> to <section> with begin and end attributes"""
        content = str(tag.contents) if tag.contents else ''
        
        # Extract begin and end attributes
        attributes = []
        if hasattr(tag, 'attributes') and tag.attributes:
            for attr in tag.attributes:
                if hasattr(attr, 'name') and hasattr(attr, 'value'):
                    attr_name = str(attr.name)
                    attr_value = str(attr.value)
                    if attr_name in ['begin', 'end']:
                        attributes.append(f'{attr_name}="{attr_value}"')
        
        # Add begin and end attributes if they exist
        attr_str = ' ' + ' '.join(attributes) if attributes else ''
        
        return f'<section{attr_str}>{content}</section>'
    
    def _handle_table(self, tag) -> str:
        """Convert <table> to <table>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<table{attr_str}>{content}</table>'
    
    def _handle_table_row(self, tag) -> str:
        """Convert <tr> to <tr>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<tr{attr_str}>{content}</tr>'
    
    def _handle_table_cell(self, tag) -> str:
        """Convert <td> to <td>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<td{attr_str}>{content}</td>'
    
    def _handle_italic(self, tag) -> str:
        """Convert <i> to <i>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<i{attr_str}>{content}</i>'
    
    def _handle_line_break(self, tag) -> str:
        """Convert <br> to <br>"""
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<br{attr_str}/>'
    
    def _handle_span(self, tag) -> str:
        """Convert <span> to <span>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<span{attr_str}>{content}</span>'
    
    def _handle_definition_description(self, tag) -> str:
        """Convert <dd> to <dd>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<dd{attr_str}>{content}</dd>'
    
    def _handle_reference(self, tag) -> str:
        """Convert <ref> to <ref>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<ref{attr_str}>{content}</ref>'
    
    def _handle_noinclude(self, tag) -> str:
        """Convert <noinclude> to <noinclude>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<noinclude{attr_str}>{content}</noinclude>'
    
    def _handle_pagequality(self, tag) -> str:
        """Convert <pagequality> to <pagequality>"""
        content = str(tag.contents) if tag.contents else ''
        attributes = self._extract_tag_attributes(tag)
        attr_str = ' ' + ' '.join([f'{k}="{v}"' for k, v in attributes.items()]) if attributes else ''
        return f'<pagequality{attr_str}>{content}</pagequality>'
    
    def _extract_tag_attributes(self, tag) -> dict[str, str]:
        """Extract all attributes from a tag"""
        attributes = {}
        if hasattr(tag, 'attributes') and tag.attributes:
            for attr in tag.attributes:
                if hasattr(attr, 'name') and hasattr(attr, 'value'):
                    attributes[str(attr.name)] = str(attr.value)
        return attributes
    
    # ============================================================================
    # PREPROCESSORS
    # ============================================================================
    
    def _fix_noinclude_line_breaks(self, content: str) -> str:
        """Insert a blank line after </noinclude> tags when followed by non-whitespace content"""
        # Pattern to match </noinclude> followed by optional whitespace and any non-whitespace character
        # This handles cases like: </noinclude>:text, </noinclude>text, </noinclude> {{template}}, etc.
        pattern = r'(</noinclude>)\s*(\S)'
        
        def replace_noinclude_content(match):
            noinclude_tag = match.group(1)
            following_content = match.group(2)
            # Insert a newline after </noinclude> and before the following content
            return f'{noinclude_tag}\n{following_content}'
        
        # Apply the replacement
        content = re.sub(pattern, replace_noinclude_content, content)
        
        return content
    
    def _normalize_whitespace(self, content: str) -> str:
        """Normalize whitespace in content"""
        # Normalize multiple spaces to single space
        content = re.sub(r' +', ' ', content)
        # Normalize line breaks, but preserve paragraph markers
        content = re.sub(r'\n+', '\n', content)
        return content.strip()
    
    def _convert_paragraph_breaks(self, content: str) -> str:
        """Convert double newlines to paragraph indicators, but skip if {{nop}} is directly adjacent"""
        
        # First, protect {{nop}} markers and their immediate context
        # Replace {{nop}} with a temporary marker
        content = content.replace('{{nop}}', '___NOP_MARKER___')
        
        # Convert \n\n to <p/>\n paragraph indicators, but not if they're adjacent to ___NOP_MARKER___
        # This regex matches \n\n that are NOT preceded or followed by ___NOP_MARKER___
        content = re.sub(r'(?<!___NOP_MARKER___)\n\n(?!___NOP_MARKER___)', '<p/>\n', content)
        
        # Restore {{nop}} markers
        content = content.replace('___NOP_MARKER___', '{{nop}}')
        
        return content
    
    def _handle_special_characters(self, content: str) -> str:
        """Handle special characters and entities - escape ampersands not in XML/HTML entities"""
        # More comprehensive regex to match XML/HTML entities
        # This includes named entities like &amp;, &lt;, &gt;, &quot;, &apos;
        # and numeric entities like &#123; and &#x1F;
        entity_pattern = r'&(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);'
        
        # Split content by entities to preserve them
        parts = re.split(f'({entity_pattern})', content)
        
        # Process each part
        result_parts = []
        for part in parts:
            if re.match(entity_pattern, part):
                # This is an entity, keep it as-is
                result_parts.append(part)
            else:
                # This is not an entity, escape standalone ampersands
                escaped_part = part.replace('&', '&amp;')
                result_parts.append(escaped_part)
        
        return ''.join(result_parts)
    
    def _extract_metadata(self, content: str) -> dict[str, Any]:
        """Extract metadata from content"""
        metadata = {}
        # Extract page quality information
        # Extract language information
        # Extract structural information
        return metadata
    
    # ============================================================================
    # POSTPROCESSORS
    # ============================================================================
    
    def _validate_xml_structure(self, content: str) -> str:
        """Validate and fix XML structure"""
        # Ensure proper nesting
        # Validate against schema
        # Fix common issues
        return content
    
    def _cleanup_empty_elements(self, content: str) -> str:
        """Remove or fix empty elements"""
        # Remove empty elements
        content = re.sub(r'<(\w+)[^>]*></\1>', '', content)
        return content
    
    def _finalize_metadata(self, content: str) -> str:
        """Finalize metadata and add to content"""
        # Add final metadata
        # Ensure proper document structure
        return content
    
    # ============================================================================
    # MAIN PROCESSING METHODS
    # ============================================================================
    
    def process_wikitext(self, wikitext: str) -> ConversionResult:
        """
        Main method to process MediaWiki wikitext to XML.
        
        Args:
            wikitext: The MediaWiki content to convert
            
        Returns:
            ConversionResult with XML content and metadata
        """
        warnings = []
        errors = []
        metadata = {}
        
        try:
            # Preprocessing
            content = wikitext
            for preprocessor in self.preprocessors:
                if preprocessor == self._extract_metadata:
                    metadata.update(preprocessor(content))
                else:
                    content = preprocessor(content)
            
            # Parse MediaWiki content
            parsed = mwparserfromhell.parse(content)
            
            # Process all nodes with nested content support
            nodes_to_replace = []
            
            # Process nodes in the order they appear in the document
            for node in parsed.nodes:
                if hasattr(node, 'name'):  # Template
                    template_name = str(node.name).strip()
                    if template_name in self.template_handlers:
                        try:
                            # Process nested content within the template
                            processed_node = self._process_template_with_nesting(node)
                            replacement = self.template_handlers[template_name](processed_node)
                            nodes_to_replace.append((node, replacement))
                        except Exception as e:
                            errors.append(f"Error processing template {template_name}: {str(e)}")
                    else:
                        warnings.append(f"Unknown template: {template_name}")
                
                elif hasattr(node, 'tag'):  # Tag
                    tag_name = str(node.tag).strip().lower()
                    if tag_name in self.tag_handlers:
                        try:
                            # Process nested content within the tag
                            processed_node = self._process_tag_with_nesting(node)
                            replacement = self.tag_handlers[tag_name](processed_node)
                            nodes_to_replace.append((node, replacement))
                        except Exception as e:
                            errors.append(f"Error processing tag {tag_name}: {str(e)}")
                    else:
                        warnings.append(f"Unknown tag: {tag_name}")
                
                elif hasattr(node, '__class__') and 'Wikilink' in str(node.__class__):  # Wikilink
                    try:
                        replacement = self._handle_wikilink(node)
                        nodes_to_replace.append((node, replacement))
                    except Exception as e:
                        errors.append(f"Error processing wikilink: {str(e)}")
            
            # Replace all nodes in order
            for node, replacement in nodes_to_replace:
                parsed.replace(node, replacement)
            
            # Get processed content
            xml_content = str(parsed)
            
            # Postprocessing
            for postprocessor in self.postprocessors:
                xml_content = postprocessor(xml_content)
            
            # Wrap in mediawiki tag
            xml_content = f'<mediawiki>{xml_content}</mediawiki>'
            
            return ConversionResult(
                xml_content=xml_content,
                metadata=metadata,
                warnings=warnings,
                errors=errors,
                wikilinks=self.wikilinks.copy()
            )
            
        except Exception as e:
            errors.append(f"Fatal error in processing: {str(e)}")
            return ConversionResult(
                xml_content="<mediawiki></mediawiki>",
                metadata={},
                warnings=warnings,
                errors=errors,
                wikilinks=[]
            )
    
    def add_template_handler(self, template_name: str, handler_func):
        """Add a custom template handler"""
        self.template_handlers[template_name] = handler_func
    
    def add_tag_handler(self, tag_name: str, handler_func):
        """Add a custom tag handler"""
        self.tag_handlers[tag_name] = handler_func
    
    def add_preprocessor(self, preprocessor_func):
        """Add a custom preprocessor"""
        self.preprocessors.append(preprocessor_func)
    
    def add_postprocessor(self, postprocessor_func):
        """Add a custom postprocessor"""
        self.postprocessors.append(postprocessor_func)
    
    def get_wikilinks(self) -> list[dict[str, Any]]:
        """Get all captured wikilinks"""
        return self.wikilinks.copy()
    
    def clear_wikilinks(self):
        """Clear all captured wikilinks"""
        self.wikilinks.clear()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_processor() -> MediaWikiProcessor:
    """Create a new MediaWiki processor instance"""
    return MediaWikiProcessor()


def process_page(page_content: str) -> ConversionResult:
    """Process a single page of MediaWiki content"""
    processor = create_processor()
    return processor.process_wikitext(page_content)


def _demo_main() -> None:  # pragma: no cover
    processor = create_processor()
    sample_wikitext = """
    {{verse|1|1|In the beginning God created the heaven and the earth.}}

    {{verse|1|2|And the earth was without form, and void; and darkness was upon the face of the deep.}}

    {{sc|Genesis}} {{c|Chapter 1}}
    {{larger|The Creation}}
    <ref name="gen1">This is a reference</ref>

    See also [[Genesis]] and [[Creation myth]] for more information.

    Nested example: {{sc|{{larger|Bold Large Text}}}}
    Complex nested: {{verse|1|3|{{sc|God}} said, {{larger|Let there be light}}}}
    """
    result = processor.process_wikitext(sample_wikitext)
    print("XML Output:")
    print(result.xml_content)
    print("\nWarnings:", result.warnings)
    print("Errors:", result.errors)
    print("Wikilinks:", result.wikilinks)


if __name__ == "__main__":  # pragma: no cover
    _demo_main()
