from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Set

from tree_sitter import Parser, Node, Language
from git import Repo
# Remove this line:
# from tree_sitter_languages import get_language


def diff_lines(before: str, after: str) -> Tuple[str, Dict[str, List[str]]]:
    """Compute unified diff and return diff text and added/deleted lines."""
    import difflib

    before_lines = before.splitlines()
    after_lines = after.splitlines()
    diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
    added = []
    deleted = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            deleted.append(line[1:])
    return "\n".join(diff), {"added_lines": added, "deleted_lines": deleted}


@dataclass
class FunctionInfo:
    name: str
    signature: str
    return_type: str
    code: str
    start_line: int
    end_line: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class FunctionDefinition:
    name: str
    file_path: str
    signature: str
    return_type: str
    start_line: int
    end_line: int
    code: str


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


@dataclass
class FunctionCallAnalysis:
    function_name: str
    file_path: str
    signature: str
    return_type: str
    callees: List[FunctionDefinition]  # Functions called by this function (with definitions)
    callers: List[CallInfo]  # Functions that call this function (with definitions)


@dataclass
class FunctionCallAnalysisBeforeAfter:
    function_name: str
    file_path_before: str
    file_path_after: str
    signature_before: str
    signature_after: str
    return_type_before: str
    return_type_after: str
    callees_before: List[FunctionDefinition]
    callees_after: List[FunctionDefinition]
    callers_before: List[CallInfo]
    callers_after: List[CallInfo]


@dataclass
class CallAnalysisComparison:
    added_callees: List[FunctionDefinition]      # New functions called after fix
    removed_callees: List[FunctionDefinition]    # Functions no longer called after fix
    unchanged_callees: List[FunctionDefinition]  # Functions called both before and after
    added_callers: List[CallInfo]                # New callers after fix
    removed_callers: List[CallInfo]              # Callers removed after fix
    unchanged_callers: List[CallInfo]            # Callers present both before and after


LANGUAGE_EXT = {
    "c": {"c"},
    "cpp": {"cc", "cpp", "cxx", "hpp", "hh", "hxx"},
    "java": {"java"},
}


def language_from_path(path: str) -> str | None:
    ext = path.split(".")[-1].lower()
    for lang, exts in LANGUAGE_EXT.items():
        if ext in exts:
            return lang
    return None


def _search_identifier(node: Node, source: bytes) -> str | None:
    if node.type == "identifier":
        return source[node.start_byte:node.end_byte].decode("utf-8")
    for child in node.children:
        result = _search_identifier(child, source)
        if result:
            return result
    return None


def extract_functions(code: str, file_path: str = None) -> List[FunctionInfo]:
    """Extract function definitions from code for given language."""
    # Determine language from file path or default to C
    language = "c"
    if file_path:
        detected_lang = language_from_path(file_path)
        if detected_lang:
            language = detected_lang
    
    # Use appropriate tree-sitter language
    if language == "c":
        from tree_sitter_c import language as c_language
        ts_language = Language(c_language())
    elif language == "cpp":
        from tree_sitter_cpp import language as cpp_language
        ts_language = Language(cpp_language())
    else:
        # Default to C
        from tree_sitter_c import language as c_language
        ts_language = Language(c_language())
        language = "c"
    
    parser = Parser(ts_language)

    tree = parser.parse(bytes(code, "utf-8"))
    root = tree.root_node
    functions: List[FunctionInfo] = []
    source_bytes = bytes(code, "utf-8")

    def traverse(node: Node):
        if language in {"c", "cpp"} and node.type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            name = _search_identifier(declarator, source_bytes) if declarator else None
            params_node = None
            if declarator is not None:
                params_node = declarator.child_by_field_name("parameters") or declarator.child_by_field_name("parameter_list")
            signature = source_bytes[params_node.start_byte:params_node.end_byte].decode("utf-8") if params_node else ""
            ret_node = node.child_by_field_name("type")
            return_type = source_bytes[ret_node.start_byte:ret_node.end_byte].decode("utf-8") if ret_node else ""
            func_code = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
            functions.append(FunctionInfo(name or "", signature, return_type,
                                          func_code, node.start_point[0] + 1, node.end_point[0] + 1))
        elif language == "java" and node.type == "method_declaration":
            name = _search_identifier(node.child_by_field_name("name"), source_bytes) or ""
            params_node = node.child_by_field_name("parameters")
            signature = source_bytes[params_node.start_byte:params_node.end_byte].decode("utf-8") if params_node else ""
            ret_node = node.child_by_field_name("type")
            return_type = source_bytes[ret_node.start_byte:ret_node.end_byte].decode("utf-8") if ret_node else ""
            func_code = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
            functions.append(FunctionInfo(name, signature, return_type,
                                          func_code, node.start_point[0] + 1, node.end_point[0] + 1))
        for child in node.children:
            traverse(child)

    traverse(root)
    return functions


