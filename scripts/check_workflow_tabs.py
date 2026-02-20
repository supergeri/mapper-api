#!/usr/bin/env python3
"""
Check GitHub Actions workflow YAML files for tab characters.
Tabs in YAML cause parsing failures in GitHub Actions.
"""

import sys
from pathlib import Path


def check_workflow_for_tabs(workflow_path: Path) -> list[str]:
    """Check a single workflow file for tab characters."""
    errors = []
    try:
        content = workflow_path.read_bytes()
        if b'\t' in content:
            # Find line numbers with tabs
            lines = content.split(b'\n')
            for line_num, line in enumerate(lines, start=1):
                if b'\t' in line:
                    errors.append(f"  Line {line_num}: contains tab character")
    except Exception as e:
        errors.append(f"  Error reading file: {e}")
    return errors


def main():
    workflows_dir = Path(".github/workflows")
    
    if not workflows_dir.exists():
        print("ERROR: .github/workflows directory not found")
        sys.exit(1)
    
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    
    if not workflow_files:
        print("No workflow files found")
        sys.exit(0)
    
    all_errors = {}
    
    for workflow_file in sorted(workflow_files):
        errors = check_workflow_for_tabs(workflow_file)
        if errors:
            all_errors[str(workflow_file)] = errors
    
    if all_errors:
        print("ERROR: Tab characters found in workflow files:")
        print("YAML files must use spaces for indentation, not tabs.")
        print("GitHub Actions will fail to parse workflows with tabs.")
        print()
        for file_path, errors in all_errors.items():
            print(f"{file_path}:")
            for error in errors:
                print(error)
        print()
        print("Please replace tabs with spaces in the affected files.")
        sys.exit(1)
    else:
        print("All workflow files are valid (no tab characters found)")
        sys.exit(0)


if __name__ == "__main__":
    main()
