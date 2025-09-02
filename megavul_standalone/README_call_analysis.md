# Function Call Analysis

This extension to the MegaVul function extraction tool adds the ability to analyze callees and callers of extracted functions across the entire repository.

## Features

- **Callees Analysis**: Find all functions called by the target functions (only those with definitions in the repo)
- **Callers Analysis**: Find all functions that call the target functions (only those with definitions in the repo)
- **Complete Function Code**: Includes the full source code of both callees and callers
- **Before/After Comparison**: Compare function call relationships before and after a fix commit
- **Change Detection**: Identify added, removed, and unchanged callees/callers
- **Cross-file Analysis**: Search across all files in the repository to find relationships
- **Multiple Language Support**: Supports C, C++, and Java (same as the base extraction tool)
- **External Dependency Filtering**: Excludes standard library functions and external dependencies that don't have definitions in the repository

## New Files Added

1. **Enhanced `utils.py`**: Added new data structures and functions:
   - `CallInfo`: Information about a function call site
   - `FunctionCallAnalysis`: Complete analysis of a function's callees and callers
   - `extract_function_calls()`: Extract function calls from code using tree-sitter
   - `analyze_function_calls()`: Analyze callees/callers across entire repository

2. **Enhanced `extract_commit_functions.py`**: Added `--analyze-calls` option to include call analysis in the main extraction workflow

3. **`analyze_function_calls.py`**: Standalone script for analyzing function calls with multiple input options

4. **`test_call_analysis.py`**: Test script to verify functionality

## Usage

### Option 1: Include call analysis in main extraction

```bash
python extract_commit_functions.py \
    https://github.com/example/repo \
    abc123def456 \
    /path/to/local/repo \
    --analyze-calls \
    --output functions_with_calls.jsonl
```

This will create two files:
- `functions_with_calls.jsonl`: Original extraction results
- `functions_with_calls_with_calls.jsonl`: Results enhanced with call analysis

### Option 1b: Include before/after call analysis in main extraction

```bash
python extract_commit_functions.py \
    https://github.com/example/repo \
    abc123def456 \
    /path/to/local/repo \
    --analyze-calls \
    --compare-before-after \
    --output functions_with_comparison.jsonl
```

This will create two files:
- `functions_with_comparison.jsonl`: Original extraction results
- `functions_with_comparison_with_call_comparison.jsonl`: Results with before/after call analysis

### Option 2: Analyze specific functions

```bash
python analyze_function_calls.py \
    /path/to/repo \
    --functions vulnerable_function helper_function \
    --output call_analysis.jsonl
```

### Option 3: Analyze functions from previous extraction

```bash
python analyze_function_calls.py \
    /path/to/repo \
    --from-jsonl extracted_functions.jsonl \
    --output call_analysis.jsonl
```

### Option 4: Analyze all functions in specific files

```bash
python analyze_function_calls.py \
    /path/to/repo \
    --from-files src/vulnerable.c src/helper.c \
    --output call_analysis.jsonl
```

### Option 5: Compare function calls before and after fix

```bash
python analyze_function_calls.py \
    /path/to/repo \
    --functions vulnerable_function \
    --fix-commit abc123def456 \
    --compare-before-after \
    --output call_comparison.jsonl
```

### Option 6: Compare calls from previous extraction before/after fix

```bash
python analyze_function_calls.py \
    /path/to/repo \
    --from-jsonl extracted_functions.jsonl \
    --fix-commit abc123def456 \
    --compare-before-after \
    --output call_comparison.jsonl
```

## Output Format

The enhanced output includes:

```json
{
  "repo_url": "https://github.com/example/repo",
  "commit": "abc123def456",
  "file_path": "src/vulnerable.c",
  "language": "c",
  "function": "vulnerable_function",
  "before": "// function code before",
  "after": "// function code after",
  "diff": "// unified diff",
  "callees": [
    {
      "name": "helper_function",
      "file_path": "src/helper.c",
      "signature": "(int x, char* str)",
      "return_type": "void",
      "start_line": 15,
      "end_line": 25,
      "code": "void helper_function(int x, char* str) {\n    printf(\"Helper: %d, %s\\n\", x, str);\n    // more implementation\n}"
    }
  ],
  "callers": [
    {
      "name": "main",
      "file_path": "src/main.c",
      "signature": "(int argc, char** argv)",
      "return_type": "int",
      "start_line": 35,
      "end_line": 50,
      "code": "int main(int argc, char** argv) {\n    // initialization\n    vulnerable_function();\n    return 0;\n}",
      "call_line": 42
    },
    {
      "name": "process_input",
      "file_path": "src/input.c",
      "signature": "(char* input)",
      "return_type": "int",
      "start_line": 150,
      "end_line": 170,
      "code": "int process_input(char* input) {\n    // validation\n    vulnerable_function();\n    return 1;\n}",
      "call_line": 156
    }
  ]
}
```

**Note**: Only functions with definitions found in the repository are included. External dependencies like `malloc`, `strcpy`, `printf` are automatically filtered out.

### Before/After Comparison Output

When using `--compare-before-after`, the output includes detailed comparison:

```json
{
  "repo_url": "https://github.com/example/repo",
  "commit": "fix_commit_hash",
  "parent_commit": "parent_commit_hash",
  "file_path": "src/vulnerable.c",
  "language": "c",
  "function": "vulnerable_function",
  "before": "// function code before fix",
  "after": "// function code after fix",
  "diff": "// unified diff",

  "call_analysis": {
    "before_fix": {
      "file_path": "src/vulnerable.c",
      "signature": "(char* input)",
      "return_type": "int",
      "callees": [...],
      "callers": [...]
    },
    "after_fix": {
      "file_path": "src/vulnerable.c",
      "signature": "(char* input)",
      "return_type": "int",
      "callees": [...],
      "callers": [...]
    },
    "changes": {
      "added_callees": [...],      // Functions newly called after fix
      "removed_callees": [...],    // Functions no longer called after fix
      "unchanged_callees": [...],  // Functions called both before and after
      "added_callers": [...],      // New callers after fix
      "removed_callers": [...],    // Callers removed after fix
      "unchanged_callers": [...]   // Callers present both before and after
    }
  }
}
```

## Implementation Details

### Tree-sitter Parsing

The call analysis uses tree-sitter to parse code and identify:
- **C/C++**: `call_expression` nodes
- **Java**: `method_invocation` nodes

### Cross-file Analysis

The tool performs a two-pass analysis:
1. **First pass**: Extract all functions from all files and identify callees for target functions
2. **Second pass**: Search all functions to find callers of target functions

### Performance Considerations

- Call analysis can be slow for large repositories as it needs to parse all source files
- Use the `--analyze-calls` flag selectively
- Consider analyzing only specific functions rather than all extracted functions

## Example Workflow

1. Extract vulnerable functions from a commit:
```bash
python extract_commit_functions.py \
    https://github.com/example/vuln-repo \
    fix-commit-hash \
    /path/to/repo \
    --output vuln_functions.jsonl
```

2. Analyze their call relationships:
```bash
python analyze_function_calls.py \
    /path/to/repo \
    --from-jsonl vuln_functions.jsonl \
    --commit fix-commit-hash \
    --output vuln_call_analysis.jsonl
```

3. The output will show:
   - What functions the vulnerable functions call (potential attack vectors)
   - What functions call the vulnerable functions (entry points)
   - Cross-file relationships that might not be obvious

## Testing

Run the test suite to verify functionality:

```bash
python test_call_analysis.py
```

This creates a temporary git repository with test C files and verifies that:
- Function calls are correctly extracted
- Function definitions are correctly identified  
- Callees and callers are correctly found across files
