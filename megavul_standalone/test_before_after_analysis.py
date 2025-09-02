#!/usr/bin/env python3
"""Test script for before/after function call analysis functionality."""

import tempfile
import os
from pathlib import Path
from git import Repo

# Allow running as a module or as a script.
if __package__ in {None, ""}:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from megavul_standalone.utils.commit_analysis import analyze_function_call_pairs
else:
    from .utils.commit_analysis import analyze_function_call_pairs


def create_test_repo_with_fix():
    """Create a temporary git repository with a vulnerability fix."""
    temp_dir = tempfile.mkdtemp()
    repo = Repo.init(temp_dir)
    
    # Initial vulnerable code
    vulnerable_c_before = """
#include <stdio.h>
#include <string.h>

void dangerous_function(char* input) {
    strcpy(buffer, input);  // Vulnerable strcpy
}

void vulnerable_function(char* input) {
    dangerous_function(input);  // Calls dangerous function
    printf("Processing: %s\\n", input);
}

void caller_function() {
    char input[100];
    gets(input);  // Another vulnerability
    vulnerable_function(input);
}

int main() {
    caller_function();
    return 0;
}
"""

    # Fixed code - removes dangerous calls and adds safe alternatives
    vulnerable_c_after = """
#include <stdio.h>
#include <string.h>

void safe_function(char* input, size_t max_len) {
    strncpy(buffer, input, max_len - 1);  // Safe strncpy
    buffer[max_len - 1] = '\\0';
}

void vulnerable_function(char* input) {
    safe_function(input, sizeof(buffer));  // Calls safe function instead
    printf("Processing: %s\\n", input);
}

void caller_function() {
    char input[100];
    fgets(input, sizeof(input), stdin);  // Safe fgets instead of gets
    vulnerable_function(input);
}

int main() {
    caller_function();
    return 0;
}
"""

    # Write initial vulnerable version
    main_path = Path(temp_dir) / "vulnerable.c"
    with open(main_path, 'w') as f:
        f.write(vulnerable_c_before)
    
    # Add and commit initial version
    repo.index.add([str(main_path)])
    initial_commit = repo.index.commit("Initial vulnerable version")
    
    # Write fixed version
    with open(main_path, 'w') as f:
        f.write(vulnerable_c_after)
    
    # Add and commit fix
    repo.index.add([str(main_path)])
    fix_commit = repo.index.commit("Fix vulnerabilities")
    
    return temp_dir, repo, initial_commit.hexsha, fix_commit.hexsha


def test_before_after_analysis():
    """Test the before/after analysis functionality."""
    print("Testing before/after function call analysis...")
    
    temp_dir, repo, initial_commit, fix_commit = create_test_repo_with_fix()
    
    try:
        # Analyze the vulnerable_function before and after the fix
        target_functions = ["vulnerable_function"]
        analysis = analyze_function_call_pairs(temp_dir, target_functions, fix_commit)
        
        if "vulnerable_function" in analysis:
            combined_analysis, comparison = analysis["vulnerable_function"]
            
            print(f"vulnerable_function before/after analysis:")
            print(f"  Before fix callees: {[c.name for c in combined_analysis.callees_before]}")
            print(f"  After fix callees: {[c.name for c in combined_analysis.callees_after]}")
            print(f"  Before fix callers: {[c.name for c in combined_analysis.callers_before]}")
            print(f"  After fix callers: {[c.name for c in combined_analysis.callers_after]}")
            
            print(f"  Changes:")
            print(f"    Added callees: {[c.name for c in comparison.added_callees]}")
            print(f"    Removed callees: {[c.name for c in comparison.removed_callees]}")
            print(f"    Added callers: {[c.name for c in comparison.added_callers]}")
            print(f"    Removed callers: {[c.name for c in comparison.removed_callers]}")
            
            # Check expected changes
            before_callees = {c.name for c in combined_analysis.callees_before}
            after_callees = {c.name for c in combined_analysis.callees_after}
            added_callees = {c.name for c in comparison.added_callees}
            removed_callees = {c.name for c in comparison.removed_callees}
            
            # Expected: dangerous_function should be removed, safe_function should be added
            if "dangerous_function" in removed_callees and "safe_function" in added_callees:
                print("✓ Before/after analysis correctly detected function call changes")
            else:
                print(f"✗ Before/after analysis failed. Expected dangerous_function removed and safe_function added")
                print(f"  Removed: {removed_callees}, Added: {added_callees}")
            
            # Check that printf is still called in both (unchanged)
            unchanged_callees = {c.name for c in comparison.unchanged_callees}
            if "printf" in unchanged_callees:
                print("✓ Correctly identified unchanged callees")
            else:
                print(f"✗ Failed to identify unchanged callees. Found: {unchanged_callees}")
                
        else:
            print("✗ vulnerable_function not found in before/after analysis")
            
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)


def main():
    """Run the before/after analysis test."""
    print("Running before/after function call analysis test...\n")
    
    test_before_after_analysis()
    
    print("\nBefore/after analysis test completed!")


if __name__ == "__main__":
    main()
