"""Explicit native activity owners, not a global EdgeToEdgeEverywhere override."""
import patch

HOOKS='''    // Test-only opt-in to the SAME wrapper/inset owner used by upstream Everywhere.
    // Do not apply to Settings, which has separate manual bottom/IME ownership.
    private boolean sandiumNativeScreenProtection() {
        return org.chromium.chrome.browser.ui.edge_to_edge.EdgeToEdgeUtils
                .isSandiumNativeSecondaryScreenEnabled(this);
    }

    @Override
    protected org.chromium.base.supplier.OneshotSupplier<
            org.chromium.ui.edge_to_edge.SystemBarColorHelper>
            createSystemBarColorHelperSupplier() {
        // The base constructs this supplier before setContentView. Create its
        // one shared coordinator now, then let the base publish that same owner.
        if (sandiumNativeScreenProtection()) ensureEdgeToEdgeLayoutCoordinator();
        return super.createSystemBarColorHelperSupplier();
    }

    @Override
    protected void initializeSystemBarColors(
            org.chromium.ui.edge_to_edge.EdgeToEdgeSystemBarColorHelper helper) {
        super.initializeSystemBarColors(helper);
        if (sandiumNativeScreenProtection()) {
            helper.setStatusBarColor(org.chromium.components.browser_ui.styles.SemanticColorUtils
                    .getDefaultBgColor(this));
        }
    }

    @Override
    protected boolean shouldDrawEdgeToEdgeOnCreate() {
        return sandiumNativeScreenProtection() || super.shouldDrawEdgeToEdgeOnCreate();
    }

    @Override
    protected boolean wrapContentWithEdgeToEdgeLayout() {
        return sandiumNativeScreenProtection() || super.wrapContentWithEdgeToEdgeLayout();
    }

    @Override
    protected boolean canColorStatusBarWithEdgeToEdgeHelper() {
        return sandiumNativeScreenProtection() || super.canColorStatusBarWithEdgeToEdgeHelper();
    }

'''

def transform(name, source):
    anchor = ('    @Override\n    public void triggerLayoutInflation() {' if name == 'WelcomeOnboardingActivity.java'
              else '    @Override\n    protected void onProfileAvailable(Profile profile) {')
    hooks = HOOKS
    if name == 'WelcomeOnboardingActivity.java':
        hooks = hooks.replace('org.chromium.components.browser_ui.styles.SemanticColorUtils\n                    .getDefaultBgColor(this)', 'android.graphics.Color.BLACK')
    source=patch.once(source,anchor,hooks+anchor)
    if name=='HistoryActivity.java':
        source=patch.once(source,'    private @Nullable HistoryManager mHistoryManager;', '''    private @Nullable ScrimManager mSandiumNativeScrimManager;
    private final org.chromium.base.Callback<Integer> mSandiumNativeScrimObserver =
            this::sandiumApplyNativeStatusScrim;

    private void sandiumApplyNativeStatusScrim(int scrimColor) {
        if (!sandiumNativeScreenProtection()) return;
        int base = org.chromium.components.browser_ui.styles.SemanticColorUtils
                .getDefaultBgColor(this);
        int color = org.chromium.ui.util.ColorUtils.overlayColor(base, scrimColor);
        org.chromium.chrome.browser.ui.system.StatusBarColorController.setStatusBarColor(
                getEdgeToEdgeManager() == null ? null
                        : getEdgeToEdgeManager().getEdgeToEdgeSystemBarColorHelper(), this, color);
    }

    private @Nullable HistoryManager mHistoryManager;''')
        source=patch.once(source,'        mBottomSheetController =\n', '''        if (sandiumNativeScreenProtection()) {
            mSandiumNativeScrimManager = scrimManager;
            scrimManager.getStatusBarColorSupplier()
                    .addSyncObserverAndPostIfNonNull(mSandiumNativeScrimObserver);
        }
        mBottomSheetController =
''')
        source=patch.once(source,'    protected void onDestroy() {', '''    protected void onDestroy() {
        if (mSandiumNativeScrimManager != null) {
            mSandiumNativeScrimManager.getStatusBarColorSupplier()
                    .removeObserver(mSandiumNativeScrimObserver);
            mSandiumNativeScrimManager = null;
        }''')
    return source
