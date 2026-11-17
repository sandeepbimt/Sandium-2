#!/usr/bin/env python3
"""Retain pinned Chromium gesture-reveal ordering and repair disabled-feed handoff.

Chromium pin d331de35ca8ab1358c7a17e4bd41627d55eaef51.
Normal navigation, native-page, focus and security visibility constraints remain.
"""
from pathlib import Path
import subprocess
import sys

PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
PREFIX = 'chrome/android/java/src/org/chromium/chrome/browser/'
LEGACY_GESTURE_CHANGES = [
    (PREFIX + 'toolbar/ToolbarManager.java', '''                // Always force to show the top control at the start of the gesture.
                TabBrowserControlsConstraintsHelper.update(
                        mLocationBarModel.getTab(),
                        BrowserControlsState.SHOWN,
                        /* animate= */ true);
''', '''                // Sandium: retain the outgoing controls position while previewing history.
                // Revealing them here resizes the live page during its slide animation.
'''),
    (PREFIX + 'gesturenav/NavigationHandler.java', '''                    if (TabOnBackGestureHandler.shouldAnimateNavigationTransition(
                            forward, initiatingEdge)) {
                        // Always force to show the top control at the start of the gesture.
                        TabBrowserControlsConstraintsHelper.update(
                                mTab, BrowserControlsState.SHOWN, /* animate= */ true);
                    }
''', '''                    // Sandium: preview history without revealing hidden controls.
                    // Cancellation keeps the original controls and scroll position.
'''),
    (PREFIX + 'gesturenav/NavigationHandler.java',
     'import org.chromium.cc.input.BrowserControlsState;\n', ''),
    (PREFIX + 'gesturenav/NavigationHandler.java',
     'import org.chromium.chrome.browser.tab.TabBrowserControlsConstraintsHelper;\n', ''),

]

CHANGES = [
    (PREFIX + 'ntp/NewTabPage.java',
'                            getView(), mFeedSurfaceProvider.getRestoringStateSupplier());',
'                            getView(),\n                            sandiumRestoringState(\n                                    org.chromium.chrome.browser.feed.FeedFeatures.isFeedEnabled(\n                                            mTab.getProfile()),\n                                    mFeedSurfaceProvider.getRestoringStateSupplier()));'),
    (PREFIX + 'ntp/NewTabPage.java',
'    @Override\n    public SmoothTransitionDelegate enableSmoothTransition() {',
'    // SANDIUM_NO_FEED_HANDOFF: do not await restoration of a feed that is disabled.\n    // Keep the native delegate\'s fade, cancellation and view lifecycle unchanged.\n    private static NonNullObservableSupplier<Integer> sandiumRestoringState(\n            boolean feedEnabled, NonNullObservableSupplier<Integer> restoringState) {\n        if (feedEnabled) return restoringState;\n        TraceEvent.instant("SandiumNtpFeedWaitSkipped");\n        return org.chromium.base.supplier.ObservableSuppliers.createNonNull(\n                FeedSurfaceProvider.RestoringState.NO_STATE_TO_RESTORE);\n    }\n\n    @Override\n    public SmoothTransitionDelegate enableSmoothTransition() {') ,

]

def plan(root):
    result = {}
    # Restore exact pinned upstream gesture ordering on reused source trees,
    # and leave fresh upstream code untouched. Do not defer SHOWN until a later
    # navigation/loading lock while the destination is being handed off.
    for relative, upstream, legacy in LEGACY_GESTURE_CHANGES[:2]:
        path = root / relative
        source = result.get(path, path.read_text())
        if source.count(upstream) == 1 and legacy not in source:
            pass
        elif source.count(legacy) == 1 and upstream not in source:
            source = source.replace(legacy, upstream, 1)
        else:
            raise RuntimeError('upstream back gesture anchor mismatch: ' + relative)
        result[path] = source
    path = root / LEGACY_GESTURE_CHANGES[1][0]
    source = result[path]
    anchors = [
        'import org.chromium.chrome.browser.back_press.BackPressMetrics;\n',
        'import org.chromium.chrome.browser.tab.TabObserver;\n',
    ]
    for (_, upstream, _), anchor in zip(LEGACY_GESTURE_CHANGES[2:4], anchors):
        if upstream not in source:
            if source.count(anchor) != 1:
                raise RuntimeError('upstream back gesture import anchor mismatch')
            source = source.replace(anchor, upstream + anchor, 1)
        elif source.count(upstream) != 1:
            raise RuntimeError('duplicate upstream back gesture import')
    result[path] = source
    for relative, old, new in CHANGES:
        path = root / relative
        source = result.get(path, path.read_text())
        if new and source.count(new) == 1 and old not in source.replace(new, "", 1):
            result[path] = source
        elif source.count(old) == 1 and (not new or new not in source):
            result[path] = source.replace(old, new, 1)
        elif not new and old not in source and 'Sandium: preview history' in source:
            result[path] = source
        else:
            raise RuntimeError('back-controls anchor mismatch: ' + relative)
    return result

def main():
    root = Path(sys.argv[1]).resolve()
    if subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != PIN:
        raise RuntimeError('back-controls revision mismatch')
    for path, source in plan(root).items():
        path.write_text(source)
    print('SANDIUM_BACK_CONTROLS=UPSTREAM_GESTURE_ORDER; runtime validation pending')

if __name__ == '__main__':
    main()
