#!/usr/bin/env python3
"""Native profile entrypoint with opt-in, safely nested single-handoff profile."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[2] / 'experiments/single-handoff/composition.py'), run_name='__main__')
