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
    private static final String ALL_MENU = "sandium:all-menu";
    private boolean mAllMenu;
    private final int mGroupColor, mPanelColor, mTextColor, mSecondaryTextColor, mDividerColor, mAccentColor;
    private final ModelList mModels;
    private final SandiumMenuMetadata.FooterProvider mFooter;
    private final View mNative;
    private final ListView mNativeList;
    private int mUncataloguedNativeRow = -1;
    private final LinkedHashMap<String, Entry> mCatalog = new LinkedHashMap<>();
    private SandiumMenuState mSaved;
    private SandiumMenuState mDraft;
    private SandiumMenuState mPersisted;
    private int mPage;
    private int mRenderedScreen = -1;
    private int mRenderedPage = -1;
    private View mMotionPanel;
    private FrameLayout mPageViewport;
    private View mPageContent;
    private View mOutgoingPage;
    private android.animation.ValueAnimator mPageAnimator;
    private int mPageMotionGeneration;
    private android.animation.ValueAnimator mPanelAnimator;
    private android.animation.ValueAnimator mEntranceAnimator;
    private float mPanelAlpha = 1f;
    private boolean mNativeVisible;
    private float mDownX, mDownY;
    private boolean mSwipeEligible;
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
    private int mDragPageTarget = -1;
    private Runnable mDragPageTask;
    private ScrollView mScroll;
    private LinearLayout mHeading, mBody;

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
        mGroupColor = context.getColor(R.color.sandium_menu_group_surface);
        mPanelColor = context.getColor(R.color.sandium_menu_surface_container);
        mTextColor = context.getColor(R.color.sandium_menu_on_surface);
        mSecondaryTextColor = context.getColor(R.color.sandium_menu_on_surface_variant);
        mDividerColor = context.getColor(R.color.sandium_menu_outline_variant);
        mAccentColor = context.getColor(R.color.sandium_menu_accent);
        mFooter = footer instanceof SandiumMenuMetadata.FooterProvider
                ? (SandiumMenuMetadata.FooterProvider) footer : null;
        if (mFooter != null) SandiumMenuMetadata.watchFooter(mFooter, mFooterChanged);
        mModels = models; mNative = nativeContent; mNativeList = nativeList;
        setBackground(shape(mPanelColor, 16));
        setClipToOutline(true);
        refreshCatalog();
        Set<String> hidden = new HashSet<>();
        for (Map.Entry<String, Entry> e : mCatalog.entrySet()) {
            if (!SandiumMenuMetadata.wasVisible(e.getValue().model)) hidden.add(e.getKey());
        }
        mSaved = SandiumMenuState.load(context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                .getString("layout", ""), mCatalog.keySet(), hidden);
        mPersisted = mSaved.copy();
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
        if ("brave_customize_menu_id".equals(key)
                || "default_browser_promo_menu_id".equals(key)) return;
        CharSequence title = model.containsKey(AppMenuItemProperties.TITLE)
                ? model.get(AppMenuItemProperties.TITLE) : null;
        if (key == null || title == null || title.length() == 0) {
            // Do not silently strand conditional/custom native controls lacking stable tile IDs.
            // Explicitly excluded actions above never create this fallback.
            if (row >= 0 && mUncataloguedNativeRow < 0) mUncataloguedNativeRow = row;
            return;
        }
        mCatalog.putIfAbsent(key, new Entry(model, row, nativeRow));
    }

    private void observe(PropertyModel model) {
        if (mObserved.add(model)) model.addObserver(mObserver);
    }
    private void scheduleRefresh() {
        if (!mRefreshPending) { mRefreshPending = true; post(mRefreshTask); }
    }
    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        finishEntranceMotion();
        if (org.chromium.base.SysUtils.isLowEndDevice()
                || !android.animation.ValueAnimator.areAnimatorsEnabled()) return;
        // Own the opening fade: OEM PopupWindow window-animation styles can be skipped.
        // Set before the first draw; no translation, scale, delayed input or hidden controls.
        setAlpha(0f);
        mEntranceAnimator = android.animation.ValueAnimator.ofFloat(0f, 1f);
        mEntranceAnimator.setDuration(100);
        mEntranceAnimator.setInterpolator(new android.view.animation.LinearInterpolator());
        mEntranceAnimator.addUpdateListener(animation -> setAlpha((float) animation.getAnimatedValue()));
        mEntranceAnimator.addListener(new android.animation.AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(android.animation.Animator animation) {
                if (mEntranceAnimator == animation) {
                    mEntranceAnimator = null;
                    setAlpha(1f);
                }
            }
        });
        mEntranceAnimator.start();
    }
    private void finishEntranceMotion() {
        if (mEntranceAnimator != null) {
            android.animation.ValueAnimator animation = mEntranceAnimator;
            mEntranceAnimator = null;
            animation.cancel();
        }
        setAlpha(1f);
    }
    @Override protected void onDetachedFromWindow() {
        finishEntranceMotion();
        cancelDragPage(); mDragging = null;
        for (PropertyModel model : mObserved) model.removeObserver(mObserver);
        mObserved.clear(); mRequestedIcons.clear(); removeCallbacks(mRefreshTask); mRefreshPending = false;
        if (mFooter != null) SandiumMenuMetadata.watchFooter(mFooter, null);
        if (mResize != null) removeCallbacks(mResize);
        clearPendingNativeAction();
        finishPanelMotion(); finishPageMotion();
        super.onDetachedFromWindow();
    }
    private void refreshCatalog() {
        for (PropertyModel model : mObserved) model.removeObserver(mObserver);
        mObserved.clear();
        mCatalog.clear();
        mUncataloguedNativeRow = -1;
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
    // Presentation-only short names; native titles remain the accessibility/action names.
    private String tileTitle(String key, Entry entry) {
        switch (key) {
            case "new_incognito_tab_menu_id": case "new_incognito_window_menu_id": return s(R.string.sandium_menu_private_tab);
            case "add_to_group_menu_id": return s(R.string.sandium_menu_group_tab);
            case "reader_mode_menu_id": return s(R.string.sandium_menu_reader);
            case "translate_id": return s(R.string.sandium_menu_translate);
            case "universal_install": return s(R.string.sandium_menu_install);
            case "brave_shred_id": return s(R.string.sandium_menu_shred);
            case "sandium_add_home_shortcut": return s(R.string.sandium_menu_add_home);
            case "forward_menu_id": return s(R.string.sandium_menu_forward);
            case "bookmark_this_page_id": return "Bookmark this page".equals(title(entry))
                    ? s(R.string.sandium_menu_bookmark) : title(entry); // Preserve Edit bookmark.
            case "download_page_id": return s(R.string.sandium_menu_save_page);
            case "home_menu_id": return s(R.string.sandium_menu_home);
            case "reload_menu_id": return "Reload this page".equals(title(entry))
                    ? s(R.string.sandium_menu_reload) : title(entry); // Preserve Stop loading.
            default: return title(entry);
        }
    }
    private int columns() { return getResources().getConfiguration().fontScale > 1.3f ? 2 : 4; }
    private int labelHeight() {
        TextView sample = text("", 12, mTextColor);
        sample.setIncludeFontPadding(false);
        return Math.max(dp(48) + sample.getLineHeight(), sample.getLineHeight() * 2);
    }
    private int tileHeight() { return dp(26 + 4 + 28 + 10) + labelHeight(); }
    private TextView tileLabel(String value) {
        TextView label = text(value, 12, mTextColor);
        label.setIncludeFontPadding(false);
        label.setGravity(Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        label.setMaxLines(2);
        label.setEllipsize(android.text.TextUtils.TruncateAt.END);
        label.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        return label;
    }
    private LinearLayout tile() {
        LinearLayout tile = column();
        tile.setGravity(Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        tile.setPadding(dp(3), dp(28), dp(3), dp(10));
        tile.setMinimumHeight(tileHeight());
        bindPressFeedback(tile);
        return tile;
    }
    private void addTileLabel(LinearLayout tile, View label) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, labelHeight());
        params.topMargin = dp(4);
        tile.addView(label, params);
    }
    private Drawable allMenuIcon() {
        return new Drawable() {
            private final android.graphics.Paint paint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
            private int alpha = 255;
            @Override public void draw(android.graphics.Canvas canvas) {
                paint.setColor(mTextColor); paint.setAlpha(alpha); paint.setStyle(android.graphics.Paint.Style.STROKE);
                float unit = Math.min(getBounds().width(), getBounds().height()) / 26f;
                paint.setStrokeWidth(1.7f * unit);
                for (int row = 0; row < 3; row++) for (int col = 0; col < 3; col++) {
                    float x = getBounds().left + (3 + col * 7) * unit;
                    float y = getBounds().top + (3 + row * 7) * unit;
                    canvas.drawRoundRect(x, y, x + 5 * unit, y + 5 * unit, unit, unit, paint);
                }
            }
            @Override public void setAlpha(int value) { alpha = value; invalidateSelf(); }
            @Override public void setColorFilter(android.graphics.ColorFilter filter) { paint.setColorFilter(filter); }
            @Override public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
        };
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
    private void bindPressFeedback(View view) {
        // Browser-owned controls get native, bounded feedback without changing geometry,
        // delaying dispatch, intercepting gestures or repeatedly animating their content.
        int pressed = (mAccentColor & 0x00ffffff) | 0x24000000;
        android.graphics.drawable.StateListDrawable states =
                new android.graphics.drawable.StateListDrawable();
        states.addState(new int[] {-android.R.attr.state_enabled}, shape(Color.TRANSPARENT, 12));
        states.addState(new int[] {android.R.attr.state_pressed}, shape(pressed, 12));
        states.addState(new int[] {android.R.attr.state_focused}, shape(pressed, 12));
        states.addState(new int[] {}, shape(Color.TRANSPARENT, 12));
        if (org.chromium.base.SysUtils.isLowEndDevice()
                || !android.animation.ValueAnimator.areAnimatorsEnabled()) {
            view.setBackground(states);
        } else {
            // Focus remains visible for keyboard users; only pressed ripple uses native timing.
            android.graphics.drawable.StateListDrawable focus =
                    new android.graphics.drawable.StateListDrawable();
            focus.addState(new int[] {-android.R.attr.state_enabled}, shape(Color.TRANSPARENT, 12));
            focus.addState(new int[] {android.R.attr.state_focused}, shape(pressed, 12));
            focus.addState(new int[] {}, shape(Color.TRANSPARENT, 12));
            view.setBackground(new android.graphics.drawable.RippleDrawable(
                    android.content.res.ColorStateList.valueOf(pressed), focus,
                    shape(Color.WHITE, 12)));
        }
    }

    private TextView button(String label, String description, Runnable click) {
        TextView t = text(label, 12, mTextColor); t.setMinHeight(dp(48));
        bindPressFeedback(t);
        t.setTag("control:" + description); t.setContentDescription(description); t.setFocusable(true); t.setOnClickListener(v -> click.run());
        return t;
    }
    private LinearLayout column() {
        LinearLayout l = new LinearLayout(getContext()); l.setOrientation(LinearLayout.VERTICAL); return l;
    }
    private LinearLayout group(LinearLayout parent) {
        LinearLayout group = column();
        group.setBackground(shape(mGroupColor, 12));
        group.setPadding(dp(4), dp(4), dp(4), dp(4));
        // Decorative surface only: do not intercept item clicks, drags or accessibility.
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.bottomMargin = dp(10);
        parent.addView(group, params);
        return group;
    }
    private LinearLayout row() {
        LinearLayout l = new LinearLayout(getContext()); l.setOrientation(LinearLayout.HORIZONTAL); return l;
    }
    private void weighted(LinearLayout row, View child) {
        row.addView(child, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
    }

    // Completed edits are durable before the UI acknowledges them. Android apply() only
    // queues disk I/O, which can be lost when Exit/process termination follows an edit.
    // This bounded layout write is performed only on user edits, never during scrolling.
    private boolean writeLayout(SandiumMenuState value) {
        android.os.StrictMode.ThreadPolicy policy = android.os.StrictMode.allowThreadDiskWrites();
        boolean saved;
        try {
            saved = getContext().getApplicationContext()
                    .getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                    .putString("layout", value.serialize()).commit();
        } finally {
            android.os.StrictMode.setThreadPolicy(policy);
        }
        if (saved) mPersisted = value.copy();
        else android.widget.Toast.makeText(getContext(), R.string.sandium_menu_save_failed,
                android.widget.Toast.LENGTH_LONG).show();
        return saved;
    }

    private void persistDraft() {
        if (mDraft != null && !writeLayout(mDraft)) mDraft = mPersisted.copy();
    }

    private void finishEditing() {
        if (mDraft == null) return;
        // Also retry any prior failed write. Cancel, unlike Back/dismiss, restores mSaved.
        if (writeLayout(mDraft)) { mSaved = mDraft; mDraft = null; }
    }

    boolean handleBack() {
        if (mDraft != null) { finishEditing(); render(); return true; }
        if (mAllMenu && !mNativeVisible) { mAllMenu = false; render(); return true; }
        if (mNativeVisible) { if (mNativeReset != null) mNativeReset.run(); render(); return true; }
        return false;
    }
    void setNativeDrillDown(java.util.function.BooleanSupplier supplier) { mNativeDrillDown = supplier; }
    void setNativeReset(Runnable reset) { mNativeReset = reset; }
    void setResizeListener(Runnable resize) { mResize = resize; }
    int preferredHeight(int width, int available) {
        // One sheet envelope for quick pages, directory, editor and native fallback.
        // Only window/font configuration changes it, never current labels or action count.
        int rows = (LIBRARY.length + columns() - 1) / columns()
                + (PAGE_SIZE + columns() - 1) / columns();
        return Math.max(1, Math.min(available, dp(16 + 48 + 36 + 48) + rows * tileHeight()));
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

    private void finishPageMotion() {
        ++mPageMotionGeneration;
        if (mPageAnimator != null) { mPageAnimator.cancel(); mPageAnimator = null; }
        if (mPageContent != null) mPageContent.setTranslationX(0f);
        if (mOutgoingPage != null && mOutgoingPage.getParent() instanceof ViewGroup) {
            ((ViewGroup) mOutgoingPage.getParent()).removeView(mOutgoingPage);
        }
        mOutgoingPage = null;
    }

    private void slidePage(View oldPage, int direction) {
        if (oldPage == null || mPageContent == null || mPageViewport == null
                || mDragging != null || !isAttachedToWindow()
                || !android.animation.ValueAnimator.areAnimatorsEnabled()) return;
        if (oldPage.getParent() instanceof ViewGroup) {
            ((ViewGroup) oldPage.getParent()).removeView(oldPage);
        }
        // Retain the outgoing grid until the incoming grid settles; fixed header never moves.
        disableTree(oldPage);
        oldPage.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        mOutgoingPage = oldPage;
        FrameLayout viewport = mPageViewport;
        View incoming = mPageContent;
        viewport.addView(oldPage, 0, new FrameLayout.LayoutParams(-1, -2));
        int initialSign = getLayoutDirection() == LAYOUT_DIRECTION_RTL ? -direction : direction;
        incoming.setTranslationX(initialSign * Math.max(1, getWidth()));
        int generation = mPageMotionGeneration;
        viewport.post(() -> {
            if (generation != mPageMotionGeneration || viewport != mPageViewport
                    || !viewport.isAttachedToWindow()) return;
            if (!android.animation.ValueAnimator.areAnimatorsEnabled()) {
                finishPageMotion(); return;
            }
            float width = viewport.getWidth();
            int sign = getLayoutDirection() == LAYOUT_DIRECTION_RTL ? -direction : direction;
            incoming.setTranslationX(sign * width);
            mPageAnimator = android.animation.ValueAnimator.ofFloat(0f, 1f);
            mPageAnimator.setDuration(180);
            mPageAnimator.setInterpolator(new android.view.animation.DecelerateInterpolator());
            mPageAnimator.addUpdateListener(animation -> {
                float progress = (float) animation.getAnimatedValue();
                incoming.setTranslationX(sign * width * (1f - progress));
                oldPage.setTranslationX(-sign * width * progress);
            });
            mPageAnimator.addListener(new android.animation.AnimatorListenerAdapter() {
                @Override public void onAnimationEnd(android.animation.Animator animation) {
                    if (generation == mPageMotionGeneration) finishPageMotion();
                }
            });
            mPageAnimator.start();
        });
    }

    private void render() {
        // Fade only actual navigation, never network/model updates or drag reorders.
        int screen = mDraft != null ? 2 : mAllMenu ? 1 : 0;
        int pageDirection = Integer.compare(mPage, mRenderedPage);
        boolean pageTransition = mRenderedScreen == screen && mRenderedPage >= 0
                && mPage != mRenderedPage && !mNativeVisible && mDragging == null;
        finishPageMotion();
        View oldPage = pageTransition ? mPageContent : null;
        mPageViewport = null; mPageContent = null;
        boolean transition = mRenderedScreen != -1
                && (screen != mRenderedScreen || mNativeVisible);
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
        LinearLayout heading = row(); mHeading = heading;
        heading.setMinimumHeight(dp(48));
        if (mDraft != null) {
            weighted(heading, button(s(R.string.sandium_menu_cancel), s(R.string.sandium_menu_cancel_edits), () -> {
                if (writeLayout(mSaved)) { mDraft = null; render(); }
            }));
            // A plain View with WRAP_CONTENT uses the parent's available height.
            // Keep this empty title slot bounded or the header consumes the editor body.
            heading.addView(new View(getContext()), new LinearLayout.LayoutParams(0, 1, 1));
            weighted(heading, button(s(R.string.sandium_menu_done), s(R.string.sandium_menu_save_edits), () -> {
                finishEditing(); render();
            }));
        } else {
            // Only show a native escape hatch when an unrepresentable custom action exists.
            if (mUncataloguedNativeRow >= 0) {
                heading.addView(button(s(R.string.sandium_menu_native),
                        s(R.string.sandium_menu_native_description),
                        () -> showNative(mUncataloguedNativeRow)));
            }
            {
                if (mAllMenu) {
                    heading.addView(button(s(R.string.sandium_menu_back_all),
                            s(R.string.sandium_menu_back_description),
                            () -> { mAllMenu = false; render(); }), new LinearLayout.LayoutParams(dp(64), dp(48)));
                } else {
                    heading.addView(new View(getContext()), new LinearLayout.LayoutParams(dp(64), 1));
                }
                TextView title = text(s(mAllMenu ? R.string.sandium_menu_all : R.string.sandium_menu_title), 16, mTextColor);
                title.setGravity(Gravity.CENTER);
                heading.addView(title, new LinearLayout.LayoutParams(0, dp(48), 1));
                TextView editAction = button(s(R.string.sandium_menu_edit),
                        s(R.string.sandium_menu_edit_description),
                        () -> { mDraft = mSaved.copy(); render(); });
                editAction.setMinWidth(dp(64));
                LinearLayout.LayoutParams editParams = new LinearLayout.LayoutParams(dp(64), dp(48));
                heading.addView(editAction, editParams);
            }

        }
        panel.addView(heading);
        if (mResize != null && mDragging == null) post(mResize);
        ScrollView scroll = new ScrollView(getContext()); mScroll = scroll; scroll.setFillViewport(false);
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout body = column(); mBody = body; scroll.addView(body);
        List<String> libraryKeys = new ArrayList<>();
        for (String key : LIBRARY) if (mCatalog.containsKey(key)) libraryKeys.add(key);
        LinearLayout libraryGroup = group(body);
        grid(libraryGroup, libraryKeys, false);
        LinearLayout actionsGroup = group(body);
        if (mDraft != null) {
            TextView instructions = text(s(R.string.sandium_menu_drag_hint), 13, mSecondaryTextColor);
            instructions.setPadding(0, dp(10), 0, dp(10)); actionsGroup.addView(instructions);
        }
        if (mAllMenu && mDraft == null) {
            // Browse every catalogued action using its live enabled/managed state.
            // Hidden means hidden from the quick pages, not removed from this directory.
            List<String> directory = new ArrayList<>();
            Set<String> available = editableKeys();
            for (String key : mSaved.knownKeys()) if (available.contains(key)) directory.add(key);
            grid(actionsGroup, directory, false);
            return;
        }
        List<String> visible = quickKeys();
        int pages = quickPageCount();
        mPage = Math.max(0, Math.min(mPage, pages - 1));
        { // Paged menu/editor share exactly the same indicator geometry.
            FrameLayout viewport = new FrameLayout(getContext());
            viewport.setClipChildren(true); viewport.setClipToPadding(true);
            // A sparse final page must not pull the editor's available-actions region upward.
            viewport.setMinimumHeight(((PAGE_SIZE + columns() - 1) / columns()) * tileHeight());
            LinearLayout pageGrid = column();
            grid(pageGrid, visible.subList(mPage * PAGE_SIZE, Math.min(visible.size(), (mPage + 1) * PAGE_SIZE)), false);
            viewport.addView(pageGrid, new FrameLayout.LayoutParams(-1, -2));
            actionsGroup.addView(viewport);
            mPageViewport = viewport; mPageContent = pageGrid;
            if (pageTransition) slidePage(oldPage, pageDirection);
            LinearLayout pager = row(); pager.setGravity(Gravity.CENTER);
            // Small Edge-style marks with full 48dp touch targets, also keyboard/TalkBack reachable.
            for (int i = 0; i < pages; i++) {
                final int destination = i;
                FrameLayout target = new FrameLayout(getContext());
                target.setFocusable(true); target.setClickable(true);
                bindPressFeedback(target);
                target.setTag("page:" + i);
                target.setContentDescription(s(R.string.sandium_menu_page_description, i + 1, pages));
                target.setSelected(i == mPage);
                target.setOnClickListener(v -> page(destination - mPage));
                target.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                    @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                        super.onInitializeAccessibilityNodeInfo(host, info);
                        info.setClassName("android.widget.Button");
                    }
                });
                View mark = new View(getContext());
                mark.setBackground(shape(i == mPage ? mAccentColor : mDividerColor, 2));
                mark.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                // Two marks sit together around their shared seam (8dp visual gap),
                // while each retains its own non-overlapping 48dp accessible hit target.
                FrameLayout.LayoutParams markParams = new FrameLayout.LayoutParams(dp(20), dp(3), Gravity.CENTER);
                if (pages == 2) {
                    markParams.gravity = Gravity.CENTER_VERTICAL | (i == 0 ? Gravity.END : Gravity.START);
                    if (i == 0) markParams.setMarginEnd(dp(4));
                    else markParams.setMarginStart(dp(4));
                }
                target.addView(mark, markParams);
                pager.addView(target, new LinearLayout.LayoutParams(dp(48), dp(48)));
            }
            // Horizontal scrolling keeps every page selector accessible for large customized menus.
            android.widget.HorizontalScrollView pagerScroll = new android.widget.HorizontalScrollView(getContext());
            pagerScroll.setHorizontalScrollBarEnabled(false); pagerScroll.setFillViewport(true);
            pagerScroll.addView(pager);
            actionsGroup.addView(pagerScroll);
        }
        if (mDraft != null) {
            LinearLayout availableGroup = group(body);
            availableGroup.addView(text(s(R.string.sandium_menu_available), 15, mSecondaryTextColor));
            grid(availableGroup, mDraft.hiddenKeys(editableKeys()), true);
            availableGroup.addView(button(s(R.string.sandium_menu_reset), s(R.string.sandium_menu_reset_description), () -> {
                SandiumMenuState editing = mDraft;
                new AlertDialog.Builder(getContext()).setMessage(s(R.string.sandium_menu_reset_question))
                        .setNegativeButton(s(R.string.sandium_menu_cancel), null).setPositiveButton(s(R.string.sandium_menu_reset_confirm), (d, which) -> {
                            if (mDraft == null || mDraft != editing) return;
                            List<String> defaults = new ArrayList<>(mCatalog.keySet());
                            for (String known : mDraft.knownKeys()) if (!defaults.contains(known)) defaults.add(known);
                            mDraft = SandiumMenuState.reset(defaults, new HashSet<>()); persistDraft(); mPage = 0; render();
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
        int columns = columns();
        LinearLayout line = null;
        for (int i = 0; i < keys.size(); i++) {
            if (i % columns == 0) { line = row(); parent.addView(line); }
            final String key = keys.get(i);
            if (ALL_MENU.equals(key)) {
                LinearLayout all = tile();
                ImageView icon = new ImageView(getContext());
                icon.setImageDrawable(allMenuIcon());
                icon.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                all.addView(icon, new LinearLayout.LayoutParams(dp(26), dp(26)));
                addTileLabel(all, tileLabel(s(R.string.sandium_menu_all)));
                all.setContentDescription(s(R.string.sandium_menu_all_description));
                all.setFocusable(true);
                all.setOnClickListener(v -> { mAllMenu = true; render(); });
                all.setTag(ALL_MENU);
                // Persist order like other tiles, but never offer removal.
                if (mDraft != null) {
                    all.setOnClickListener(v -> editOptions(ALL_MENU));
                    bindMove(all, ALL_MENU);
                }
                weighted(line, all);
                continue;
            }
            Entry entry = mCatalog.get(key);
            LinearLayout tile = tile();
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
            if (library(key)) icon.setImageTintList(android.content.res.ColorStateList.valueOf(mAccentColor));
            icon.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            // Exactly one icon slot, including the monogram fallback.
            icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
            if (drawable != null) tile.addView(icon, new LinearLayout.LayoutParams(dp(26), dp(26)));
            TextView label = tileLabel(tileTitle(key, entry));
            addTileLabel(tile, label);
            tile.setTag("action:" + key); tile.setFocusable(true); tile.setContentDescription(title(entry));
            tile.setAlpha(enabled(entry.model) || mDraft != null ? 1 : .4f);
            FrameLayout editCell = null;
            if (mDraft != null && !library(key)) {
                editCell = new FrameLayout(getContext());
                editCell.addView(tile, new FrameLayout.LayoutParams(-1, -2));
                TextView editControl = button(available ? "+" : "−",
                        s(available ? R.string.sandium_menu_add_action : R.string.sandium_menu_remove_action, title(entry)),
                        () -> { if (available) mDraft.show(key); else mDraft.hide(key); persistDraft(); render(); });
                FrameLayout.LayoutParams editControlParams = new FrameLayout.LayoutParams(dp(48), dp(48), Gravity.TOP | Gravity.END);
                editCell.addView(editControl, editControlParams);
                tile.setOnClickListener(v -> editOptions(key));
                if (!available) {
                    bindMove(tile, key);
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
                    control.setIncludeFontPadding(false);
                    control.setSingleLine(true);
                    control.setEllipsize(android.text.TextUtils.TruncateAt.END);
                    control.setEnabled(enabled(action));
                    tile.removeView(label);
                    // Keep state in a separate line so a long/localized title cannot hide it.
                    LinearLayout captionSlot = column();
                    label.setSingleLine(true);
                    captionSlot.addView(label, new LinearLayout.LayoutParams(-1, label.getLineHeight()));
                    captionSlot.addView(control, new LinearLayout.LayoutParams(-1, dp(48)));
                    addTileLabel(tile, captionSlot);
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
            weighted(line, editCell == null ? tile : editCell);
        }
        if (line != null) for (int i = keys.size() % columns; i != 0 && i < columns; i++) line.addView(new View(getContext()), new LinearLayout.LayoutParams(0, 1, 1));
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
        finishPanelMotion(); finishPageMotion(); mMotionPanel = null;
        clearPendingNativeAction();
        mNativeVisible = true;
        if (mNativeReset != null) mNativeReset.run();
        removeAllViews();
        if (mNative.getParent() instanceof ViewGroup) ((ViewGroup) mNative.getParent()).removeView(mNative);
        LinearLayout content = column();
        content.addView(button(s(R.string.sandium_menu_back_all), s(R.string.sandium_menu_back_description), () -> { if (mNativeReset != null) mNativeReset.run(); render(); }));
        content.addView(mNative, new LinearLayout.LayoutParams(-1, 0, 1));
        addView(content, new LayoutParams(-1, -1));
        if (mResize != null && mDragging == null) post(mResize);
        if (row >= 0) mNativeList.setSelection(row + mNativeList.getHeaderViewsCount());
    }

    private Set<String> quickAvailable() {
        Set<String> keys = editableKeys(); keys.add(ALL_MENU); return keys;
    }
    private List<String> quickKeys() {
        // Repair stale hidden state and append to old profiles once. Never disappear
        // even when the bounded saved catalog is full or contains corrupt old data.
        state().reconcile(java.util.Collections.singleton(ALL_MENU), java.util.Collections.emptySet());
        state().show(ALL_MENU);
        List<String> keys = new ArrayList<>(state().visibleKeys(quickAvailable()));
        if (!keys.contains(ALL_MENU)) keys.add(ALL_MENU);
        return keys;
    }
    private int quickPageCount() { return (quickKeys().size() + PAGE_SIZE - 1) / PAGE_SIZE; }

    private void bindMove(View tile, String key) {
        tile.setOnLongClickListener(v -> {
            mDragging = key;
            boolean started = v.startDragAndDrop(ClipData.newPlainText("Sandium menu action", key),
                    new View.DragShadowBuilder(v), key, 0);
            if (!started) mDragging = null;
            return started;
        });
    }

    private void page(int direction) {
        if (mAllMenu && mDraft == null) return;
        int count = quickPageCount();
        int next = Math.max(0, Math.min(count - 1, mPage + direction));
        if (next == mPage) return;
        View focus = findFocus();
        View a11yFocus = accessibilityFocus(this);
        boolean restoreKeyFocus = focus != null && String.valueOf(focus.getTag()).startsWith("page:");
        boolean restoreA11yFocus = a11yFocus != null && String.valueOf(a11yFocus.getTag()).startsWith("page:");
        mPage = next; render();
        View destination = findViewWithTag("page:" + mPage);
        if (destination != null) {
            if (restoreKeyFocus) destination.requestFocus();
            if (restoreA11yFocus) destination.performAccessibilityAction(
                    AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null);
        }
    }
    private void cancelDragPage() {
        if (mDragPageTask != null) removeCallbacks(mDragPageTask);
        mDragPageTask = null; mDragPageTarget = -1;
    }
    private boolean dragHit(View view, float x, float y) {
        if (view == null || !view.isShown()) return false;
        android.graphics.Rect bounds = new android.graphics.Rect();
        if (!view.getGlobalVisibleRect(bounds)) return false;
        android.graphics.Point origin = new android.graphics.Point();
        if (!getGlobalVisibleRect(new android.graphics.Rect(), origin)) return false;
        return bounds.contains(origin.x + (int) x, origin.y + (int) y);
    }
    private int dragPageAt(float x, float y) {
        for (int i = 0; i < quickPageCount(); i++) {
            if (i != mPage && dragHit(findViewWithTag("page:" + i), x, y)) return i;
        }
        // Either viewport edge also changes page, without aiming at the small indicator.
        if (!dragHit(mPageViewport, x, y)) return -1;
        android.graphics.Rect bounds = new android.graphics.Rect();
        mPageViewport.getGlobalVisibleRect(bounds);
        android.graphics.Point origin = new android.graphics.Point();
        if (!getGlobalVisibleRect(new android.graphics.Rect(), origin)) return -1;
        float rootX = origin.x + x;
        int direction = rootX < bounds.left + dp(32) ? -1
                : rootX >= bounds.right - dp(32) ? 1 : 0;
        if (getLayoutDirection() == LAYOUT_DIRECTION_RTL) direction = -direction;
        int target = mPage + direction;
        return direction != 0 && target >= 0 && target < quickPageCount() ? target : -1;
    }
    private void hoverDragPage(float x, float y) {
        int target = dragPageAt(x, y);
        if (target == mDragPageTarget) return;
        cancelDragPage();
        if (target < 0) return;
        mDragPageTarget = target;
        final SandiumMenuState draft = mDraft;
        final String moving = mDragging;
        mDragPageTask = () -> {
            cancelDragPage();
            if (mDraft == draft && moving != null && moving.equals(mDragging)) page(target - mPage);
        };
        postDelayed(mDragPageTask, 450);
    }
    private void editOptions(String key) {
        Entry entry = mCatalog.get(key);
        boolean permanent = ALL_MENU.equals(key);
        if ((!permanent && entry == null) || mDraft == null) return;
        final boolean hidden = mDraft.isHidden(key);
        String[] options = hidden ? new String[] {s(R.string.sandium_menu_add)} : new String[] {
                s(R.string.sandium_menu_earlier), s(R.string.sandium_menu_later), s(R.string.sandium_menu_previous_page), s(R.string.sandium_menu_next_page), s(R.string.sandium_menu_remove)};
        if (permanent) options = java.util.Arrays.copyOf(options, 4); // No Remove action.
        new AlertDialog.Builder(getContext()).setTitle(permanent ? s(R.string.sandium_menu_all) : title(entry)).setItems(options, (dialog, which) -> {
            if (mDraft == null) return;
            if (hidden) mDraft.show(key);
            else {
                int index = quickKeys().indexOf(key);
                if (which == 4 && !permanent) mDraft.hide(key);
                else mDraft.move(key, index + new int[] {-1, 1, -PAGE_SIZE, PAGE_SIZE}[which], quickAvailable());
            }
            persistDraft(); render();
        }).show();
    }
    @Override public boolean dispatchDragEvent(DragEvent event) {
        // The sheet owns its local drag for the whole session. Re-rendering a page
        // replaces tiles; those new children did not receive Android DRAG_STARTED.
        // Never depend on their per-view drag eligibility after a page switch.
        boolean local = mDragging != null && mDragging.equals(event.getLocalState());
        if (!local || mDraft == null) return super.dispatchDragEvent(event);
        switch (event.getAction()) {
            case DragEvent.ACTION_DRAG_LOCATION:
                hoverDragPage(event.getX(), event.getY());
                break;
            case DragEvent.ACTION_DROP:
                cancelDragPage();
                for (String key : quickKeys()) {
                    View target = findViewWithTag(ALL_MENU.equals(key) ? ALL_MENU : "action:" + key);
                    if (dragHit(target, event.getX(), event.getY())) {
                        int destination = quickKeys().indexOf(key);
                        mDraft.move(mDragging, destination, quickAvailable()); persistDraft(); render();
                        return true;
                    }
                }
                return false; // A drop outside visible action tiles never alters order.
            case DragEvent.ACTION_DRAG_EXITED:
                cancelDragPage();
                break;
            case DragEvent.ACTION_DRAG_ENDED:
                cancelDragPage(); mDragging = null; scheduleRefresh();
                if (mResize != null) post(mResize);
                break;
            default:
                break;
        }
        return true;
    }
    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) clearPendingNativeAction();
        return super.dispatchKeyEvent(event);
    }
    @Override public boolean onInterceptTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) clearPendingNativeAction();
        if (mNativeVisible || mDragging != null) return super.onInterceptTouchEvent(event);
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
            mDownX = event.getX(); mDownY = event.getY();
            android.graphics.Rect bounds = new android.graphics.Rect();
            mSwipeEligible = mPageViewport != null;
            if (mSwipeEligible) {
                mPageViewport.getDrawingRect(bounds);
                offsetDescendantRectToMyCoords(mPageViewport, bounds);
                mSwipeEligible = bounds.contains((int) mDownX, (int) mDownY);
            }
        } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE
                && mSwipeEligible && Math.abs(event.getX() - mDownX) > dp(48)
                && Math.abs(event.getX() - mDownX) > Math.abs(event.getY() - mDownY) * 1.5f) return true;
        return super.onInterceptTouchEvent(event);
    }
    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
            mSwipeEligible = false; return true;
        }
        if (event.getActionMasked() == MotionEvent.ACTION_UP) {
            boolean eligible = mSwipeEligible; mSwipeEligible = false;
            if (!eligible) return super.onTouchEvent(event);
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
