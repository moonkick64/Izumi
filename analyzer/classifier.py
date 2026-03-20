"""Classify scanned files as CONFIRMED / INFERRED / UNKNOWN."""

from dataclasses import dataclass, field
from enum import Enum

from .scanner import FileInfo, ScanResult


class Classification(Enum):
    """Three-tier classification of source file OSS status."""

    CONFIRMED = "CONFIRMED"
    """License/copyright is unambiguously identified (SPDX tag or LICENSE file in same dir)."""

    INFERRED = "INFERRED"
    """Circumstantial evidence suggests OSS origin; human review not required."""

    UNKNOWN = "UNKNOWN"
    """Cannot determine origin; must be forwarded to LLM analysis phase."""


@dataclass
class ClassifiedFile:
    """A source file together with its classification and the reason for it."""

    file_info: FileInfo
    classification: Classification
    reason: str


@dataclass
class ClassificationResult:
    """Complete classification output for a scan."""

    confirmed: list[ClassifiedFile] = field(default_factory=list)
    inferred: list[ClassifiedFile] = field(default_factory=list)
    unknown: list[ClassifiedFile] = field(default_factory=list)

    @property
    def all_files(self) -> list[ClassifiedFile]:
        return self.confirmed + self.inferred + self.unknown

    def summary(self) -> dict[str, int]:
        return {
            'confirmed': len(self.confirmed),
            'inferred': len(self.inferred),
            'unknown': len(self.unknown),
            'total': len(self.all_files),
        }


def classify(scan_result: ScanResult) -> ClassificationResult:
    """Classify every file in *scan_result* and return a :class:`ClassificationResult`."""
    result = ClassificationResult()

    for file_info in scan_result.source_files:
        cf = _classify_file(file_info)
        if cf.classification == Classification.CONFIRMED:
            result.confirmed.append(cf)
        elif cf.classification == Classification.INFERRED:
            result.inferred.append(cf)
        else:
            result.unknown.append(cf)

    return result


def _classify_file(fi: FileInfo) -> ClassifiedFile:
    """Apply classification rules to a single :class:`FileInfo`."""
    ci = fi.copyright_info

    # ── CONFIRMED rules ────────────────────────────────────────────────────

    # Rule C1: SPDX-License-Identifier tag present (most authoritative)
    if ci.spdx_license_id:
        reason = f"SPDX-License-Identifier: {ci.spdx_license_id}"
        if ci.all_copyright_texts:
            reason += f"; {ci.all_copyright_texts[0]}"
        return ClassifiedFile(fi, Classification.CONFIRMED, reason)

    # Rule C2: LICENSE file exists in the *same* directory
    if fi.license_file and fi.license_file.parent == fi.path.parent:
        reason = f"LICENSE file in same directory: {fi.license_file.name}"
        if ci.all_copyright_texts:
            reason += f"; {ci.all_copyright_texts[0]}"
        return ClassifiedFile(fi, Classification.CONFIRMED, reason)

    # ── INFERRED rules ─────────────────────────────────────────────────────

    # Rule I1: Any copyright notice found in the file header
    if ci.has_copyright:
        return ClassifiedFile(
            fi,
            Classification.INFERRED,
            f"Copyright notice: {ci.all_copyright_texts[0]}",
        )

    # Rule I2: File lives in a third-party directory AND a LICENSE file exists nearby
    if fi.third_party_dir and fi.license_file:
        return ClassifiedFile(
            fi,
            Classification.INFERRED,
            (
                f"In third-party directory '{fi.third_party_dir}'; "
                f"LICENSE file at '{fi.license_file}'"
            ),
        )

    # Rule I3: File lives in a third-party directory (directory heuristic alone)
    if fi.third_party_dir:
        return ClassifiedFile(
            fi,
            Classification.INFERRED,
            f"In third-party directory '{fi.third_party_dir}'",
        )

    # ── UNKNOWN ────────────────────────────────────────────────────────────
    return ClassifiedFile(
        fi,
        Classification.UNKNOWN,
        "No copyright notice, SPDX tag, or adjacent LICENSE file found",
    )
