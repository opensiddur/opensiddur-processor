import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from saxonche import PySaxonProcessor


def _to_xdm_value(proc: PySaxonProcessor, value: Any) -> Any:
    if isinstance(value, str):
        return proc.make_string_value(value)
    elif isinstance(value, bool):
        return proc.make_boolean_value(value)
    elif isinstance(value, int):
        return proc.make_integer_value(value)
    elif isinstance(value, float):
        return proc.make_double_value(value)
    else:
        # For other types, try to convert to string as a fallback
        return proc.make_string_value(str(value))

def xslt_transform_string(
    xslt_file: Path,
    input_xml: str,
    multiple_results: bool = False,
    xslt_params: dict[str, Any] | None = None,
    ) -> str | dict[str, str]:
    
    try:
        with PySaxonProcessor(license=False) as proc:
            # Create XSLT processor
            xslt_proc = proc.new_xslt30_processor()
            
            # Compile the stylesheet
            executable = xslt_proc.compile_stylesheet(stylesheet_file=str(xslt_file))
            if executable is None:
                raise ValueError(f"Failed to compile XSLT: {xslt_proc.error_message}")
            if multiple_results:
                executable.set_base_output_uri("file:///output/")
                executable.set_capture_result_documents(True, False)
            if xslt_params:
                for param, value in xslt_params.items():
                    executable.set_parameter(param, _to_xdm_value(proc, value))
            # Parse the input XML
            document = proc.parse_xml(xml_text=input_xml)
            
            # Transform the document
            result = executable.transform_to_string(xdm_node=document)
            
            if multiple_results:
                secondaries = executable.get_result_documents()
                results = {
                    "": result,
                    **{
                        uri.split("/")[-1]: str(xdm)
                        for uri, xdm in secondaries.items()
                    }
                }
                return results
            else:
                return result
    except Exception as e:
        print(f"Error in XSLT transform function: {e}", file=sys.stderr)
        raise


def xslt_transform(
    xslt_file: Path,
    input_file: Path,
    output_file: Path | None = None,
    *,
    xslt_params: dict[str, Any] | None = None,
):
    try:
        # Read the input XML
        with open(input_file, encoding='utf-8') as input_fd:
            input_xml = input_fd.read()

        result = xslt_transform_string(
            xslt_file, input_xml, xslt_params=xslt_params
        )
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as output_fd:
                output_fd.write(result)
        else:
            sys.stdout.write(result)
        
    except Exception as e:
        print(f"Error in transform function: {e}", file=sys.stderr)
        raise


def main(): # pragma: no cover
    parser = ArgumentParser()
    parser.add_argument("-o", "--output", type=Path, required=False, default=None)
    parser.add_argument("transform_file", type=Path)
    parser.add_argument("input_file", type=Path)
    
    args = parser.parse_args()

    xslt_transform(args.transform_file, args.input_file, args.output)


if __name__ == "__main__": # pragma: no cover
    main()