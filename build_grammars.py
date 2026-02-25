#!/usr/bin/env python3
"""
Build tree-sitter grammars for Java and TypeScript.
This script downloads and compiles tree-sitter language grammars into a shared library.
"""

import os
import sys
import subprocess
from pathlib import Path

try:
    from tree_sitter import Language
except ImportError:
    print("Error: tree-sitter package not found. Please install it with: pip install tree-sitter")
    sys.exit(1)


def clone_grammar(language: str, repo_url: str, build_dir: Path) -> Path:
    """Clone a tree-sitter grammar repository if it doesn't exist."""
    repo_dir = build_dir / f"tree-sitter-{language}"
    
    if repo_dir.exists():
        print(f"Grammar repository for {language} already exists at {repo_dir}")
        return repo_dir
    
    print(f"Cloning {language} grammar from {repo_url}...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Successfully cloned {language} grammar")
    except subprocess.CalledProcessError as e:
        print(f"Error cloning {language} grammar: {e.stderr}")
        raise
    
    return repo_dir


def build_library(grammars: dict, build_dir: Path, output_path: Path):
    """Build shared library containing all grammars."""
    print(f"\nBuilding shared library at {output_path}...")
    
    # Prepare grammar paths
    grammar_paths = []
    for language, repo_dir in grammars.items():
        # For TypeScript, we need the typescript/typescript subdirectory
        if language == "typescript":
            grammar_path = repo_dir / "typescript"
        else:
            grammar_path = repo_dir
        
        if not grammar_path.exists():
            raise FileNotFoundError(f"Grammar path not found: {grammar_path}")
        
        grammar_paths.append(str(grammar_path))
        print(f"  - Including {language} from {grammar_path}")
    
    try:
        # Build the shared library with all grammars
        Language.build_library(
            str(output_path),
            grammar_paths
        )
        print(f"\nSuccessfully built shared library: {output_path}")
        
        # Verify the library was created
        if not output_path.exists():
            raise FileNotFoundError(f"Library file was not created: {output_path}")
        
        # Get file size for confirmation
        size_kb = output_path.stat().st_size / 1024
        print(f"Library size: {size_kb:.2f} KB")
        
    except Exception as e:
        print(f"Error building shared library: {e}")
        raise


def main():
    """Build all required grammars and compile them into a shared library."""
    print("=" * 60)
    print("Tree-sitter Grammar Builder")
    print("=" * 60)
    
    # Create build directory
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    print(f"\nUsing build directory: {build_dir.absolute()}")
    
    # Define grammars to build
    grammar_repos = {
        "java": "https://github.com/tree-sitter/tree-sitter-java",
        "typescript": "https://github.com/tree-sitter/tree-sitter-typescript",
    }
    
    # Clone all grammar repositories
    print("\n" + "-" * 60)
    print("Step 1: Cloning grammar repositories")
    print("-" * 60)
    
    cloned_grammars = {}
    for language, repo_url in grammar_repos.items():
        try:
            repo_dir = clone_grammar(language, repo_url, build_dir)
            cloned_grammars[language] = repo_dir
        except Exception as e:
            print(f"Failed to clone {language} grammar: {e}")
            sys.exit(1)
    
    # Build shared library
    print("\n" + "-" * 60)
    print("Step 2: Building shared library")
    print("-" * 60)
    
    # Determine output file extension based on platform
    if sys.platform == "darwin":
        lib_extension = "dylib"
    elif sys.platform == "win32":
        lib_extension = "dll"
    else:  # Linux and other Unix-like systems
        lib_extension = "so"
    
    output_path = build_dir / f"languages.{lib_extension}"
    
    try:
        build_library(cloned_grammars, build_dir, output_path)
    except Exception as e:
        print(f"Failed to build shared library: {e}")
        sys.exit(1)
    
    # Success summary
    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print("=" * 60)
    print(f"\nShared library location: {output_path.absolute()}")
    print(f"Supported languages: {', '.join(cloned_grammars.keys())}")
    print("\nYou can now use the grammars in your application:")
    print(f"  Language('{output_path}', 'java')")
    print(f"  Language('{output_path}', 'typescript')")
    print()


if __name__ == "__main__":
    main()
