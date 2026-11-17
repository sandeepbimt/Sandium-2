#!/usr/bin/env python3
"""Shipping entry point for the isolated reversible native-navigation profile."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[2] / 'experiments/native-navigation/apply.py'), run_name='__main__')
