#!/usr/bin/env python3
"""Pinned toolbar capture state fixes; preserve native suppression and scheduling."""
import argparse
from pathlib import Path
import subprocess

PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BASE='chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/'

def replace(source, old, new):
    if source.count(new)==1 and old not in source.replace(new,'',1): return source
    if source.count(old)!=1 or new in source: raise RuntimeError('Capture coherence anchor mismatch: '+old[:100])
    return source.replace(old,new,1)

def token(source):
    source=replace(source,'    private final boolean mHomeButtonIsVisible;', '''    private final boolean mHomeButtonIsVisible;
    private final boolean mSandiumForwardEnabled;
    private final int mSandiumForwardImageAlpha;''')
    signature='''    public PhoneCaptureStateToken(
            @ColorInt int tint,
            @ColorInt int themeColor,
            int tabCount,
            @Nullable ButtonData optionalButtonData,
            @VisualState int visualState,
            VisibleUrlText visibleUrlText,
            @DrawableRes int securityIcon,
            ColorStateList homeButtonColorStateList,
            boolean homeButtonIsVisible,
            boolean isShowingUpdateBadgeDuringLastCapture,
            boolean isPaintPreview,
            float progress,
            int unfocusedLocationBarLayoutWidth,
            @ControlsPosition int controlsPosition,
            int urlBarWidth) {'''
    extended=signature.replace('int urlBarWidth) {','''int urlBarWidth,
            boolean sandiumForwardEnabled,
            int sandiumForwardImageAlpha) {''')
    legacy=signature+'''
        // Preserve upstream callers/tests that still describe the original Home button.
        this(tint, themeColor, tabCount, optionalButtonData, visualState, visibleUrlText,
                securityIcon, homeButtonColorStateList, homeButtonIsVisible,
                isShowingUpdateBadgeDuringLastCapture, isPaintPreview, progress,
                unfocusedLocationBarLayoutWidth, controlsPosition, urlBarWidth, true, 255);
    }

'''+extended
    source=replace(source,signature,legacy)
    source=replace(source,'        mHomeButtonIsVisible = homeButtonIsVisible;', '''        mHomeButtonIsVisible = homeButtonIsVisible;
        mSandiumForwardEnabled = sandiumForwardEnabled;
        mSandiumForwardImageAlpha = sandiumForwardImageAlpha;''')
    source=replace(source,'                || current.mHomeButtonIsVisible != next.mHomeButtonIsVisible) {', '''                || current.mHomeButtonIsVisible != next.mHomeButtonIsVisible
                || current.mSandiumForwardEnabled != next.mSandiumForwardEnabled
                || current.mSandiumForwardImageAlpha != next.mSandiumForwardImageAlpha) {''')
    return source

def phone(source):
    return replace(source,'''                mBrowserControlsStateProvider.getControlsPosition(),
                urlBar.getWidth());''','''                mBrowserControlsStateProvider.getControlsPosition(),
                urlBar.getWidth(),
                mHomeButton.isEnabled(),
                mHomeButton.getImageAlpha());''')

def container(source):
    old='''        private boolean shouldCaptureWhileHidden() {
            return ChromeFeatureList.sToolbarCaptureFixForSPAs.isEnabled()
                    && !mIsDestroyed
                    && mBrowserControlsStateProvider != null
                    && mBrowserControlsStateProvider.getTopControlHiddenRatio() >= 1f;
        }'''
    new=old.replace('getTopControlHiddenRatio()', 'getBrowserControlHiddenRatio()')
    new=new.replace('            return ChromeFeatureList', '''            // Follow the actual toolbar position, not an independent top status spacer.
            // Retain upstream feature, lifecycle and native capture-readiness checks.
            return ChromeFeatureList''')
    return replace(source,old,new)

def plan(root):
    out={}
    for name,fn in [('PhoneCaptureStateToken.java',token),('ToolbarPhone.java',phone),('ToolbarControlContainer.java',container)]:
        path=root/BASE/name
        out[path]=fn(path.read_text())
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    if subprocess.check_output(['git','-C',str(a.source),'rev-parse','HEAD'],text=True).strip()!=PIN:raise RuntimeError('Chromium pin mismatch')
    result=plan(a.source)
    if not a.verify_only:
        for path,s in result.items():path.write_text(s)
    if any(path.read_text()!=s for path,s in result.items()):raise RuntimeError('Capture coherence readback mismatch')
    print('TOOLBAR_CAPTURE_COHERENCE=VERIFIED')
if __name__=='__main__':main()
