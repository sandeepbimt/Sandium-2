#!/usr/bin/env python3
"""Refresh native bottom-focus geometry; numeric trace, no custom IME layout."""
from pathlib import Path
import argparse
import subprocess

PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
PATH='chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java'
MARK='SANDIUM_FOCUS_FOLLOW_V1'

def transform(s):
    if MARK in s:return s
    if 'SANDIUM_FOCUSED_BOTTOM_V1' not in s:
        raise ValueError('Apply after reviewed unified bottom-focus routing')
    old='        if (newControlsPosition == mCurrentPosition.get()) return;'
    if s.count(old)!=1:raise ValueError('Pinned same-position anchor changed')
    s=s.replace(old,'''        // SANDIUM_FOCUS_FOLLOW_V1: focus itself changes offset/max-height semantics.
        // When the IME was already open, its height/visibility may not emit again.
        if (org.chromium.base.TraceEvent.enabled() && isOmniboxFocused) {
            org.chromium.base.TraceEvent.instant("SandiumOmniboxPosition",
                    "current=" + mCurrentPosition.get() + ",target=" + newControlsPosition
                    + ",transition=" + stateTransition
                    + ",prefTop=" + isToolbarConfiguredToShowOnTop()
                    + ",find=" + isFindInPageShowing + ",pip=" + isPictureInPictureShowing
                    + ",ntp=" + ntpShowing + ",hub=" + tabSwitcherShowing);
        }
        if (newControlsPosition == mCurrentPosition.get()) {
            // Initial supplier callbacks run before layers are constructed.
            if (newControlsPosition == ControlsPosition.BOTTOM
                    && mBottomToolbarLayer != null && mProgressBarLayer != null) {
                updateViewOffset(mBottomToolbarLayer, mControlContainer.getView());
                updateViewOffset(mProgressBarLayer, mToolbarProgressBarContainer);
            }
            return;
        }''',1)
    anchor='        viewForLayer.setTranslationY(layerYOffset);'
    if s.count(anchor)!=1:raise ValueError('Pinned native offset anchor changed')
    s=s.replace(anchor,'''        if (org.chromium.base.TraceEvent.enabled()
                && mIsOmniboxFocusedSupplier.get() && layer == mBottomToolbarLayer) {
            View container = mControlContainer.getView();
            android.graphics.Rect visible = new android.graphics.Rect();
            container.getWindowVisibleDisplayFrame(visible);
            org.chromium.base.TraceEvent.instant("SandiumOmniboxGeometry",
                    "position=" + mCurrentPosition.get() + ",offset=" + layerYOffset
                    + ",layerOffset=" + layer.getLayerOffsetPx()
                    + ",extraOffset=" + mControlContainerTranslationSupplier.get()
                    + ",ime=" + mKeyboardHeightSupplier.get()
                    + ",ignoreIme=" + shouldIgnoreKeyboardHeightInResizeMode()
                    + ",rootHeight=" + container.getRootView().getHeight()
                    + ",containerHeight=" + container.getHeight()
                    + ",containerTop=" + container.getTop()
                    + ",toolbarHeight=" + mToolbarLayout.getHeight()
                    + ",toolbarTop=" + mToolbarLayout.getTop()
                    + ",visibleTop=" + visible.top + ",visibleBottom=" + visible.bottom);
        }
        viewForLayer.setTranslationY(layerYOffset);''',1)
    return s

def apply(src,verify=False):
    if subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()!=PIN:
        raise ValueError('Unexpected Chromium pin')
    p=src/PATH;s=p.read_text();out=transform(s)
    if verify:
        if s!=out:raise ValueError('Missing native focus refresh')
    else:p.write_text(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--verify-only',action='store_true')
    a=p.parse_args();apply(a.src,a.verify_only)
