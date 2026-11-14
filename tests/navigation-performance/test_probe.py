"""Static sanity tests for the self-contained Sandium navigation probe.

These tests do not replace on-device BFCache, animation or network measurements.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

PROBE = Path(__file__).with_name("probe.html")


class NavigationProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PROBE.read_text(encoding="utf-8")

    def test_required_navigation_paths(self):
        for snippet in (
            'history.back()', 'history.forward()', 'location.reload()',
            '"pageshow"', '"pagehide"', '"scroll-after-pageshow"',
            'bfcacheRestored', 'notRestoredReasons', 'sessionStorage',
            'longtask', 'unhandledrejection', 'scrollIntoView',
        ):
            self.assertIn(snippet, self.html, snippet)

    def test_does_not_block_bfcache_with_unload_listeners(self):
        self.assertNotRegex(
            self.html, r'addEventListener\s*\(\s*["\x27](?:beforeunload|unload)["\x27]'
        )
        self.assertNotRegex(self.html, r'\bonbeforeunload\s*=')
        self.assertNotRegex(self.html, r'\bonunload\s*=')
        self.assertNotIn('history.scrollRestoration = "manual"', self.html)

    def test_page_a_page_b_and_export_controls(self):
        for item in ('id="next"', 'id="back"', 'id="forward"', 'id="reload"',
                     'id="jump"', 'id="download"', 'id="clear"', '?page=b',
                     '"sandium-navigation-probe.json"'):
            self.assertIn(item, self.html, item)

    def test_script_syntax_with_node_if_available(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable; browser/device validation still required")
        match = re.search(r"<script>(.*?)</script>", self.html, re.DOTALL)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "probe.js"
            src.write_text(match.group(1), encoding="utf-8")
            subprocess.run([node, "--check", str(src)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
