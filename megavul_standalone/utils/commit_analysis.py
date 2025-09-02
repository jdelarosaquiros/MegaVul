from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from git import Repo, Commit
from pathlib import Path
from git import Repo

from .filters import is_test_file, is_large_function, is_large_change
from .static_code_processor import extract_functions, extract_function_calls, get_file_language_type, diff_lines
# Remove this line:
# from tree_sitter_languages import get_language

@dataclass
class FunctionDefinition:
    name: str
    file_path: str
    signature: str
    return_type: str
    start_line: int
    end_line: int
    code: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "file_path": self.file_path,
            "signature": self.signature,
            "return_type": self.return_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code
        }

@dataclass
class CallInfo:
    name: str
    file_path: str
    signature: str
    return_type: str
    start_line: int
    end_line: int
    code: str
    callee_function: str
    call_line: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "file_path": self.file_path,
            "signature": self.signature,
            "return_type": self.return_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code,
            "call_line": self.call_line
        }


@dataclass
class FunctionCallAnalysis:
    function_name: str
    file_path: str
    signature: str
    return_type: str
    callees: List[FunctionDefinition]  # Functions called by this function (with definitions)
    callers: List[CallInfo]  # Functions that call this function (with definitions)


@dataclass
class FunctionCallAnalysisPairs:
    function_name: str
    before_analysis: FunctionCallAnalysis
    after_analysis: FunctionCallAnalysis

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "function_name": self.function_name,
            "before_fix": {
                "file_path": self.before_analysis.file_path,
                "signature": self.before_analysis.signature,
                "return_type": self.before_analysis.return_type,
                "callees": [callee.to_dict() for callee in self.before_analysis.callees],
                "callers": [caller.to_dict() for caller in self.before_analysis.callers]
            },
            "after_fix": {
                "file_path": self.after_analysis.file_path,
                "signature": self.after_analysis.signature,
                "return_type": self.after_analysis.return_type,
                "callees": [callee.to_dict() for callee in self.after_analysis.callees],
                "callers": [caller.to_dict() for caller in self.after_analysis.callers]
            }
        }

@dataclass
class CallAnalysisComparison:
    added_callees: List[FunctionDefinition]      # New functions called after fix
    removed_callees: List[FunctionDefinition]    # Functions no longer called after fix
    unchanged_callees: List[FunctionDefinition]  # Functions called both before and after
    added_callers: List[CallInfo]                # New callers after fix
    removed_callers: List[CallInfo]              # Callers removed after fix
    unchanged_callers: List[CallInfo]            # Callers present both before and after

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "added_callees": [callee.to_dict() for callee in self.added_callees],
            "removed_callees": [callee.to_dict() for callee in self.removed_callees],
            "unchanged_callees": [callee.to_dict() for callee in self.unchanged_callees],
            "added_callers": [caller.to_dict() for caller in self.added_callers],
            "removed_callers": [caller.to_dict() for caller in self.removed_callers],
            "unchanged_callers": [caller.to_dict() for caller in self.unchanged_callers]
        }

@dataclass
class FileChangeInfo:
    """Information about changes to a single file in a commit."""
    file_path: str
    language: str
    content_before: str
    content_after: str

@dataclass
class FunctionChangeInfo:
    """Information about a function in a specific state (before or after)."""
    name: str
    signature: str
    return_type: str
    start_line: int
    end_line: int
    code: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "signature": self.signature,
            "return_type": self.return_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code
        }

@dataclass
class FunctionChangeResult:
    """Result of analyzing a single function change."""
    repo_url: str
    commit_hash: str
    file_path: str
    language: str
    function_name: str
    function_before: FunctionChangeInfo
    function_after: FunctionChangeInfo
    diff_text: str
    diff_statistics: Dict[str, List[str]]
    call_analysis: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "repo_url": self.repo_url,
            "commit": self.commit_hash,
            "file_path": self.file_path,
            "language": self.language,
            "function": self.function_name,
            "before": self.function_before.code,
            "after": self.function_after.code,
            "diff": self.diff_text,
            "diff_stat": self.diff_statistics,
            "start_line_before": self.function_before.start_line,
            "end_line_before": self.function_before.end_line,
            "start_line_after": self.function_after.start_line,
            "end_line_after": self.function_after.end_line,
            **({"call_analysis": self.call_analysis} if self.call_analysis else {})
        }

