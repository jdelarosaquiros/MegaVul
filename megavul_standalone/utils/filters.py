"""Simple filters used by the standalone extractor."""
# TODO: Remove and replace with megavul filters in megavul/pipeline/extract_commit_diff_filter.py

from dataclasses import dataclass


@dataclass
class FunctionChange:
    file_path: str
    function_name: str
    before_code: str
    after_code: str
    diff_stat: dict


def is_test_file(file_path: str) -> bool:
    lower = file_path.lower()
    return "test" in lower or "unittest" in lower


def is_large_function(func_code: str, max_lines: int = 800) -> bool:
    return len(func_code.splitlines()) > max_lines


def is_large_change(diff_stat: dict, max_changed: int = 200) -> bool:
    return (len(diff_stat.get("added_lines", [])) + len(diff_stat.get("deleted_lines", []))) > max_changed
