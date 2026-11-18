"""Host-only grid state tests, not Android/native popup or touch validation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class NativeMenuPagerTest(unittest.TestCase):
    def test_paging_all_menu_and_stale_tile_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu'
            sources = [base/'RawSMenuModel.java', base/'RawSMenuPager.java',
                       ROOT/'sandium/menu/tests/RawSMenuPagerTest.java']
            result = subprocess.run(['java','com.sun.tools.javac.Main','-Xlint:all','-Werror',
                            '-d',temp,*map(str,sources)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run(['java','-cp',temp,'RawSMenuPagerTest'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