class CommitChangeCollector:
    """Collects and processes file changes from a git commit."""

    def __init__(self, repository: Repo):
        self.repository = repository

    def collect_file_changes(self, commit_hash: str) -> Dict[str, FileChangeInfo]:
        """Collect all relevant file changes from the specified commit."""
        commit = self.repository.commit(commit_hash)
        if not commit.parents:
            raise ValueError("Commit has no parent; cannot compute diff")

        parent_commit = commit.parents[0]
        file_diffs = commit.diff(parent_commit, create_patch=False)

        file_changes: Dict[str, FileChangeInfo] = {}

        for diff_item in file_diffs:
            if diff_item.change_type not in {"M", "A", "D"}:
                continue

            file_path = self._get_file_path_from_diff(diff_item)
            language = get_file_language_type(file_path or "")

            if language is None:
                continue

            try:
                content_before, content_after = self._extract_file_contents(
                    diff_item, parent_commit, commit
                )

                file_changes[file_path] = FileChangeInfo(
                    file_path=file_path,
                    language=language,
                    content_before=content_before,
                    content_after=content_after
                )
            except Exception:
                # Skip binary files or files with decoding issues
                continue

        return file_changes

    def _get_file_path_from_diff(self, diff_item) -> str:
        """Extract file path from diff item based on change type."""
        return diff_item.b_path if diff_item.change_type != "D" else diff_item.a_path

    def _extract_file_contents(self, diff_item, parent_commit: Commit, commit: Commit) -> tuple[str, str]:
        """Extract before and after content for a file."""
        content_before = ""
        content_after = ""

        if diff_item.a_blob:
            content_before = (parent_commit.tree / diff_item.a_path).data_stream.read().decode("utf-8")

        if diff_item.b_blob:
            content_after = (commit.tree / diff_item.b_path).data_stream.read().decode("utf-8")

        return content_before, content_after


