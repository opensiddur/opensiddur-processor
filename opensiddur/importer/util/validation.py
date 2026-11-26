from pathlib import Path
import re
from lxml import etree
from lxml.etree import _ElementTree
from typing import Tuple, List, Optional
import argparse
from saxonche import PySaxonProcessor
import subprocess
import tempfile


from .constants import SCHEMA_RNG_PATH, SCHEMA_SCH_XSLT_PATH

def validate(xml: Path | str, 
    schema_file: Optional[Path] = None,
    schema: str = None,
    schematron_xslt_file: Optional[Path] = None,
    schematron: str = None) -> Tuple[bool, List[str]]:
    """
    Validate an XML file against the RelaxNG schema or the Schematron schema
    One of schema_file or schema, and one of schematron_file or schematron must be provided.

    Args:
        xml_file: Path to the XML file to validate or XML content as a string
        schema_file: Optional path to the RelaxNG schema file. If not provided,
            will use the default schema at schema/jlptei.odd.xml.relaxng
        schema: Optional RelaxNG schema as a string.
        schematron_file: Optional path to the Schematron XSLT schema file. If not provided,
            will use the default schema at schema/jlptei.odd.xml.schematron.xslt
        schematron: Optional Schematron XSLT schema as a string.
                   
    Returns:
        Tuple of (is_valid, errors) where:
        - is_valid: Boolean indicating if the XML is valid
        - errors: List of error messages if validation fails, empty list if valid
    """
    try:
        # Load and parse the XML file
        if isinstance(xml, str):
            xml_str = xml
            xml_doc = etree.fromstring(xml)
        else:
            with open(xml, "r", encoding="utf-8") as f:
                xml_str = f.read()
            xml_doc = etree.parse(str(xml))
        
        # Determine the schema file to use
        is_valid_relax, errors_relax = relaxng_validate(xml_doc, schema or schema_file)
        is_valid_sch, errors_sch = schematron_validate(xml_str, schematron or schematron_xslt_file)
        
    
        return is_valid_relax and is_valid_sch, errors_relax + errors_sch
    except etree.DocumentInvalid as e:
        # This catches validation errors that occur during parsing
        return False, [str(e)]
    except etree.XMLSyntaxError as e:
        # This catches XML syntax errors
        return False, [f"XML syntax error: {e.msg} at line {e.lineno}, column {e.position[0]}"]
    except Exception as e:
        # Catch any other exceptions
        return False, [f"Error during validation: {str(e)}"]

def schematron_validate(
    xml_doc: str, 
    schematron_xslt_file: Optional[str |Path] = None) -> Tuple[bool, List[str]]:
    schematron_xslt_file = schematron_xslt_file or SCHEMA_SCH_XSLT_PATH
    try:
        # Load and parse the Schematron schema
        with PySaxonProcessor(license=False) as proc:
            # Create XSLT processor
            xslt_proc = proc.new_xslt30_processor()
            
            # Compile the stylesheet
            executable = xslt_proc.compile_stylesheet(stylesheet_file=str(schematron_xslt_file))
            if executable is None:
                raise ValueError(f"Failed to compile XSLT: {xslt_proc.error_message}")
            
            # Parse the input XML
            document = proc.parse_xml(xml_text=xml_doc)
            
            # Transform the document
            result = executable.transform_to_string(xdm_node=document)

        result = re.sub(r'^<\?xml[^>]*\?>\s*', '', result)   
        schematron_result = etree.fromstring(result)
        failures = schematron_result.xpath(".//svrl:failed-assert|.//svrl:successful-report", namespaces=schematron_result.nsmap) 

        if len(failures) == 0:
            return True, []
        else:
            # Get validation errors
            errors = []
            for error in failures:
                # Get all text content from the error element and its children
                error_text = "".join(error.itertext()).strip()
                errors.append(f"{error.attrib.get('location')}: {error_text}")
            return False, errors       
    except Exception as e:
        # Catch any other exceptions
        return False, [f"Error during validation: {str(e)}"]
    

