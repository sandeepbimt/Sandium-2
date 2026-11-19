#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
for name in ('test_autofill_off_ui.py','test_autofill_off_runtime.py','test_autofill_off_integration.py'):
    subprocess.run([sys.executable,str(root/'tests'/name)],check=True)
