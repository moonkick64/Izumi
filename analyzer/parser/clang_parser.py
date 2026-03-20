"""libclang-based C/C++ function extractor.

Uses the Python ``clang`` bindings (libclang) for accurate AST-based
function extraction.  Raises ImportError or RuntimeError if libclang is
unavailable – callers should fall back to regex_parser in that case.
"""

from pathlib import Path
from typing import Optional

from .regex_parser import FunctionInfo  # reuse the same dataclass


def extract_functions_clang(
    file_path: Path,
    source_root: Optional[Path] = None,
) -> list[FunctionInfo]:
    """Extract function definitions using libclang.

    Args:
        file_path: C/C++ source file to parse.
        source_root: Used to set include paths if needed.

    Returns:
        List of :class:`FunctionInfo` objects, or empty list on parse failure.

    Raises:
        ImportError: If the ``clang`` Python package is not installed.
        RuntimeError: If libclang shared library cannot be loaded.
    """
    import clang.cindex as cindex  # type: ignore[import]

    index = cindex.Index.create()
    args = ['-x', 'c++', '-std=c++17']

    try:
        tu = index.parse(str(file_path), args=args)
    except cindex.TranslationUnitLoadError as exc:
        raise RuntimeError(f"libclang failed to parse {file_path}") from exc

    if not tu:
        return []

    functions: list[FunctionInfo] = []

    def _visit(node: cindex.Cursor) -> None:
        if (
            node.kind in (
                cindex.CursorKind.FUNCTION_DECL,
                cindex.CursorKind.CXX_METHOD,
            )
            and node.is_definition()
            and node.location.file
            and Path(node.location.file.name).resolve() == file_path.resolve()
        ):
            extent = node.extent
            start_line = extent.start.line
            end_line = extent.end.line

            # Read the function body from the source file
            try:
                lines = file_path.read_text(encoding='utf-8', errors='replace').splitlines()
                body_lines = lines[start_line - 1:end_line]
                body = '\n'.join(body_lines)
            except OSError:
                body = ''

            functions.append(FunctionInfo(
                name=node.spelling,
                start_line=start_line,
                end_line=end_line,
                body=body,
                file_path=file_path,
            ))

        for child in node.get_children():
            _visit(child)

    _visit(tu.cursor)
    return functions
