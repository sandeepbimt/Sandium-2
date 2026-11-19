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
import org.chromium.components.embedder_support.util.UrlUtilities;
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
    // One bounded worker per attached surface. Never decode/scan artwork on the UI thread.
    private java.util.concurrent.ThreadPoolExecutor mIconWorker;
    private void cancelIconWork() {
        mGeneration++; // Invalidate already-posted completions as well as queued work.
        if (mIconWorker != null) { mIconWorker.shutdownNow(); mIconWorker = null; }
    }
    private void normalizeIcon(android.graphics.Bitmap original, ImageView icon, int generation) {
        if (generation != mGeneration || !isAttachedToWindow() || !isShown()
                || getWindowVisibility() != VISIBLE) return;
        if (original.getWidth() > 512 || original.getHeight() > 512) return;
        if (mIconWorker == null) {
            mIconWorker = new java.util.concurrent.ThreadPoolExecutor(1, 1, 1,
                    java.util.concurrent.TimeUnit.SECONDS,
                    new java.util.concurrent.ArrayBlockingQueue<Runnable>(25), task -> {
                        Thread thread = new Thread(() -> {
                            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
                            task.run();
                        }, "SandiumShortcutArtwork");
                        thread.setDaemon(true); thread.setPriority(Thread.MIN_PRIORITY); return thread;
                    }, new java.util.concurrent.ThreadPoolExecutor.DiscardPolicy());
            mIconWorker.allowCoreThreadTimeOut(true);
        }
        mIconWorker.execute(() -> {
            try {
                int w = original.getWidth(), h = original.getHeight();
                int[] pixels = new int[w * h];
                original.getPixels(pixels, 0, w, 0, 0, w, h);
                int[] bounds = ArtworkPadding.bounds(pixels, w, h);
                if (bounds == null || Thread.currentThread().isInterrupted()) return;
                android.graphics.Bitmap trimmed = android.graphics.Bitmap.createBitmap(
                        original, bounds[0], bounds[1], bounds[2], bounds[3]);
                if (Thread.currentThread().isInterrupted()) return;
                post(() -> {
                    if (generation == mGeneration && isAttachedToWindow() && isShown()
                            && getWindowVisibility() == VISIBLE && icon.isAttachedToWindow()) icon.setImageBitmap(trimmed);
                });
            } catch (IllegalArgumentException | IllegalStateException ignored) {
                // Hardware/recycled/unreadable icons retain the already visible original.
            }
        });
    }
    /** Display-only normalization; never mutates bitmap, persisted links or the icon cache. */
    static final class ArtworkPadding {
        static boolean empty(int pixel, int background, boolean transparent) {
            if (transparent) return (pixel >>> 24) <= 8;
            // Opaque uniform neutral perimeter only. Coloured or varying artwork is uncertain.
            return (pixel >>> 24) >= 250 &&
                    Math.abs((pixel & 255) - (background & 255)) <= 2 &&
                    Math.abs(((pixel >>> 8) & 255) - ((background >>> 8) & 255)) <= 2 &&
                    Math.abs(((pixel >>> 16) & 255) - ((background >>> 16) & 255)) <= 2;
        }
        static int[] bounds(int[] pixels, int w, int h) {
            if (w < 16 || h < 16 || w > 512 || h > 512 || pixels.length != w * h) return null;
            int bg = pixels[0], r = (bg >>> 16) & 255, g = (bg >>> 8) & 255, b = bg & 255;
            boolean transparent = (bg >>> 24) <= 8;
            if (!transparent && !((r <= 8 && g <= 8 && b <= 8) || (r >= 247 && g >= 247 && b >= 247))) return null;
            for (int x = 0; x < w; x++)
                if (!empty(pixels[x], bg, transparent) || !empty(pixels[(h-1)*w+x], bg, transparent)) return null;
            for (int y = 0; y < h; y++)
                if (!empty(pixels[y*w], bg, transparent) || !empty(pixels[y*w+w-1], bg, transparent)) return null;
            int left = w, top = h, right = -1, bottom = -1;
            for (int y = 0; y < h; y++) {
                if (Thread.currentThread().isInterrupted()) return null;
                for (int x = 0; x < w; x++) if (!empty(pixels[y*w+x], bg, transparent)) {
                    left = Math.min(left,x); right = Math.max(right,x);
                    top = Math.min(top,y); bottom = Math.max(bottom,y);
                }
            }
            if (right < 0) return null;
            // Require real, balanced padding on all edges. Keep a safety rim and cap
            // zoom at 1.4x; sparse, off-centre, full-bleed and ambiguous art stays intact.
            int minX = Math.max(2,w/16), minY = Math.max(2,h/16);
            if (left < minX || w-1-right < minX || top < minY || h-1-bottom < minY
                    || Math.abs(left-(w-1-right)) > w/10 || Math.abs(top-(h-1-bottom)) > h/10) return null;
            left = Math.min(Math.max(0,left-2),w/7);
            top = Math.min(Math.max(0,top-2),h/7);
            right = Math.max(Math.min(w-1,right+2),w-1-w/7);
            bottom = Math.max(Math.min(h-1,bottom+2),h-1-h/7);
            if (left == 0 && top == 0 && right == w-1 && bottom == h-1) return null;
            return new int[]{left,top,right-left+1,bottom-top+1};
        }
    }
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
        mText = Color.WHITE; // Subtle text shadows retain contrast against the wallpaper.
        mPanel = 0xff1a1a1a; // Delete glyph only; no group backing is drawn.
        mAccent = color(android.R.attr.colorAccent, 0xff198cff);
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
        cancelIconWork();
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
            cancelIconWork();
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
        setBackground(shape(Color.TRANSPARENT, 16));
        int scroll = mScroll == null ? 0 : mScroll.getScrollY();
        cancelIconWork();
        stopWiggles(); mEditTiles.clear(); mGeneration++; removeAllViews();
        if (mSites.isEmpty()) {
            // No empty Add card or invisible reserved panel. Add remains in the page menu.
            mScroll = null; mEditing = false; mExpanded = false; mBack.setEnabled(false);
            setPadding(0, 0, 0, 0);
            return;
        }
        setPadding(dp(8), dp(4), dp(8), dp(4));
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
        mScroll.setBackground(null); // Wallpaper is visible between every shortcut.
        mScroll.setClipToOutline(true);
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
        int firstRowCount = count - (rows - 1) * 5;
        // Native order is newest first. The partial row is the TOP row, not bottom.
        // [6] sits above [5,4,3,2,1]; later insertions fill that top row from the left.
        for (int i = 0; i < count; i++) {
            SiteSuggestion site = mSites.get(i);
            View tile = tile(site, i);
            int row = i < firstRowCount ? 0 : 1 + (i - firstRowCount) / 5;
            int column = i < firstRowCount ? i : (i - firstRowCount) % 5;
            GridLayout.LayoutParams lp = new GridLayout.LayoutParams(GridLayout.spec(row), GridLayout.spec(column, 1f));
            lp.width = 0; lp.height = dp(76); grid.addView(tile, lp);
        }
        // Complete only the partial TOP row; placeholders cannot receive focus or touch.
        for (int column = firstRowCount; column < 5; column++) {
            View slot = new View(getContext());
            slot.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            GridLayout.LayoutParams lp = new GridLayout.LayoutParams(GridLayout.spec(0), GridLayout.spec(column, 1f));
            lp.width = 0; lp.height = dp(76); grid.addView(slot, lp);
        }
        mScroll.addView(grid);
        int parentHeight = getParent() instanceof View ? ((View)getParent()).getHeight() : 0;
        if (parentHeight == 0) parentHeight = getResources().getDisplayMetrics().heightPixels;
        // Always reserve the same 48dp footer, so revealing the expand control does
        // not lift the bottom row. With the 16dp outer gap this matches the low anchor.
        int footerHeight = 48;
        int headerHeight = mEditing ? 48 : 0;
        int available = Math.max(dp(76), parentHeight - dp(16 + 8 + footerHeight + headerHeight));
        int maxHeight = Math.min(available, dp((mExpanded ? 5 : 4) * 76));
        int height = Math.min(maxHeight, dp(rows * 76));
        addView(mScroll, new LinearLayout.LayoutParams(-1, height));
        if (mSites.size() > 20) {
            FrameLayout footer = new FrameLayout(getContext());
            View arrow = new ChevronButton(getContext());
            arrow.setContentDescription(getResources().getString(mExpanded ? R.string.sandium_home_less : R.string.sandium_home_all));
            arrow.setFocusable(true);
            arrow.setOnClickListener(v -> { mExpanded = !mExpanded; render(); });
            footer.addView(arrow,new FrameLayout.LayoutParams(dp(48),dp(48),Gravity.CENTER));
            addView(footer,new LinearLayout.LayoutParams(-1,dp(48)));
        } else {
            View footer = new View(getContext());
            footer.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            addView(footer, new LinearLayout.LayoutParams(-1, dp(48)));
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
        private final android.graphics.Path chevronPath = new android.graphics.Path();
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
            chevronPath.reset();
            float sign=mExpanded?-1:1;
            chevronPath.moveTo(x-dp(8),y+sign*dp(3));chevronPath.lineTo(x,y-sign*dp(4));chevronPath.lineTo(x+dp(8),y+sign*dp(3));
            canvas.drawPath(chevronPath,paint);
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
        content.setClipChildren(false);
        box.setClipChildren(false);
        FrameLayout iconBox = new FrameLayout(getContext());
        // Uniform frosted rounded-square backing, not a blur of the favicon or page.
        // Static drawable avoids per-frame wallpaper sampling/render effects.
        GradientDrawable frost = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{0xd645484e, 0xd623262c});
        frost.setCornerRadius(dp(12));
        frost.setStroke(dp(1), 0x48ffffff);
        iconBox.setBackground(frost);
        iconBox.setClipToOutline(true);
        iconBox.setElevation(dp(4));
        if (android.os.Build.VERSION.SDK_INT >= 28) {
            iconBox.setOutlineAmbientShadowColor(0x60000000);
            iconBox.setOutlineSpotShadowColor(0x60000000);
        }
        iconBox.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        String label = shortcutLabel(site.title, site.url);
        TextView letter = text(label.isEmpty() ? "•" : label.substring(0, label.offsetByCodePoints(0, 1)).toUpperCase(java.util.Locale.ROOT), 23);
        iconBox.addView(letter, new FrameLayout.LayoutParams(-1, -1));
        ImageView icon = new ImageView(getContext()); icon.setPadding(dp(6),dp(6),dp(6),dp(6));
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        iconBox.addView(icon, new FrameLayout.LayoutParams(-1, -1));
        content.addView(iconBox, new LinearLayout.LayoutParams(dp(44), dp(44)));
        TextView title = text(label, 11);
        title.setShadowLayer(dp(2), 0, dp(1), 0x80000000);
        title.setMaxLines(2); title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        content.addView(title, new LinearLayout.LayoutParams(-1, dp(28)));
        box.addView(content, new FrameLayout.LayoutParams(-1,-1));
        final int generation = mGeneration;
        if (mIcons != null) mIcons.getLargeIconForUrl(site.url, dp(32), (bitmap, color, def, type) -> {
            if (generation == mGeneration && bitmap != null && isAttachedToWindow()) {
                icon.setImageBitmap(bitmap); letter.setVisibility(GONE);
                normalizeIcon(bitmap, icon, generation); // Original is visible immediately.
            }
        });
        content.setContentDescription(title.getText()); content.setFocusable(true);
        // A native pressed-state ripple acknowledges the tap before any redirects.
        // Keep it on the tile: no extra canvas, layout pass or deferred navigation.
        if (!mEditing && safe(site.url)) {
            content.setForeground(new android.graphics.drawable.RippleDrawable(
                    android.content.res.ColorStateList.valueOf((mAccent & 0x00ffffff) | 0x60000000),
                    null, shape(Color.WHITE, 12)));
        }
        content.setOnClickListener(v -> {
            if (!mEditing && safe(site.url)) {
                mOpen.accept(site.url);
            } else if (mEditing) {
                editDialog(site,index);
            }
        });
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
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(dp(32),dp(32),Gravity.TOP|Gravity.END);
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
                .setItems(new String[]{getResources().getString(R.string.sandium_home_rename),
                        getResources().getString(R.string.sandium_home_move_before),
                        getResources().getString(R.string.sandium_home_move_after),
                        getResources().getString(R.string.sandium_home_remove)}, (d,which) -> {
                    if (mBridge == null || indexForUrl(site.url) < 0) return;
                    if (which == 0) {
                        d.dismiss();
                        post(() -> { if (isAttachedToWindow() && isShown()) renameDialog(site); });
                    } else if (which == 3) mBridge.deleteCustomLink(site.url);
                    else mBridge.reorderCustomLink(site.url, Math.max(0,Math.min(mSites.size()-1,indexForUrl(site.url)+(which==1?-1:1))));
                }).create();
        mDialog.setOnDismissListener(d -> mDialog = null);
        mDialog.show();
    }
    private void renameDialog(SiteSuggestion site) {
        if (mDialog != null && mDialog.isShowing()) return;
        EditText name = new EditText(getContext());
        name.setSingleLine(true);
        name.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        name.setHint(R.string.sandium_home_name);
        name.setContentDescription(getResources().getString(R.string.sandium_home_name));
        name.setText(shortcutLabel(site.title, site.url));
        name.selectAll();
        LinearLayout form = new LinearLayout(getContext());
        form.setPadding(dp(20), 0, dp(20), 0);
        form.addView(name, new LinearLayout.LayoutParams(-1, -2));
        AlertDialog dialog = new AlertDialog.Builder(getContext())
                .setTitle(R.string.sandium_home_rename).setView(form)
                .setNegativeButton(R.string.sandium_home_cancel, null)
                .setPositiveButton(R.string.sandium_home_rename_save, null).create();
        mDialog = dialog;
        dialog.setOnDismissListener(d -> { if (mDialog == dialog) mDialog = null; });
        dialog.setOnShowListener(d -> {
            name.requestFocus();
            dialog.getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String title = name.getText().toString().trim();
                if (title.isEmpty() || title.codePoints().allMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c))) {
                    name.setError(getResources().getString(R.string.sandium_home_name_required));
                    return;
                }
                // Do not resurrect a link removed while this dialog was open. Assign uses
                // the existing URL as both key and value: native UpdateLink preserves order.
                if (mBridge == null || indexForUrl(site.url) < 0 || !mBridge.hasCustomLink(site.url)) {
                    name.setError(getResources().getString(R.string.sandium_home_rename_failed));
                    return;
                }
                if (!mBridge.assignCustomLink(site.url, title, site.url)) {
                    name.setError(getResources().getString(R.string.sandium_home_rename_failed));
                    return;
                }
                dialog.dismiss();
                Toast.makeText(getContext(), R.string.sandium_home_renamed, Toast.LENGTH_SHORT).show();
            });
        });
        dialog.show();
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
            if (mBridge != null && addNewest(mBridge, title.getText().toString().trim(), url)) dialog.dismiss();
            else address.setError(getResources().getString(R.string.sandium_home_limit));
        })); dialog.show();
    }
    private static String shortcutLabel(String savedTitle, GURL url) {
        // Existing/custom titles have no provenance flag: never guess and overwrite them.
        if (savedTitle != null && !savedTitle.trim().isEmpty()) return savedTitle;
        String host = url.getHost();
        // Chromium's PSL handles co.uk/co.in and private hosting registries, not a
        // guessed last-two-label suffix. Keep canonical ASCII IDNs to avoid spoofing.
        String domain = UrlUtilities.getDomainAndRegistry(url.getSpec(), true);
        if (domain == null || domain.isEmpty()) return host; // IP, localhost or intranet.
        int dot = domain.indexOf('.');
        String name = dot < 0 ? domain : domain.substring(0, dot);
        if (name.isEmpty() || name.startsWith("xn--")) return name.isEmpty() ? host : name;
        int first = name.offsetByCodePoints(0, 1);
        return name.substring(0, first).toUpperCase(java.util.Locale.ROOT) + name.substring(first);
    }
    private static boolean addNewest(MostVisitedSitesBridge bridge, String title, GURL url) {
        // Native indexed insertion persists the final order in a single mutation.
        // No intermediate append state or second reorder can be lost on shutdown.
        return bridge.addCustomLink(shortcutLabel(title, url), url, 0);
    }
    public static boolean addCurrent(Tab tab) {
        if (tab == null || tab.isIncognito() || !safe(tab.getUrl())) return false;
        MostVisitedSitesBridge bridge = new MostVisitedSitesBridge(tab.getProfile(), true);
        try { return addNewest(bridge, "", tab.getUrl()); }
        finally { bridge.destroy(); }
    }
}
