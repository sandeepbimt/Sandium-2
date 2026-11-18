package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.content.res.Resources;
import android.os.Bundle;
import android.os.Handler;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.os.Looper;
import android.widget.ListView;

import androidx.appcompat.app.AlertDialog;

import org.chromium.base.task.PostTask;
import org.chromium.base.task.TaskTraits;
import org.chromium.build.annotations.Nullable;
import org.chromium.chrome.browser.ui.appmenu.internal.R;
import org.chromium.chrome.browser.ui.appmenu.AppMenuHandler.AppMenuItemType;
import org.chromium.ui.modelutil.ListObservable;
import org.chromium.ui.modelutil.ListObservable.ListObserver;
import org.chromium.ui.modelutil.MVCListAdapter.ListItem;
import org.chromium.ui.modelutil.MVCListAdapter.ModelList;
import org.chromium.ui.modelutil.PropertyModel;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Opt-in customization within Chromium's native menu, not a replacement window. */
final class RawSNativeMenu {
    private final Context context;
    private final RawSMenuStore store;
    private final LinkedHashMap<String, ListItem> catalog = new LinkedHashMap<>();
    private @Nullable ModelList nativeSource;
    private @Nullable ModelList projection;
    private @Nullable RawSMenuModel<ListItem> currentState;
    private @Nullable ListItem customizeItem;
    private final ListObserver<Void> nativeObserver = new ListObserver<Void>() {
        @Override public void onItemRangeInserted(ListObservable source, int index, int count) { refresh(); }
        @Override public void onItemRangeRemoved(ListObservable source, int index, int count) { refresh(); }
        @Override public void onItemRangeChanged(ListObservable<Void> source, int index, int count,
                @Nullable Void payload) { refresh(); }
        @Override public void onItemMoved(ListObservable source, int from, int to) { refresh(); }
    };
    private final Map<String, Integer> groups = new HashMap<>();
    private @Nullable AlertDialog editorDialog;
    private @Nullable AlertDialog moveDialog;

    RawSNativeMenu(Context context) {
        this.context = context;
        store = new RawSMenuStore(context);
    }

    /** Never persist generated resource IDs or reinterpret compound/native protected rows. */
    @Nullable String key(ListItem item) {
        if (item.type != AppMenuItemType.STANDARD
                && item.type != AppMenuItemType.STANDARD_NO_ICON) return null;
        PropertyModel model = item.model;
        if (model.get(AppMenuItemProperties.MENU_ITEM_ID) == R.id.raws_customize_menu) return null;
        if ((model.containsKey(AppMenuItemProperties.MANAGED) && model.get(AppMenuItemProperties.MANAGED))
                || (model.containsKey(AppMenuItemProperties.ADDITIONAL_ICONS)
                    && model.get(AppMenuItemProperties.ADDITIONAL_ICONS) != null)) return null;
        try {
            String name = context.getResources().getResourceEntryName(
                    model.get(AppMenuItemProperties.MENU_ITEM_ID));
            // Keep access to settings and emergency/administrative controls immutable.
            if (name.contains("settings") || name.contains("update") || name.contains("exit"))
                return null;
            return name.matches("[a-z][a-z0-9_]{0,127}") ? name : null;
        } catch (Resources.NotFoundException exception) {
            return null;
        }
    }

