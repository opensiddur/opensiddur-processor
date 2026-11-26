"""
MediaWiki Template Finder for JPS1917 Converter

This module provides functionality to identify all MediaWiki templates
used across all pages in the 1917 JPS Wikisource project.
"""

import mwparserfromhell
from collections import Counter, defaultdict
from typing import Dict, Optional
from pathlib import Path

# Import the get_page function from the page utilities
from opensiddur.importer.util.pages import default_sourcetexts_root, get_page


def find_all_tags(
    start_page: int = 1,
    end_page: Optional[int] = None,
    sourcetexts_root: Optional[Path] = None,
) -> Dict[str, Dict]:
    """
    Find all MediaWiki tags used across all pages.
    
    Args:
        start_page: Starting page number (default: 1)
        end_page: Ending page number (if None, will scan until no more pages found)
    
    Returns:
        Dictionary containing:
        - 'tags': Counter of tag names and their usage counts
        - 'tag_details': Dict mapping tag names to detailed info
        - 'pages_processed': Number of pages successfully processed
        - 'errors': List of pages that couldn't be processed
    """
    tags_counter = Counter()
    tag_details = defaultdict(lambda: {
        'usage_count': 0,
        'pages_used': set(),
        'attributes': set(),
        'examples': []
    })
    
    pages_processed = 0
    errors = []
    
    # If end_page not specified, try to find the last page
    if end_page is None:
        start_page, end_page = find_page_range(sourcetexts_root)
    
    print(f"Scanning pages {start_page} to {end_page} for MediaWiki tags...")
    
    for page_num in range(start_page, end_page + 1):
        try:
            page_obj = get_page(page_num, sourcetexts_root)
            if page_obj is None:
                print(f"Page {page_num} not found, stopping scan")
                break
                
            page_content = page_obj.content
            page_tags = extract_tags_from_wikitext(page_content)
            
            for tag_name, tag_info in page_tags.items():
                tags_counter[tag_name] += tag_info['count']
                tag_details[tag_name]['usage_count'] += tag_info['count']
                tag_details[tag_name]['pages_used'].add(page_num)
                tag_details[tag_name]['attributes'].update(tag_info['attributes'])
                
                # Store a few examples (limit to 3 per tag)
                if len(tag_details[tag_name]['examples']) < 3:
                    tag_details[tag_name]['examples'].extend(tag_info['examples'])
            
            pages_processed += 1
            
            if pages_processed % 100 == 0:
                print(f"Processed {pages_processed} pages...")
                
        except Exception as e:
            error_msg = f"Error processing page {page_num}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    # Convert sets to lists for JSON serialization
    for tag_name in tag_details:
        tag_details[tag_name]['pages_used'] = sorted(list(tag_details[tag_name]['pages_used']))
        tag_details[tag_name]['attributes'] = sorted(list(tag_details[tag_name]['attributes']))
    
    return {
        'tags': dict(tags_counter),
        'tag_details': dict(tag_details),
        'pages_processed': pages_processed,
        'errors': errors
    }


def find_all_templates(
    start_page: int = 1,
    end_page: Optional[int] = None,
    sourcetexts_root: Optional[Path] = None,
) -> Dict[str, Dict]:
    """
    Find all MediaWiki templates used across all pages.
    
    Args:
        start_page: Starting page number (default: 1)
        end_page: Ending page number (if None, will scan until no more pages found)
    
    Returns:
        Dictionary containing:
        - 'templates': Counter of template names and their usage counts
        - 'template_details': Dict mapping template names to detailed info
        - 'pages_processed': Number of pages successfully processed
        - 'errors': List of pages that couldn't be processed
    """
    templates_counter = Counter()
    template_details = defaultdict(lambda: {
        'usage_count': 0,
        'pages_used': set(),
        'parameters': set(),
        'examples': []
    })
    
    pages_processed = 0
    errors = []
    
    # If end_page not specified, try to find the last page
    if end_page is None:
        start_page, end_page = find_page_range(sourcetexts_root)
    
    print(f"Scanning pages {start_page} to {end_page} for MediaWiki templates...")
    
    for page_num in range(start_page, end_page + 1):
        try:
            page_obj = get_page(page_num, sourcetexts_root)
            if page_obj is None:
                print(f"Page {page_num} not found, stopping scan")
                break
                
            page_content = page_obj.content
            page_templates = extract_templates_from_wikitext(page_content)
            
            for template_name, template_info in page_templates.items():
                templates_counter[template_name] += template_info['count']
                template_details[template_name]['usage_count'] += template_info['count']
                template_details[template_name]['pages_used'].add(page_num)
                template_details[template_name]['parameters'].update(template_info['parameters'])
                
                # Store a few examples (limit to 3 per template)
                if len(template_details[template_name]['examples']) < 3:
                    template_details[template_name]['examples'].extend(template_info['examples'])
            
            pages_processed += 1
            
            if pages_processed % 100 == 0:
                print(f"Processed {pages_processed} pages...")
                
        except Exception as e:
            error_msg = f"Error processing page {page_num}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    # Convert sets to lists for JSON serialization
    for template_name in template_details:
        template_details[template_name]['pages_used'] = sorted(list(template_details[template_name]['pages_used']))
        template_details[template_name]['parameters'] = sorted(list(template_details[template_name]['parameters']))
    
    return {
        'templates': dict(templates_counter),
        'template_details': dict(template_details),
        'pages_processed': pages_processed,
        'errors': errors
    }


