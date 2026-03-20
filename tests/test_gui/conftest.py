"""pytest-qt GUI test configuration.

Sets the Qt platform to offscreen so tests run without a display.
"""

import os
import pytest

# Force offscreen rendering before any Qt import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
