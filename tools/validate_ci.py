#!/usr/bin/env python3
"""Compatibility shim for `xptools validate-ci` (works without installing the package)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xptools.validate_ci import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
