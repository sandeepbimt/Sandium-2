#!/usr/bin/env python3
"""Opt-in trace-only loading geometry diagnostic. NOT a visual fix or CI hook."""
import argparse
import subprocess
from pathlib import Path
PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
PATH = 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarProgressBarLayer.java'
MARKER = 'SANDIUM_PROGRESS_GEOMETRY_V1'

def transform(s):
    if MARKER in s: return s
    anchor = '    private final ToolbarProgressBar mProgressBarView;'
    if s.count(anchor) != 1: raise ValueError('Pinned progress entry changed')
    s = s.replace(anchor, '''    // SANDIUM_PROGRESS_GEOMETRY_V1: local trace only; no browsing data or visual changes.
    private int mSandiumProgressTraceCount;
    private @Nullable String mSandiumLastProgressGeometry;

'''+anchor, 1)
    anchor = '        drawingInfo.progressBarStaticBackgroundRect.offset(0, yOffset);'
    if s.count(anchor) != 1: raise ValueError('Pinned progress offset changed')
    return s.replace(anchor, anchor+'''
        if (!org.chromium.base.TraceEvent.enabled()) {
            mSandiumProgressTraceCount = 0;
            mSandiumLastProgressGeometry = null;
        } else if (mSandiumProgressTraceCount < 24) {
            int[] control = new int[2];
            int[] progress = new int[2];
            int[] hairline = new int[2];
            mControlContainer.getView().getLocationOnScreen(control);
            mProgressBarContainer.getLocationOnScreen(progress);
            mToolbarHairline.getLocationOnScreen(hairline);
            View animating = mProgressBarContainer.findViewById(R.id.progress_bar_animating_view);
            String geometry = "position=" + mControlsPositionSupplier.get()
                    + ",controlY=" + control[1]
                    + ",controlH=" + mControlContainer.getView().getHeight()
                    + ",controlLocalY=" + mControlContainer.getView().getY()
                    + ",progressLocalY=" + mProgressBarContainer.getY()
                    + ",rootH=" + mControlContainer.getView().getRootView().getHeight()
                    + ",toolbarH=" + mControlContainer.getToolbarHeight()
                    + ",captureH=" + mControlContainer.getToolbarCaptureHeight()
                    + ",offsetY=" + yOffset
                    + ",progressY=" + progress[1]
                    + ",progressH=" + mProgressBarContainer.getHeight()
                    + ",hairlineY=" + hairline[1]
                    + ",hairlineH=" + mToolbarHairline.getHeight()
                    + ",hairlineV=" + mToolbarHairline.getVisibility()
                    + ",reportedNativeV=" + mProgressBarView.getVisibility()
                    + ",desiredNativeV=" + mProgressBarView.getDesiredAndroidVisibility()
                    + ",nativeAlphaOn=" + (mProgressBarView.getAlpha() > 0f)
                    + ",animatingV=" + (animating == null ? -1 : animating.getVisibility())
                    + ",animatingAlphaOn=" + (animating != null && animating.getAlpha() > 0f)
                    + ",rectY=" + drawingInfo.progressBarRect.top
                    + ",rectH=" + drawingInfo.progressBarRect.height()
                    + ",bgY=" + drawingInfo.progressBarBackgroundRect.top
                    + ",visible=" + drawingInfo.visible
                    + ",foregroundOn=" + ((drawingInfo.progressBarColor >>> 24) != 0)
                    + ",backgroundOn=" + ((drawingInfo.progressBarBackgroundColor >>> 24) != 0)
                    + ",animated=" + ChromeFeatureList.sAndroidAnimatedProgressBarInBrowser.isEnabled()
                    + ",apb1=" + ChromeFeatureList.sAndroidApb144Patch1.isEnabled()
                    + ",apb4=" + ChromeFeatureList.sAndroidApb144Patch4.isEnabled()
                    + ",apb6=" + ChromeFeatureList.sAndroidApb144Patch6.isEnabled();
            if (!geometry.equals(mSandiumLastProgressGeometry)) {
                mSandiumLastProgressGeometry = geometry;
                mSandiumProgressTraceCount++;
                org.chromium.base.TraceEvent.instant("SandiumProgressGeometry", geometry);
            }
        }''',1)

def apply(src, verify=False):
    if subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()!=PIN:
        raise ValueError('Unexpected Chromium pin')
    p=src/PATH
    original=p.read_text();out=transform(original)
    if verify:
        if original!=out:raise ValueError('Missing progress diagnostic')
    else:p.write_text(out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--verify-only',action='store_true')
    a=p.parse_args();apply(a.src,a.verify_only)
