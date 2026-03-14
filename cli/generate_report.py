"""
CLI entry point for Dashboard Generation.
Wraps the reporting engine logic.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package is found if run as a standalone script (fallback).
# While not strictly necessary with `pip install -e .`, it's a good safety net.
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chaos_engine.reporting.dashboard import main

if __name__ == "__main__":
    main()