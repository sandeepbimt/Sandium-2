package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.graphics.drawable.Drawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.ImageView;
import android.widget.CheckBox;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.chromium.components.browser_ui.util.motion.MotionEventInfo;
import org.chromium.components.browser_ui.util.motion.OnPeripheralClickListener;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Inactive native-host grid prototype: owns no window, dismissal, command or page navigation.
 * The host supplies already themed native icons and original command dispatcher. No invented actions.
 * Must be the direct custom ListView row for RawSMenuTileTargets to apply.
 */
final class RawSMenuGridView<T> extends LinearLayout implements RawSMenuTileTargets {
    interface MotionDispatcher<T> extends RawSMenuModel.Dispatcher<T> {
        void triggeringMotion(MotionEventInfo info);
    }
    interface Presentation<T> {
        CharSequence title(T action);
        Drawable icon(T action);
        default void decorateIcon(T action, ImageView view) {}
        default boolean checkable(T action) { return false; }
        default boolean checked(T action) { return false; }
        boolean enabled(T action);
        default boolean longClick(T action, View view) { return false; }
        CharSequence allMenuTitle();
        CharSequence previousPageTitle();
        CharSequence nextPageTitle();
        CharSequence pageDescription(int page, int count);
    }
    private final List<View> targets = new ArrayList<>();
    private final int slop;
    private RawSMenuPager<T> pager;
    private Presentation<T> presentation;
    private RawSMenuModel.Dispatcher<T> dispatcher;
    private Runnable sizeChanged;
    private float downX, downY;
    private boolean tracking, horizontal, vertical, blocked;
    private int pointer;

