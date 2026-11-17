"""Execute production swipe classifier; source contracts cover Android dispatch wiring."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
S = (ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()

class MenuSwipe(unittest.TestCase):
    def test_production_direction_classifier(self):
        classifier = S[S.index('    private static final class PageSwipe {'):S.index('    private static final class Entry {')]
        java = '''public class SwipeTest {
''' + classifier + '''
static void check(boolean value) { if (!value) throw new AssertionError(); }
public static void main(String[] args) {
    PageSwipe p = new PageSwipe();
    for (int sign : new int[] {-1, 1}) {
        // Both directions: less than old 48dp threshold must succeed.
        p.begin(100, 100, true);
        check(!p.move(100 + sign * 5, 102, 8));
        check(p.move(100 + sign * 12, 104, 8));
        check(p.finish(100 + sign * 30, 0, 8, 50) == -sign);
        check(!p.eligible && !p.captured);
        // Short intentional fling succeeds, tiny/slow drift does not.
        p.begin(100, 100, true); check(p.move(100 + sign * 10, 100, 8));
        check(p.finish(100 + sign * 12, sign * 100, 8, 50) == -sign);
        p.begin(100, 100, true); p.move(100 + sign * 10, 100, 8);
        check(p.finish(100 + sign * 12, sign * 20, 8, 50) == 0);
        // Opposing velocity must not count as a fling.
        p.begin(100, 100, true); p.move(100 + sign * 10, 100, 8);
        check(p.finish(100 + sign * 12, -sign * 100, 8, 50) == 0);
    }
    // Vertical-first movement never becomes a page swipe later.
    p.begin(0, 0, true); check(!p.move(5, 10, 8));
    check(!p.move(80, 20, 8)); check(p.finish(80, 800, 8, 50) == 0);
    // A tap, an outside touch or cancellation never pages.
    p.begin(0, 0, true); check(p.finish(0, 0, 8, 50) == 0);
    p.begin(0, 0, false); check(!p.move(80, 0, 8));
    check(p.finish(80, 800, 8, 50) == 0);
    p.begin(0, 0, true); p.move(20, 0, 8); p.cancel();
    check(p.finish(80, 800, 8, 50) == 0);
    // Return to start abandons gesture, next gesture is independent.
    p.begin(0, 0, true); p.move(20, 0, 8);
    check(p.finish(2, 0, 8, 50) == 0);
    p.begin(0, 0, true); p.move(-20, 0, 8);
    check(p.finish(-30, 0, 8, 50) == 1);
}
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'SwipeTest.java'; source.write_text(java)
            subprocess.run(['java', 'com.sun.tools.javac.Main', '-Xlint:all', '-Werror', str(source)], check=True, capture_output=True)
            subprocess.run(['java', '-cp', tmp, 'SwipeTest'], check=True, capture_output=True)

    def test_platform_touch_dispatch_contract(self):
        section = S[S.index('private void clearPageSwipe()'):]
        self.assertNotIn('dp(48)', section)
        self.assertIn('getScaledTouchSlop()', section)
        self.assertIn('getScaledMinimumFlingVelocity()', section)
        self.assertIn('getScaledMaximumFlingVelocity()', section)
        self.assertIn('MotionEvent.ACTION_POINTER_DOWN', section)
        self.assertIn('MotionEvent.ACTION_POINTER_UP', section)
        self.assertIn('getLayoutDirection() == LAYOUT_DIRECTION_RTL', section)
        self.assertIn('if (direction != 0) page(direction)', section)
        self.assertIn('mPageGestureArea = actionsGroup', S)
        self.assertIn('quickPageCount() <= 1', section)
        self.assertIn('(mAllMenu && mDraft == null)', section)
        self.assertIn('mNativeVisible || mDragging != null', section)
        self.assertIn('clearPageSwipe();', S[S.index('onDetachedFromWindow()'):S.index('onDetachedFromWindow()')+100])

if __name__ == '__main__': unittest.main()
