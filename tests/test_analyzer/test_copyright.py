"""Unit tests for analyzer.copyright."""

import pytest
from pathlib import Path

from analyzer.copyright import CopyrightInfo, extract_copyright_info


# ── Helper ────────────────────────────────────────────────────────────────

def make_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding='utf-8')
    return p


# ── CopyrightInfo property tests ──────────────────────────────────────────

class TestCopyrightInfo:
    def test_has_license_true(self):
        ci = CopyrightInfo(spdx_license_id="MIT")
        assert ci.has_license is True

    def test_has_license_false(self):
        ci = CopyrightInfo()
        assert ci.has_license is False

    def test_has_copyright_from_texts(self):
        ci = CopyrightInfo(copyright_texts=["Copyright 2021 Foo"])
        assert ci.has_copyright is True

    def test_has_copyright_from_spdx(self):
        ci = CopyrightInfo(spdx_copyright_texts=["2021 Foo Inc"])
        assert ci.has_copyright is True

    def test_has_copyright_empty(self):
        assert CopyrightInfo().has_copyright is False

    def test_all_copyright_texts_deduplication(self):
        ci = CopyrightInfo(
            copyright_texts=["Copyright 2021 Foo"],
            spdx_copyright_texts=["Copyright 2021 Foo"],
        )
        assert len(ci.all_copyright_texts) == 1

    def test_all_copyright_texts_ordering(self):
        ci = CopyrightInfo(
            spdx_copyright_texts=["SPDX Owner"],
            copyright_texts=["Copyright 2021 Other"],
        )
        # SPDX texts appear first
        assert ci.all_copyright_texts[0] == "SPDX Owner"


# ── extract_copyright_info tests ──────────────────────────────────────────

class TestExtractCopyrightInfo:
    def test_spdx_license_identifier(self, tmp_path):
        f = make_file(tmp_path, "foo.c", """\
// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2021 Alice <alice@example.com>
int main() { return 0; }
""")
        ci = extract_copyright_info(f)
        assert ci.spdx_license_id == "MIT"
        assert "2021 Alice <alice@example.com>" in ci.spdx_copyright_texts

    def test_spdx_apache(self, tmp_path):
        f = make_file(tmp_path, "bar.c", """\
/*
 * SPDX-License-Identifier: Apache-2.0
 * SPDX-FileCopyrightText: 2020 Bob Corp
 */
void foo() {}
""")
        ci = extract_copyright_info(f)
        assert ci.spdx_license_id == "Apache-2.0"
        assert any("Bob Corp" in t for t in ci.spdx_copyright_texts)

    def test_generic_copyright_c_style(self, tmp_path):
        f = make_file(tmp_path, "baz.h", """\
/*
 * Copyright (c) 2019 Acme Corp.
 * All rights reserved.
 */
""")
        ci = extract_copyright_info(f)
        assert ci.has_copyright
        assert any("Acme Corp" in t for t in ci.copyright_texts)

    def test_copyright_symbol(self, tmp_path):
        f = make_file(tmp_path, "sym.h", "// © 2022 Symbol Inc.\n")
        ci = extract_copyright_info(f)
        assert ci.has_copyright

    def test_no_copyright(self, tmp_path):
        f = make_file(tmp_path, "none.c", "int x = 1;\n")
        ci = extract_copyright_info(f)
        assert not ci.has_license
        assert not ci.has_copyright

    def test_missing_file_returns_empty(self, tmp_path):
        ci = extract_copyright_info(tmp_path / "nonexistent.c")
        assert not ci.has_license
        assert not ci.has_copyright

    def test_only_scans_header(self, tmp_path):
        # Put SPDX tag far below the header limit and expect it to be missed
        header = "// no info here\n" * 60
        footer = "// SPDX-License-Identifier: GPL-2.0\n"
        f = make_file(tmp_path, "deep.c", header + footer)
        ci = extract_copyright_info(f, header_lines=50)
        assert ci.spdx_license_id is None

    def test_spdx_with_expression(self, tmp_path):
        f = make_file(tmp_path, "expr.c", "// SPDX-License-Identifier: GPL-2.0-or-later\n")
        ci = extract_copyright_info(f)
        assert ci.spdx_license_id == "GPL-2.0-or-later"

    def test_latin1_file(self, tmp_path):
        # Files with Latin-1 encoding should not crash
        f = tmp_path / "latin.c"
        f.write_bytes(b"// Copyright (c) 2020 \xe9\xe0\n")
        ci = extract_copyright_info(f)
        assert ci.has_copyright

    def test_multiple_copyright_lines(self, tmp_path):
        f = make_file(tmp_path, "multi.c", """\
// Copyright (c) 2018 First Author
// Copyright (c) 2020 Second Author
""")
        ci = extract_copyright_info(f)
        assert len(ci.copyright_texts) == 2
