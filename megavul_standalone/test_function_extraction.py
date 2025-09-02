#!/usr/bin/env python3
"""Test script for extract_functions utility."""

import argparse
from pathlib import Path
import sys

# Add the megavul_standalone directory to path
sys.path.append(str(Path(__file__).parent / "megavul_standalone"))

from megavul_standalone.utils.commit_analysis import extract_functions, language_from_path


def test_extract_functions(file_path: str):
    """Test extract_functions on a given file."""
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: File {file_path} does not exist")
        return
    
    # Determine language from file extension
    language = language_from_path(str(path))
    if not language:
        print(f"Error: Could not determine language for {file_path}")
        return
    
    print(f"File: {file_path}")
    print(f"Language: {language}")
    print("-" * 50)
    
    try:
        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Extract functions
        functions = extract_functions(code)
        
        print(f"Found {len(functions)} functions:")
        print()
        
        for i, func in enumerate(functions, 1):
            print(f"{i}. Function: {func.name}")
            print(f"   Return type: {func.return_type}")
            print(f"   Signature: {func.signature}")
            print(f"   Lines: {func.start_line}-{func.end_line}")
            print(f"   Code preview: {func.code[:100]}...")
            print()
            
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Test extract_functions on a file")
    parser.add_argument("file_path", help="Path to the source file to analyze")
    args = parser.parse_args()
    
    test_extract_functions(args.file_path)


if __name__ == "__main__":
    main()