from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple

from tree_sitter import Parser, Node
from tree_sitter_languages import get_language


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


def extract_functions(code: str, language: str) -> List[FunctionInfo]:
    """Extract function definitions from code for given language."""
    parser = Parser()
    parser.set_language(get_language(language))
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


def save_jsonl(data: List[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
