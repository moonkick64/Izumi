# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Group classified files into OSS components.

Strategy:
  1. Files that share the same LICENSE file → one component per license dir.
  2. Files in a third-party directory (vendor/, extern/, …) → one component
     per immediate sub-directory under the third-party dir.
  3. All other files → one component per source directory.

The component name is derived from the grouping directory's last path segment.
"""

from pathlib import Path

from .classifier import Classification, ClassificationResult, ClassifiedFile
from .copyright import guess_spdx_id
from .models import Component
from .scanner import FileInfo, THIRD_PARTY_DIR_NAMES


def group_into_components(
    classification: ClassificationResult,
    root: Path,
) -> list[Component]:
    """Convert a :class:`ClassificationResult` into a list of :class:`Component` objects."""
    root = root.resolve()

    # Bucket files by their component key (a representative directory)
    buckets: dict[Path, list[ClassifiedFile]] = {}
    for cf in classification.all_files:
        key = _component_key(cf.file_info, root)
        buckets.setdefault(key, []).append(cf)

    components: list[Component] = []
    for key_dir, cfs in sorted(buckets.items()):
        components.append(_make_component(key_dir, cfs, root))

    return components


# ── Internal helpers ──────────────────────────────────────────────────────

def _component_key(fi: FileInfo, root: Path) -> Path:
    """Return the grouping key (a directory Path) for *fi*."""

    # Rule 1: group by the directory that owns the closest LICENSE file
    if fi.license_file:
        return fi.license_file.parent.resolve()

    # Rule 2: group by the sub-directory immediately under the third-party dir
    if fi.third_party_dir:
        subdir = _subdir_under_third_party(fi.path, fi.third_party_dir, root)
        if subdir is not None:
            return subdir

    # Rule 3: group by the file's own directory
    return fi.path.parent.resolve()


def _subdir_under_third_party(
    file_path: Path,
    third_party_dir: str,
    root: Path,
) -> Path | None:
    """Return the path up to (and including) the first sub-dir under the
    third-party directory, or None if that can't be determined."""
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        return None

    parts = rel.parts
    # Locate the third-party directory segment (case-insensitive)
    for i, part in enumerate(parts):
        if part.lower() == third_party_dir.lower():
            # The component sub-dir is the next segment (if it exists)
            if i + 1 < len(parts) - 1:
                return (root / Path(*parts[: i + 2])).resolve()
            # Files are directly inside the third-party dir itself
            return (root / Path(*parts[: i + 1])).resolve()
    return None


def _make_component(
    key_dir: Path,
    cfs: list[ClassifiedFile],
    root: Path,
) -> Component:
    """Build a :class:`Component` from a bucket of :class:`ClassifiedFile` objects."""

    # Use the highest-priority classification present in the bucket
    classification_priority = [
        Classification.CONFIRMED,
        Classification.INFERRED,
        Classification.UNKNOWN,
    ]
    classes_present = {cf.classification for cf in cfs}
    main_class = next(c for c in classification_priority if c in classes_present)

    # Reason comes from the first file that has the winning classification
    main_reason = next(
        cf.reason for cf in cfs if cf.classification == main_class
    )

    # Collect unique license expressions and copyright texts
    license_ids: set[str] = set()
    copyrights: list[str] = []
    seen_copyrights: set[str] = set()
    license_files_checked: set[Path] = set()

    for cf in cfs:
        ci = cf.file_info.copyright_info
        if ci.spdx_license_id:
            license_ids.add(ci.spdx_license_id)
        else:
            # No SPDX tag in the source file; try to infer from the LICENSE file.
            # If the license name is not recognisable, record NOASSERTION so the
            # SBOM makes clear that a license file exists but could not be identified.
            lf = cf.file_info.license_file
            if lf and lf not in license_files_checked:
                license_files_checked.add(lf)
                try:
                    content = lf.read_text(errors='replace')
                    guessed = guess_spdx_id(content)
                    license_ids.add(guessed if guessed else "NOASSERTION")
                except OSError:
                    license_ids.add("NOASSERTION")
        for c in ci.all_copyright_texts:
            if c not in seen_copyrights:
                seen_copyrights.add(c)
                copyrights.append(c)

    # Separate confirmed SPDX IDs from NOASSERTION.
    # If any real license is identified in the component, use it exclusively –
    # NOASSERTION from other files in the same component does not override it.
    # Only fall back to NOASSERTION when no license could be identified at all.
    real_ids = license_ids - {"NOASSERTION"}
    if real_ids:
        license_expr = " AND ".join(sorted(real_ids))
    elif "NOASSERTION" in license_ids:
        license_expr = "NOASSERTION"
    else:
        license_expr = None

    return Component(
        name=_component_name(key_dir, root),
        directory=key_dir,
        files=[cf.file_info.path for cf in cfs],
        classification=main_class,
        classification_reason=main_reason,
        license_expression=license_expr,
        copyright_texts=copyrights,
        confirmed_file_count=sum(
            1 for cf in cfs if cf.classification == Classification.CONFIRMED
        ),
    )


def _component_name(key_dir: Path, root: Path) -> str:
    """Derive a human-readable component name from *key_dir*."""
    try:
        rel = key_dir.relative_to(root)
        parts = [p for p in rel.parts if p.lower() not in THIRD_PARTY_DIR_NAMES]
        if parts:
            return parts[-1]
    except ValueError:
        pass
    return key_dir.name
