"""Executable original model tests; no claim of Android popup/device validation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class NativeMenuModelTest(unittest.TestCase):
    def test_compile_behavior_and_separate_process_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            model = ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu/RawSMenuModel.java'
            test = ROOT/'sandium/menu/tests/RawSMenuModelTest.java'
            subprocess.run(['java','com.sun.tools.javac.Main','-Xlint:all','-Werror',
                            '-d',temp,str(model),str(test)],check=True,capture_output=True)
            for mode in ('write','read'):
                subprocess.run(['java','-cp',temp,'RawSMenuModelTest',mode,str(Path(temp)/'state')],
                               check=True,capture_output=True)
