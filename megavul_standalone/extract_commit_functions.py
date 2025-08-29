#!/usr/bin/env python3
"""Standalone utility to extract changed functions from a commit.

The script expects the repository already exists locally. It will parse
functions before and after the specified commit using tree-sitter and
store the filtered results in a JSONL file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from git import Repo

# Allow running as a module or as a script.
if __package__ in {None, ""}:
    import os
    import sys
    sys.path.append(os.path.dirname(__file__))
    from utils import extract_functions, diff_lines, language_from_path, save_jsonl, analyze_function_calls_in_repo, analyze_function_calls_before_after
    from filters import is_test_file, is_large_function, is_large_change
else:  # pragma: no cover - normal package imports
    from .utils import extract_functions, diff_lines, language_from_path, save_jsonl, analyze_function_calls_in_repo, analyze_function_calls_before_after
    from .filters import is_test_file, is_large_function, is_large_change


def collect_changes(repo: Repo, commit_hash: str) -> Dict[str, Dict[str, str]]:
    """Return mapping of file path to tuple(before, after)."""
    commit = repo.commit(commit_hash)
    if not commit.parents:
        raise ValueError("Commit has no parent; cannot compute diff")
    parent = commit.parents[0]
    diffs = commit.diff(parent, create_patch=False)
    result: Dict[str, Dict[str, str]] = {}
    for d in diffs:
        if d.change_type not in {"M", "A", "D"}:
            continue
        file_path = d.b_path if d.change_type != "D" else d.a_path
        lang = language_from_path(file_path or "")
        if lang is None:
            continue
        try:
            before = (parent.tree / d.a_path).data_stream.read().decode("utf-8") if d.a_blob else ""
            after = (commit.tree / d.b_path).data_stream.read().decode("utf-8") if d.b_blob else ""
        except Exception:
            # binary file or decoding issue
            continue
        result[file_path] = {"language": lang, "before": before, "after": after}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract changed functions from a commit")
    parser.add_argument("repo_url", help="URL of repository (for record only)")
    parser.add_argument("commit", help="Commit id of the fix")
    parser.add_argument("repo_path", help="Path to local repository")
    parser.add_argument("--output", default="extracted_functions.jsonl", help="Output JSONL file")
    parser.add_argument("--analyze-calls", default=True, action="store_true",
                       help="Analyze callees and callers of extracted functions (may be slow for large repos)")
    args = parser.parse_args()

    repo = Repo(args.repo_path)
    file_changes = collect_changes(repo, args.commit)

    results: List[dict] = []

    for path, info in file_changes.items():
        if is_test_file(path):
            continue
        language = info["language"]
        before_funcs = {f.name: f for f in extract_functions(info["before"], language)}
        after_funcs = {f.name: f for f in extract_functions(info["after"], language)}
        for name, after_func in after_funcs.items():
            if name not in before_funcs:
                continue
            before_func = before_funcs[name]
            if is_large_function(after_func.code) or is_large_function(before_func.code):
                continue
            diff_text, diff_stat = diff_lines(before_func.code, after_func.code)
            if is_large_change(diff_stat):
                continue
            results.append(
                {
                    "repo_url": args.repo_url,
                    "commit": args.commit,
                    "file_path": path,
                    "language": language,
                    "function": name,
                    "before": before_func.code,
                    "after": after_func.code,
                    "diff": diff_text,
                    "diff_stat": diff_stat,
                    "start_line_before": before_func.start_line,
                    "end_line_before": before_func.end_line,
                    "start_line_after": after_func.start_line,
                    "end_line_after": after_func.end_line,
                }
            )

    save_jsonl(results, Path(args.output))
    print(f"Saved {len(results)} functions to {args.output}")

    # Extract callees and callers for the functions we found (if requested)
    if args.analyze_calls and results:
        function_names = [result["function"] for result in results]

        print("Analyzing function calls before and after fix commit...")
        before_after_analysis = analyze_function_calls_before_after(args.repo_path, function_names, args.commit)

        # Add before/after call analysis to results
        for result in results:
            func_name = result["function"]
            if func_name in before_after_analysis:
                combined_analysis, comparison = before_after_analysis[func_name]

                result["call_analysis"] = {
                    "before_fix": {
                        "file_path": combined_analysis.file_path_before,
                        "signature": combined_analysis.signature_before,
                        "return_type": combined_analysis.return_type_before,
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
                            for callee in combined_analysis.callees_before
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
                            for caller in combined_analysis.callers_before
                        ]
                    },
                    "after_fix": {
                        "file_path": combined_analysis.file_path_after,
                        "signature": combined_analysis.signature_after,
                        "return_type": combined_analysis.return_type_after,
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
                            for callee in combined_analysis.callees_after
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
                            for caller in combined_analysis.callers_after
                        ]
                    },
                    "changes": {
                        "added_callees": [
                            {
                                "name": callee.name,
                                "file_path": callee.file_path,
                                "signature": callee.signature,
                                "return_type": callee.return_type,
                                "start_line": callee.start_line,
                                "end_line": callee.end_line,
                                "code": callee.code
                            }
                            for callee in comparison.added_callees
                        ],
                        "removed_callees": [
                            {
                                "name": callee.name,
                                "file_path": callee.file_path,
                                "signature": callee.signature,
                                "return_type": callee.return_type,
                                "start_line": callee.start_line,
                                "end_line": callee.end_line,
                                "code": callee.code
                            }
                            for callee in comparison.removed_callees
                        ],
                        "unchanged_callees": [
                            {
                                "name": callee.name,
                                "file_path": callee.file_path,
                                "signature": callee.signature,
                                "return_type": callee.return_type,
                                "start_line": callee.start_line,
                                "end_line": callee.end_line,
                                "code": callee.code
                            }
                            for callee in comparison.unchanged_callees
                        ],
                        "added_callers": [
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
                            for caller in comparison.added_callers
                        ],
                        "removed_callers": [
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
                            for caller in comparison.removed_callers
                        ],
                        "unchanged_callers": [
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
                            for caller in comparison.unchanged_callers
                        ]
                    }
                }

        # Save results with before/after call analysis
        save_jsonl(results, Path(args.output))
        print(f"Saved {len(results)} functions call analysis to {args.output}")

if __name__ == "__main__":
    main()
