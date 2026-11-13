#!/usr/bin/env python3
"""Remove Android daily-ping restart integration, not a runtime off switch."""
import argparse
from pathlib import Path

JAVA='android/java/org/chromium/chrome/browser/app/BraveActivity.java'
CPP='browser/android/brave_init_android.cc'
REMOVALS={
 JAVA: ['        BraveActivityJni.get().restartStatsUpdater();\n','        void restartStatsUpdater();\n'],
 CPP: ['#include "brave/browser/brave_browser_process.h"\n','#include "brave/browser/brave_stats/brave_stats_updater.h"\n',
       'static void JNI_BraveActivity_RestartStatsUpdater(JNIEnv* env) {\n  g_brave_browser_process->brave_stats_updater()->Stop();\n  g_brave_browser_process->brave_stats_updater()->Start();\n}\n\n']
}

def apply(core):
    updates={}
    for name,blocks in REMOVALS.items():
        path=core/name;text=path.read_text();counts=[text.count(block) for block in blocks]
        if counts not in ([1]*len(blocks),[0]*len(blocks)):
            raise ValueError('Partial or drifted usage restart removal: '+name)
        for block in blocks:text=text.replace(block,'')
        if 'restartStatsUpdater' in text or 'RestartStatsUpdater' in text or (name==CPP and 'brave_stats_updater' in text):
            raise ValueError('Unexpected residual usage restart integration: '+name)
        if name==JAVA and 'String getSafeBrowsingApiKey();' not in text:raise ValueError('Safe Browsing JNI contract missing')
        if name==CPP and 'JNI_BraveActivity_GetSafeBrowsingApiKey' not in text:raise ValueError('Safe Browsing implementation missing')
        updates[path]=text
    build=core/'browser/brave_stats/BUILD.gn'
    source=build.read_text()
    lines='    "//brave/browser/brave_stats/brave_stats_updater_params.cc",\n    "//brave/browser/brave_stats/brave_stats_updater_params.h",\n'
    marker='  if (enable_brave_stats_updater) {\n    sources += [\n'
    nested='      "//brave/browser/brave_stats/brave_stats_updater_params.cc",\n      "//brave/browser/brave_stats/brave_stats_updater_params.h",\n'
    if source.count(lines)==1 and source.count(marker)==1:
        source=source.replace(lines,'').replace(marker,marker+nested)
    elif source.count(lines)==0 and source.count(marker+nested)==1:
        pass
    else:raise ValueError('Drifted updater parameter source group')
    updates[build]=source
    # Validate all files before writing any.
    for path,text in updates.items():
        if path.read_text()!=text:path.write_text(text)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);args=p.parse_args();apply(args.core)
    print('SANDIUM_USAGE_RESTART_REMOVAL=PASS')
