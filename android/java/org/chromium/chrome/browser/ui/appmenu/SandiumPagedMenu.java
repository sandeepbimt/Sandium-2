package org.chromium.chrome.browser.ui.appmenu;

import android.app.AlertDialog;
import android.content.ClipData;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.view.DragEvent;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;

import org.chromium.ui.modelutil.MVCListAdapter.ListItem;
import org.chromium.ui.modelutil.MVCListAdapter.ModelList;
import org.chromium.ui.modelutil.PropertyModel;
import org.chromium.base.supplier.LazyOneshotSupplier;
import org.chromium.chrome.browser.ui.appmenu.internal.R;
import org.chromium.ui.modelutil.PropertyObservable;
import org.chromium.ui.modelutil.PropertyKey;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Original Sandium presentation over the live Chromium action model; no browser policy writes. */
@SuppressWarnings("UseSharedPreferencesManagerFromChromeCheck") // Private versioned UI layout, not browser preferences.
final class SandiumPagedMenu extends FrameLayout {
    private static final String PREF = "sandium.menu.layout.v1";
    private static final int PAGE_SIZE = 8;
    private final int mPanelColor, mTextColor, mSecondaryTextColor, mDividerColor;
    private final ModelList mModels;
    private final SandiumMenuMetadata.FooterProvider mFooter;
    private final View mNative;
    private final ListView mNativeList;
    private final LinkedHashMap<String, Entry> mCatalog = new LinkedHashMap<>();
    private SandiumMenuState mSaved;
    private SandiumMenuState mDraft;
    private int mPage;
    private boolean mAll;
    private int mRenderedScreen = -1;
    private int mRenderedPage = -1;
    private View mMotionPanel;
    private android.animation.ValueAnimator mPanelAnimator;
    private float mPanelAlpha = 1f;
    private boolean mNativeVisible;
    private float mDownX, mDownY;
    private String mDragging;
    private final Map<PropertyModel, LazyOneshotSupplier<Drawable>> mRequestedIcons = new java.util.IdentityHashMap<>();
    private final Set<PropertyModel> mObserved = new HashSet<>();
    private boolean mRefreshPending;
    private final Runnable mFooterChanged = () -> scheduleRefresh();
    private final Runnable mRefreshTask = () -> {
        mRefreshPending = false;
        if (mSaved != null && mDragging == null) refresh();
    };
    private final PropertyObservable.PropertyObserver<PropertyKey> mObserver = (source, key) -> {
        if (key == AppMenuItemProperties.TITLE || key == AppMenuItemProperties.ICON
                || key == AppMenuItemProperties.ENABLED || key == AppMenuItemProperties.CHECKED
                || key == AppMenuItemProperties.ADDITIONAL_ICONS
                || key == AppMenuItemProperties.ICON_SUPPLIER || key == AppMenuItemProperties.ICON_COLOR_RES
                || key == AppMenuItemProperties.ICON_NO_TINT || key == AppMenuItemProperties.ICON_SHOW_BADGE) scheduleRefresh();
    };
    private Runnable mResize;
    private Runnable mNativeReset;
    private java.util.function.BooleanSupplier mNativeDrillDown;
    private PendingNativeAction mPendingNativeAction;
    private long mLastPageDrag;
    private ScrollView mScroll;

    private static final class Entry {
        final PropertyModel model;
        final int row;
        final boolean nativeRow;
        Entry(PropertyModel model, int row, boolean nativeRow) {
            this.model = model; this.row = row; this.nativeRow = nativeRow;
        }
    }

    SandiumPagedMenu(Context context, ModelList models, View nativeContent, ListView nativeList, View footer) {
        super(context);
        mPanelColor = context.getColor(R.color.sandium_menu_surface_container);
        mTextColor = context.getColor(R.color.sandium_menu_on_surface);
        mSecondaryTextColor = context.getColor(R.color.sandium_menu_on_surface_variant);
        mDividerColor = context.getColor(R.color.sandium_menu_outline_variant);
        mFooter = footer instanceof SandiumMenuMetadata.FooterProvider
                ? (SandiumMenuMetadata.FooterProvider) footer : null;
        if (mFooter != null) SandiumMenuMetadata.watchFooter(mFooter, mFooterChanged);
        mModels = models; mNative = nativeContent; mNativeList = nativeList;
        setBackground(shape(mPanelColor, 12));
        setClipToOutline(true);
        refreshCatalog();
        Set<String> hidden = new HashSet<>();
        for (Map.Entry<String, Entry> e : mCatalog.entrySet()) {
            if (!SandiumMenuMetadata.wasVisible(e.getValue().model)) hidden.add(e.getKey());
        }
        mSaved = SandiumMenuState.load(context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                .getString("layout", ""), mCatalog.keySet(), hidden);
        render();
    }

