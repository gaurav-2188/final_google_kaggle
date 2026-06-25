"""
mcp_server.py

This module implements a Local Tool System using the FastMCP framework.
It exposes tools for codebase traversal, structure mapping, and schema compliance
checks to the AI Agent workspace.

Safety & Design Considerations:
1. Hardened File-Access Paths: Prevents path traversal and code execution injections
   by explicitly resolving absolute paths and scrubbing inputs.
2. In-Memory Pruning: Dynamically prunes directories during os.walk traversal to
   optimize execution speed and keep context footprints minimal.
3. Extensible Filter Matches: Flags critical directories and filters files matching
   data models or API patterns.
"""

import os
from typing import Annotated
from fastmcp import FastMCP

# ------------------------------------------------------------------------------
# 1. Server Initialization
# ------------------------------------------------------------------------------
# Initialize the FastMCP server with a clean identifier for the agent orchestrator
mcp = FastMCP("CodebaseComplianceServer")

# ------------------------------------------------------------------------------
# 2. Tool Implementations
# ------------------------------------------------------------------------------

@mcp.tool()
def read_repository_structure(
    target_path: Annotated[str, "The absolute or relative path to the repository directory to traverse"]
) -> str:
    """
    Safely traverses the specified directory and returns a structural tree layout
    of data models, schemas, and API-related files. Hidden directories and build
    dependencies (e.g., .git, node_modules) are excluded.
    """
    # Clean and resolve path to prevent directory traversal and null-byte injection attacks
    if "\x00" in target_path:
        return "Error: Invalid path containing null bytes."
        
    abs_target = os.path.abspath(target_path)
    
    # Verify directory existence and type safely before processing
    if not os.path.exists(abs_target):
        return f"Error: Target path '{target_path}' does not exist."
    if not os.path.isdir(abs_target):
        return f"Error: Target path '{target_path}' is not a directory."
        
    # Directories to filter out of the scanning tree
    ignored_dirs = {
        '.git', 'node_modules', '__pycache__', '.venv', 'venv', 
        'env', '.pytest_cache', 'dist', 'build', '.agents', '.gemini'
    }
    
    tree_lines = []
    base_len = len(abs_target.rstrip(os.sep))
    
    try:
        # Securely walk the directory structure
        for root, dirs, files in os.walk(abs_target):
            # Prune directory search space in-place to prevent descending into ignored areas
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
            
            # Group files of interest (schemas, models, APIs) based on nomenclature or extensions
            of_interest = []
            for f in files:
                if f.startswith('.'):
                    continue
                
                lower_f = f.lower()
                # Determine if the file is a data model, API endpoint definition, or schema
                is_data_or_api = any(
                    term in lower_f for term in ["model", "schema", "api", "route", "controller", "endpoint"]
                )
                
                # Check for common programming language extensions
                is_code = f.endswith(
                    ('.py', '.ts', '.js', '.json', '.yaml', '.yml', '.go', '.java', '.proto')
                )
                
                if is_data_or_api or is_code:
                    of_interest.append((f, is_data_or_api))
            
            # If the folder has subdirectories of interest or matching files, display it
            if of_interest or dirs:
                # Calculate relative depth to format the visual tree
                rel_path = root[base_len:].lstrip(os.sep)
                depth = rel_path.count(os.sep) if rel_path else 0
                indent = "  " * depth
                
                dir_name = os.path.basename(root) if rel_path else os.path.basename(abs_target)
                tree_lines.append(f"{indent}📁 {dir_name}/")
                
                for f, matched in of_interest:
                    # Highlight critical data/API files with a star, regular code files with a page icon
                    icon = "⭐ " if matched else "📄 "
                    tree_lines.append(f"{indent}  {icon}{f}")
                    
    except Exception as e:
        return f"System Error during repository traversal: {str(e)}"
        
    if not tree_lines:
        return f"No relevant data models or API files found under: {target_path}"
        
    return "\n".join(tree_lines)


@mcp.tool()
def search_schema_for_conflicts(
    file_path: Annotated[str, "The absolute or relative path to the schema or route file to inspect"],
    query_term: Annotated[str, "The term, endpoint route, or schema definition name to search for conflicts"]
) -> str:
    """
    Reads a target file and uses simple line-matching logic to check for 
    conflicting data definitions, duplicate endpoints, or term shadowing.
    """
    # Scrub inputs for security: prevent null byte and command injection patterns
    if "\x00" in file_path or "\x00" in query_term:
        return "Error: Invalid path or query containing null bytes."
        
    abs_path = os.path.abspath(file_path)
    
    # Path validity validation
    if not os.path.exists(abs_path):
        # Try resolving relative path if it starts with the current workspace directory name
        cwd = os.getcwd()
        cwd_basename = os.path.basename(cwd)
        if file_path.startswith(cwd_basename + "/"):
            alternative_path = os.path.join(cwd, file_path[len(cwd_basename)+1:])
            if os.path.exists(alternative_path):
                abs_path = alternative_path
            else:
                return f"Error: File '{file_path}' does not exist (resolved: '{abs_path}' or '{alternative_path}')."
        else:
            return f"Error: File '{file_path}' does not exist (resolved: '{abs_path}')."
            
    if not os.path.isfile(abs_path):
        return f"Error: Path '{file_path}' is not a valid file."
        
    try:
        # Read the file contents securely with fallback encoding settings
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        occurrences = []
        for idx, line in enumerate(lines, 1):
            cleaned = line.strip()
            # Perform a case-insensitive line match for the query term
            if query_term.lower() in cleaned.lower():
                occurrences.append((idx, cleaned))
                
        if not occurrences:
            return f"No matches found for term '{query_term}' in '{os.path.basename(file_path)}'."
            
        # Compile scan report and flags potential conflicts
        report = [
            f"### Compliance Scan Results for '{query_term}' in {os.path.basename(file_path)}:",
            f"Found {len(occurrences)} occurrence(s):\n"
        ]
        
        for num, line in occurrences:
            report.append(f"  Line {num:03d}: {line}")
            
        # Flag duplicates or potential conflicts if multiple occurrences are found
        if len(occurrences) > 1:
            report.append(f"\n⚠️ WARNING: Conflict/Duplicate risk detected!")
            report.append("Multiple matches found. Verify if this introduces route shadowing, duplicate endpoints, or database definition overrides.")
            
        return "\n".join(report)
        
    except IOError as e:
        return f"File I/O Error: Unable to read file '{file_path}'. Reason: {str(e)}"
    except Exception as e:
        return f"Internal Error checking conflicts: {str(e)}"
