import java.util.*;
import org.chromium.chrome.browser.sandium.dark.*;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.*;
public class DarkPolicyTest {
    static int checks;
    static void check(boolean value) { checks++; if (!value) throw new AssertionError("check " + checks); }
    static class MemoryStore implements Store {
        Map<String, Choice> sites = new HashMap<>();
        EnumMap<Control, Boolean> globals = new EnumMap<>(Control.class);
        int writes;
        public Choice read(String origin, Control control) { return sites.get(origin + control); }
        public void write(String origin, Control control, Choice choice) {
            writes++; if (choice == Choice.FOLLOW_GLOBAL) sites.remove(origin + control);
            else sites.put(origin + control, choice);
        }
        public boolean global(Control control) { return globals.getOrDefault(control, true); }
        public void setGlobal(Control control, boolean value) { globals.put(control, value); }
    }
    public static void main(String[] args) {
        MemoryStore store = new MemoryStore(); DarkPagePolicy policy = new DarkPagePolicy(store);
        String a = "https://example.com", b = "https://other.example.com";
        for (Control control : Control.values()) check(policy.effective(a, control, false));
        policy.set(a, Control.DARK_PAGE, Choice.OFF, false);
        check(!policy.effective(a, Control.DARK_PAGE, false));
        check(policy.effective(b, Control.DARK_PAGE, false));
        check(policy.effective("http://example.com", Control.DARK_PAGE, false));
        check(!policy.effective(a, Control.DARK_PAGE, false));
        check(policy.effective(a, Control.DARK_PAGE, true)); // no regular site history leakage
        int writes = store.writes;
        policy.set(a, Control.DARK_PAGE, Choice.OFF, true);
        check(!policy.effective(a, Control.DARK_PAGE, true));
        check(!policy.effective(a, Control.DARK_PAGE, false));
        check(store.writes == writes);
        policy.closePrivateSession(); check(policy.effective(a, Control.DARK_PAGE, true));
        policy.setGlobal(Control.DARK_PAGE, false);
        check(!policy.effective(a, Control.DARK_PAGE, false));
        policy.set(a, Control.DARK_PAGE, Choice.ON, false);
        check(policy.effective(a, Control.DARK_PAGE, false));
        policy.reset(a, false); check(!policy.effective(a, Control.DARK_PAGE, false));
        check(!new DarkPagePolicy(store).effective(a, Control.DARK_PAGE, false));
        for (String bad : new String[]{"file:///tmp", "https://a/path", "https://user@a", "https://a?q=secret", "https://a#secret", "https://", "javascript:x", "https://a\nb"}) {
            boolean rejected = false;
            try { policy.set(bad, Control.DARK_PAGE, Choice.ON, false); }
            catch (IllegalArgumentException expected) { rejected = true; }
            check(rejected);
        }
        policy.close(); boolean closed = false;
        try { policy.effective(a, Control.DARK_PAGE, false); } catch (IllegalStateException expected) { closed = true; }
        check(closed);
        System.out.println(checks + " Dark Pages policy assertions passed");
    }
}
