"""Internationalisation (i18n) support.

Usage:
    from i18n import t, set_language, get_language

    label = t("scan_start_btn")
    msg   = t("invalid_path_msg", path="/foo/bar")

Language is stored in ~/.izumi/config.json under the key "language".
Supported values: "en" (default), "ja".
Restart is required after changing the language.

Translation files: i18n/en.json, i18n/ja.json
"""

from __future__ import annotations

import json
from pathlib import Path

_I18N_DIR    = Path(__file__).parent
_CONFIG_PATH = Path.home() / ".izumi" / "config.json"
_SUPPORTED   = {"en", "ja"}
_DEFAULT     = "en"

# Active string table (filled in _load_strings)
_strings: dict[str, str] = {}


def _load_strings() -> None:
    global _strings
    lang = get_language()
    json_path = _I18N_DIR / f"{lang}.json"
    try:
        _strings = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        # Fallback to English if the file is missing or corrupt
        fallback = _I18N_DIR / "en.json"
        try:
            _strings = json.loads(fallback.read_text(encoding="utf-8"))
        except Exception:
            _strings = {}


def get_language() -> str:
    """Return the current language code from the config file (default: 'en')."""
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        lang = data.get("language", _DEFAULT)
        return lang if lang in _SUPPORTED else _DEFAULT
    except Exception:
        return _DEFAULT


def set_language(lang: str) -> None:
    """Persist *lang* to the config file (does not reload strings at runtime)."""
    if lang not in _SUPPORTED:
        raise ValueError(f"Unsupported language: {lang!r}. Choose from {_SUPPORTED}.")
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            data: dict = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        data["language"] = lang
        _CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to save language setting: {exc}") from exc


def t(key: str, **kwargs: object) -> str:
    """Return the localised string for *key*, optionally formatted with *kwargs*.

    Falls back to the key itself if not found (never raises).
    """
    template = _strings.get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


# Load strings at import time
_load_strings()
