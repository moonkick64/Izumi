"""Regex-based fallback C/C++ function extractor.

This parser is intentionally simple: it finds function definitions using
heuristics that work well enough for embedded code where libclang may fail
due to compiler-specific extensions.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Match a C/C++ function definition (not declaration):
#   optional qualifiers / return type  +  name  +  (  params  )  +  {
_FUNC_DEF_RE = re.compile(
    r'^'
    r'(?:(?:static|inline|extern|const|volatile|unsigned|signed|long|short|struct|enum|union)\s+)*'
    r'(?:[\w\s\*\:\<\>]+?)\s+'   # return type (greedy but not too greedy)
    r'(\w+)\s*'                   # function name (captured)
    r'\([^)]*\)\s*'              # parameter list
    r'(?:const\s*)?'             # optional trailing const (C++)
    r'\{',                        # opening brace
    re.MULTILINE,
)


@dataclass
class FunctionInfo:
    """A function extracted from a source file."""

    name: str
    start_line: int
    end_line: int
    body: str
    file_path: Path


def extract_functions_regex(file_path: Path) -> list[FunctionInfo]:
    """Extract top-level function definitions from *file_path* using regex."""
    content = _read_file(file_path)
    if content is None:
        return []

    lines = content.splitlines(keepends=True)
    functions: list[FunctionInfo] = []

    for m in _FUNC_DEF_RE.finditer(content):
        name = m.group(1)
        # Ignore common false positives (struct/enum bodies, if/for/while)
        if name in {'if', 'for', 'while', 'switch', 'do', 'else', 'struct', 'enum', 'union'}:
            continue

        start_char = m.start()
        brace_pos = content.index('{', start_char)
        end_char = _find_closing_brace(content, brace_pos)
        if end_char == -1:
            continue

        body = content[start_char:end_char + 1]
        start_line = content[:start_char].count('\n') + 1
        end_line = content[:end_char].count('\n') + 1

        functions.append(FunctionInfo(
            name=name,
            start_line=start_line,
            end_line=end_line,
            body=body,
            file_path=file_path,
        ))

    return functions


def _find_closing_brace(content: str, open_pos: int) -> int:
    """Return the index of the closing brace matching the one at *open_pos*."""
    depth = 0
    i = open_pos
    in_string = False
    string_char: Optional[str] = None
    while i < len(content):
        ch = content[i]
        if in_string:
            if ch == '\\':
                i += 2
                continue
            if ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _read_file(file_path: Path) -> Optional[str]:
    for enc in ('utf-8', 'latin-1'):
        try:
            return file_path.read_text(encoding=enc, errors='replace')
        except OSError:
            return None
    return None
