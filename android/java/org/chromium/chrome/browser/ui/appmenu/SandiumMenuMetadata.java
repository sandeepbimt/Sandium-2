package org.chromium.chrome.browser.ui.appmenu;

import org.chromium.ui.modelutil.PropertyModel;
import org.chromium.ui.modelutil.MVCListAdapter.ModelList;
import java.util.WeakHashMap;

/** Visibility migration only, never a source of actions or permission decisions. UI-thread only. */
public final class SandiumMenuMetadata {
    private static final WeakHashMap<PropertyModel, Boolean> LEGACY = new WeakHashMap<>();
    private static final WeakHashMap<Object, java.lang.ref.WeakReference<Runnable>> FOOTERS = new WeakHashMap<>();
    public static void watchFooter(Object footer, Runnable listener) {
        if (listener == null) FOOTERS.remove(footer);
        else FOOTERS.put(footer, new java.lang.ref.WeakReference<>(listener));
    }
    public static void footerChanged(Object footer) {
        java.lang.ref.WeakReference<Runnable> ref = FOOTERS.get(footer);
        Runnable listener = ref == null ? null : ref.get();
        if (listener != null) listener.run();
    }
    public interface FooterProvider { ModelList sandiumActions(); }
    private static final WeakHashMap<PropertyModel, Runnable> ACTIONS = new WeakHashMap<>();
    public static void action(PropertyModel model, Runnable action) { ACTIONS.put(model, action); }
    public static boolean dispatch(PropertyModel model) {
        Runnable action = ACTIONS.get(model);
        if (action == null) return false;
        action.run(); return true;
    }
    private SandiumMenuMetadata() {}
    public static void record(PropertyModel model, boolean visible) { LEGACY.put(model, visible); }
    public static boolean wasVisible(PropertyModel model) {
        return !Boolean.FALSE.equals(LEGACY.get(model));
    }
}