def extract_function_calls(code: str, file_path: str = None) -> List[str]:
    """Extract function call names from code for given language."""
    # Determine language from file path or default to C
    language = "c"
    if file_path:
        detected_lang = language_from_path(file_path)
        if detected_lang:
            language = detected_lang

    # Use appropriate tree-sitter language
    if language == "c":
        from tree_sitter_c import language as c_language
        ts_language = Language(c_language())
    elif language == "cpp":
        from tree_sitter_cpp import language as cpp_language
        ts_language = Language(cpp_language())
    else:
        # Default to C
        from tree_sitter_c import language as c_language
        ts_language = Language(c_language())
        language = "c"

    parser = Parser(ts_language)
    tree = parser.parse(bytes(code, "utf-8"))
    root = tree.root_node
    calls: List[str] = []
    source_bytes = bytes(code, "utf-8")

    def traverse(node: Node):
        if language in {"c", "cpp"} and node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            if function_node:
                call_name = _search_identifier(function_node, source_bytes)
                if call_name:
                    calls.append(call_name)
        elif language == "java" and node.type == "method_invocation":
            name_node = node.child_by_field_name("name")
            if name_node:
                call_name = _search_identifier(name_node, source_bytes)
                if call_name:
                    calls.append(call_name)

        for child in node.children:
            traverse(child)

    traverse(root)
    return list(set(calls))  # Remove duplicates


def analyze_function_calls_in_repo(repo_path: str, target_functions: List[str], commit_hash: str = None) -> Dict[str, FunctionCallAnalysis]:
    """Analyze callees and callers for target functions across the entire repository.
    Only includes functions that have definitions found in the repository.
    """
    from git import Repo

    repo = Repo(repo_path)

    # Use specific commit if provided, otherwise use current HEAD
    if commit_hash:
        commit = repo.commit(commit_hash)
        tree = commit.tree
    else:
        tree = repo.head.commit.tree

    # Dictionary to store analysis results
    analysis_results: Dict[str, FunctionCallAnalysis] = {}

    # Dictionary to store all function definitions found in the repo
    all_function_definitions: Dict[str, FunctionDefinition] = {}  # function_name -> FunctionDefinition

    # First pass: collect all function definitions in the repository
    for item in tree.traverse():
        if item.type != 'blob':
            continue

        file_path = item.path
        language = language_from_path(file_path)
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
        language = language_from_path(file_path)
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


def compare_call_analysis(before: FunctionCallAnalysis, after: FunctionCallAnalysis) -> CallAnalysisComparison:
    """Compare function call analysis before and after to identify changes."""

    # Compare callees
    before_callees = {f.name: f for f in before.callees}
    after_callees = {f.name: f for f in after.callees}

    added_callees = [after_callees[name] for name in after_callees.keys() - before_callees.keys()]
    removed_callees = [before_callees[name] for name in before_callees.keys() - after_callees.keys()]
    unchanged_callees = [after_callees[name] for name in before_callees.keys() & after_callees.keys()]

    # Compare callers
    before_callers = {f.name: f for f in before.callers}
    after_callers = {f.name: f for f in after.callers}

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


def analyze_function_calls_before_after(repo_path: str, target_functions: List[str], fix_commit_hash: str) -> Dict[str, Tuple[FunctionCallAnalysisBeforeAfter, CallAnalysisComparison]]:
    """Analyze callees and callers for target functions before and after a fix commit."""
    from git import Repo

    repo = Repo(repo_path)
    fix_commit = repo.commit(fix_commit_hash)

    if not fix_commit.parents:
        raise ValueError("Fix commit has no parent; cannot compare before/after")

    parent_commit = fix_commit.parents[0]

    # Analyze before (parent commit) and after (fix commit)
    print("Analyzing function calls before fix...")
    before_analysis = analyze_function_calls_in_repo(repo_path, target_functions, parent_commit.hexsha)

    print("Analyzing function calls after fix...")
    after_analysis = analyze_function_calls_in_repo(repo_path, target_functions, fix_commit_hash)

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
        combined_analysis = FunctionCallAnalysisBeforeAfter(
            function_name=func_name,
            file_path_before=before_func.file_path,
            file_path_after=after_func.file_path,
            signature_before=before_func.signature,
            signature_after=after_func.signature,
            return_type_before=before_func.return_type,
            return_type_after=after_func.return_type,
            callees_before=before_func.callees,
            callees_after=after_func.callees,
            callers_before=before_func.callers,
            callers_after=after_func.callers
        )

        # Create comparison
        comparison = compare_call_analysis(before_func, after_func)

        results[func_name] = (combined_analysis, comparison)

    return results


def save_jsonl(data: List[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
