package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.graphics.drawable.Drawable;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import org.chromium.chrome.browser.ui.appmenu.internal.R;
import org.chromium.components.browser_ui.util.motion.MotionEventInfo;
import org.chromium.ui.modelutil.MVCListAdapter.ListItem;
import org.chromium.ui.modelutil.MVCListAdapter.ModelList;
import org.chromium.ui.modelutil.ListObservable;
import org.chromium.ui.modelutil.ListObservable.ListObserver;
import org.chromium.ui.modelutil.PropertyKey;
import org.chromium.ui.modelutil.PropertyModel;
import org.chromium.ui.modelutil.PropertyObservable.PropertyObserver;

/** Held native-host bridge. Original native models, dispatcher, window and producers stay owners. */
final class RawSGridHost {
    // Allocated after native delegate registration: ModelListAdapter requires contiguous types.
    private int gridType = -1;
    int gridType() { return gridType; }
    void setGridType(int type) {
        if (type < 0) throw new IllegalArgumentException();
        if (type == gridType) return;
        gridType=type;grid=null;refresh();
    }
    private final Context context;
    private final RawSMenuStore store;
    private ModelList nativeSource, nativeProjection, display;
    private RawSNativeMenu owner;
    private AppMenuClickHandler clickHandler;
    private Runnable sizeChanged;
    private RawSMenuModel<ListItem> state;
    private RawSMenuPager<ListItem> pager;
    private ListItem grid;
    private final List<PropertyModel> observed = new ArrayList<>();
    private final LinkedHashMap<String,ListItem> catalog = new LinkedHashMap<>();
    private boolean refreshing, fallbackForViewport, adjustingViewport;
    private final java.util.Map<ListItem,Object> requestedIcons=new java.util.IdentityHashMap<>();
    private final PropertyObserver<PropertyKey> propertyObserver = (source, key) -> {
        if (key == AppMenuItemProperties.ENABLED || key == AppMenuItemProperties.TITLE
                || key == AppMenuItemProperties.ICON || key == AppMenuItemProperties.CHECKED
                || key == AppMenuItemProperties.CHECKABLE || key == AppMenuItemProperties.ICON_SUPPLIER
                || key == AppMenuItemProperties.ICON_COLOR_RES || key == AppMenuItemProperties.ICON_NO_TINT
                || key == AppMenuItemProperties.ICON_SHOW_BADGE || key == AppMenuItemProperties.MANAGED) refresh();
    };
    private final ListObserver<Void> sourceObserver = new ListObserver<Void>() {
        @Override public void onItemRangeInserted(ListObservable source,int index,int count) { refresh(); }
        @Override public void onItemRangeRemoved(ListObservable source,int index,int count) { refresh(); }
        @Override public void onItemRangeChanged(ListObservable<Void> source,int index,int count,Void payload) { refresh(); }
        @Override public void onItemMoved(ListObservable source,int from,int to) { refresh(); }
    };
    RawSGridHost(Context context) { this.context=context; store=new RawSMenuStore(context); }
    ModelList prepare(RawSNativeMenu owner, ModelList source, AppMenuClickHandler clickHandler,
            Runnable sizeChanged) {
        close(); this.owner=owner; this.nativeSource=source; this.clickHandler=clickHandler;
        this.sizeChanged=sizeChanged;
        state=new RawSMenuModel<>(store.read());
        nativeProjection=owner.prepare(source);
        display=new ModelList();
        refresh();
        nativeSource.addObserver(sourceObserver);
        return display;
    }
    private void refresh() {
        if (nativeSource==null || refreshing) return;
        refreshing=true;
        try {
            owner.refresh();
            for (PropertyModel model:observed) model.removeObserver(propertyObserver);
            observed.clear(); catalog.clear();
            boolean collision=false;
            for (ListItem item:nativeSource) {
                if (item.type==gridType) collision=true;
                String key=owner.key(item);
                if (key!=null && catalog.put(key,item)!=null) collision=true;
                item.model.addObserver(propertyObserver); observed.add(item.model);
            }
            if (catalog.size()>256) collision=true;
            if (!collision) state.bind(catalog);
            ModelList desired=new ModelList();
            if (gridType<0 || fallbackForViewport || collision || !state.writable() || catalog.isEmpty()) {
                if (pager!=null) pager.close(); pager=null; grid=null;
                // Complete native output, not the partial quick-menu projection, on unsafe input.
                desired.addAll(nativeSource);
            } else {
                if (pager==null) pager=new RawSMenuPager<>(state); else pager.refresh();
                pager.setLargeText(context.getResources().getConfiguration().fontScale>1.3f);
                if (grid==null) {
                    List<PropertyKey> keys=new ArrayList<>(java.util.Arrays.asList(AppMenuItemProperties.ALL_KEYS));
                    keys.add(RawSMenuGridBinder.DATA);
                    grid=new ListItem(gridType,new PropertyModel.Builder(keys.toArray(new PropertyKey[0]))
                            .with(AppMenuItemProperties.MENU_ITEM_ID,R.id.raws_menu_grid)
                            .with(AppMenuItemProperties.TITLE,context.getString(R.string.raws_menu_grid))
                            .with(AppMenuItemProperties.ENABLED,true).build());
                }
                grid.model.set(RawSMenuGridBinder.DATA,new RawSMenuGridBinder.Binding<>(pager,
                        new RawSMenuGridView.Presentation<ListItem>() {
                            public CharSequence title(ListItem item) { return item.model.get(AppMenuItemProperties.TITLE); }
                            public Drawable icon(ListItem item) { return item.model.get(AppMenuItemProperties.ICON); }
                            public boolean checkable(ListItem item) { return item.model.get(AppMenuItemProperties.CHECKABLE); }
                            public boolean checked(ListItem item) { return item.model.get(AppMenuItemProperties.CHECKED); }
                            public void decorateIcon(ListItem item,android.widget.ImageView icon) {
                                icon.setId(R.id.menu_item_icon);
                                Object supplier=item.model.get(AppMenuItemProperties.ICON_SUPPLIER);
                                if (supplier!=null && requestedIcons.put(item,supplier)!=supplier)
                                    AppMenuItemViewBinder.bindStandardItem(item.model,icon,AppMenuItemProperties.ICON_SUPPLIER);
                                AppMenuItemViewBinder.bindStandardItem(item.model,icon,AppMenuItemProperties.ICON);
                            }
                            public boolean enabled(ListItem item) { return item.model.get(AppMenuItemProperties.ENABLED); }
                            public boolean longClick(ListItem item, android.view.View view) {
                                return nativeSource!=null && nativeSource.contains(item)
                                    && owner.key(item)!=null && enabled(item)
                                    && clickHandler.onItemLongClick(item.model,view);
                            }
                            public CharSequence allMenuTitle() { return context.getString(R.string.raws_menu_all); }
                            public CharSequence previousPageTitle() { return context.getString(R.string.raws_menu_previous); }
                            public CharSequence nextPageTitle() { return context.getString(R.string.raws_menu_next); }
                            public CharSequence pageDescription(int page,int count) { return context.getString(R.string.raws_menu_page,page,count); }
                        },new RawSMenuGridView.MotionDispatcher<ListItem>() {
                            private MotionEventInfo motion;
                            public void triggeringMotion(MotionEventInfo info) { motion=info; }
                            public boolean canExecute(ListItem item) {
                                return nativeSource!=null && nativeSource.contains(item)
                                    && item.model.get(AppMenuItemProperties.ENABLED)
                                    && owner.key(item)!=null;
                            }
                            public void execute(ListItem item) { clickHandler.onItemClick(item.model,motion); }
                        },sizeChanged));
                boolean added=false;
                // Keep compound and protected rows in native order. One grid owns editable rows.
                for (ListItem item:nativeProjection) {
                    if (owner.key(item)!=null) {
                        if (!added) { desired.add(grid); added=true; }
                    } else desired.add(item);
                }
                // All quick actions may be hidden; All Menu must still remain available.
                if (!added) desired.add(0,grid);
            }
            for (int i=0;i<desired.size();i++) {
                ListItem item=desired.get(i);
                if (i<display.size() && display.get(i)==item) continue;
                int old=display.indexOf(item); if (old>=0) display.removeAt(old);
                display.add(i,item);
            }
            while(display.size()>desired.size()) display.removeAt(display.size()-1);
        } finally { refreshing=false; }
    }
    /** Called from native popup's actual available-height calculation, after protected rows.
     * Five directory rows remain the default. Only an impossible viewport uses fewer rows
     * and additional horizontal pages; labels and touch targets are never shrunk/clipped.
     */
    int fitAvailableHeight(int available) {
        if (pager == null || grid == null) return -1;
        if (RawSMenuGridMetrics.heightForLimit(context,pager,1) > available) {
            // A custom row itself cannot fit. Return the unchanged native list for this popup,
            // not an oversized custom row. Suppress intermediate native resize animations.
            fallbackForViewport=true;adjustingViewport=true;
            try { refresh(); } finally { adjustingViewport=false; }
            return 0; // Native caller recalculates once from the now-native adapter.
        }
        int chosen = 1;
        for (int rows = RawSMenuPager.DIRECTORY_ROWS; rows >= 1; rows--) {
            if (RawSMenuGridMetrics.heightForLimit(context,pager,rows) <= available || rows == 1) {
                chosen=rows;break;
            }
        }
        if (pager.setAvailableRows(chosen)) {
            RawSMenuGridBinder.Binding<?> binding = grid.model.get(RawSMenuGridBinder.DATA);
            refreshBinding(binding);
        }
        return RawSMenuGridMetrics.height(context,pager);
    }
    boolean isAdjustingViewport() { return adjustingViewport; }
    private <T> void refreshBinding(RawSMenuGridBinder.Binding<T> old) {
        grid.model.set(RawSMenuGridBinder.DATA,new RawSMenuGridBinder.Binding<>(
                old.pager,old.presentation,old.dispatcher,old.sizeChanged));
    }
    boolean backToQuick() {
        if (pager==null || !pager.backToQuick()) return false;
        refresh(); sizeChanged.run(); return true;
    }
    void close() {
        if (nativeSource!=null) nativeSource.removeObserver(sourceObserver);
        for (PropertyModel model:observed) model.removeObserver(propertyObserver);
        observed.clear(); requestedIcons.clear(); if (pager!=null) pager.close();
        nativeSource=null; nativeProjection=null; display=null; pager=null; grid=null;
        clickHandler=null; sizeChanged=null; owner=null;fallbackForViewport=false;adjustingViewport=false;
    }
}
