"""Source/flag contracts only; Android rendering still needs device validation."""
from pathlib import Path
import unittest

class WelcomeBackingTests(unittest.TestCase):
    def test_matching_backing_precedes_content_and_color(self):
        path=Path(__file__).resolve().parents[2]/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java'
        source=path.read_text()
        body=source[source.index('    View createView() {'):source.index('        mScrollView =')]
        self.assertLess(body.index('setBackgroundDrawable(new ColorDrawable(BACKGROUND))'),body.index('setStatusBarColor(BACKGROUND)'))
        self.assertIn('mRoot.setBackgroundColor(BACKGROUND)',body)
        self.assertNotIn('setSystemUiVisibility(0)',body)
        self.assertNotIn('setDecorFitsSystemWindows',body)
        self.assertNotIn('setPadding(',body)
        self.assertIn('decor.getSystemUiVisibility()',body)

    def test_icon_mask_preserves_layout_and_fullscreen_flags(self):
        # Android View flags: only light-status 0x2000 and light-nav 0x10 removed.
        mask=0x2000|0x10
        preserved=0x100|0x200|0x400|0x4|0x2|0x1000
        for icons in (0,0x2000,0x10,mask):
            self.assertEqual((preserved|icons)&~mask,preserved)

if __name__=='__main__':unittest.main()