def extract_tags_from_wikitext(wikitext: str) -> Dict[str, Dict]:
    """
    Extract tag information from MediaWiki wikitext.
    
    Args:
        wikitext: The MediaWiki wikitext content
    
    Returns:
        Dictionary mapping tag names to their information
    """
    try:
        parsed = mwparserfromhell.parse(wikitext)
        tags = {}
        
        for tag in parsed.filter_tags():
            tag_name = str(tag.tag).strip().lower()
            
            if tag_name not in tags:
                tags[tag_name] = {
                    'count': 0,
                    'attributes': set(),
                    'examples': []
                }
            
            tags[tag_name]['count'] += 1
            
            # Extract attributes
            if hasattr(tag, 'attributes') and tag.attributes:
                if isinstance(tag.attributes, dict):
                    for attr_name, attr_value in tag.attributes.items():
                        tags[tag_name]['attributes'].add(attr_name)
                elif isinstance(tag.attributes, list):
                    for attr in tag.attributes:
                        if hasattr(attr, 'name'):
                            tags[tag_name]['attributes'].add(str(attr.name))
            
            # Store example (limit to avoid memory issues)
            if len(tags[tag_name]['examples']) < 2:
                example = {
                    'full_tag': str(tag),
                    'attributes': dict(tag.attributes) if hasattr(tag, 'attributes') and isinstance(tag.attributes, dict) else {},
                    'contents': str(tag.contents) if hasattr(tag, 'contents') and tag.contents else None,
                    'self_closing': getattr(tag, 'self_closing', False)
                }
                tags[tag_name]['examples'].append(example)
    
    except Exception as e:
        print(f"Error parsing wikitext for tags: {str(e)}")
        return {}
    
    return tags


def extract_templates_from_wikitext(wikitext: str) -> Dict[str, Dict]:
    """
    Extract template information from MediaWiki wikitext.
    
    Args:
        wikitext: The MediaWiki wikitext content
    
    Returns:
        Dictionary mapping template names to their information
    """
    try:
        parsed = mwparserfromhell.parse(wikitext)
        templates = {}
        
        for template in parsed.filter_templates():
            template_name = str(template.name).strip()
            
            if template_name not in templates:
                templates[template_name] = {
                    'count': 0,
                    'parameters': set(),
                    'examples': []
                }
            
            templates[template_name]['count'] += 1
            
            # Extract parameters
            for param in template.params:
                param_name = str(param.name).strip() if param.name else "unnamed"
                templates[template_name]['parameters'].add(param_name)
            
            # Store example (limit to avoid memory issues)
            if len(templates[template_name]['examples']) < 2:
                example = {
                    'full_template': str(template),
                    'parameters': {str(p.name).strip() if p.name else "unnamed": str(p.value).strip() 
                                 for p in template.params}
                }
                templates[template_name]['examples'].append(example)
    
    except Exception as e:
        print(f"Error parsing wikitext: {str(e)}")
        return {}
    
    return templates


def find_page_range(sourcetexts_root: Optional[Path] = None) -> tuple[int, int]:
    """
    Find the last available page by checking for consecutive missing pages.
    
    Returns:
        The first and last page number found
    """
    first_page = 1
    last_page = 1
    
    # Start from a reasonable point and work backwards
    for page_num in range(1200, 0, -1):
        page_obj = get_page(page_num, sourcetexts_root)
        if page_obj is not None:
            last_page = page_num
            break
    
    for page_num in range(last_page, 0, -1):
        page_obj = get_page(page_num, sourcetexts_root)
        if page_obj is None:
            first_page = page_num + 1
            break
    
    return first_page, last_page


