from typing import List, Dict, Tuple, Optional
from git import Repo, Commit
from pathlib import Path
from tree_sitter import Parser, Node, Language
import difflib
from dataclasses import dataclass, asdict
import json

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

LANGUAGE_EXT = {
    "c": {"c"},
    "cpp": {"cc", "cpp", "cxx", "hpp", "hh", "hxx"},
    "java": {"java"},
}


def diff_lines(before: str, after: str) -> Tuple[str, Dict[str, List[str]]]:
    """Compute unified diff and return diff text and added/deleted lines."""

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


def extract_functions(code: str, file_path: str = None) -> List[FunctionInfo]:
    """Extract function definitions from code for given language."""
    # Determine language from file path or default to C
    language = "c"
    if file_path:
        detected_lang = get_file_language_type(file_path)
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
        detected_lang = get_file_language_type(file_path)
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


def get_file_language_type(path: str) -> str | None:
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
