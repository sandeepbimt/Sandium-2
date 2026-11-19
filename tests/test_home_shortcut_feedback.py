"""Guard direct navigation and native press feedback for the shortcut grid."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / 'android/java/org/chromium/chrome/browser/suggestions/mostvisited/SandiumHomeShortcuts.java'
ADAPTER = ROOT / '.circleci/scripts/apply-sandium-home-shortcuts.py'


class HomeShortcutFeedbackTest(unittest.TestCase):
    def test_ripple_is_clipped_and_not_interactive_in_edit_mode(self):
        source = JAVA.read_text()
        tap = source.split('A native pressed-state ripple', 1)[1].split('content.setOnLongClickListener', 1)[0]
        self.assertIn('if (!mEditing && safe(site.url))', tap)
        self.assertIn('content.setForeground(new android.graphics.drawable.RippleDrawable(', tap)
        self.assertIn('null, shape(Color.WHITE, 12)', tap)
        self.assertIn('else if (mEditing) {', tap)
        self.assertIn('editDialog(site,index);', tap)
        self.assertNotIn('requestLayout', tap)

    def test_same_direct_navigation_without_waiting_or_rewriting(self):
        java = JAVA.read_text()
        listener = java.split('content.setOnClickListener(v ->', 1)[1].split('content.setOnLongClickListener', 1)[0]
        self.assertEqual(listener.count('mOpen.accept(site.url);'), 1)
        self.assertNotIn('post', listener)
        adapter = ADAPTER.read_text()
        start = adapter.split('getContext(), profile, url ->', 1)[1].split('shortcutsParams', 1)[0]
        self.assertIn('tab.loadUrl(new org.chromium.content_public.browser.LoadUrlParams(url.getSpec()));', start)
        self.assertNotIn('post', start)


if __name__ == '__main__':
    unittest.main()
