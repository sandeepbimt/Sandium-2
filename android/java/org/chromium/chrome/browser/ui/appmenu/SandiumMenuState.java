package org.chromium.chrome.browser.ui.appmenu;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** User ordering only. Callers must supply the live policy-filtered catalog before rendering.
 * Missing/temporarily unavailable entries survive persistence, but never become executable here.
 * Edit a copy and publish it only on Done; dismissing the editor discards that copy.
 */
public final class SandiumMenuState {
    private static final String VERSION = "sandium-menu-v1";
    private static final int MAX_ENTRIES = 512;
    private final ArrayList<String> mOrder = new ArrayList<>();
    private final HashSet<String> mHidden = new HashSet<>();

    private SandiumMenuState() {}

    /** Invalid/corrupt state fails safely to defaults and the existing visibility preferences. */
    public static SandiumMenuState load(String saved, Collection<String> defaults,
            Set<String> legacyHidden) {
        SandiumMenuState result = parse(saved);
        if (result == null) result = new SandiumMenuState();
        result.reconcile(defaults, legacyHidden);
        return result;
    }

    /** Adds newly discovered keys once. Does not remove keys absent from this page's catalog. */
    public void reconcile(Collection<String> defaults, Set<String> legacyHidden) {
        for (String key : defaults) {
            if (!validKey(key) || mOrder.contains(key) || mOrder.size() >= MAX_ENTRIES) continue;
            mOrder.add(key);
            if (legacyHidden.contains(key)) mHidden.add(key);
        }
    }

    public SandiumMenuState copy() {
        SandiumMenuState copy = new SandiumMenuState();
        copy.mOrder.addAll(mOrder);
        copy.mHidden.addAll(mHidden);
        return copy;
    }

    public List<String> visibleKeys(Set<String> available) {
        ArrayList<String> result = new ArrayList<>();
        for (String key : mOrder) {
            if (available.contains(key) && !mHidden.contains(key)) result.add(key);
        }
        return Collections.unmodifiableList(result);
    }

    public List<String> hiddenKeys(Set<String> available) {
        ArrayList<String> result = new ArrayList<>();
        for (String key : mOrder) {
            if (available.contains(key) && mHidden.contains(key)) result.add(key);
        }
        return Collections.unmodifiableList(result);
    }

    public List<String> knownKeys() { return Collections.unmodifiableList(new ArrayList<>(mOrder)); }

    public boolean isHidden(String key) { return mHidden.contains(key); }

    public boolean hide(String key) {
        return mOrder.contains(key) && mHidden.add(key);
    }

    /** Re-add preserves its last order. A subsequent move may place it at a different position. */
    public boolean show(String key) {
        return mOrder.contains(key) && mHidden.remove(key);
    }

    /** Move an available visible action to its final index among available visible actions.
     * Excluded/missing/hidden keys stay remembered; this method cannot expose an action.
     */
    public boolean move(String key, int destination, Set<String> available) {
        List<String> visible = visibleKeys(available);
        int oldIndex = visible.indexOf(key);
        if (oldIndex < 0) return false;
        int target = Math.max(0, Math.min(destination, visible.size() - 1));
        if (oldIndex == target) return false;
        ArrayList<String> other = new ArrayList<>(visible);
        other.remove(key);
        mOrder.remove(key);
        if (target < other.size()) {
            mOrder.add(mOrder.indexOf(other.get(target)), key);
        } else {
            int last = mOrder.indexOf(other.get(other.size() - 1));
            mOrder.add(last + 1, key);
        }
        return true;
    }

    /** Zero-based page/slot; empty trailing pages resolve to the last visible position. */
    public boolean moveToPage(String key, int page, int slot, int pageSize,
            Set<String> available) {
        if (pageSize <= 0 || page < 0 || slot < 0 || slot >= pageSize) return false;
        long destination = (long) page * pageSize + slot;
        return move(key, (int) Math.min(Integer.MAX_VALUE, destination), available);
    }

    public List<String> page(Set<String> available, int page, int pageSize) {
        if (pageSize <= 0 || page < 0) return Collections.emptyList();
        List<String> visible = visibleKeys(available);
        long fromLong = (long) page * pageSize;
        if (fromLong >= visible.size()) return Collections.emptyList();
        int from = (int) fromLong;
        int to = (int) Math.min((long) visible.size(), fromLong + pageSize);
        return Collections.unmodifiableList(new ArrayList<>(visible.subList(from, to)));
    }

    public int pageCount(Set<String> available, int pageSize) {
        if (pageSize <= 0) return 0;
        int count = visibleKeys(available).size();
        return count == 0 ? 1 : (count - 1) / pageSize + 1;
    }

    /** Reset to product defaults, NOT migrated historical visibility preferences.
     * Pass the complete known catalog, not just currently available page actions.
     */
    public static SandiumMenuState reset(Collection<String> defaults, Set<String> defaultHidden) {
        return load(null, defaults, defaultHidden);
    }

    public String serialize() {
        StringBuilder text = new StringBuilder(VERSION).append('\n');
        for (String key : mOrder) {
            text.append(key).append('\t').append(mHidden.contains(key) ? '1' : '0').append('\n');
        }
        return text.toString();
    }

    private static SandiumMenuState parse(String saved) {
        if (saved == null || saved.length() > 131072) return null;
        String[] lines = saved.split("\n", -1);
        if (lines.length < 2 || !VERSION.equals(lines[0])) return null;
        SandiumMenuState result = new SandiumMenuState();
        Set<String> seen = new LinkedHashSet<>();
        for (int i = 1; i < lines.length; i++) {
            if (i == lines.length - 1 && lines[i].isEmpty()) continue;
            String[] fields = lines[i].split("\t", -1);
            if (fields.length != 2 || !validKey(fields[0])
                    || !(fields[1].equals("0") || fields[1].equals("1"))
                    || !seen.add(fields[0]) || seen.size() > MAX_ENTRIES) return null;
            result.mOrder.add(fields[0]);
            if (fields[1].equals("1")) result.mHidden.add(fields[0]);
        }
        return result;
    }

    private static boolean validKey(String key) {
        return key != null && key.length() <= 200 && key.matches("[A-Za-z0-9_.:-]+");
    }
}
