package org.chromium.chrome.browser.suggestions.mostvisited;

import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.DragEvent;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;
import org.chromium.chrome.R;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.browser.suggestions.SiteSuggestion;
import org.chromium.chrome.browser.suggestions.tile.TileSource;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.components.favicon.LargeIconBridge;
import org.chromium.url.GURL;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

/** Profile-owned native custom links. No second database, URL upload or launcher shortcut. */
public final class SandiumHomeShortcuts extends LinearLayout {
    public static final int LIMIT = 200;
    private final Profile mProfile;
    private final Consumer<GURL> mOpen;
    private final List<SiteSuggestion> mSites = new ArrayList<>();
    private final java.util.Map<View,ObjectAnimator> mWiggles = new java.util.IdentityHashMap<>();
    private final List<View> mEditTiles = new ArrayList<>();
    private MostVisitedSitesBridge mBridge;
    private LargeIconBridge mIcons;
    private ScrollView mScroll;
    private boolean mExpanded, mEditing;
    private GURL mDragging;
    private View mDragView;
    private int mGeneration;
    private AlertDialog mDialog;
    private final Runnable mRender = this::render;
    private final androidx.activity.OnBackPressedCallback mBack = new androidx.activity.OnBackPressedCallback(false) {
        @Override public void handleOnBackPressed() {
            if (mEditing) mEditing = false; else mExpanded = false;
            render();
        }
    };
    private final View.OnLayoutChangeListener mParentLayout = (v,l,t,r,b,ol,ot,or,ob) -> {
        if (r-l != or-ol || b-t != ob-ot) post(mRender);
    };
    private final int mText, mPanel, mAccent;

