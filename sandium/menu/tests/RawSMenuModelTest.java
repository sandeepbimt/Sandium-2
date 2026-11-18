import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.chromium.chrome.browser.ui.appmenu.RawSMenuModel;

public final class RawSMenuModelTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static Map<String, String> catalog(String... keys) {
        Map<String,String> result = new LinkedHashMap<>();
        for (String key : keys) result.put(key, new String(key));
        return result;
    }
    private static String key(RawSMenuModel<String> model, int page) {
        return model.page(page, 1).get(0).key;
    }
    private static final class Disk implements RawSMenuModel.Store {
        final Path file;
        boolean fail;
        Disk(Path path) { file = path; }
        public String read() { try { return Files.exists(file) ? Files.readString(file) : ""; }
            catch (Exception e) { throw new RuntimeException(e); } }
        public boolean write(String value) {
            if (fail) return false;
            try { Files.writeString(file, value); return true; }
            catch (Exception e) { return false; }
        }
    }
    public static void main(String[] args) throws Exception {
        Disk disk = new Disk(Path.of(args[1]));
        if (args[0].equals("read")) {
            RawSMenuModel<String> restarted = new RawSMenuModel<>(disk.read());
            restarted.bind(catalog("one", "two", "three"));
            check(key(restarted, 0).equals("three"));
            check(restarted.page(0, 9).size() == 2);
            return;
        }
        RawSMenuModel<String> model = new RawSMenuModel<>("");
        model.bind(catalog("one", "two", "three"));
        check(key(model, 99).equals("three")); check(key(model, -1).equals("one"));
        RawSMenuModel<String>.Editor canceled = model.edit();
        canceled.setVisible("two", false); canceled.cancel();
        check(!canceled.save(disk)); check(model.page(0, 9).size() == 3);
        RawSMenuModel<String>.Editor editor = model.edit();
        editor.move("three", 0); editor.setVisible("two", false);
        disk.fail = true; check(!editor.save(disk)); check(key(model, 0).equals("one"));
        disk.fail = false; check(editor.save(disk)); check(key(model, 0).equals("three"));
        check(!editor.save(disk));
        // Temporarily unavailable and hidden actions survive process restart and catalog changes.
        model.bind(catalog("one")); check(key(model, 0).equals("one"));
        check(model.serialize().contains("three\t1")); check(model.serialize().contains("two\t0"));
        model.bind(catalog("one", "two", "three", "four"));
        check(model.page(0, 9).size() == 3);
        RawSMenuModel<String>.Editor stale = model.edit();
        model.bind(catalog("one")); check(!stale.save(disk));
        RawSMenuModel.Entry<String> old = model.page(0, 1).get(0);
        model.bind(catalog("one"));
        final int[] count = {0};
        RawSMenuModel.Dispatcher<String> dispatch = new RawSMenuModel.Dispatcher<>() {
            public boolean canExecute(String value) { return true; }
            public void execute(String value) { count[0]++; }
        };
        check(!model.dispatch(old, dispatch));
        RawSMenuModel.Entry<String> current = model.page(0, 1).get(0);
        check(model.dispatch(current, dispatch)); check(!model.dispatch(current, dispatch));
        check(count[0] == 1);
        model.bind(catalog("one")); current = model.page(0, 1).get(0);
        check(!model.dispatch(current, new RawSMenuModel.Dispatcher<>() {
            public boolean canExecute(String value) { return false; }
            public void execute(String value) { throw new AssertionError(); }
        }));
        model.close(); check(!model.dispatch(current, dispatch));
        for (String corrupt : List.of("garbage", "raws-menu-v2\n", "raws-menu-v1\none\t1\none\t0\n", "raws-menu-v1\n123\t1\n")) {
            RawSMenuModel<String> broken = new RawSMenuModel<>(corrupt);
            broken.bind(catalog("one")); check(!broken.writable());
            check(!broken.edit().save(disk)); check(key(broken, 0).equals("one"));
        }
        Disk race = new Disk(Path.of(args[1] + ".race"));
        RawSMenuModel<String> first = new RawSMenuModel<>("");
        RawSMenuModel<String> second = new RawSMenuModel<>("");
        first.bind(catalog("one", "two")); second.bind(catalog("one", "two"));
        var firstEdit = first.edit(); var staleEdit = second.edit();
        firstEdit.setVisible("one", false); check(firstEdit.save(race));
        staleEdit.setVisible("two", false); check(!staleEdit.save(race));
        check(race.read().contains("one\t0")); check(race.read().contains("two\t1"));
        Disk subsetDisk = new Disk(Path.of(args[1] + ".subset"));
        String subsetSaved = "raws-menu-v1\nunavailable\t1\none\t1\ntwo\t1\n";
        check(subsetDisk.write(subsetSaved));
        RawSMenuModel<String> subset = new RawSMenuModel<>(subsetSaved);
        subset.bind(catalog("one", "two"));
        var subsetEdit = subset.edit();
        check(subsetEdit.reorderAvailable(List.of("two", "one")));
        check(subsetEdit.save(subsetDisk));
        check(subset.orderedKeys().equals(List.of("unavailable", "two", "one")));
        var resetEdit = subset.edit(); check(resetEdit.resetToDefaults());
        check(resetEdit.save(subsetDisk));
        check(subset.orderedKeys().equals(List.of("one", "two")));
        check(subset.isVisible("one") && subset.isVisible("two"));
        StringBuilder full = new StringBuilder("raws-menu-v1\n");
        for (int i = 0; i < 256; i++) full.append("old_").append(i).append("\t1\n");
        RawSMenuModel<String> capacity = new RawSMenuModel<>(full.toString());
        capacity.bind(catalog("new_native_action"));
        check(!capacity.writable()); check(key(capacity, 0).equals("new_native_action"));
        check(capacity.serialize().equals(full.toString()));
        check(!capacity.edit().save(disk));
        // Failed validation does not partially replace the current catalog.
        model.bind(catalog("one"));
        try { model.bind(catalog("two", "bad key")); throw new AssertionError(); }
        catch (IllegalArgumentException expected) { check(key(model, 0).equals("one")); }
    }
}
