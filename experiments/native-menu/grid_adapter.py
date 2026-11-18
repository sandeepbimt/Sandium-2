"""Held grid host composition. Produces exact source transforms; no CI/automatic activation."""
from pathlib import Path
import hashlib
import adapter
import grid_input_adapter
HERE=Path(__file__).resolve().parent
APP=adapter.JAVA+'AppMenu.java'
DRAG=adapter.JAVA+'AppMenuDragHelper.java'
APP_SHA='66a58df87ad367a628931417628f2ca46ed383ced84581d279d1395f239809bf'
SOURCES=('RawSMenuEditorState.java','RawSMenuEditorView.java','RawSMenuGridEditor.java','RawSMenuGridMetrics.java','RawSMenuPager.java','RawSMenuTileTargets.java','RawSMenuGridView.java','RawSMenuGridBinder.java','RawSGridHost.java')

def handler(original):
    s=adapter.transform(adapter.HANDLER,original)
    s=adapter.once(s,'    private final RawSNativeMenu mRawSMenu;',
                   '    private final RawSNativeMenu mRawSMenu;\n    private final RawSGridHost mRawSGrid;')
    s=adapter.once(s,'        mRawSMenu = new RawSNativeMenu(context);',
                   '        mRawSMenu = new RawSNativeMenu(context);\n        mRawSGrid = new RawSGridHost(context);')
    s=adapter.once(s,'        mModelList = mRawSMenu.prepare(mDelegate.getMenuItems());',
                   '''        mModelList = mRawSGrid.prepare(mRawSMenu, mDelegate.getMenuItems(), this,
                () -> { if (mAppMenu != null && mAppMenu.isShowing())
                    mAppMenu.updateMenuHeightWithAnimation(); });''')
    for method in ('    void destroy() {','    public void appMenuDismissed() {'):
        s=adapter.once(s,method,method+'\n        mRawSGrid.close();')
    s=adapter.once(s,'        if (!model.get(AppMenuItemProperties.ENABLED)) return;',
                   '        if (!model.get(AppMenuItemProperties.ENABLED)) return;\n'
                   '        if (model.get(AppMenuItemProperties.MENU_ITEM_ID) == R.id.raws_menu_grid) return;')
    s=adapter.once(s,'            mRawSMenu.showEditor();','            mRawSMenu.showGridEditor();')
    resize_guard='                        if (mainPopup != null && mainPopup.isShowing()) {'
    if s.count(resize_guard)!=2: raise ValueError('Native list resize guards changed')
    s=s.replace(resize_guard,'                        if (mainPopup != null && mainPopup.isShowing() && !mRawSGrid.isAdjustingViewport()) {')
    s=adapter.once(s,'        mAppMenu.updateMenu(initialSizingHelper, adapter);',
                   '        mAppMenu.updateMenu(initialSizingHelper, adapter);\n        mAppMenu.setRawSBackHandler(mRawSGrid::backToQuick);\n        mAppMenu.setRawSAvailableHeightHandler(mRawSGrid::fitAvailableHeight);')
    s=adapter.once(s,'        mDelegate.registerCustomViewBinders(adapter, customSizingProviders);',
                   '''        mDelegate.registerCustomViewBinders(adapter, customSizingProviders);
        int rawSGridType = adapter.getViewTypeCount();
        adapter.registerType(rawSGridType,
                parent -> RawSMenuGridBinder.create(parent.getContext()), RawSMenuGridBinder::bind);
        customSizingProviders.append(rawSGridType, RawSMenuGridBinder::pixelHeight);
        mRawSGrid.setGridType(rawSGridType);''')
    return s

