# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""pytest-qt GUI test configuration.

Sets the Qt platform to offscreen so tests run without a display.
"""

import os
import pytest

# Force offscreen rendering before any Qt import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
