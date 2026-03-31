# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""Persistence layer for LLM analysis results.

Results are stored in ~/.izumi/results/<project_name>_<hash>/llm_results.json.
Each function is saved individually so results survive interrupted analysis runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analyzer.parser import FunctionInfo


_RESULTS_FILE = "llm_results.json"


def _project_dir(source_root: Path, app_dir: Path) -> Path:
    """Return the per-project results directory inside *app_dir*.

    The directory name is ``<project_folder_name>_<8-char hash>`` so it is
    both human-readable and collision-resistant even when two projects share
    the same folder name.
    """
    resolved = source_root.resolve()
    h = hashlib.sha256(str(resolved).encode()).hexdigest()[:8]
    name = resolved.name or "root"
    return app_dir / "results" / f"{name}_{h}"


class LLMResultsStore:
    """Read/write LLM analysis results for a given source tree.

    Files are stored under *app_dir* (default: ``~/.izumi``) so the scanned
    source tree is never modified.
    """

    def __init__(
        self,
        source_root: Path,
        app_dir: Path | None = None,
    ) -> None:
        self._source_root = source_root
        self._app_dir     = app_dir or (Path.home() / ".izumi")
        self._results_path = (
            _project_dir(source_root, self._app_dir) / _RESULTS_FILE
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def exists(self) -> bool:
        return self._results_path.exists()

    def load(self) -> list[dict[str, Any]]:
        """Return the list of saved result dicts, or [] on missing/corrupt file."""
        raw = self._load_raw()
        return raw.get("results", [])

    def save_result(self, fn: FunctionInfo, option: int, hint: str) -> None:
        """Upsert *fn*'s result and write the file immediately."""
        raw = self._load_raw()
        results: list[dict] = raw.get("results", [])

        rel_file = self._rel(fn.file_path)
        entry: dict[str, Any] = {
            "file":       rel_file,
            "function":   fn.name,
            "start_line": fn.start_line,
            "option":     option,
            "hint":       hint,
        }

        for i, r in enumerate(results):
            if (r.get("file") == rel_file
                    and r.get("function") == fn.name
                    and r.get("start_line") == fn.start_line):
                results[i] = entry
                break
        else:
            results.append(entry)

        raw["results"]    = results
        raw["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._results_path.parent.mkdir(parents=True, exist_ok=True)
        self._results_path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def delete(self) -> None:
        """Delete the results file (directory is kept)."""
        if self._results_path.exists():
            self._results_path.unlink()

    def save_match(self, fn: FunctionInfo, component_name: str, license_str: str) -> None:
        """Persist user match decision (component + license) for *fn*."""
        raw = self._load_raw()
        results: list[dict] = raw.get("results", [])

        rel_file = self._rel(fn.file_path)
        # Find existing entry or create a stub
        for i, r in enumerate(results):
            if (r.get("file") == rel_file
                    and r.get("function") == fn.name
                    and r.get("start_line") == fn.start_line):
                results[i]["matched_component"] = component_name
                results[i]["matched_license"]   = license_str
                break
        else:
            results.append({
                "file":              rel_file,
                "function":          fn.name,
                "start_line":        fn.start_line,
                "option":            0,
                "hint":              "",
                "matched_component": component_name,
                "matched_license":   license_str,
            })

        raw["results"]    = results
        raw["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._results_path.parent.mkdir(parents=True, exist_ok=True)
        self._results_path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def matches_by_key(self) -> dict[tuple, tuple[str, str]]:
        """Return a dict mapping (abs_file_path, func_name, start_line) → (component, license)."""
        out: dict[tuple, tuple[str, str]] = {}
        for r in self.load():
            comp = r.get("matched_component", "")
            lic  = r.get("matched_license", "")
            if not comp and not lic:
                continue
            try:
                abs_path = (self._source_root / r["file"]).resolve()
                key = (abs_path, r["function"], r["start_line"])
                out[key] = (comp, lic)
            except Exception:
                pass
        return out

    def hints_by_key(self) -> dict[tuple, str]:
        """Return a dict mapping (abs_file_path, func_name, start_line) → hint.

        Suitable for merging directly into ``ReviewView._fn_hints``.
        """
        out: dict[tuple, str] = {}
        for r in self.load():
            try:
                abs_path = (self._source_root / r["file"]).resolve()
                key = (abs_path, r["function"], r["start_line"])
                out[key] = r["hint"]
            except Exception:
                pass
        return out

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._source_root))
        except ValueError:
            return str(path)

    def _load_raw(self) -> dict[str, Any]:
        if self._results_path.exists():
            try:
                return json.loads(
                    self._results_path.read_text(encoding="utf-8")
                )
            except Exception:
                pass
        return {
            "source_root": str(self._source_root.resolve()),
            "created_at":  datetime.now(timezone.utc).isoformat(),
            "results":     [],
        }