def app(original):
    if hashlib.sha256(original.encode()).hexdigest()!=APP_SHA: raise ValueError('Unreviewed native AppMenu')
    s=adapter.once(original,'class AppMenu implements OnKeyListener {',
        '''class AppMenu implements OnKeyListener {
    private @Nullable java.util.function.BooleanSupplier mRawSBackHandler;
    private @Nullable java.util.function.IntUnaryOperator mRawSAvailableHeightHandler;
    void setRawSAvailableHeightHandler(java.util.function.IntUnaryOperator handler) { mRawSAvailableHeightHandler = handler; }
    void setRawSBackHandler(java.util.function.BooleanSupplier handler) { mRawSBackHandler = handler; }
''')
    s=adapter.once(s,'        mHierarchicalMenuController.setupBackPressBehaviorForPopupWindow(\n                contentView, this::dismiss);',
        '        mHierarchicalMenuController.setupBackPressBehaviorForPopupWindow(\n'
        '                contentView, () -> {\n'
        '                    if (mRawSBackHandler == null || !mRawSBackHandler.getAsBoolean()) dismiss();\n'
        '                });')
    s=adapter.once(s,'        int menuHeight = calculateHeightForItems(heightList, canBeLastList, availableScreenSpace);',
        '        if (mRawSAvailableHeightHandler != null) {\n            int gridIndex = -1;\n            int protectedHeight = 0;\n            for (int i = 0; i < itemCount; i++) {\n                Object item = mAdapter.getItem(i);\n                if (item instanceof org.chromium.ui.modelutil.MVCListAdapter.ListItem\n                        && ((org.chromium.ui.modelutil.MVCListAdapter.ListItem) item).model.get(AppMenuItemProperties.MENU_ITEM_ID) == R.id.raws_menu_grid)\n                    gridIndex = i;\n                else protectedHeight += heightList[i];\n            }\n            if (gridIndex >= 0) {\n                int fitHeight = mRawSAvailableHeightHandler.applyAsInt(Math.max(0, availableScreenSpace - protectedHeight));\n                if (fitHeight == 0) return calculateMenuHeight();\n                if (fitHeight > 0) heightList[gridIndex] = fitHeight;\n            }\n        }\n        int menuHeight = calculateHeightForItems(heightList, canBeLastList, availableScreenSpace);')
    return adapter.once(s,'        if (event.getKeyCode() == KeyEvent.KEYCODE_MENU\n                || !mHierarchicalMenuController.handleBackPress()) {\n            dismiss();',
        '        if (event.getKeyCode() == KeyEvent.KEYCODE_MENU\n                || !mHierarchicalMenuController.handleBackPress()) {\n'
        '            if (event.getKeyCode() == KeyEvent.KEYCODE_BACK\n'
        '                    && mRawSBackHandler != null && mRawSBackHandler.getAsBoolean()) return true;\n'
        '            dismiss();')

def plan(source):
    source=Path(source)
    if (source/'.git').exists() and adapter.subprocess.check_output(
            ['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=adapter.REVISION:
        raise ValueError('Wrong Chromium revision')
    provenance=adapter.json.loads((HERE/'provenance.json').read_text())
    originals={}
    for path in (adapter.HANDLER,adapter.BUILD,APP,DRAG):
        original=(HERE/'fixtures'/Path(path).name).read_text()
        if path in (adapter.HANDLER,adapter.BUILD) and hashlib.sha256(original.encode()).hexdigest()!=provenance['sha256'][Path(path).name]:
            raise ValueError('Native fixture changed')
        originals[path]=original
    result={source/adapter.HANDLER:handler(originals[adapter.HANDLER]),
            source/APP:app(originals[APP]),source/DRAG:grid_input_adapter.transform(originals[DRAG])}
    build=adapter.transform(adapter.BUILD,originals[adapter.BUILD])
    anchor='    "java/src/org/chromium/chrome/browser/ui/appmenu/RawSNativeMenu.java",'
    result[source/adapter.BUILD]=adapter.once(build,anchor,anchor+'\n'+'\n'.join(
        '    "java/src/org/chromium/chrome/browser/ui/appmenu/'+name+'",' for name in SOURCES))
    for name in adapter.SOURCES+SOURCES:
        result[source/adapter.JAVA/name]=(adapter.ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu'/name).read_text()
    menu_path=source/adapter.JAVA/'RawSNativeMenu.java'
    native_menu_base=result[menu_path]
    result[menu_path]=adapter.once(native_menu_base,'    void showEditor() {',
        '    void showGridEditor() {\n        dismissEditor();\n'
        '        editorDialog = RawSMenuGridEditor.show(context, new LinkedHashMap<>(catalog), store);\n'
        '    }\n    void showEditor() {')
    result[source/adapter.BASE/'java/res/values/raws_menu.xml']=(adapter.ROOT/'sandium/menu/raws_menu.xml').read_text()
    result[source/adapter.BASE/'java/res/values-hi/raws_menu.xml']=(adapter.ROOT/'sandium/menu/raws_menu_hi.xml').read_text()
    # Exact pre/post-image replay permits stage handoff/retry, never unknown source overwrites.
    for target,expected in result.items():
        relative=str(target.relative_to(source))
        if relative in originals:
            if not target.exists() or target.read_text() not in (originals[relative],expected):
                raise ValueError('Unreviewed native grid source: '+relative)
        elif target.exists() and target.read_text() not in ((native_menu_base,expected) if target==menu_path else (expected,)):
            raise ValueError('Unreviewed grid module: '+relative)
    return result

def verify_applied(source):
    """Exact feature postimages only; caller must ALSO enforce baseline + other-change checks."""
    result=plan(source)
    for target,expected in result.items():
        if not target.exists() or target.read_text()!=expected:
            raise ValueError('Grid feature not completely applied: '+str(target))
    return {str(target.relative_to(Path(source))):hashlib.sha256(content.encode()).hexdigest()
            for target,content in result.items()}
