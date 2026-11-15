import org.chromium.chrome.browser.sandium.video.SandiumVideoGestureState;
import org.chromium.chrome.browser.sandium.video.SandiumVideoGestureState.Kind;
public class GestureStateTest {
    static int checks;
    static void check(boolean b) { checks++; if (!b) throw new AssertionError("check " + checks); }
    public static void main(String[] args) {
        var s = new SandiumVideoGestureState(8, 24);
        check(!s.down(2, 100, 1000, 500, 0));
        check(!s.down(Float.NaN, 100, 1000, 500, 0));
        check(s.down(500, 250, 1000, 500, 0));
        check(s.up(500, 250, 100, true).kind == Kind.TAP);
        check(s.up(500, 250, 100, true).kind == Kind.NONE);
        s.down(500, 250, 1000, 500, 0);
        check(s.up(500, 250, 500, true).kind == Kind.NONE);
        s.down(100, 250, 1000, 500, 0);
        check(s.up(100, 250, 100, true).kind == Kind.NONE);
        s.down(500, 250, 1000, 500, 0);
        var r = s.move(600, 250, 1, true);
        check(r.kind == Kind.SEEK && !r.commit && Math.abs(r.delta - 12000) < 1);
        r = s.up(600, 250, 100, true);
        check(r.kind == Kind.SEEK && r.commit);
        s.down(500, 250, 1000, 500, 0);
        check(s.move(600, 250, 1, false).kind == Kind.NONE);
        check(s.up(600, 250, 100, true).kind == Kind.NONE);
        s.down(500, 250, 1000, 500, 0);
        s.move(600, 250, 1, true);
        check(s.up(600, 250, 100, false).kind == Kind.NONE);
        s.down(100, 250, 1000, 500, 0);
        r = s.move(100, 150, 1, true);
        check(r.kind == Kind.BRIGHTNESS && Math.abs(r.delta - .2) < .001);
        s.cancel();
        check(s.up(100, 150, 100, true).kind == Kind.NONE);
        s.down(800, 250, 1000, 500, 0);
        check(s.move(800, 350, 1, true).kind == Kind.VOLUME);
        check(s.move(500, 150, 1, true).kind == Kind.VOLUME); // direction remains locked
        s.down(500, 250, 1000, 500, 0);
        check(s.move(600, 250, 2, true).kind == Kind.NONE);
        check(s.up(500, 250, 100, true).kind == Kind.NONE);
        s.down(500, 250, 1000, 500, 0);
        check(s.move(10000, 250, 1, true).delta == 120000);
        s.down(100, 250, 1000, 500, 0);
        check(s.move(100, -10000, 1, true).delta == 1);
        s.down(500, 250, 1000, 500, 0);
        s.move(520, 270, 1, true);
        check(s.up(500, 250, 100, true).kind == Kind.NONE);
        System.out.println(checks + " gesture policy checks passed");
    }
}
