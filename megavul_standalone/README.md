# Extract Commit Functions

A standalone utility to extract changed functions from a specific commit in a Git repository. This script analyzes the differences between a commit and its parent, identifies modified functions using tree-sitter parsing, and outputs detailed information about the changes in JSONL format.

## Features

- **Function-level Analysis**: Extracts only the functions that were modified in a commit
- **Multi-language Support**: Supports C, C++, and Java through tree-sitter parsers
- **Call Analysis**: Optional analysis of function callees and callers (may be slow for large repositories)
- **Detailed Output**: Provides before/after code, diff statistics, and metadata for each changed function
- **JSONL Format**: Outputs results in JSON Lines format for easy processing

## Prerequisites

- Python 3.11+
- Git repository with the target commit
- Required Python packages (see `requirements.txt`)
- Tree-sitter parsers for supported languages

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure tree-sitter parsers are available in the `tree-sitter/` directory

## Usage

### Basic Usage

```bash
python extract_commit_functions.py <repo_url> <commit_hash> <repo_path>
```

### Parameters

- `repo_url`: URL of the repository (used for record-keeping only)
- `commit_hash`: The commit ID to analyze
- `repo_path`: Path to the local Git repository
- `--output`: Output JSONL file path (default: `extracted_functions.jsonl`)
- `--analyze-calls`: Enable call analysis for extracted functions (default: True, may be slow)

### Examples

```bash
# Basic extraction
python extract_commit_functions.py \
    https://github.com/example/repo \
    abc123def456 \
    /path/to/local/repo

# Custom output file
python extract_commit_functions.py \
    https://github.com/example/repo \
    abc123def456 \
    /path/to/local/repo \
    --output my_functions.jsonl

# Disable call analysis for faster processing
python extract_commit_functions.py \
    https://github.com/example/repo \
    abc123def456 \
    /path/to/local/repo \
    --analyze-calls false
```

## Output Format

The script outputs a JSONL file where each line contains a JSON object representing a changed function with the following fields:

### Core Fields
- `repo_url`: Repository URL
- `commit`: Commit hash
- `file_path`: Path to the file containing the function
- `language`: Programming language (c, cpp, java)
- `function`: Function name
- `before`: Function code before the commit
- `after`: Function code after the commit
- `diff`: Unified diff of the function changes
- `diff_stat`: Statistics about the changes (lines added/removed)
- `start_line_before`/`end_line_before`: Line numbers in the original file
- `start_line_after`/`end_line_after`: Line numbers in the modified file

### Call Analysis Fields (when enabled)
- `call_analysis`: Object containing:
  - `before_fix`: Callees and callers before the commit
  - `after_fix`: Callees and callers after the commit

### Example Output

```json
{
  "repo_url": "https://github.com/example/repo",
  "commit": "abc123def456",
  "file_path": "src/main.c",
  "language": "c",
  "function": "vulnerable_function",
  "before": "int vulnerable_function(char *input) {\n    strcpy(buffer, input);\n    return 0;\n}",
  "after": "int vulnerable_function(char *input) {\n    strncpy(buffer, input, sizeof(buffer)-1);\n    return 0;\n}",
  "diff": "@@ -1,3 +1,3 @@\n int vulnerable_function(char *input) {\n-    strcpy(buffer, input);\n+    strncpy(buffer, input, sizeof(buffer)-1);\n     return 0;\n }",
  "diff_stat": {"lines_added": 1, "lines_removed": 1},
  "start_line_before": 10,
  "end_line_before": 13,
  "start_line_after": 10,
  "end_line_after": 13
}
```

## How It Works

1. **Repository Analysis**: The script analyzes the specified commit and its parent to identify changed files
2. **Language Detection**: Uses file extensions and patterns to determine programming language
3. **Function Extraction**: Employs tree-sitter parsers to extract function definitions from both versions
4. **Change Detection**: Compares functions by name to identify modifications
5. **Diff Generation**: Creates unified diffs and statistics for changed functions
6. **Call Analysis** (optional): Analyzes function calls and dependencies across the repository
7. **Output Generation**: Serializes results to JSONL format

## Supported Languages

- **C**: `.c`, `.h` files
- **C++**: `.cpp`, `.cxx`, `.cc`, `.hpp`, `.hxx` files  
- **Java**: `.java` files

## Performance Considerations

- **Call Analysis**: The `--analyze-calls` option can be slow for large repositories as it requires parsing the entire codebase
- **Repository Size**: Processing time scales with repository size and number of changed functions
- **Memory Usage**: Large repositories may require significant memory for call analysis

## Limitations

- Only analyzes functions that exist in both the commit and its parent (skips new functions)
- Requires the repository to be available locally
- Test files are automatically filtered out
- Binary files and files with encoding issues are skipped

## Related Tools

This script is part of the MegaVul project. For more comprehensive vulnerability analysis, see:
- `analyze_function_calls.py`: Standalone call analysis tool
- Main MegaVul pipeline: Full dataset generation pipeline

## License

This tool is part of MegaVul and is licensed under GPL 3.0.
