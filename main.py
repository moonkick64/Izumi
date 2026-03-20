"""Izumi – OSS detection and SBOM assistance tool.

CLI entry point (GUI-free mode for development and CI use).

Usage:
    uv run python main.py <source-tree-dir>
    uv run python main.py <source-tree-dir> --verbose
"""

import argparse
import sys
from pathlib import Path


def _progress(i: int, total: int, path: Path) -> None:
    print(f"\r  Scanning {i+1}/{total} ...", end='', flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="izumi",
        description="Scan a C/C++ source tree for OSS components.",
    )
    parser.add_argument(
        "source_dir",
        nargs="?",
        default=None,
        help="Source tree directory to scan (omit to launch GUI – not yet implemented).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-file classification details.",
    )
    args = parser.parse_args()

    if args.source_dir is None:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        return app.exec()

    source_dir = Path(args.source_dir)
    if not source_dir.is_dir():
        print(f"Error: '{source_dir}' is not a directory.", file=sys.stderr)
        return 2

    # ── Phase 1: Static analysis ──────────────────────────────────────────
    from analyzer.scanner import scan_tree
    from analyzer.classifier import classify, Classification

    print(f"Scanning: {source_dir.resolve()}")
    scan_result = scan_tree(source_dir, progress_callback=_progress)
    print()  # newline after progress

    if scan_result.total_files == 0:
        print("No C/C++ source files found.")
        return 0

    print(f"Found {scan_result.total_files} source file(s), "
          f"{len(scan_result.license_files)} license file(s).\n")

    # ── Phase 1: Classification ───────────────────────────────────────────
    classification = classify(scan_result)
    summary = classification.summary()

    print("── Classification summary ──────────────────────────────")
    print(f"  CONFIRMED : {summary['confirmed']:>5}")
    print(f"  INFERRED  : {summary['inferred']:>5}")
    print(f"  UNKNOWN   : {summary['unknown']:>5}")
    print(f"  Total     : {summary['total']:>5}")
    print()

    if args.verbose:
        for label, files in [
            ("CONFIRMED", classification.confirmed),
            ("INFERRED",  classification.inferred),
            ("UNKNOWN",   classification.unknown),
        ]:
            if not files:
                continue
            print(f"── {label} ──")
            for cf in files:
                rel = cf.file_info.path.relative_to(source_dir.resolve())
                print(f"  {rel}  →  {cf.reason}")
            print()

    if classification.unknown:
        print(f"⚠  {len(classification.unknown)} file(s) classified as UNKNOWN.")
        print("   Run with --verbose to see details.")
        print("   (LLM-based review phase not yet implemented in CLI mode.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
