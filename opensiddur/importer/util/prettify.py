"""
XML prettification utilities for formatting XML strings with proper indentation.
"""
import sys
import argparse

from lxml import etree as lxml_etree



def prettify_xml(xml_string: str,
                remove_xml_declaration: bool=False,
                encoding: str="utf-8",
                keep_blank_text: bool=False) -> str:
    """
    Prettify an XML string with proper indentation and formatting.
    Uses lxml if available (preserves namespace prefixes), falls back to minidom.
    
    Args:
        xml_string (str): The XML string to prettify
        remove_xml_declaration (bool): Whether to remove the XML declaration (default: False)
        encoding (str): The encoding to use (default: utf-8)
        keep_blank_text (bool): Keep whitespace-only text. By default it is removed so that
            the document can be re-indented, which also removes the space between two
            adjacent inline elements; a caller whose input has no whitespace between block
            elements can keep it and still be indented.
    
    Returns:
        str: The prettified XML string
        
    Raises:
        lxml.etree.ParseError: If the XML string is not valid XML
    """
    try:
        # lxml preserves namespace prefixes
        parser = lxml_etree.XMLParser(remove_blank_text=not keep_blank_text)
        root = lxml_etree.fromstring(xml_string.encode(encoding), parser)
        
        pretty_xml = lxml_etree.tostring(
            root,
            pretty_print=True,
            encoding=encoding,
            xml_declaration=not remove_xml_declaration
        )
        
        if isinstance(pretty_xml, bytes):
            pretty_xml = pretty_xml.decode(encoding)
     
        return pretty_xml.rstrip()
    except lxml_etree.XMLSyntaxError:
        # Re-raise XMLSyntaxError (which is a subclass of ParseError) with original error
        raise
    except lxml_etree.ParseError:
        # Re-raise ParseError with original error
        raise


def main(): # pragma: no cover
    """Main function to handle command-line arguments and prettify XML files."""
    parser = argparse.ArgumentParser(
        description="Prettify XML files with proper indentation and formatting"
    )
    parser.add_argument(
        "input_file",
        help="Input XML file to prettify"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "-i", "--indent",
        type=int,
        default=2,
        help="Number of spaces for indentation (default: 2)"
    )
    parser.add_argument(
        "--remove-declaration",
        action="store_true",
        help="Remove XML declaration from output"
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8)"
    )
    
    args = parser.parse_args()
    
    try:
        # Read input file
        with open(args.input_file, 'r', encoding=args.encoding) as f:
            xml_content = f.read()
        
        # Prettify the XML
        # Note: indent parameter is not used by prettify_xml (lxml handles indentation)
        prettified = prettify_xml(
            xml_content,
            remove_xml_declaration=args.remove_declaration,
            encoding=args.encoding
        )
        
        # Write output
        if args.output:
            with open(args.output, 'w', encoding=args.encoding) as f:
                f.write(prettified)
            print(f"Prettified XML written to {args.output}", file=sys.stderr)
        else:
            print(prettified)
            
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except lxml_etree.ParseError as e:
        print(f"Error: Invalid XML in '{args.input_file}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__": # pragma: no cover
    main()