    RawSMenuGridView(Context context) {
        super(context);
        setOrientation(VERTICAL);
        setClickable(false);
        setFocusable(false);
        slop = ViewConfiguration.get(context).getScaledTouchSlop();
    }
    void bind(RawSMenuPager<T> pager, Presentation<T> presentation,
            RawSMenuModel.Dispatcher<T> dispatcher, Runnable sizeChanged) {
        cancelGesture();
        this.pager = pager; this.presentation = presentation;
        this.dispatcher = dispatcher; this.sizeChanged = sizeChanged;
        render();
    }
    private int dp(int size) {
        return Math.round(size * getResources().getDisplayMetrics().density);
    }
    int desiredHeight() { return pager == null ? 0 : RawSMenuGridMetrics.height(getContext(),pager); }
    private void nativeSelectableBackground(View view) {
        TypedValue value = new TypedValue();
        if (getContext().getTheme().resolveAttribute(android.R.attr.selectableItemBackground, value, true))
            view.setBackgroundResource(value.resourceId);
    }
    private TextView label(CharSequence text) {
        TextView label = new TextView(getContext());
        RawSMenuGridMetrics.styleLabel(label);
        label.setGravity(Gravity.CENTER);
        label.setText(text);
        label.setMaxLines(2);

        label.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        return label;
    }
    private void render() {
        targets.clear(); removeAllViews();
        if (pager == null || presentation == null) return;
        List<RawSMenuPager.Tile<T>> tiles = pager.tiles();
        int cols = pager.columns();
        for (int r = 0; r < pager.rows(); r++) {
            LinearLayout row = new LinearLayout(getContext()); row.setOrientation(HORIZONTAL);
            addView(row, new LayoutParams(LayoutParams.MATCH_PARENT, RawSMenuGridMetrics.rowHeight(getContext())));
            for (int c = 0; c < cols; c++) {
                int index = r * cols + c;
                if (index >= tiles.size()) {
                    row.addView(new View(getContext()), new LayoutParams(0, LayoutParams.MATCH_PARENT, 1));
                    continue;
                }
                RawSMenuPager.Tile<T> tile = tiles.get(index);
                boolean all = tile.kind == RawSMenuPager.Kind.ALL_MENU;
                CharSequence title = all ? presentation.allMenuTitle() : presentation.title(tile.entry.action);
                LinearLayout root = new LinearLayout(getContext());
                root.setOrientation(VERTICAL); root.setGravity(Gravity.CENTER);
                root.setFocusable(true); root.setContentDescription(title);
                boolean enabled=all || presentation.enabled(tile.entry.action);
                boolean checkable=!all && presentation.checkable(tile.entry.action);
                boolean checked=checkable && presentation.checked(tile.entry.action);
                root.setEnabled(enabled);root.setAlpha(enabled?1f:0.38f);root.setSelected(checked);
                root.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                    @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                        super.onInitializeAccessibilityNodeInfo(host, info);
                        info.setClassName(checkable?"android.widget.RadioButton":"android.widget.Button");
                        info.setCheckable(checkable);info.setChecked(checked);
                    }
                });
                nativeSelectableBackground(root);
                ImageView icon = new ImageView(getContext());
                icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
                if (all) icon.setImageResource(android.R.drawable.ic_menu_sort_by_size);
                else icon.setImageDrawable(presentation.icon(tile.entry.action));
                FrameLayout iconArea=new FrameLayout(getContext());
                iconArea.addView(icon,new FrameLayout.LayoutParams(dp(24),dp(24),Gravity.CENTER));
                if (!all) presentation.decorateIcon(tile.entry.action,icon);
                if (checkable) {
                    CheckBox mark=new CheckBox(getContext());mark.setChecked(checked);
                    mark.setClickable(false);mark.setFocusable(false);mark.setEnabled(enabled);
                    mark.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
                    iconArea.addView(mark,new FrameLayout.LayoutParams(dp(24),dp(24),Gravity.END));
                }
                root.addView(iconArea,new LayoutParams(LayoutParams.MATCH_PARENT,dp(24)));
                root.addView(label(title), new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
                root.setOnTouchListener(new OnPeripheralClickListener(motion -> activate(tile, motion)));
                root.setOnClickListener(v -> activate(tile, null));
                if (!all) root.setOnLongClickListener(v -> pager.isCurrent(tile)
                        && presentation.enabled(tile.entry.action)
                        && presentation.longClick(tile.entry.action, v));
                row.addView(root, new LayoutParams(0, LayoutParams.MATCH_PARENT, 1));
                targets.add(root);
            }
        }
        // No empty footer/line for a single page. Page count is stable within each directory.
        if (pager.showPageIndicator()) {
            LinearLayout footer = new LinearLayout(getContext()); footer.setGravity(Gravity.CENTER);
            addView(footer, new LayoutParams(LayoutParams.MATCH_PARENT, RawSMenuGridMetrics.footerHeight(getContext())));
            addPageButton(footer, "‹", presentation.previousPageTitle(), -1, pager.page() > 0);
            int first=Math.max(0,Math.min(pager.page()-1,pager.pageCount()-3));
            for(int index=first;index<Math.min(first+3,pager.pageCount());index++) {
                final int destination=index;
                FrameLayout button=new FrameLayout(getContext());button.setFocusable(true);
                button.setContentDescription(presentation.pageDescription(index+1,pager.pageCount()));
                button.setSelected(index==pager.page());nativeSelectableBackground(button);
                View line=new View(getContext());line.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
                TypedValue color=new TypedValue();getContext().getTheme().resolveAttribute(
                        index==pager.page()?android.R.attr.colorControlActivated:android.R.attr.colorControlNormal,color,true);
                line.setBackgroundColor(color.resourceId!=0?getContext().getColor(color.resourceId):color.data);
                button.addView(line,new FrameLayout.LayoutParams(dp(20),dp(3),Gravity.CENTER));
                button.setOnClickListener(v->{if(pager.selectPage(destination))render();});
                footer.addView(button,new LayoutParams(0,LayoutParams.MATCH_PARENT,1));targets.add(button);
            }
            addPageButton(footer, "›", presentation.nextPageTitle(), 1, pager.page() + 1 < pager.pageCount());
        }
    }
    private void activate(RawSMenuPager.Tile<T> tile, MotionEventInfo motion) {
        if (dispatcher instanceof MotionDispatcher<?>)
            ((MotionDispatcher<?>) dispatcher).triggeringMotion(motion);
        try {
            if (pager.activate(tile, dispatcher) && tile.kind == RawSMenuPager.Kind.ALL_MENU) {
                render(); sizeChanged.run();
            }
        } finally {
            if (dispatcher instanceof MotionDispatcher<?>)
                ((MotionDispatcher<?>) dispatcher).triggeringMotion(null);
        }
    }
    private void addPageButton(LinearLayout footer, CharSequence glyph, CharSequence title, int direction, boolean enabled) {
        TextView button = label(glyph); button.setFocusable(true); button.setEnabled(enabled);
        button.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        button.setContentDescription(title); nativeSelectableBackground(button);
        button.setOnClickListener(v -> { if (pager.movePage(direction)) render(); });
        footer.addView(button, new LayoutParams(0, LayoutParams.MATCH_PARENT, 1)); targets.add(button);
    }
    /** Native Back handler should call this before dismissing the existing AppMenu. */
    boolean backToQuick() {
        if (pager == null || !pager.backToQuick()) return false;
        cancelGesture(); render(); sizeChanged.run(); return true;
    }
    @Override public List<View> rawSVisibleTileTargets() {
        return Collections.unmodifiableList(new ArrayList<>(targets));
    }
    private void cancelGesture() { tracking = false; horizontal = false; vertical = false; }
    @Override public boolean onInterceptTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
            cancelGesture(); blocked = false; tracking = true; pointer = event.getPointerId(0);
            downX = event.getX(); downY = event.getY(); return false;
        }
        if (event.getPointerCount() != 1 || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
            cancelGesture(); blocked = true; return true;
        }
        if (blocked) return true;
        if (!tracking || event.getPointerId(0) != pointer) return false;
        if (event.getActionMasked() == MotionEvent.ACTION_MOVE && !vertical) {
            float dx = Math.abs(event.getX() - downX), dy = Math.abs(event.getY() - downY);
            if (!horizontal && Math.max(dx, dy) > slop) {
                horizontal = dx > dy; vertical = !horizontal;
            }
            if (horizontal) {
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
                return true; // Android cancels the previously pressed child.
            }
        }
        return horizontal;
    }
    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getPointerCount() != 1 || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
            cancelGesture(); blocked = true; return true;
        }
        if (blocked) return true;
        if (!tracking || !horizontal) return super.onTouchEvent(event);
        if (event.getActionMasked() == MotionEvent.ACTION_UP) {
            float dx = event.getX() - downX;
            boolean rtl = getLayoutDirection() == View.LAYOUT_DIRECTION_RTL;
            if (Math.abs(dx) > slop * 2 && pager != null) {
                int direction = dx < 0 ? 1 : -1;
                if (pager.movePage(rtl ? -direction : direction)) render();
            }
            cancelGesture();
        }
        return true;
    }
    @Override protected void onDetachedFromWindow() {
        cancelGesture(); targets.clear(); super.onDetachedFromWindow();
    }
}
