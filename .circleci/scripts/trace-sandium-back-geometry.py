#!/usr/bin/env python3
"""Trace existing underlap decisions only; do not change inset/gesture semantics."""
import importlib.util
from pathlib import Path
import subprocess
import sys
spec=importlib.util.spec_from_file_location('back_patch',Path(__file__).with_name('apply-sandium-back-transition.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PATH='chrome/browser/ui/android/edge_to_edge/internal/java/src/org/chromium/chrome/browser/ui/edge_to_edge/EdgeToEdgeControllerImpl.java'
OLD='''        if (mInsetObserver != null
                && shouldSandiumUnderlap(mCurrentTab) != mSandiumScrollUnderStatusBar) {
            mInsetObserver.retriggerOnApplyWindowInsets();'''
NEW='''        if (mInsetObserver != null
                && shouldSandiumUnderlap(mCurrentTab) != mSandiumScrollUnderStatusBar) {
            if (org.chromium.base.TraceEvent.enabled()) {
                org.chromium.base.TraceEvent.instant("SandiumUnderlapReapply",
                        "current=" + mSandiumScrollUnderStatusBar
                        + ",requested=" + shouldSandiumUnderlap(mCurrentTab)
                        + ",systemTop=" + mSystemInsets.top
                        + ",consumed=" + mConsumeTopInset
                        + ",forced=" + (mBrowserControlsStateProvider != null
                                && mBrowserControlsStateProvider.isVisibilityForced()));
            }
            mInsetObserver.retriggerOnApplyWindowInsets();'''
def transform(source):return m.transform(source,OLD,NEW)
def reset(source):
    if NEW in source:
        if (source.count(NEW) != 1 or source.count("SandiumUnderlapReapply") != 1
                or OLD in source.replace(NEW, "", 1)):
            raise RuntimeError('Duplicate back geometry instrumentation')
        return source.replace(NEW,OLD,1)
    if 'SandiumUnderlapReapply' in source:
        raise RuntimeError('Unrecognized back geometry instrumentation')
    return source
def main():
    root=Path(sys.argv[1]).resolve()
    for directory,pin in ((root,m.CHROMIUM_SHA),(root/'brave',m.BRAVE_SHA)):
        if subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()!=pin:
            raise RuntimeError('Back-geometry pinned source mismatch')
    path=root/PATH;operation=reset if "--reset" in sys.argv[2:] else transform
    path.write_text(operation(path.read_text()))
    print('SANDIUM_BACK_GEOMETRY_TRACE=APPLIED; inset behavior unchanged')
if __name__=='__main__':main()