    private String key(PropertyModel model) {
        if (!model.containsKey(AppMenuItemProperties.MENU_ITEM_ID)) return null;
        int id = model.get(AppMenuItemProperties.MENU_ITEM_ID);
        if (id == 0) return null; // Unstable external custom actions remain in the native menu.
        try { return getResources().getResourceEntryName(id); }
        catch (android.content.res.Resources.NotFoundException ex) { return null; }
    }

    private void add(PropertyModel model, int row, boolean nativeRow) {
        String key = key(model);
        if (key == null || key.equals("brave_customize_menu_id")) return;
        if (!model.containsKey(AppMenuItemProperties.TITLE)) return;
        CharSequence title = model.get(AppMenuItemProperties.TITLE);
        if (title == null || title.length() == 0) return;
        mCatalog.putIfAbsent(key, new Entry(model, row, nativeRow));
    }

    private void observe(PropertyModel model) {
        if (mObserved.add(model)) model.addObserver(mObserver);
    }
    private void scheduleRefresh() {
        if (!mRefreshPending) { mRefreshPending = true; post(mRefreshTask); }
    }
    @Override protected void onDetachedFromWindow() {
        for (PropertyModel model : mObserved) model.removeObserver(mObserver);
        mObserved.clear(); mRequestedIcons.clear(); removeCallbacks(mRefreshTask); mRefreshPending = false;
        if (mFooter != null) SandiumMenuMetadata.watchFooter(mFooter, null);
        if (mResize != null) removeCallbacks(mResize);
        clearPendingNativeAction();
        finishPanelMotion();
        super.onDetachedFromWindow();
    }
    private void refreshCatalog() {
        for (PropertyModel model : mObserved) model.removeObserver(mObserver);
        mObserved.clear();
        mCatalog.clear();
        for (int i = 0; i < mModels.size(); i++) {
            ListItem item = mModels.get(i);
            observe(item.model);
            if (item.type == AppMenuHandler.AppMenuItemType.DIVIDER
                    || item.type == AppMenuHandler.AppMenuItemType.HEADER
                    || item.type == AppMenuHandler.AppMenuItemType.SUBMENU_HEADER) continue;
            ModelList children = item.model.containsKey(AppMenuItemProperties.ADDITIONAL_ICONS)
                    ? item.model.get(AppMenuItemProperties.ADDITIONAL_ICONS) : null;
            if (children != null) for (ListItem child : children) observe(child.model);
            if (item.type == AppMenuHandler.AppMenuItemType.BUTTON_ROW && children != null) {
                for (ListItem child : children) add(child.model, i, false);
            } else {
                boolean nativeRow = item.type != AppMenuHandler.AppMenuItemType.STANDARD
                        && item.type != AppMenuHandler.AppMenuItemType.STANDARD_NO_ICON
                        && item.type != AppMenuHandler.AppMenuItemType.TITLE_BUTTON;
                String actionKey = key(item.model);
                if (("new_incognito_tab_menu_id".equals(actionKey)
                        || "new_incognito_window_menu_id".equals(actionKey))
                        && !(item.model.containsKey(AppMenuItemProperties.MANAGED)
                                && item.model.get(AppMenuItemProperties.MANAGED))) nativeRow = false;
                add(item.model, i, nativeRow);
            }
        }
        if (mFooter != null) for (ListItem item : mFooter.sandiumActions()) add(item.model, -1, false);
    }

