"""Source tree scanner: walk directory tree and collect file metadata."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .copyright import CopyrightInfo, extract_copyright_info

# Source file extensions to analyse
SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx', '.hh', '.hxx', '.c++', '.h++',
})

# File names (case-insensitive) that indicate a license/copyright file
_LICENSE_NAMES: frozenset[str] = frozenset({
    'license', 'license.txt', 'license.md', 'license.rst',
    'copying', 'copying.txt', 'copying.lesser',
    'notice', 'notice.txt',
    'copyright', 'copyright.txt',
})

# Directory name fragments (lower-cased) that suggest third-party code
THIRD_PARTY_DIR_NAMES: frozenset[str] = frozenset({
    'third_party', 'third-party', 'thirdparty',
    'vendor', 'vendors',
    'extern', 'external', 'externals',
    'deps', 'dependencies',
    'contrib', 'contributed',
    'imported', 'upstream',
})

ProgressCallback = Callable[[int, int, Path], None]


@dataclass
class FileInfo:
    """Metadata collected for a single source file."""

    path: Path
    copyright_info: CopyrightInfo = field(default_factory=CopyrightInfo)

    license_file: Optional[Path] = None
    """Closest LICENSE/COPYING file found by walking up the tree."""

    third_party_dir: Optional[str] = None
    """Name of the ancestor directory that matches a third-party heuristic."""


@dataclass
class ScanResult:
    """Aggregated result of scanning a source tree."""

    root_path: Path
    source_files: list[FileInfo] = field(default_factory=list)
    license_files: list[Path] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.source_files)


def scan_tree(
    root_path: Path,
    progress_callback: Optional[ProgressCallback] = None,
) -> ScanResult:
    """Scan *root_path* recursively and return a :class:`ScanResult`.

    Args:
        root_path: Directory to scan.
        progress_callback: Optional ``(current, total, path)`` callback
            called for each source file processed.
    """
    root_path = root_path.resolve()
    result = ScanResult(root_path=root_path)

    # Pass 1 – collect all LICENSE-like files indexed by their directory
    license_by_dir: dict[Path, Path] = {}
    for p in root_path.rglob('*'):
        if p.is_file() and p.name.lower() in _LICENSE_NAMES:
            result.license_files.append(p)
            # Keep the first (shallowest) license file per directory
            license_by_dir.setdefault(p.parent, p)

    # Pass 2 – collect and analyse source files
    source_paths = [
        p for p in root_path.rglob('*')
        if p.is_file() and p.suffix.lower() in SOURCE_EXTENSIONS
    ]

    for i, file_path in enumerate(source_paths):
        if progress_callback:
            progress_callback(i, len(source_paths), file_path)

        fi = FileInfo(path=file_path)
        fi.license_file = _find_closest_license(file_path, license_by_dir)
        fi.third_party_dir = _detect_third_party_dir(file_path, root_path)
        fi.copyright_info = extract_copyright_info(file_path)
        result.source_files.append(fi)

    return result


def _find_closest_license(
    file_path: Path,
    license_by_dir: dict[Path, Path],
) -> Optional[Path]:
    """Walk up from *file_path*'s directory to find the nearest LICENSE file."""
    current = file_path.parent
    while True:
        if current in license_by_dir:
            return license_by_dir[current]
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _detect_third_party_dir(file_path: Path, root_path: Path) -> Optional[str]:
    """Return the first ancestor directory name that matches a third-party heuristic."""
    try:
        relative = file_path.relative_to(root_path)
    except ValueError:
        return None

    for part in relative.parts[:-1]:  # Exclude the filename itself
        if part.lower() in THIRD_PARTY_DIR_NAMES:
            return part
    return None
