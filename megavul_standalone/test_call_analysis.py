#!/usr/bin/env python3
"""Test script for function call analysis functionality."""

import tempfile
import os
from pathlib import Path
from git import Repo

# Allow running as a module or as a script.
if __package__ in {None, ""}:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from megavul_standalone.utils.commit_analysis import analyze_function_calls, extract_function_calls, extract_functions
else:
    from .utils.commit_analysis import analyze_function_calls, extract_function_calls, extract_functions


def create_test_repo():
    """Create a temporary git repository with test C files."""
    temp_dir = tempfile.mkdtemp()
    repo = Repo.init(temp_dir)
    
    # Create test files
    main_c = """
#include <stdio.h>

void helper_function() {
    printf("Helper called\\n");
}

void target_function() {
    helper_function();
    another_function();
    printf("Target function\\n");
}

void name() {
    target_function();
    printf("Caller function\\n");
}

int main() {
    name();
    target_function();
    return 0;
}
"""

    utils_c = """
#include <stdio.h>

void another_function() {
    printf("Another function\\n");
}

void utility_function() {
    target_function();  // This should be found as a caller
}

void standalone_function() {
    printf("Standalone\\n");
}
"""

    # Write files
    main_path = Path(temp_dir) / "main.c"
    utils_path = Path(temp_dir) / "utils.c"
    
    with open(main_path, 'w') as f:
        f.write(main_c)
    with open(utils_path, 'w') as f:
        f.write(utils_c)
    
    # Add and commit files
    repo.index.add([str(main_path), str(utils_path)])
    repo.index.commit("Initial commit")
    
    return temp_dir, repo


def test_extract_function_calls():
    """Test the extract_function_calls function."""
    print("Testing extract_function_calls...")
    
    code = """
void test_function() {
    helper_function();
    another_function(1, 2);
    printf("Hello");
    some_lib_function();
}
"""
    
    calls = extract_function_calls(code, "test.c")
    print(f"Found calls: {calls}")
    
    expected_calls = {"helper_function", "another_function", "printf", "some_lib_function"}
    found_calls = set(calls)
    
    if expected_calls.issubset(found_calls):
        print("✓ extract_function_calls test passed")
    else:
        print(f"✗ extract_function_calls test failed. Expected {expected_calls}, got {found_calls}")


def test_extract_functions():
    """Test the extract_functions function."""
    print("\nTesting extract_functions...")
    
    code = """
void function_one() {
    printf("One");
}

int function_two(int x, int y) {
    return x + y;
}

static void helper() {
    // helper code
}
"""
    
    functions = extract_functions(code, "test.c")
    function_names = [f.name for f in functions]
    print(f"Found functions: {function_names}")
    
    expected_functions = {"function_one", "function_two", "helper"}
    found_functions = set(function_names)
    
    if expected_functions == found_functions:
        print("✓ extract_functions test passed")
    else:
        print(f"✗ extract_functions test failed. Expected {expected_functions}, got {found_functions}")


def test_analyze_function_calls():
    """Test the full repository analysis."""
    print("\nTesting analyze_function_calls...")
    
    temp_dir, repo = create_test_repo()
    
    try:
        # Analyze the target_function
        target_functions = ["target_function"]
        analysis = analyze_function_calls(temp_dir, target_functions)
        
        if "target_function" in analysis:
            result = analysis["target_function"]
            print(f"target_function analysis:")
            print(f"  File: {result.file_path}")
            print(f"  Callees: {[c.name for c in result.callees]}")
            print(f"  Callers: {[(c.name, c.file_path) for c in result.callers]}")

            # Check callees (only functions with definitions in repo)
            expected_callees = {"helper_function", "another_function"}  # printf is external, should be filtered out
            found_callees = {c.name for c in result.callees}

            if expected_callees.issubset(found_callees):
                print("✓ Callees analysis passed")
            else:
                print(f"✗ Callees analysis failed. Expected {expected_callees}, got {found_callees}")

            # Check callers
            names = {c.name for c in result.callers}
            expected_callers = {"name", "main", "utility_function"}

            if expected_callers.issubset(names):
                print("✓ Callers analysis passed")
            else:
                print(f"✗ Callers analysis failed. Expected {expected_callers}, got {names}")
        else:
            print("✗ target_function not found in analysis")
            
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)


def main():
    """Run all tests."""
    print("Running function call analysis tests...\n")
    
    test_extract_function_calls()
    test_extract_functions()
    test_analyze_function_calls()
    
    print("\nAll tests completed!")


if __name__ == "__main__":
    main()