    void refresh() {
        refreshCatalog();
        Set<String> legacy = new HashSet<>();
        for (Map.Entry<String, Entry> e : mCatalog.entrySet()) {
            if (!SandiumMenuMetadata.wasVisible(e.getValue().model)) legacy.add(e.getKey());
        }
        mSaved.reconcile(mCatalog.keySet(), legacy);
        if (mDraft != null) mDraft.reconcile(mCatalog.keySet(), legacy);
        if (!mNativeVisible) {
            int scrollY = mScroll == null ? 0 : mScroll.getScrollY();
            View focus = findFocus();
            Object focusTag = focus == null ? null : focus.getTag();
            View accessibilityFocus = accessibilityFocus(this);
            Object accessibilityTag = accessibilityFocus == null ? null : accessibilityFocus.getTag();
            render();
            post(() -> {
                if (mScroll != null) mScroll.scrollTo(0, scrollY);
                if (accessibilityTag != null) {
                    View restored = findViewWithTag(accessibilityTag);
                    if (restored != null) restored.performAccessibilityAction(
                            AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null);
                }
                if (focusTag != null) {
                    View restored = findViewWithTag(focusTag);
                    if (restored != null) restored.requestFocus();
                }
            });
        }
    }

    private static final String[] LIBRARY = {"all_bookmarks_menu_id", "open_history_menu_id", "downloads_menu_id", "preferences_id"};
    private boolean library(String key) {
        for (String name : LIBRARY) if (name.equals(key)) return true;
        return false;
    }
    private Set<String> editableKeys() {
        Set<String> keys = new java.util.LinkedHashSet<>(mCatalog.keySet());
        for (String key : LIBRARY) keys.remove(key);
        return keys;
    }
    private View accessibilityFocus(View view) {
        if (view.isAccessibilityFocused()) return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = accessibilityFocus(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }
    private SandiumMenuState state() { return mDraft == null ? mSaved : mDraft; }
    private boolean enabled(PropertyModel model) {
        return model.containsKey(AppMenuItemProperties.ENABLED)
                && model.get(AppMenuItemProperties.ENABLED);
    }
    private String title(Entry entry) {
        CharSequence title = entry.model.get(AppMenuItemProperties.TITLE);
        return title == null ? "" : title.toString();
    }
    private String s(int id, Object... args) { return getResources().getString(id, args); }
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius));
        return d;
    }
    private TextView text(String label, int size, int color) {
        TextView t = new TextView(getContext()); t.setText(label); t.setTextSize(size);
        t.setTextColor(color); t.setGravity(Gravity.CENTER); return t;
    }
    private TextView button(String label, String description, Runnable click) {
        TextView t = text(label, 16, mTextColor); t.setMinHeight(dp(48));
        t.setTag("control:" + description); t.setContentDescription(description); t.setFocusable(true); t.setOnClickListener(v -> click.run());
        return t;
    }
    private LinearLayout column() {
        LinearLayout l = new LinearLayout(getContext()); l.setOrientation(LinearLayout.VERTICAL); return l;
    }
    private LinearLayout row() {
        LinearLayout l = new LinearLayout(getContext()); l.setOrientation(LinearLayout.HORIZONTAL); return l;
    }
    private void weighted(LinearLayout row, View child) {
        row.addView(child, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
    }

    boolean handleBack() {
        if (mDraft != null) { mDraft = null; render(); return true; }
        if (mNativeVisible) { if (mNativeReset != null) mNativeReset.run(); mAll = true; render(); return true; }
        if (mAll) { mAll = false; render(); return true; }
        return false;
    }
    void setNativeDrillDown(java.util.function.BooleanSupplier supplier) { mNativeDrillDown = supplier; }
    void setNativeReset(Runnable reset) { mNativeReset = reset; }
    void setResizeListener(Runnable resize) { mResize = resize; }
    int preferredHeight(int available) {
        return Math.min(available, mAll || mDraft != null || mNativeVisible
                ? (int) (available * .88f) : dp(410));
    }
    private void finishPanelMotion() {
        if (mPanelAnimator != null) { mPanelAnimator.cancel(); mPanelAnimator = null; }
        mPanelAlpha = 1f;
        if (mMotionPanel != null) mMotionPanel.setAlpha(1f);
    }
    private void startPanelMotion() {
        finishPanelMotion();
        if (mDragging != null || !isAttachedToWindow()
                || !android.animation.ValueAnimator.areAnimatorsEnabled()) return;
        mPanelAlpha = 0f;
        if (mMotionPanel != null) mMotionPanel.setAlpha(0f);
        mPanelAnimator = android.animation.ValueAnimator.ofFloat(0f, 1f);
        mPanelAnimator.setDuration(120);
        mPanelAnimator.setInterpolator(new android.view.animation.LinearInterpolator());
        mPanelAnimator.addUpdateListener(animation -> {
            mPanelAlpha = (float) animation.getAnimatedValue();
            if (mMotionPanel != null) mMotionPanel.setAlpha(mPanelAlpha);
        });
        mPanelAnimator.start();
    }

    private void render() {
        // Fade only actual navigation, never network/model updates or drag reorders.
        int screen = mDraft != null ? 2 : mAll ? 1 : 0;
        boolean transition = mRenderedScreen != -1
                && (screen != mRenderedScreen || mPage != mRenderedPage || mNativeVisible);
        mRenderedScreen = screen; mRenderedPage = mPage;
        clearPendingNativeAction();
        removeAllViews(); mNativeVisible = false;
        LinearLayout panel = column(); panel.setPadding(dp(12), dp(8), dp(12), dp(8));
        addView(panel, new LayoutParams(-1, -1));
        // The sheet background stays opaque. Model refresh replaces only the
        // content target; the current animator/progress continues uninterrupted.
        mMotionPanel = panel;
        panel.setAlpha(mPanelAlpha);
        if (transition) startPanelMotion();
        LinearLayout heading = row();
        if (mDraft != null) {
            weighted(heading, button(s(R.string.sandium_menu_cancel), s(R.string.sandium_menu_cancel_edits), () -> { mDraft = null; render(); }));
            weighted(heading, text(s(R.string.sandium_menu_edit), 18, mTextColor));
            weighted(heading, button(s(R.string.sandium_menu_done), s(R.string.sandium_menu_save_edits), () -> {
                mSaved = mDraft; mDraft = null;
                getContext().getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                        .putString("layout", mSaved.serialize()).apply(); render();
            }));
        } else {
            weighted(heading, button(mAll ? "‹" : s(R.string.sandium_menu_all), mAll ? s(R.string.sandium_menu_back_paged) : s(R.string.sandium_menu_all),
                    () -> { mAll = !mAll; render(); }));
            weighted(heading, text(mAll ? s(R.string.sandium_menu_all) : "", 18, mTextColor));
            weighted(heading, button("+", s(R.string.sandium_menu_edit_description), () -> { mDraft = mSaved.copy(); render(); }));
        }
        panel.addView(heading);
        if (mResize != null) post(mResize);
        ScrollView scroll = new ScrollView(getContext()); mScroll = scroll; scroll.setFillViewport(false);
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout body = column(); scroll.addView(body);
        List<String> libraryKeys = new ArrayList<>();
        for (String key : LIBRARY) if (mCatalog.containsKey(key)) libraryKeys.add(key);
        grid(body, libraryKeys, false);
        View divider = new View(getContext()); divider.setBackgroundColor(mDividerColor);
        body.addView(divider, new LinearLayout.LayoutParams(-1, dp(1)));
        if (mDraft != null) {
            TextView instructions = text(s(R.string.sandium_menu_drag_hint), 13, mSecondaryTextColor);
            instructions.setPadding(0, dp(10), 0, dp(10)); body.addView(instructions);
        }
        List<String> visible = state().visibleKeys(editableKeys());
        int pages = Math.max(1, state().pageCount(editableKeys(), PAGE_SIZE));
        mPage = Math.max(0, Math.min(mPage, pages - 1));
        if (mAll && mDraft == null) {
            grid(body, new ArrayList<>(editableKeys()), false);
            body.addView(button(s(R.string.sandium_menu_native), s(R.string.sandium_menu_native_description),
                    () -> showNative(-1)));
        } else {
            grid(body, state().page(editableKeys(), mPage, PAGE_SIZE), false);
            LinearLayout pager = row();
            TextView previous = button("‹", s(R.string.sandium_menu_previous), () -> page(-1));
            previous.setEnabled(mPage > 0); dragPage(previous, -1); weighted(pager, previous);
            StringBuilder dots = new StringBuilder();
            for (int i = 0; i < pages; i++) dots.append(i == mPage ? "● " : "○ ");
            TextView indicator = text(dots.toString(), 14, mSecondaryTextColor);
            indicator.setContentDescription(s(R.string.sandium_menu_page_description, mPage + 1, pages));
            weighted(pager, indicator);
            TextView next = button("›", s(R.string.sandium_menu_next), () -> page(1));
            next.setEnabled(mPage < pages - 1); dragPage(next, 1); weighted(pager, next);
            body.addView(pager);
        }
        if (mDraft != null) {
            body.addView(text(s(R.string.sandium_menu_available), 15, mSecondaryTextColor));
            grid(body, mDraft.hiddenKeys(editableKeys()), true);
            body.addView(button(s(R.string.sandium_menu_reset), s(R.string.sandium_menu_reset_description), () -> {
                SandiumMenuState editing = mDraft;
                new AlertDialog.Builder(getContext()).setMessage(s(R.string.sandium_menu_reset_question))
                        .setNegativeButton(s(R.string.sandium_menu_cancel), null).setPositiveButton(s(R.string.sandium_menu_reset_confirm), (d, which) -> {
                            if (mDraft == null || mDraft != editing) return;
                            List<String> defaults = new ArrayList<>(mCatalog.keySet());
                            for (String known : mDraft.knownKeys()) if (!defaults.contains(known)) defaults.add(known);
                            mDraft = SandiumMenuState.reset(defaults, new HashSet<>()); mPage = 0; render();
                        }).show();
            }));
        }
    }

    private void requestIcon(PropertyModel model) {
        if (!model.containsKey(AppMenuItemProperties.ICON_SUPPLIER)) return;
        LazyOneshotSupplier<Drawable> supplier = model.get(AppMenuItemProperties.ICON_SUPPLIER);
        if (supplier == null || mRequestedIcons.get(model) == supplier) return;
        mRequestedIcons.put(model, supplier);
        supplier.onAvailable(drawable -> model.set(AppMenuItemProperties.ICON, drawable));
        supplier.get();
    }

    private void grid(LinearLayout parent, List<String> keys, boolean available) {
        int columns = getResources().getConfiguration().fontScale > 1.3f ? 2 : 4;
        LinearLayout line = null;
        for (int i = 0; i < keys.size(); i++) {
            if (i % columns == 0) { line = row(); parent.addView(line); }
            final String key = keys.get(i);
            Entry entry = mCatalog.get(key);
            LinearLayout tile = column(); tile.setGravity(Gravity.CENTER);
            tile.setPadding(dp(3), dp(10), dp(3), dp(10)); tile.setMinimumHeight(dp(96));
            ImageView icon = new ImageView(getContext());
            icon.setId(R.id.menu_item_icon);
            requestIcon(entry.model);
            Drawable drawable = entry.model.containsKey(AppMenuItemProperties.ICON)
                    ? entry.model.get(AppMenuItemProperties.ICON) : null;
            int level = drawable == null ? 0 : drawable.getLevel();
            if (drawable != null && drawable.getConstantState() != null) {
                drawable = drawable.getConstantState().newDrawable(getResources()).mutate();
                drawable.setLevel(level);
            }
            if (drawable == null) {
                TextView monogram = text(title(entry).isEmpty() ? "•" : title(entry).substring(0, 1), 22, mTextColor);
                tile.addView(monogram, new LinearLayout.LayoutParams(dp(26), dp(26)));
            }
            // Button-row models have fewer keys; normalize only presentation properties.
            PropertyModel iconModel = new PropertyModel.Builder(AppMenuItemProperties.ALL_KEYS)
                    .with(AppMenuItemProperties.ICON, drawable)
                    .with(AppMenuItemProperties.ICON_COLOR_RES,
                            entry.model.containsKey(AppMenuItemProperties.ICON_COLOR_RES)
                                    ? entry.model.get(AppMenuItemProperties.ICON_COLOR_RES) : 0)
                    .with(AppMenuItemProperties.ICON_NO_TINT,
                            entry.model.containsKey(AppMenuItemProperties.ICON_NO_TINT)
                                    && entry.model.get(AppMenuItemProperties.ICON_NO_TINT))
                    .with(AppMenuItemProperties.ICON_SHOW_BADGE,
                            drawable != null && entry.model.containsKey(AppMenuItemProperties.ICON_SHOW_BADGE)
                                    && entry.model.get(AppMenuItemProperties.ICON_SHOW_BADGE))
                    .build();
            icon.setEnabled(mDraft != null || enabled(entry.model));
            AppMenuItemViewBinder.bindStandardItem(iconModel, icon, AppMenuItemProperties.ICON);
            if (icon.getDrawable() != null) icon.getDrawable().setLevel(level);
            icon.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            tile.addView(icon, new LinearLayout.LayoutParams(dp(26), dp(26)));
            TextView label = text(title(entry), 12, mTextColor); label.setMaxLines(3);
            label.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            tile.addView(label, new LinearLayout.LayoutParams(-1, -2));
            tile.setTag("action:" + key); tile.setFocusable(true); tile.setContentDescription(title(entry));
            tile.setAlpha(enabled(entry.model) || mDraft != null ? 1 : .4f);
            if (mDraft != null && !library(key)) {
                tile.addView(button(available ? "+" : "−", s(available ? R.string.sandium_menu_add_action : R.string.sandium_menu_remove_action, title(entry)),
                        () -> { if (available) mDraft.show(key); else mDraft.hide(key); render(); }));
                tile.setOnClickListener(v -> editOptions(key));
                if (!available) {
                    tile.setOnLongClickListener(v -> {
                        mDragging = key;
                        boolean started = v.startDragAndDrop(ClipData.newPlainText("Sandium menu action", key),
                                new View.DragShadowBuilder(v), key, 0);
                        if (!started) mDragging = null;
                        return started;
                    });
                    tile.setOnDragListener((v, event) -> {
                        if (event.getAction() == DragEvent.ACTION_DRAG_ENDED) { mDragging = null; scheduleRefresh(); return true; }
                        if (!(event.getLocalState() instanceof String) || mDraft == null) return false;
                        if (event.getAction() == DragEvent.ACTION_DROP) {
                            String moving = (String) event.getLocalState();
                            if (!moving.equals(mDragging)) return false;
                            int destination = mDraft.visibleKeys(editableKeys()).indexOf(key);
                            mDraft.move(moving, destination, editableKeys()); render(); return true;
                        }
                        return true;
                    });
                }
            } else {
                tile.setEnabled(enabled(entry.model)); tile.setOnClickListener(v -> activate(key));
                ModelList secondary = entry.model.containsKey(AppMenuItemProperties.ADDITIONAL_ICONS)
                        ? entry.model.get(AppMenuItemProperties.ADDITIONAL_ICONS) : null;
                if (secondary != null && secondary.size() == 1) {
                    PropertyModel action = secondary.get(0).model;
                    boolean checkable = action.containsKey(AppMenuItemProperties.CHECKABLE)
                            && action.get(AppMenuItemProperties.CHECKABLE);
                    String caption = checkable ? (action.get(AppMenuItemProperties.CHECKED) ? s(R.string.sandium_menu_on) : s(R.string.sandium_menu_off)) : s(R.string.sandium_menu_options);
                    TextView control = button(caption, title(entry) + " " + caption, () -> {
                        refreshCatalog();
                        Entry current = mCatalog.get(key);
                        if (current == null || !enabled(current.model)) return;
                        ModelList liveChildren = current.model.get(AppMenuItemProperties.ADDITIONAL_ICONS);
                        if (liveChildren == null || liveChildren.size() != 1) return;
                        PropertyModel liveAction = liveChildren.get(0).model;
                        if (!enabled(liveAction)) return;
                        AppMenuClickHandler handler = current.model.get(AppMenuItemProperties.CLICK_HANDLER);
                        if (handler != null) handler.onItemClick(liveAction, null);
                    });
                    control.setEnabled(enabled(action)); tile.addView(control);
                }
                tile.setOnLongClickListener(v -> { mDraft = mSaved.copy(); render(); return true; });
                if (mDraft != null) { disableTree(tile); tile.setAlpha(.45f); }
                tile.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                    @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                        super.onInitializeAccessibilityNodeInfo(host, info);
                        info.setClassName("android.widget.Button");
                        if (entry.model.containsKey(AppMenuItemProperties.CHECKABLE)
                                && entry.model.get(AppMenuItemProperties.CHECKABLE)) {
                            info.setCheckable(true); info.setChecked(entry.model.get(AppMenuItemProperties.CHECKED));
                        }
                    }
                });
            }
            weighted(line, tile);
        }
        if (line != null) for (int i = keys.size() % columns; i != 0 && i < columns; i++) weighted(line, new View(getContext()));
    }

    private void disableTree(View view) {
        view.setEnabled(false); view.setFocusable(false); view.setClickable(false); view.setLongClickable(false);
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) disableTree(group.getChildAt(i));
        }
    }
    private void activate(String key) {
        // Resolve again: page/permissions may have changed while the popup was open.
        refreshCatalog(); Entry entry = mCatalog.get(key);
        if (entry == null || !enabled(entry.model)) { refresh(); return; }
        if (entry.nativeRow) {
            showNative(entry.row);
            if (entry.model.containsKey(AppMenuItemWithSubmenuProperties.CLICK_LISTENER)
                    && entry.model.containsKey(AppMenuItemWithSubmenuProperties.SUBMENU_PROVIDER)
                    && mNativeDrillDown != null && mNativeDrillDown.getAsBoolean()) {
                mPendingNativeAction = new PendingNativeAction(key);
                mNativeList.addOnLayoutChangeListener(mPendingNativeAction);
                mNativeList.post(mPendingNativeAction);
                mNativeList.postDelayed(mPendingNativeAction.mExpire, 500);
            }
            return;
        }
        if (SandiumMenuMetadata.dispatch(entry.model)) return;
        AppMenuClickHandler handler = entry.model.containsKey(AppMenuItemProperties.CLICK_HANDLER)
                ? entry.model.get(AppMenuItemProperties.CLICK_HANDLER) : null;
        if (handler != null) handler.onItemClick(entry.model, null);
    }

    private void clearPendingNativeAction() {
        if (mPendingNativeAction == null) return;
        mNativeList.removeOnLayoutChangeListener(mPendingNativeAction);
        mNativeList.removeCallbacks(mPendingNativeAction);
        mNativeList.removeCallbacks(mPendingNativeAction.mExpire);
        mPendingNativeAction = null;
    }

    /** Activate an existing hierarchical listener once, using its attached native row anchor. */
    private final class PendingNativeAction implements View.OnLayoutChangeListener, Runnable {
        private final String mKey;
        private int mAttempts;
        private final long mDeadline = android.os.SystemClock.uptimeMillis() + 500;
        final Runnable mExpire = () -> { if (mPendingNativeAction == this) clearPendingNativeAction(); };
        PendingNativeAction(String key) { mKey = key; }
        @Override public void onLayoutChange(View v, int l, int t, int r, int b,
                int oldL, int oldT, int oldR, int oldB) { run(); }
        @Override public void run() {
            if (mPendingNativeAction != this || !mNativeVisible) return;
            if (android.os.SystemClock.uptimeMillis() >= mDeadline) { clearPendingNativeAction(); return; }
            if (!mNativeList.isAttachedToWindow() || mNativeDrillDown == null
                    || !mNativeDrillDown.getAsBoolean()) { clearPendingNativeAction(); return; }
            refreshCatalog();
            Entry current = mCatalog.get(mKey);
            if (current == null || !enabled(current.model)
                    || !current.model.containsKey(AppMenuItemWithSubmenuProperties.CLICK_LISTENER)) {
                clearPendingNativeAction(); return;
            }
            int position = current.row + mNativeList.getHeaderViewsCount();
            View row = mNativeList.getChildAt(position - mNativeList.getFirstVisiblePosition());
            int id = current.model.get(AppMenuItemProperties.MENU_ITEM_ID);
            View anchor = row == null ? null : row.findViewById(id);
            if (anchor == null || !anchor.isAttachedToWindow() || anchor.getHeight() == 0) {
                if (++mAttempts >= 3) clearPendingNativeAction();
                return; // Safe fallback: native controls remain available; never guess an anchor.
            }
            View.OnClickListener listener = current.model.get(AppMenuItemWithSubmenuProperties.CLICK_LISTENER);
            clearPendingNativeAction();
            if (listener != null && anchor.isEnabled()) listener.onClick(anchor);
        }
    }

    private void showNative(int row) {
        finishPanelMotion(); mMotionPanel = null;
        clearPendingNativeAction();
        mNativeVisible = true;
        if (mNativeReset != null) mNativeReset.run();
        removeAllViews();
        if (mNative.getParent() instanceof ViewGroup) ((ViewGroup) mNative.getParent()).removeView(mNative);
        LinearLayout content = column();
        content.addView(button(s(R.string.sandium_menu_back_all), s(R.string.sandium_menu_back_description), () -> { if (mNativeReset != null) mNativeReset.run(); mAll = true; render(); }));
        content.addView(mNative, new LinearLayout.LayoutParams(-1, 0, 1));
        addView(content, new LayoutParams(-1, -1));
        if (mResize != null) post(mResize);
        if (row >= 0) mNativeList.setSelection(row + mNativeList.getHeaderViewsCount());
    }

    private void page(int direction) {
        int count = Math.max(1, state().pageCount(editableKeys(), PAGE_SIZE));
        mPage = Math.max(0, Math.min(count - 1, mPage + direction)); render();
    }
    private void dragPage(View v, int direction) {
        v.setOnDragListener((target, event) -> {
            if (mDraft == null || mDragging == null || !mDragging.equals(event.getLocalState())) return false;
            if (event.getAction() == DragEvent.ACTION_DRAG_ENTERED
                    && android.os.SystemClock.uptimeMillis() - mLastPageDrag > 650) {
                mLastPageDrag = android.os.SystemClock.uptimeMillis(); page(direction);
            }
            return true;
        });
    }
    private void editOptions(String key) {
        Entry entry = mCatalog.get(key); if (entry == null || mDraft == null) return;
        final boolean hidden = mDraft.isHidden(key);
        String[] options = hidden ? new String[] {s(R.string.sandium_menu_add)} : new String[] {
                s(R.string.sandium_menu_earlier), s(R.string.sandium_menu_later), s(R.string.sandium_menu_previous_page), s(R.string.sandium_menu_next_page), s(R.string.sandium_menu_remove)};
        new AlertDialog.Builder(getContext()).setTitle(title(entry)).setItems(options, (dialog, which) -> {
            if (mDraft == null) return;
            if (hidden) mDraft.show(key);
            else {
                int index = mDraft.visibleKeys(editableKeys()).indexOf(key);
                if (which == 4) mDraft.hide(key);
                else mDraft.move(key, index + new int[] {-1, 1, -PAGE_SIZE, PAGE_SIZE}[which], editableKeys());
            }
            render();
        }).show();
    }
    @Override public boolean dispatchDragEvent(DragEvent event) {
        boolean handled = super.dispatchDragEvent(event);
        if (event.getAction() == DragEvent.ACTION_DRAG_ENDED) {
            mDragging = null; scheduleRefresh();
        }
        return handled;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) clearPendingNativeAction();
        return super.dispatchKeyEvent(event);
    }
    @Override public boolean onInterceptTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) clearPendingNativeAction();
        if (mNativeVisible || mAll || mDraft != null) return super.onInterceptTouchEvent(event);
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
            mDownX = event.getX(); mDownY = event.getY();
        } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE
                && Math.abs(event.getX() - mDownX) > dp(48)
                && Math.abs(event.getX() - mDownX) > Math.abs(event.getY() - mDownY) * 1.5f) return true;
        return super.onInterceptTouchEvent(event);
    }
    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_UP) {
            float distance = event.getX() - mDownX;
            if (Math.abs(distance) > dp(48)) {
                int direction = distance < 0 ? 1 : -1;
                if (getLayoutDirection() == LAYOUT_DIRECTION_RTL) direction = -direction;
                page(direction);
            }
            return true;
        }
        return true;
    }
}