    ModelList prepare(ModelList nativeItems) {
        closeProjection();
        currentState = new RawSMenuModel<>(store.read());
        customizeItem = null;
        projection = project(nativeItems, currentState);
        nativeSource = nativeItems;
        nativeSource.addObserver(nativeObserver);
        return projection;
    }
    void closeProjection() {
        if (nativeSource != null) nativeSource.removeObserver(nativeObserver);
        nativeSource = null; projection = null;
    }
    void refresh() {
        if (nativeSource == null || projection == null || currentState == null) return;
        ModelList desired = project(nativeSource, currentState);
        // Native producers retain their own indices (including async Read Aloud insertion).
        // Only update the rendered projection with minimal native list notifications.
        for (int i = 0; i < desired.size(); i++) {
            ListItem wanted = desired.get(i);
            if (i < projection.size() && projection.get(i) == wanted) continue;
            int old = projection.indexOf(wanted);
            if (old >= 0) projection.removeAt(old);
            projection.add(i, wanted);
        }
        while (projection.size() > desired.size()) projection.removeAt(projection.size() - 1);
    }
    private ModelList project(ModelList nativeItems, RawSMenuModel<ListItem> state) {
        catalog.clear(); groups.clear();
        int groupIndex = 0;
        for (ListItem item : nativeItems) {
            String name = key(item);
            if (name == null) { groupIndex++; continue; }
            if (catalog.containsKey(name) || catalog.size() >= 256) {
                catalog.clear(); groups.clear();
                ModelList unchanged = new ModelList();
                unchanged.addAll(nativeItems); return unchanged;
            }
            catalog.put(name, item); groups.put(name, groupIndex);
        }
        state.bind(catalog);
        if (!state.writable()) {
            ModelList unchanged = new ModelList(); unchanged.addAll(nativeItems); return unchanged;
        }
        ModelList result = new ModelList();
        // Reorder within native contiguous groups only. Preserve separators and compound rows.
        LinkedHashMap<String, ListItem> group = new LinkedHashMap<>();
        for (ListItem item : nativeItems) {
            String name = key(item);
            if (name != null) {
                group.put(name, item);
            } else {
                appendGroup(result, group, state);
                result.add(item);
            }
        }
        appendGroup(result, group, state);
        if (!catalog.isEmpty() && state.writable()) {
            if (customizeItem == null) customizeItem = new ListItem(AppMenuItemType.STANDARD_NO_ICON,
                    new PropertyModel.Builder(AppMenuItemProperties.ALL_KEYS)
                            .with(AppMenuItemProperties.MENU_ITEM_ID, R.id.raws_customize_menu)
                            .with(AppMenuItemProperties.TITLE, context.getString(R.string.raws_customize_menu))
                            .with(AppMenuItemProperties.TITLE_CONDENSED, context.getString(R.string.raws_customize_menu))
                            .with(AppMenuItemProperties.TITLE_MAX_LINES, 1)
                            .with(AppMenuItemProperties.ENABLED, true)
                            .build());
            result.add(customizeItem);
        }
        return result;
    }
    private static void appendGroup(ModelList out, Map<String, ListItem> group,
            RawSMenuModel<ListItem> state) {
        for (String name : state.orderedKeys()) {
            ListItem item = group.get(name);
            if (item != null && state.isVisible(name)) out.add(item);
        }
        group.clear();
    }
    boolean isEditor(PropertyModel model) {
        return model.get(AppMenuItemProperties.MENU_ITEM_ID) == R.id.raws_customize_menu;
    }
    void dismissEditor() {
        if (moveDialog != null) moveDialog.dismiss();
        moveDialog = null;
        if (editorDialog != null) editorDialog.dismiss();
        editorDialog = null;
    }
    private boolean moveEditorItem(int position, int step, List<String> keys,
            CharSequence[] titles, boolean[] checked, Map<String, Boolean> visible, ListView list) {
        int target = position + step;
        if (!list.isEnabled() || position < 0 || position >= keys.size() || target < 0 || target >= keys.size()
                || !groups.get(keys.get(position)).equals(groups.get(keys.get(target)))) return false;
        String name = keys.remove(position); keys.add(target, name);
        CharSequence label = titles[position]; titles[position] = titles[target]; titles[target] = label;
        list.invalidateViews();
        for (int i = 0; i < keys.size(); i++) {
            checked[i] = Boolean.TRUE.equals(visible.get(keys.get(i)));
            list.setItemChecked(i, checked[i]);
        }
        list.setSelection(target);
        return true;
    }
    private void addReorderAccessibility(View row, ListView list, List<String> keys,
            CharSequence[] titles, boolean[] checked, Map<String, Boolean> visible) {
        row.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                int position = list.getPositionForView(host);
                if (position > 0 && position < keys.size()
                        && groups.get(keys.get(position)).equals(groups.get(keys.get(position - 1))))
                    info.addAction(new AccessibilityNodeInfo.AccessibilityAction(R.id.raws_menu_move_up_action,
                            context.getString(R.string.raws_menu_move_up)));
                if (position >= 0 && position + 1 < keys.size()
                        && groups.get(keys.get(position)).equals(groups.get(keys.get(position + 1))))
                    info.addAction(new AccessibilityNodeInfo.AccessibilityAction(R.id.raws_menu_move_down_action,
                            context.getString(R.string.raws_menu_move_down)));
            }
            @Override public boolean performAccessibilityAction(View host, int action, Bundle arguments) {
                if (action == R.id.raws_menu_move_up_action || action == R.id.raws_menu_move_down_action)
                    return moveEditorItem(list.getPositionForView(host), action == R.id.raws_menu_move_up_action ? -1 : 1,
                            keys, titles, checked, visible, list);
                return super.performAccessibilityAction(host, action, arguments);
            }
        });
    }
    void showEditor() {
        dismissEditor();
        RawSMenuModel<ListItem> state = new RawSMenuModel<>(store.read());
        state.bind(catalog);
        if (!state.writable()) return;
        List<String> keys = new ArrayList<>();
        for (String name : state.orderedKeys()) if (catalog.containsKey(name)) keys.add(name);
        CharSequence[] titles = new CharSequence[keys.size()];
        boolean[] checked = new boolean[keys.size()];
        Map<String, Boolean> visible = new HashMap<>();
        for (int i = 0; i < keys.size(); i++) {
            String name = keys.get(i);
            titles[i] = catalog.get(name).model.get(AppMenuItemProperties.TITLE);
            checked[i] = state.isVisible(name);
            visible.put(name, checked[i]);
        }
        boolean[] resetRequested = {false};
        AlertDialog dialog = new AlertDialog.Builder(context)
                .setTitle(R.string.raws_customize_menu)
                .setMultiChoiceItems(titles, checked, (ignored, which, selected) ->
                        visible.put(keys.get(which), selected))
                .setNegativeButton(android.R.string.cancel, (ignored, which) -> {})
                .setNeutralButton(R.string.raws_menu_reset, null)
                .setPositiveButton(R.string.raws_menu_save, null)
                .create();
        editorDialog = dialog;
        dialog.setOnDismissListener(ignored -> {
            if (editorDialog == dialog) {
                editorDialog = null;
                if (moveDialog != null) moveDialog.dismiss();
                moveDialog = null;
            }
        });
        dialog.setOnShowListener(ignored -> {
            ListView list = dialog.getListView();
            list.setContentDescription(context.getString(R.string.raws_menu_edit_hint));
            list.setTooltipText(context.getString(R.string.raws_menu_edit_hint));
            list.setOnKeyListener((view, code, event) -> {
                if (event.getAction() != KeyEvent.ACTION_DOWN || !event.isCtrlPressed()
                        || (code != KeyEvent.KEYCODE_DPAD_UP && code != KeyEvent.KEYCODE_DPAD_DOWN)) return false;
                return moveEditorItem(list.getSelectedItemPosition(), code == KeyEvent.KEYCODE_DPAD_UP ? -1 : 1,
                        keys, titles, checked, visible, list);
            });
            list.setOnHierarchyChangeListener(new ViewGroup.OnHierarchyChangeListener() {
                @Override public void onChildViewAdded(View parent, View child) {
                    addReorderAccessibility(child, list, keys, titles, checked, visible);
                }
                @Override public void onChildViewRemoved(View parent, View child) {}
            });
            for (int i = 0; i < list.getChildCount(); i++)
                addReorderAccessibility(list.getChildAt(i), list, keys, titles, checked, visible);
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(view -> {
                resetRequested[0] = true;
                keys.clear(); keys.addAll(catalog.keySet());
                for (int i = 0; i < keys.size(); i++) {
                    titles[i] = catalog.get(keys.get(i)).model.get(AppMenuItemProperties.TITLE);
                    visible.put(keys.get(i), true); checked[i] = true; list.setItemChecked(i, true);
                }
                list.invalidateViews();
            });
            list.setOnItemLongClickListener((parent, view, position, id) -> {
                moveDialog = new AlertDialog.Builder(context)
                        .setTitle(titles[position])
                        .setItems(new CharSequence[] {context.getString(R.string.raws_menu_move_up),
                                context.getString(R.string.raws_menu_move_down)}, (move, direction) -> {
                            if (editorDialog != dialog) return;
                            moveEditorItem(position, direction == 0 ? -1 : 1,
                                    keys, titles, checked, visible, list);
                        }).show();
                return true;
            });
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
                RawSMenuModel<ListItem>.Editor draft = state.edit();
                if (resetRequested[0]) draft.resetToDefaults();
                draft.reorderAvailable(keys);
                for (int i = 0; i < keys.size(); i++) {
                    draft.setVisible(keys.get(i), Boolean.TRUE.equals(visible.get(keys.get(i))));
                }
                dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                list.setEnabled(false);
                dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(false);
                PostTask.postTask(TaskTraits.USER_VISIBLE_MAY_BLOCK, () -> {
                    boolean saved = draft.save(store);
                    new Handler(Looper.getMainLooper()).post(() -> {
                        if (editorDialog != dialog) return;
                        if (saved) dialog.dismiss();
                        else {
                            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                            list.setEnabled(true);
                            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setEnabled(true);
                            dialog.setTitle(R.string.raws_menu_save_failed);
                        }
                    });
                });
            });
        });
        dialog.show();
    }
}
