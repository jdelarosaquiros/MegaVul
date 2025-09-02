#!/usr/bin/env python3
"""Standalone utility to extract changed functions from a commit.

The script expects the repository already exists locally. It will parse
functions before and after the specified commit using tree-sitter and
store the filtered results in a JSONL file.
"""
import argparse
from pathlib import Path
import sys

script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

from megavul_standalone.utils.commit_analysis import CommitFunctionExtractor
import json

def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Extract changed functions from a commit")
    parser.add_argument("repo_url", help="URL of repository (for record only)")
    parser.add_argument("commit", help="Commit id of the fix")
    parser.add_argument("repo_path", help="Path to local repository")
    parser.add_argument("--output", default="extracted_functions.jsonl", help="Output JSONL file")
    parser.add_argument("--analyze-calls", default=True, action="store_true",
                       help="Analyze callees and callers of extracted functions (may be slow for large repos)")
    args = parser.parse_args()

    # Create extractor and process the commit
    extractor = CommitFunctionExtractor(args.repo_path, args.repo_url, args.commit)
    function_changes = extractor.extract_changed_functions(args.analyze_calls)

    # Convert results to dictionaries for JSON serialization
    json_results = [change.to_dict() for change in function_changes]

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for item in json_results:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    analysis_type = "with call analysis" if args.analyze_calls else ""
    print(f"Saved {len(function_changes)} functions {analysis_type} to {args.output}")

if __name__ == "__main__":
    main()
