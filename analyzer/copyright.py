"""Extract copyright notices and SPDX identifiers from source file headers."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# SPDX tag patterns
_SPDX_LICENSE_RE = re.compile(
    r'SPDX-License-Identifier:\s*([^\s\*\n/][^\n\*]*?)[\s\*]*$',
    re.MULTILINE | re.IGNORECASE,
)
_SPDX_COPYRIGHT_RE = re.compile(
    r'SPDX-FileCopyrightText:\s*(.+?)[\s\*]*$',
    re.MULTILINE | re.IGNORECASE,
)

# Generic copyright patterns: "Copyright (c) 2021 Foo", "© 2021 Foo", etc.
_COPYRIGHT_RE = re.compile(
    r'(?:©\s*|[Cc]opyright\s*(?:\(c\)|©)?\s*)'
    r'(\d{4}(?:\s*[-,–]\s*\d{4})?(?:\s*,\s*\d{4})*\s+[^\n]{2,80})',
    re.IGNORECASE,
)

# Free-text license mention pattern (e.g. "Licensed under the MIT License")
_LICENSE_MENTION_RE = re.compile(
    r'[^\n]{0,40}(?:licen[sc]e(?:d\s+under)?|under\s+the\s+terms\s+of|released\s+under)[^\n]{0,100}',
    re.IGNORECASE,
)

# Only scan the first N lines of a file for header info
_HEADER_MAX_LINES = 50


@dataclass
class CopyrightInfo:
    """Copyright and license information extracted from a source file header."""

    copyright_texts: list[str] = field(default_factory=list)
    """Raw copyright notices (e.g. 'Copyright 2021 Foo Inc.')"""

    spdx_license_id: Optional[str] = None
    """SPDX-License-Identifier value (e.g. 'MIT', 'Apache-2.0')"""

    spdx_copyright_texts: list[str] = field(default_factory=list)
    """SPDX-FileCopyrightText values"""

    license_candidates: list[str] = field(default_factory=list)
    """Free-text license mentions found in the header (e.g. 'Licensed under the MIT License')."""

    @property
    def has_license(self) -> bool:
        return self.spdx_license_id is not None

    @property
    def has_copyright(self) -> bool:
        return bool(self.copyright_texts or self.spdx_copyright_texts)

    @property
    def all_copyright_texts(self) -> list[str]:
        """Deduplicated list of all copyright strings."""
        seen: set[str] = set()
        result: list[str] = []
        for text in self.spdx_copyright_texts + self.copyright_texts:
            normalized = text.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result


def extract_copyright_info(
    file_path: Path,
    header_lines: int = _HEADER_MAX_LINES,
) -> CopyrightInfo:
    """Extract copyright and SPDX info from the header of a source file.

    Only reads the first *header_lines* lines to avoid scanning large files.
    Returns an empty CopyrightInfo on read errors or binary files.
    """
    info = CopyrightInfo()

    content = _read_header(file_path, header_lines)
    if not content:
        return info

    # SPDX-License-Identifier
    m = _SPDX_LICENSE_RE.search(content)
    if m:
        info.spdx_license_id = m.group(1).strip()

    # SPDX-FileCopyrightText
    info.spdx_copyright_texts = [t.strip() for t in _SPDX_COPYRIGHT_RE.findall(content)]

    # Generic copyright lines
    for match in _COPYRIGHT_RE.finditer(content):
        text = f"Copyright {match.group(1).strip()}"
        # Trim trailing comment noise (* / etc.)
        text = re.sub(r'[\s\*/]+$', '', text)
        if text not in info.copyright_texts:
            info.copyright_texts.append(text)

    # Free-text license mentions (only when no SPDX tag present)
    if not info.spdx_license_id:
        for match in _LICENSE_MENTION_RE.finditer(content):
            candidate = re.sub(r'[\s\*/]+$', '', match.group(0).strip())
            # Skip lines that are just "all rights reserved" noise
            if candidate and candidate not in info.license_candidates:
                info.license_candidates.append(candidate)

    return info


def _read_header(file_path: Path, max_lines: int) -> str:
    """Read the first *max_lines* lines, trying UTF-8 then Latin-1 fallback."""
    for encoding in ('utf-8', 'latin-1'):
        try:
            with open(file_path, 'r', encoding=encoding, errors='replace') as fh:
                lines: list[str] = []
                for i, line in enumerate(fh):
                    if i >= max_lines:
                        break
                    lines.append(line)
            return ''.join(lines)
        except OSError:
            return ''
    return ''