def print_tag_summary(tag_data: Dict) -> None: # pragma: no cover
    """
    Print a summary of found tags.
    
    Args:
        tag_data: Output from find_all_tags()
    """
    tags = tag_data['tags']
    tag_details = tag_data['tag_details']
    
    print("\n=== MediaWiki Tag Analysis ===")
    print(f"Pages processed: {tag_data['pages_processed']}")
    print(f"Total unique tags found: {len(tags)}")
    print(f"Total tag instances: {sum(tags.values())}")
    
    if tag_data['errors']:
        print(f"Errors encountered: {len(tag_data['errors'])}")
    
    print("\n=== Top 20 Most Used Tags ===")
    # Sort tags by usage count
    sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
    for tag_name, count in sorted_tags[:20]:
        details = tag_details[tag_name]
        print(f"{tag_name}: {count} uses across {len(details['pages_used'])} pages")
        if details['attributes']:
            print(f"  Attributes: {', '.join(list(details['attributes'])[:5])}{'...' if len(details['attributes']) > 5 else ''}")
    
    print("\n=== All Tags (sorted by name) ===")
    for tag_name in sorted(tags.keys()):
        count = tags[tag_name]
        details = tag_details[tag_name]
        print(f"{tag_name}: {count} uses")


def print_template_summary(template_data: Dict) -> None: # pragma: no cover
    """
    Print a summary of found templates.
    
    Args:
        template_data: Output from find_all_templates()
    """
    templates = template_data['templates']
    template_details = template_data['template_details']
    
    print("\n=== MediaWiki Template Analysis ===")
    print(f"Pages processed: {template_data['pages_processed']}")
    print(f"Total unique templates found: {len(templates)}")
    print(f"Total template instances: {sum(templates.values())}")
    
    if template_data['errors']:
        print(f"Errors encountered: {len(template_data['errors'])}")
    
    print("\n=== Top 20 Most Used Templates ===")
    # Sort templates by usage count
    sorted_templates = sorted(templates.items(), key=lambda x: x[1], reverse=True)
    for template_name, count in sorted_templates[:20]:
        details = template_details[template_name]
        print(f"{template_name}: {count} uses across {len(details['pages_used'])} pages")
        if details['parameters']:
            print(f"  Parameters: {', '.join(list(details['parameters'])[:5])}{'...' if len(details['parameters']) > 5 else ''}")
    
    print("\n=== All Templates (sorted by name) ===")
    for template_name in sorted(templates.keys()):
        count = templates[template_name]
        details = template_details[template_name]
        print(f"{template_name}: {count} uses")


def save_tag_analysis(tag_data: Dict, output_file: str = "tag_analysis.json") -> None: # pragma: no cover
    """
    Save tag analysis to a JSON file.
    
    Args:
        tag_data: Output from find_all_tags()
        output_file: Path to save the analysis
    """
    import json
    
    # Convert any remaining sets to lists for JSON serialization
    serializable_data = {
        'tags': tag_data['tags'],
        'tag_details': tag_data['tag_details'],
        'pages_processed': tag_data['pages_processed'],
        'errors': tag_data['errors']
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_data, f, indent=2, ensure_ascii=False)
    
    print(f"Tag analysis saved to {output_file}")


def save_template_analysis(template_data: Dict, output_file: str = "template_analysis.json") -> None: # pragma: no cover
    """
    Save template analysis to a JSON file.
    
    Args:
        template_data: Output from find_all_templates()
        output_file: Path to save the analysis
    """
    import json
    
    # Convert any remaining sets to lists for JSON serialization
    serializable_data = {
        'templates': template_data['templates'],
        'template_details': template_data['template_details'],
        'pages_processed': template_data['pages_processed'],
        'errors': template_data['errors']
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_data, f, indent=2, ensure_ascii=False)
    
    print(f"Template analysis saved to {output_file}")


def _run_cli() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Analyze JPS 1917 Wikisource MediaWiki templates and tags.")
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help="Root of sourcetexts repo; JPS pages under <root>/jps1917 (default: <repo>/sourcetexts/sources).",
    )
    args = parser.parse_args()
    root = args.sourcetexts_root

    print("Starting MediaWiki template and tag analysis...")

    print("\n" + "=" * 50)
    print("ANALYZING TEMPLATES")
    print("=" * 50)
    template_data = find_all_templates(sourcetexts_root=root)
    print_template_summary(template_data)
    save_template_analysis(template_data, "jps1917_template_analysis.json")

    print("\n" + "=" * 50)
    print("ANALYZING TAGS")
    print("=" * 50)
    tag_data = find_all_tags(sourcetexts_root=root)
    print_tag_summary(tag_data)
    save_tag_analysis(tag_data, "jps1917_tag_analysis.json")

    print("\n" + "=" * 50)
    print("ANALYSIS COMPLETE!")
    print("=" * 50)
    print("Template analysis saved to: jps1917_template_analysis.json")
    print("Tag analysis saved to: jps1917_tag_analysis.json")


if __name__ == "__main__":  # pragma: no cover
    _run_cli()