class FunctionCallAnalyzer:
    """Analyzes function calls before and after a fix commit."""

    def __init__(self, repo_path: str, commit_hash: str):
        self.repo =  Repo(repo_path)
        self.commit = self.repo.commit(commit_hash)

    def analyze_function_call_pairs(self, target_functions: List[str]) -> Dict[str, Tuple[FunctionCallAnalysisPairs, CallAnalysisComparison]]:
        """Analyze callees and callers for target functions before and after a fix commit."""
        if not self.commit.parents:
            raise ValueError("Fix commit has no parent; cannot compare before/after")

        parent_commit = self.commit.parents[0]

        # Analyze before (parent commit) and after (fix commit)
        print("Analyzing function calls before fix...")
        before_analysis = self.analyze_function_calls(target_functions, parent_commit.hexsha)

        print("Analyzing function calls after fix...")
        after_analysis = self.analyze_function_calls(target_functions)

        results = {}

        for func_name in target_functions:
            before_func = before_analysis.get(func_name)
            after_func = after_analysis.get(func_name)

            if before_func is None and after_func is None:
                continue  # Function not found in either commit

            # Handle cases where function exists in only one commit
            if before_func is None:
                before_func = FunctionCallAnalysis(
                    function_name=func_name,
                    file_path="",
                    signature="",
                    return_type="",
                    callees=[],
                    callers=[]
                )

            if after_func is None:
                after_func = FunctionCallAnalysis(
                    function_name=func_name,
                    file_path="",
                    signature="",
                    return_type="",
                    callees=[],
                    callers=[]
                )

            # Create combined analysis
            combined_analysis = FunctionCallAnalysisPairs(
                function_name=func_name,
                before_analysis=before_func,
                after_analysis=after_func
            )

            # Create comparison
            comparison = self.compare_call_analysis(before_func, after_func)

            results[func_name] = (combined_analysis, comparison)

        return results

    def analyze_function_calls(self, target_functions: List[str], commit_hash: str = None) -> Dict[str, FunctionCallAnalysis]:
        """Analyze callees and callers for target functions across the entire repository.
        Only includes functions that have definitions found in the repository.
        """
        # Use specific commit if provided, otherwise use current HEAD
        if commit_hash:
            tree = self.commit.tree
        else:
            tree = self.repo.head.commit.tree

        # Dictionary to store analysis results
        analysis_results: Dict[str, FunctionCallAnalysis] = {}

        # Dictionary to store all function definitions found in the repo
        all_function_definitions: Dict[str, FunctionDefinition] = {}  # function_name -> FunctionDefinition

        # First pass: collect all function definitions in the repository
        for item in tree.traverse():
            if item.type != 'blob':
                continue

            file_path = item.path
            language = get_file_language_type(file_path)
            if language is None:
                continue

            try:
                file_content = item.data_stream.read().decode("utf-8")
            except Exception:
                continue

            # Extract functions from this file
            functions = extract_functions(file_content, file_path)

            # Store all function definitions
            for func in functions:
                func_def = FunctionDefinition(
                    name=func.name,
                    file_path=file_path,
                    signature=func.signature,
                    return_type=func.return_type,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    code=func.code
                )
                all_function_definitions[func.name] = func_def

        # Initialize analysis for target functions that were found
        for func_name in target_functions:
            if func_name in all_function_definitions:
                func_def = all_function_definitions[func_name]
                analysis_results[func_name] = FunctionCallAnalysis(
                    function_name=func_name,
                    file_path=func_def.file_path,
                    signature=func_def.signature,
                    return_type=func_def.return_type,
                    callees=[],
                    callers=[]
                )

        # Second pass: analyze callees for target functions and find callers
        for item in tree.traverse():
            if item.type != 'blob':
                continue

            file_path = item.path
            language = get_file_language_type(file_path)
            if language is None:
                continue

            try:
                file_content = item.data_stream.read().decode("utf-8")
            except Exception:
                continue

            # Extract all functions from this file
            functions = extract_functions(file_content, file_path)

            for func in functions:
                # If this is a target function, analyze its callees
                if func.name in analysis_results:
                    calls = extract_function_calls(func.code, file_path)
                    # Only include callees that have definitions in the repo
                    for call in calls:
                        if call in all_function_definitions:
                            callee_def = all_function_definitions[call]
                            analysis_results[func.name].callees.append(callee_def)

                # Check if this function calls any of our target functions
                calls = extract_function_calls(func.code, file_path)
                for call in calls:
                    if call in analysis_results and func.name in all_function_definitions:
                        caller_def = all_function_definitions[func.name]
                        caller_info = CallInfo(
                            name=func.name,
                            file_path=caller_def.file_path,
                            signature=caller_def.signature,
                            return_type=caller_def.return_type,
                            start_line=caller_def.start_line,
                            end_line=caller_def.end_line,
                            code=caller_def.code,
                            callee_function=call,
                            call_line=func.start_line  # Approximate line number
                        )
                        analysis_results[call].callers.append(caller_info)

        return analysis_results


    def compare_call_analysis(self, before: FunctionCallAnalysis, after: FunctionCallAnalysis) -> CallAnalysisComparison:
        """Compare function call analysis before and after to identify changes."""

        # Compare callees
        before_callees = {func.name: func for func in before.callees}
        after_callees = {func.name: func for func in after.callees}

        added_callees = [after_callees[name] for name in after_callees.keys() - before_callees.keys()]
        removed_callees = [before_callees[name] for name in before_callees.keys() - after_callees.keys()]
        unchanged_callees = [after_callees[name] for name in before_callees.keys() & after_callees.keys()]

        # Compare callers
        before_callers = {func.name: func for func in before.callers}
        after_callers = {func.name: func for func in after.callers}

        added_callers = [after_callers[name] for name in after_callers.keys() - before_callers.keys()]
        removed_callers = [before_callers[name] for name in before_callers.keys() - after_callers.keys()]
        unchanged_callers = [after_callers[name] for name in before_callers.keys() & after_callers.keys()]

        return CallAnalysisComparison(
            added_callees=added_callees,
            removed_callees=removed_callees,
            unchanged_callees=unchanged_callees,
            added_callers=added_callers,
            removed_callers=removed_callers,
            unchanged_callers=unchanged_callers
        )

