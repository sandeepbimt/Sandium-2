#!/usr/bin/env python3
"""Run pinned capsule paint/state regressions in product composition."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[2]/'tests/test_address_progress.py'), run_name='__main__')
