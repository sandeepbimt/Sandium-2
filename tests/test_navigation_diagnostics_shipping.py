"""Run typed recorder, production transform and cold-restart source contracts."""
from pathlib import Path
import subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
class NavigationDiagnosticsShipping(unittest.TestCase):
 def test_producer_and_recorder_suites(self):
  for relative in ('experiments/navigation-diagnostics/tests','experiments/navigation-diagnostics/native-bridge','experiments/navigation-diagnostics/ad'):
   with self.subTest(suite=relative):
    p=subprocess.run([sys.executable,'-m','unittest','discover','-s',relative,'-p','test*.py'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    self.assertEqual(p.returncode,0,p.stdout[-15000:])

 def test_capture_bootstrap_existing_dependency(self):
  text=(ROOT/'experiments/navigation-diagnostics/fixtures/chrome_android_BUILD.gn').read_text()
  target=text.split('android_library("chrome_java") {',1)[1].split('sources = chrome_java_sources',1)[0]
  self.assertIn('"//chrome/browser/gesturenav/android:java"',target)