def relaxng_validate(
    xml_doc: _ElementTree | str, 
    schema_file: Optional[str | Path] = None) -> Tuple[bool, List[str]]:
    """
    Validate XML against RelaxNG schema using Jing validator.
    
    Args:
        xml_doc: Either an lxml ElementTree or a string containing XML
        schema_file: Path to RelaxNG schema file or schema content as string
        
    Returns:
        Tuple of (is_valid, errors)
    """
    schema_file = schema_file or SCHEMA_RNG_PATH

    try:
        # Handle XML input
        if isinstance(xml_doc, str):
            xml_content = xml_doc
        else:
            xml_content = etree.tostring(xml_doc, encoding='unicode', pretty_print=True)
        # Create temporary XML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', encoding='utf-8', delete_on_close=False) as xml_temp:
            xml_temp.write(xml_content)
            xml_temp.flush()
            xml_temp.seek(0)
            xml_temp_path = xml_temp.name
            # Handle schema input
            if isinstance(schema_file, str) and schema_file.strip().startswith('<'):
                # Schema is provided as a string
                with tempfile.NamedTemporaryFile(mode='w', suffix='.rng', encoding='utf-8', delete_on_close=False) as schema_temp:
                    schema_content = re.sub(r'^<\?xml[^>]*\?>\s*', '', schema_file)
                    schema_temp.write(schema_content)
                    schema_temp.flush()
                    schema_temp.seek(0)
                    schema_path = schema_temp.name
                    # Call Jing validator
                    result = subprocess.run(
                        ['jing', schema_path, xml_temp_path],
                        capture_output=True,
                        text=True
                    )                
            else:
                # Schema is a file path
                schema_path = str(schema_file)
                
                # Call Jing validator
                result = subprocess.run(
                    ['jing', schema_path, xml_temp_path],
                    capture_output=True,
                    text=True
                )
            # Parse Jing output
            if result.returncode == 0:
                return True, []
            else:
                # Parse error messages from stderr
                errors = []
                error_lines = result.stdout.strip().split('\n') if result.stdout else []
                
                for line in error_lines:
                    if line.strip():
                        # Jing outputs errors in format: file:line:column: message
                        # Clean up the temporary file path from error messages
                        cleaned_line = line.replace(xml_temp_path, 'XML')
                        errors.append(cleaned_line)
                
                return False, errors
                
    except FileNotFoundError:
        return False, ["Error: Jing validator not found. Please install Jing (https://relaxng.org/jclark/jing.html)"]
    except Exception as e:
        return False, [f"Error during validation: {str(e)}"]