    public SandiumHomeShortcuts(Context context, Profile profile, Consumer<GURL> open) {
        super(context);
        mProfile = profile; mOpen = open;
        setOrientation(VERTICAL);
        mText = color(android.R.attr.textColorPrimary, Color.WHITE);
        mPanel = color(android.R.attr.colorBackground, 0xff080808);
        mAccent = color(android.R.attr.colorAccent, 0xff6e8eb5);
        setPadding(dp(8), dp(4), dp(8), dp(4));
        setBackground(shape(Color.TRANSPARENT, 16));
    }
    private int color(int attr, int fallback) {
        android.content.res.TypedArray a = getContext().obtainStyledAttributes(new int[]{attr});
        int c = a.getColor(0, fallback); a.recycle(); return c;
    }
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); return d;
    }
    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        Context host = getContext();
        while (host instanceof android.content.ContextWrapper && !(host instanceof androidx.activity.ComponentActivity))
            host = ((android.content.ContextWrapper)host).getBaseContext();
        if (host instanceof androidx.activity.ComponentActivity)
            ((androidx.activity.ComponentActivity)host).getOnBackPressedDispatcher().addCallback(mBack);
        if (getParent() instanceof View) ((View)getParent()).addOnLayoutChangeListener(mParentLayout);
        mIcons = new LargeIconBridge(mProfile);
        mBridge = new MostVisitedSitesBridge(mProfile, true);
        mBridge.setObserver(new MostVisitedSites.Observer() {
            @Override public void onSiteSuggestionsAvailable(boolean user, List<SiteSuggestion> sites) {
                if (mBridge == null) return;
                mSites.clear();
                for (SiteSuggestion site : sites) if (site.source == TileSource.CUSTOM_LINKS) mSites.add(site);
                // Defer reconstruction during a drag; the source/target must remain attached.
                if (mDragging == null) render();
            }
            @Override public void onIconMadeAvailable(GURL url) {
                if (mDragging == null) { removeCallbacks(mRender); postDelayed(mRender, 32); }
            }
        }, 15); // Native custom-link capacity is independent of most-visited metrics capacity.
    }
    @Override protected void onDetachedFromWindow() {
        if (getParent() instanceof View) ((View)getParent()).removeOnLayoutChangeListener(mParentLayout);
        if (mDialog != null) { mDialog.dismiss(); mDialog = null; }
        removeCallbacks(mRender); mBack.remove(); mBack.setEnabled(false);
        if (mDragView != null) { mDragView.setAlpha(1f); mDragView = null; }
        stopWiggles(); mGeneration++; mDragging = null; mEditing = false;
        if (mBridge != null) { mBridge.destroy(); mBridge = null; }
        if (mIcons != null) { mIcons.destroy(); mIcons = null; }
        super.onDetachedFromWindow();
    }
    @Override protected void onWindowVisibilityChanged(int visibility) {
        super.onWindowVisibilityChanged(visibility);
        updateVisibility();
    }
    @Override protected void onVisibilityChanged(View changed, int visibility) {
        super.onVisibilityChanged(changed,visibility);
        updateVisibility();
    }
    private void updateVisibility() {
        // View construction may call these overrides before member initialization.
        if (mBack == null || mWiggles == null) return;
        if (!isShown() || getWindowVisibility() != VISIBLE) {
            if (mDragView != null) { mDragView.setAlpha(1f); mDragView = null; }
            mEditing = false; mDragging = null;
            stopWiggles(); mBack.setEnabled(false);
            if (mDialog != null) { mDialog.dismiss(); mDialog = null; }
        } else if (isAttachedToWindow()) {
            removeCallbacks(mRender); post(mRender);
        }
    }
    private void stopWiggles() { for (ObjectAnimator a : mWiggles.values()) a.cancel(); mWiggles.clear(); }
    private TextView text(String s, int size) {
        TextView t = new TextView(getContext()); t.setText(s); t.setTextColor(mText);
        t.setTextSize(size); t.setGravity(Gravity.CENTER); return t;
    }
    private TextView button(String label, Runnable action) {
        TextView t = text(label, 14); t.setTextColor(mAccent); t.setMinHeight(dp(48));
        t.setFocusable(true); t.setOnClickListener(v -> action.run()); return t;
    }
    @Override protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w,h,oldw,oldh);
        if (w != oldw) post(mRender);
    }
    private void render() {
        if (!isAttachedToWindow() || mDragging != null) return;
        mBack.setEnabled(isShown() && getWindowVisibility() == VISIBLE && (mEditing || mExpanded));
        setBackground(shape(mExpanded ? mPanel : Color.TRANSPARENT, 16));
        int scroll = mScroll == null ? 0 : mScroll.getScrollY();
        stopWiggles(); mEditTiles.clear(); mGeneration++; removeAllViews();
        if (mEditing) {
            FrameLayout header = new FrameLayout(getContext());
            TextView done = button(getResources().getString(R.string.sandium_home_done), () -> {
                mEditing = false; render();
            });
            header.addView(done,new FrameLayout.LayoutParams(dp(72),dp(48),Gravity.END));
            addView(header,new LinearLayout.LayoutParams(-1,dp(48)));
        }
        mScroll = new ScrollView(getContext()); mScroll.setFillViewport(false);
        mScroll.setClipToPadding(false);
        mScroll.setVerticalScrollBarEnabled(mExpanded);
        mScroll.setScrollbarFadingEnabled(false);
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            GradientDrawable thumb = shape(mAccent,2); thumb.setSize(dp(3),dp(32));
            mScroll.setVerticalScrollbarThumbDrawable(thumb);
        }
        mScroll.setOnScrollChangeListener((v,x,y,oldx,oldy) -> updateWiggles());
        GridLayout grid = new GridLayout(getContext()); grid.setColumnCount(5);
        int count = mExpanded ? mSites.size() : Math.min(20, mSites.size());
        int rows = Math.max(1, (count + 4) / 5); grid.setRowCount(rows);
        for (int i = 0; i < count; i++) {
            SiteSuggestion site = mSites.get(i);
            View tile = tile(site, i);
            GridLayout.LayoutParams lp = new GridLayout.LayoutParams(GridLayout.spec(i / 5), GridLayout.spec(i % 5, 1f));
            lp.width = 0; lp.height = dp(76); grid.addView(tile, lp);
        }
        if (count == 0) {
            TextView empty = button(getResources().getString(R.string.sandium_home_add),this::addDialog);
            GridLayout.LayoutParams emptyParams = new GridLayout.LayoutParams(GridLayout.spec(0),GridLayout.spec(0,5));
            emptyParams.width = -1; emptyParams.height = dp(76); grid.addView(empty,emptyParams);
        }
        mScroll.addView(grid);
        int parentHeight = getParent() instanceof View ? ((View)getParent()).getHeight() : 0;
        if (parentHeight == 0) parentHeight = getResources().getDisplayMetrics().heightPixels;
        int footerHeight = mSites.size() > 20 ? 48 : 0;
        int headerHeight = mEditing ? 48 : 0;
        // Expanded surface reaches near the top, covering stats, but never the native toolbar.
        int available = Math.max(dp(76), parentHeight - dp(8 + 16 + 8 + footerHeight + headerHeight));
        int height = mExpanded ? available : Math.min(available, dp(Math.min(4, rows) * 76));
        addView(mScroll, new LinearLayout.LayoutParams(-1, height));
        if (mSites.size() > 20) {
            FrameLayout footer = new FrameLayout(getContext());
            View arrow = new ChevronButton(getContext());
            arrow.setContentDescription(getResources().getString(mExpanded ? R.string.sandium_home_less : R.string.sandium_home_all));
            arrow.setFocusable(true);
            arrow.setOnClickListener(v -> { mExpanded = !mExpanded; render(); });
            footer.addView(arrow,new FrameLayout.LayoutParams(dp(48),dp(48),Gravity.CENTER));
            addView(footer,new LinearLayout.LayoutParams(-1,dp(48)));
        }
        final ScrollView renderedScroll = mScroll;
        renderedScroll.post(() -> { if (mScroll == renderedScroll && isAttachedToWindow()) { renderedScroll.scrollTo(0, scroll); updateWiggles(); } });
        mScroll.setOnDragListener((v, event) -> {
            if (event.getLocalState() != this) return false;
            if (event.getAction() == DragEvent.ACTION_DRAG_LOCATION) {
                if (event.getY() < dp(48)) mScroll.smoothScrollBy(0, -dp(32));
                else if (event.getY() > mScroll.getHeight() - dp(48)) mScroll.smoothScrollBy(0, dp(32));
            }
            if (event.getAction() == DragEvent.ACTION_DRAG_ENDED) finishDrag();
            return true;
        });
    }
    private final class ChevronButton extends View {
        private final android.graphics.Paint paint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        ChevronButton(Context context) { super(context); }
        @Override public CharSequence getAccessibilityClassName() { return android.widget.Button.class.getName(); }
        @Override protected void onDraw(android.graphics.Canvas canvas) {
            super.onDraw(canvas);
            float x=getWidth()/2f,y=getHeight()/2f;
            paint.setStyle(android.graphics.Paint.Style.FILL);
            paint.setColor((mAccent & 0x00ffffff) | 0x20000000);
            canvas.drawCircle(x,y,dp(15),paint);
            paint.setColor(mAccent); paint.setStyle(android.graphics.Paint.Style.STROKE);
            paint.setStrokeWidth(dp(2)); paint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
            paint.setStrokeJoin(android.graphics.Paint.Join.ROUND);
            android.graphics.Path path = new android.graphics.Path();
            float sign=mExpanded?-1:1;
            path.moveTo(x-dp(8),y+sign*dp(3));path.lineTo(x,y-sign*dp(4));path.lineTo(x+dp(8),y+sign*dp(3));
            canvas.drawPath(path,paint);
        }
    }
    private void finishDrag() {
        if (mDragging == null) return;
        mDragging = null;
        if (mDragView != null) { mDragView.setAlpha(1f); mDragView = null; }
        post(mRender); // One cleanup, not one rebuild per accepting drag target.
    }
    private View tile(SiteSuggestion site, int index) {
        FrameLayout box = new FrameLayout(getContext());
        LinearLayout content = new LinearLayout(getContext()); content.setOrientation(VERTICAL);
        content.setGravity(Gravity.CENTER);
        FrameLayout iconBox = new FrameLayout(getContext()); iconBox.setBackground(shape(mPanel, 10));
        TextView letter = text(site.title.isEmpty() ? "•" : site.title.substring(0, 1).toUpperCase(java.util.Locale.ROOT), 23);
        iconBox.addView(letter, new FrameLayout.LayoutParams(-1, -1));
        ImageView icon = new ImageView(getContext()); icon.setPadding(dp(6),dp(6),dp(6),dp(6));
        iconBox.addView(icon, new FrameLayout.LayoutParams(-1, -1));
        content.addView(iconBox, new LinearLayout.LayoutParams(dp(44), dp(44)));
        TextView title = text(site.title.isEmpty() ? site.url.getHost() : site.title, 11);
        title.setMaxLines(2); title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        content.addView(title, new LinearLayout.LayoutParams(-1, dp(28)));
        box.addView(content, new FrameLayout.LayoutParams(-1,-1));
        final int generation = mGeneration;
        if (mIcons != null) mIcons.getLargeIconForUrl(site.url, dp(32), (bitmap, color, def, type) -> {
            if (generation == mGeneration && bitmap != null && isAttachedToWindow()) {
                icon.setImageBitmap(bitmap); letter.setVisibility(GONE);
            }
        });
        content.setContentDescription(title.getText()); content.setFocusable(true);
        content.setOnClickListener(v -> { if (!mEditing && safe(site.url)) mOpen.accept(site.url);
            else if (mEditing) editDialog(site,index); });
        content.setOnLongClickListener(v -> {
            mEditing = true;
            mDragging = site.url;
            mDragView = v;
            if (!v.startDragAndDrop(ClipData.newPlainText("Sandium shortcut", ""), new View.DragShadowBuilder(v) {
                @Override public void onDrawShadow(android.graphics.Canvas canvas) {
                    super.onDrawShadow(canvas);
                    android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
                    p.setStyle(android.graphics.Paint.Style.STROKE);p.setStrokeWidth(dp(1));p.setColor(mAccent);
                    canvas.drawRoundRect(1,1,v.getWidth()-1,v.getHeight()-1,dp(10),dp(10),p);
                }
            }, this, 0)) { mDragging = null; mDragView = null; render(); }
            else v.setAlpha(0.3f);
            return true;
        });
        box.setOnDragListener((v, event) -> {
            if (event.getLocalState() != this) return false;
            if (event.getAction() == DragEvent.ACTION_DRAG_ENTERED) {
                GradientDrawable target = shape(Color.TRANSPARENT,10); target.setStroke(dp(1),mAccent,dp(4),dp(3));
                v.setBackground(target);
            } else if (event.getAction() == DragEvent.ACTION_DRAG_EXITED) v.setBackground(null);
            if (event.getAction() == DragEvent.ACTION_DROP && mDragging != null && mBridge != null) {
                int target = indexForUrl(site.url);
                return target >= 0 && mBridge.reorderCustomLink(mDragging, target);
            }
            if (event.getAction() == DragEvent.ACTION_DRAG_ENDED) finishDrag();
            return true;
        });
        if (mEditing) {
            TextView delete = button("×", () -> {
                if (mBridge != null && mBridge.deleteCustomLink(site.url)) { mSites.remove(site); render(); }
            });
            delete.setMinHeight(0); delete.setTextSize(15); delete.setTextColor(mPanel);
            delete.setBackground(new android.graphics.drawable.InsetDrawable(shape(mAccent,10),dp(7))); delete.setContentDescription(getResources().getString(R.string.sandium_home_remove_named,site.title));
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(dp(32),dp(32),Gravity.TOP|Gravity.RIGHT);
            box.addView(delete,lp);
            mEditTiles.add(content);
        }
        return box;
    }
    private int indexForUrl(GURL url) {
        for (int i=0; i<mSites.size(); i++) if (mSites.get(i).url.equals(url)) return i;
        return -1;
    }
    private void updateWiggles() {
        android.graphics.Rect clip = new android.graphics.Rect();
        boolean animate = mEditing && isShown() && getWindowVisibility() == VISIBLE
                && ValueAnimator.areAnimatorsEnabled();
        for (View tile : mEditTiles) {
            boolean visible = animate && tile.getGlobalVisibleRect(clip);
            ObjectAnimator old = mWiggles.get(tile);
            if (visible && old == null) {
                ObjectAnimator a = ObjectAnimator.ofFloat(tile,"rotation",-1.2f,1.2f);
                a.setDuration(180); a.setRepeatMode(ValueAnimator.REVERSE); a.setRepeatCount(ValueAnimator.INFINITE);
                mWiggles.put(tile,a); a.start();
            } else if (!visible && old != null) {
                old.cancel(); tile.setRotation(0); mWiggles.remove(tile);
            }
        }
    }
    private void editDialog(SiteSuggestion site, int index) {
        if (mDialog != null && mDialog.isShowing()) return;
        mDialog = new AlertDialog.Builder(getContext()).setTitle(site.title)
                .setItems(new String[]{getResources().getString(R.string.sandium_home_move_before),
                        getResources().getString(R.string.sandium_home_move_after),
                        getResources().getString(R.string.sandium_home_remove)}, (d,which) -> {
                    if (mBridge == null || indexForUrl(site.url) < 0) return;
                    if (which == 2) mBridge.deleteCustomLink(site.url);
                    else mBridge.reorderCustomLink(site.url, Math.max(0,Math.min(mSites.size()-1,indexForUrl(site.url)+(which==0?-1:1))));
                }).create();
        mDialog.setOnDismissListener(d -> mDialog = null);
        mDialog.show();
    }
    private static boolean safe(GURL url) {
        return url != null && url.isValid() && ("https".equals(url.getScheme()) || "http".equals(url.getScheme()));
    }
    private void addDialog() {
        if (mDialog != null && mDialog.isShowing()) return;
        LinearLayout form = new LinearLayout(getContext()); form.setOrientation(VERTICAL); form.setPadding(dp(20),0,dp(20),0);
        EditText title = new EditText(getContext()); title.setHint(getResources().getString(R.string.sandium_home_name)); form.addView(title);
        EditText address = new EditText(getContext()); address.setHint(getResources().getString(R.string.sandium_home_address)); address.setInputType(17); form.addView(address);
        AlertDialog dialog = new AlertDialog.Builder(getContext()).setTitle(getResources().getString(R.string.sandium_add_home_shortcut)).setView(form)
                .setNegativeButton(getResources().getString(R.string.sandium_home_cancel),null).setPositiveButton(getResources().getString(R.string.sandium_home_save),null).create();
        mDialog = dialog;
        dialog.setOnDismissListener(d -> { if (mDialog == dialog) mDialog = null; });
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            GURL url = new GURL(address.getText().toString().trim());
            if (!safe(url)) { address.setError(getResources().getString(R.string.sandium_home_invalid)); return; }
            if (mBridge != null && mBridge.addCustomLink(title.getText().toString().trim(),url,null)) dialog.dismiss();
            else address.setError(getResources().getString(R.string.sandium_home_limit));
        })); dialog.show();
    }
    public static boolean addCurrent(Tab tab) {
        if (tab == null || tab.isIncognito() || !safe(tab.getUrl())) return false;
        MostVisitedSitesBridge bridge = new MostVisitedSitesBridge(tab.getProfile(), true);
        try { return bridge.addCustomLink(tab.getTitle(),tab.getUrl(),null); }
        finally { bridge.destroy(); }
    }
}