class CommitFunctionExtractor:
    """Main processor for extracting and analyzing changed functions from commits."""
    def __init__(self, repo_path: str, repo_url: str, commit_hash: str):
        self.repository = Repo(repo_path)
        self.repo_url = repo_url
        self.commit_hash = commit_hash
        self.analyzer = FunctionCallAnalyzer(repo_path, commit_hash)

    def extract_changed_functions(self, enable_call_analysis: bool = True) -> List[FunctionChangeResult]:
        """Extract all changed functions from the specified commit."""
        file_changes = self.collect_file_changes()
        function_changes = []

        for file_change in file_changes.values():
            if is_test_file(file_change.file_path):
                continue

            changed_functions = self._process_file_changes(file_change)
            function_changes.extend(changed_functions)

        if enable_call_analysis and function_changes:
            function_names = [change.function_name for change in function_changes]

            print("Analyzing function calls before and after fix commit...")
            call_analysis_data = self.analyzer.analyze_function_call_pairs(function_names)
            
            for function_change in function_changes:
                if function_change.function_name in call_analysis_data:
                    combined_analysis, comparison = call_analysis_data[function_change.function_name]
                    function_change.call_analysis = {
                        **combined_analysis.to_dict(),
                        "changes": comparison.to_dict()
                    }

        return function_changes
    

    def collect_file_changes(self) -> Dict[str, FileChangeInfo]:
        """Collect all relevant file changes from the specified commit."""
        commit = self.repository.commit(self.commit_hash)
        if not commit.parents:
            raise ValueError("Commit has no parent; cannot compute diff")

        parent_commit = commit.parents[0]
        file_diffs = commit.diff(parent_commit, create_patch=False)

        file_changes: Dict[str, FileChangeInfo] = {}

        for diff_item in file_diffs:
            if diff_item.change_type not in {"M", "A", "D"}:
                continue

            file_path = self._get_file_path_from_diff(diff_item)
            language = get_file_language_type(file_path or "")

            if language is None:
                continue

            try:
                content_before, content_after = self._extract_file_contents(
                    diff_item, parent_commit, commit
                )

                file_changes[file_path] = FileChangeInfo(
                    file_path=file_path,
                    language=language,
                    content_before=content_before,
                    content_after=content_after
                )
            except Exception:
                # Skip binary files or files with decoding issues
                continue

        return file_changes

    def _get_file_path_from_diff(self, diff_item) -> str:
        """Extract file path from diff item based on change type."""
        return diff_item.b_path if diff_item.change_type != "D" else diff_item.a_path

    def _extract_file_contents(self, diff_item, parent_commit: Commit, commit: Commit) -> tuple[str, str]:
        """Extract before and after content for a file."""
        content_before = ""
        content_after = ""

        if diff_item.a_blob:
            content_before = (parent_commit.tree / diff_item.a_path).data_stream.read().decode("utf-8")

        if diff_item.b_blob:
            content_after = (commit.tree / diff_item.b_path).data_stream.read().decode("utf-8")

        return content_before, content_after

    def _process_file_changes(self, file_change: FileChangeInfo) -> List[FunctionChangeResult]:
        """Process changes in a single file and extract modified functions."""
        functions_before = {func.name: func for func in extract_functions(file_change.content_before, file_change.language)}
        functions_after = {func.name: func for func in extract_functions(file_change.content_after, file_change.language)}

        changed_functions = []

        for function_name, function_after in functions_after.items():
            if function_name not in functions_before:
                continue  # Skip new functions

            function_before = functions_before[function_name]

            # TODO: Remove and replace with megavul filters in megavul/pipeline/extract_commit_diff_filter.py
            # if self._should_skip_function(function_before, function_after):
            #     continue

            diff_text, diff_stats = diff_lines(function_before.code, function_after.code)

            # TODO: Remove and replace with megavul filters in megavul/pipeline/extract_commit_diff_filter.py
            # if is_large_change(diff_stats):
            #     continue

            # Create FunctionChangeInfo objects for before and after states
            function_before_info = FunctionChangeInfo(
                name=function_before.name,
                signature=function_before.signature,
                return_type=function_before.return_type,
                start_line=function_before.start_line,
                end_line=function_before.end_line,
                code=function_before.code
            )

            function_after_info = FunctionChangeInfo(
                name=function_after.name,
                signature=function_after.signature,
                return_type=function_after.return_type,
                start_line=function_after.start_line,
                end_line=function_after.end_line,
                code=function_after.code
            )

            function_change = FunctionChangeResult(
                repo_url=self.repo_url,
                commit_hash=self.commit_hash,
                file_path=file_change.file_path,
                language=file_change.language,
                function_name=function_name,
                function_before=function_before_info,
                function_after=function_after_info,
                diff_text=diff_text,
                diff_statistics=diff_stats
            )

            changed_functions.append(function_change)

        return changed_functions

    # TODO: Remove and replace with megavul filters in megavul/pipeline/extract_commit_diff_filter.py
    # def _should_skip_function(self, function_before: FunctionInfo, function_after: FunctionInfo) -> bool:
    #     """Determine if a function should be skipped based on size filters."""
    #     return (is_large_function(function_before.code) or
    #             is_large_function(function_after.code))
