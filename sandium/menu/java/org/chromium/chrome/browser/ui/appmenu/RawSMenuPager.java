package org.chromium.chrome.browser.ui.appmenu;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Native-host independent Sandium grid state. Not a PopupWindow or an active UI adapter.
 * UI owner must call refresh after source/setting changes and close on native dismissal.
 */
public final class RawSMenuPager<T> {
    public static final int QUICK_CAPACITY = 8;
    public static final int DIRECTORY_ROWS = 5;
    public enum Kind { ACTION, ALL_MENU }
    public static final class Tile<T> {
        public final Kind kind;
        public final RawSMenuModel.Entry<T> entry;
        private final long revision;
        private Tile(Kind kind, RawSMenuModel.Entry<T> entry, long revision) {
            this.kind = kind; this.entry = entry; this.revision = revision;
        }
    }
    private final RawSMenuModel<T> model;
    private List<RawSMenuModel.Entry<T>> actions = Collections.emptyList();
    private List<Tile<T>> tiles = Collections.emptyList();
    private int columns = 4;
    private int page;
    private int availableRows = DIRECTORY_ROWS;
    private boolean directory;
    private boolean closed;
    private long revision;
    public RawSMenuPager(RawSMenuModel<T> model) { this.model = model; refresh(); }
    public int columns() { return columns; }
    public int page() { return page; }
    public boolean isDirectory() { return directory; }
    public int rows() { return directory ? availableRows : (capacity() + columns - 1) / columns; }
    public int pageCount() {
        int size = actions.size() + (directory ? 0 : 1);
        return Math.max(1, (size + capacity() - 1) / capacity());
    }
    public boolean showPageIndicator() { return pageCount() > 1; }
    private int capacity() { return directory ? availableRows * columns : Math.min(QUICK_CAPACITY, availableRows * columns); }
    public int rowsForLimit(int limit) {
        int rows = Math.max(1, Math.min(DIRECTORY_ROWS,limit));
        return directory ? rows : (Math.min(QUICK_CAPACITY,rows*columns)+columns-1)/columns;
    }
    public int pagesForLimit(int limit) {
        int rows = Math.max(1,Math.min(DIRECTORY_ROWS,limit));
        int cap = directory ? rows*columns : Math.min(QUICK_CAPACITY,rows*columns);
        return Math.max(1,(actions.size()+(directory?0:1)+cap-1)/cap);
    }
    public int availableRows() { return availableRows; }
    public boolean setAvailableRows(int rows) {
        if (closed) return false;
        int next = Math.max(1, Math.min(DIRECTORY_ROWS, rows));
        if (next == availableRows) return false;
        availableRows = next; publish(); return true;
    }
    public List<Tile<T>> tiles() { return tiles; }
    /** A rebind invalidates visible tile handles even if their action is still available. */
    public void refresh() {
        if (closed) return;
        actions = directory ? model.directory() : model.page(0, 256);
        publish();
    }
    /** Native text scaling controls columns; never truncate accessible text to force four. */
    public void setLargeText(boolean large) {
        if (closed) return;
        columns = large ? 2 : 4; publish();
    }
    private void publish() {
        revision++;
        page = Math.max(0, Math.min(page, pageCount() - 1));
        int start = page * capacity();
        List<Tile<T>> visible = new ArrayList<>();
        for (int i = start; i < Math.min(start + capacity(), actions.size()); i++)
            visible.add(new Tile<>(Kind.ACTION, actions.get(i), revision));
        // Pinned last in quick-page sequence, never a persistable/hideable native command.
        if (!directory && start <= actions.size() && actions.size() < start + capacity())
            visible.add(new Tile<>(Kind.ALL_MENU, null, revision));
        tiles = Collections.unmodifiableList(visible);
    }
    /** Previous/next are logical page directions; native UI maps RTL to these once. */
    public boolean movePage(int step) {
        if (closed || (step != -1 && step != 1)) return false;
        int next = page + step;
        if (next < 0 || next >= pageCount()) return false;
        page = next; publish(); return true;
    }
    public boolean selectPage(int requested) {
        if (closed || requested < 0 || requested >= pageCount() || requested == page) return false;
        page = requested; publish(); return true;
    }
    public boolean backToQuick() {
        if (closed || !directory) return false;
        directory = false; page = 0; refresh(); return true;
    }
    public boolean isCurrent(Tile<T> tile) {
        return !closed && tile != null && tile.revision == revision && tiles.contains(tile);
    }
    public boolean activate(Tile<T> tile, RawSMenuModel.Dispatcher<T> dispatcher) {
        if (!isCurrent(tile)) return false;
        if (tile.kind == Kind.ALL_MENU) {
            directory = true; page = 0; refresh(); return true;
        }
        // The native dispatcher owns dismissal and execution, with current enabled/policy check.
        boolean executed = model.dispatch(tile.entry, dispatcher);
        if (executed) { closed = true; revision++; tiles = Collections.emptyList(); }
        return executed;
    }
    public void close() {
        closed = true; revision++; tiles = Collections.emptyList(); model.close();
    }
}
