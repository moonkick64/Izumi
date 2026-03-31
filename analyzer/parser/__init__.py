# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""C/C++ function extractors (libclang with regex fallback)."""

from .regex_parser import extract_functions_regex, FunctionInfo

__all__ = ["extract_functions_regex", "FunctionInfo"]

def extract_functions(file_path, source_root=None):
    """Extract functions from *file_path*, preferring libclang with regex fallback."""
    try:
        from .clang_parser import extract_functions_clang
        result = extract_functions_clang(file_path, source_root=source_root)
        if result:
            return result
    except Exception:
        pass
    return extract_functions_regex(file_path)
