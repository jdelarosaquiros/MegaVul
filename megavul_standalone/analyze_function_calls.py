#!/usr/bin/env python3
"""Standalone utility to analyze callees and callers of functions.

This script can analyze function calls for:
1. Functions extracted from a previous run of extract_commit_functions.py
2. Specific function names provided as arguments
3. All functions in specific files

The script will search the entire repository to find:
- Callees: Functions called by the target functions
- Callers: Functions that call the target functions
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict

# Allow running as a module or as a script.
if __package__ in {None, ""}:
    import os
    import sys
    sys.path.append(os.path.dirname(__file__))
    from utils import analyze_function_calls_in_repo, save_jsonl, extract_functions, language_from_path
else:  # pragma: no cover - normal package imports
    from .utils import analyze_function_calls_in_repo, save_jsonl, extract_functions, language_from_path


def load_functions_from_jsonl(jsonl_path: str) -> List[str]:
    """Load function names from a JSONL file created by extract_commit_functions.py."""
    function_names = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            if 'function' in data:
                function_names.append(data['function'])
    return function_names


def extract_functions_from_files(file_paths: List[str]) -> List[str]:
    """Extract all function names from the given files."""
    function_names = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: File {file_path} does not exist")
            continue
            
        language = language_from_path(file_path)
        if language is None:
            print(f"Warning: Unsupported file type {file_path}")
            continue
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            functions = extract_functions(content, file_path)
            function_names.extend([f.name for f in functions])
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    return function_names


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze callees and callers of functions")
    parser.add_argument("repo_path", help="Path to local repository")
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--from-jsonl", help="Load function names from JSONL file")
    input_group.add_argument("--functions", nargs="+", help="Function names to analyze")
    input_group.add_argument("--from-files", nargs="+", help="Extract functions from these files")
    
    parser.add_argument("--commit", help="Commit hash to analyze (default: HEAD)")
    parser.add_argument("--output", default="function_call_analysis.jsonl", help="Output JSONL file")
    
    args = parser.parse_args()

    # Determine function names to analyze
    if args.from_jsonl:
        print(f"Loading functions from {args.from_jsonl}")
        function_names = load_functions_from_jsonl(args.from_jsonl)
    elif args.functions:
        function_names = args.functions
    elif args.from_files:
        print(f"Extracting functions from {len(args.from_files)} files")
        function_names = extract_functions_from_files(args.from_files)
    else:
        print("Error: No input method specified")
        return

    if not function_names:
        print("No functions found to analyze")
        return

    print(f"Analyzing {len(function_names)} functions: {', '.join(function_names[:5])}" + 
          (f" and {len(function_names) - 5} more" if len(function_names) > 5 else ""))

    # Perform call analysis
    call_analysis = analyze_function_calls_in_repo(args.repo_path, function_names, args.commit)

    # Convert results to JSON-serializable format
    results = []
    for func_name, analysis in call_analysis.items():
        result = {
            "function_name": func_name,
            "file_path": analysis.file_path,
            "signature": analysis.signature,
            "return_type": analysis.return_type,
            "callees": [
                {
                    "name": callee.name,
                    "file_path": callee.file_path,
                    "signature": callee.signature,
                    "return_type": callee.return_type,
                    "start_line": callee.start_line,
                    "end_line": callee.end_line,
                    "code": callee.code
                }
                for callee in analysis.callees
            ],
            "callers": [
                {
                    "name": caller.name,
                    "file_path": caller.file_path,
                    "signature": caller.signature,
                    "return_type": caller.return_type,
                    "start_line": caller.start_line,
                    "end_line": caller.end_line,
                    "code": caller.code,
                    "call_line": caller.call_line
                }
                for caller in analysis.callers
            ],
            "summary": {
                "num_callees": len(analysis.callees),
                "num_callers": len(analysis.callers),
                "unique_caller_files": len(set(caller.file_path for caller in analysis.callers))
            }
        }
        results.append(result)

    # Save results
    save_jsonl(results, Path(args.output))
    print(f"Saved call analysis for {len(results)} functions to {args.output}")
    
    # Print summary
    total_callees = sum(len(r["callees"]) for r in results)
    total_callers = sum(len(r["callers"]) for r in results)
    print(f"\nSummary:")
    print(f"  Functions analyzed: {len(results)}")
    print(f"  Total callees found: {total_callees}")
    print(f"  Total callers found: {total_callers}")
    print(f"  Average callees per function: {total_callees / len(results):.1f}")
    print(f"  Average callers per function: {total_callers / len(results):.1f}")


if __name__ == "__main__":
    main()