def _rng_with_start(start_element: str) -> str:
    # make sure the new start exists. It may be named s/:/_/

    start_element_ref = start_element.replace(":", "_")
    with open(SCHEMA_RNG_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
        # Replace the start element in the RelaxNG schema with the given start_element
        # This assumes the schema uses <start>...</start> as the entry point
        # and replaces its contents with <ref name="start_element"/>

    xslt = f'''
<xsl:stylesheet version="2.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:rng="http://relaxng.org/ns/structure/1.0"
    exclude-result-prefixes="rng">

  <!-- Identity transform -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

  <!-- Patch the <rng:choice> inside <rng:start> -->
  <xsl:template match="rng:start/rng:choice">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
      <rng:ref name="{start_element_ref}"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
'''

    with PySaxonProcessor(license=False) as proc:
        # Use Saxon/C XPath processor to check for rng:define[@name='{start_element_ref}']
        xpath_expr = f"//rng:define[@name='{start_element_ref}']"
        xpath_proc = proc.new_xpath_processor()
        xpath_proc.declare_namespace("rng", "http://relaxng.org/ns/structure/1.0")
        doc = proc.parse_xml(xml_text=schema)
        xpath_proc.set_context(xdm_item=doc)
        result_nodes = xpath_proc.evaluate(xpath_expr)
        if not result_nodes or (hasattr(result_nodes, 'count') and result_nodes.count == 0):
            raise ValueError(f"RelaxNG schema does not define an element with name {start_element}='{start_element_ref}'")
        xslt_proc = proc.new_xslt30_processor()
        
        # Compile the XSLT from string
        executable = xslt_proc.compile_stylesheet(stylesheet_text=xslt)
        if executable is None:
            raise RuntimeError("Failed to compile XSLT for patching RelaxNG start element.")
        # Transform the schema string
        document = proc.parse_xml(xml_text=schema)
        result = executable.transform_to_string(xdm_node=document)
        return result

def _add_missing_namespaces(xml: str) -> str:
    """
    Add TEI and JLPTEI namespace declarations to XML if they're missing.
    This is useful for validating XML fragments that don't have namespace declarations.
    
    Args:
        xml: XML string that may be missing namespace declarations
        
    Returns:
        XML string with namespace declarations added to the root element if needed
    """
    # Check if TEI namespace is missing
    needs_tei_ns = 'xmlns:tei=' not in xml
    needs_j_ns = 'xmlns:j=' not in xml
    
    if not needs_tei_ns and not needs_j_ns:
        # Both namespaces are already present
        return xml
    
    # Find the first element opening tag (including attributes)
    import re
    # Match opening tag like <tei:something...> or <j:something...>
    match = re.search(r'<([a-zA-Z][a-zA-Z0-9_:-]*)((?:\s+[^>]*)?)(>|/>)', xml)
    if not match:
        # Can't find an opening tag, return as-is
        return xml
    
    tag_name = match.group(1)
    existing_attrs = match.group(2)
    tag_close = match.group(3)
    
    # Build the namespace declarations to add
    ns_declarations = []
    if needs_tei_ns:
        ns_declarations.append('xmlns:tei="http://www.tei-c.org/ns/1.0"')
    if needs_j_ns:
        ns_declarations.append('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"')
    
    # Construct the new opening tag
    if existing_attrs.strip():
        # Has existing attributes, add namespaces after them
        new_opening = f'<{tag_name}{existing_attrs} {" ".join(ns_declarations)}{tag_close}'
    else:
        # No existing attributes, just add namespaces
        new_opening = f'<{tag_name} {" ".join(ns_declarations)}{tag_close}'
    
    # Replace the original opening tag with the new one
    return xml[:match.start()] + new_opening + xml[match.end():]

def validate_with_start(
    xml: str,
    start_element: str,
) -> Tuple[bool, List[str]]:
    """
    Validate an XML fragment against the schema starting from a specific element.
    Automatically adds TEI and JLPTEI namespace declarations if they're missing.
    
    Args:
        xml: XML fragment to validate
        start_element: The element name to use as the start element (e.g., "tei:div")
        
    Returns:
        Tuple of (is_valid, errors)
    """
    # Add missing namespace declarations if needed
    xml_with_ns = _add_missing_namespaces(xml)
    
    relaxng_schema = _rng_with_start(start_element)
    is_valid, errors = validate(xml_with_ns, schema=relaxng_schema, schematron=SCHEMA_SCH_XSLT_PATH)
    return is_valid, errors


def main(): # pragma: no cover
    parser = argparse.ArgumentParser(description='Validate an XML file against a RelaxNG schema.')
    parser.add_argument('xml_file', type=str, help='Path to the XML file to validate')
    parser.add_argument('--relaxng_file', type=str, help='Path to the RelaxNG schema file', default=None)
    parser.add_argument('--schematron_file', type=str, help='Path to the Schematron schema file', default=None)
    args = parser.parse_args()
    
    is_valid, errors = validate(Path(args.xml_file), 
                                Path(args.relaxng_file) if args.relaxng_file else None,
                                Path(args.schematron_file) if args.schematron_file else None)
    
    if is_valid:
        print(f"{args.xml_file} is valid.")
    else:
        print(f"{args.xml_file} is not valid.")
        for error in errors:
            print(error)
    
    return is_valid

if __name__ == "__main__": # pragma: no cover
    main()
        