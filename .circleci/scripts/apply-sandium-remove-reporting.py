#!/usr/bin/env python3
"""Compile-exclude reporting implementations, with explicit optional P3A/crash phases.
Requires enable_brave_stats_updater=false in effective GN arguments.
"""
from pathlib import Path
import argparse

JAVA = 'android/java/org/chromium/chrome/browser/app/BraveActivity.java'
NATIVE = 'browser/android/brave_init_android.cc'
GN = 'browser/brave_stats/BUILD.gn'
MARKER = '// Sandium: usage-ping Android entry removed at build time.'


def transform_java(s):
    call = '        BraveActivityJni.get().restartStatsUpdater();\n'
    decl = '        void restartStatsUpdater();\n'
    if MARKER in s:
        if 'restartStatsUpdater' in s:
            raise RuntimeError('partial usage-ping Java removal')
        return s
    if s.count(call) != 1 or s.count(decl) != 1:
        raise RuntimeError('unexpected pinned usage-ping Java anchors')
    return s.replace(call, '        ' + MARKER + '\n', 1).replace(decl, '', 1)


def transform_native(s):
    block = '''static void JNI_BraveActivity_RestartStatsUpdater(JNIEnv* env) {
  g_brave_browser_process->brave_stats_updater()->Stop();
  g_brave_browser_process->brave_stats_updater()->Start();
}
'''
    inc = '#include "brave/browser/brave_stats/brave_stats_updater.h"\n'
    if MARKER in s:
        if 'RestartStatsUpdater' in s or inc in s:
            raise RuntimeError('partial usage-ping native removal')
        return s
    if s.count(block) != 1 or s.count(inc) != 1:
        raise RuntimeError('unexpected pinned usage-ping native anchors')
    return s.replace(block, MARKER + '\n', 1).replace(inc, '', 1)


def transform_gn(s):
    params = '''    "//brave/browser/brave_stats/brave_stats_updater_params.cc",
    "//brave/browser/brave_stats/brave_stats_updater_params.h",
'''
    marker = '# Sandium: updater-only params follow compile-time updater exclusion.'
    if marker in s:
        if s.count(params) != 1:
            raise RuntimeError('partial usage-ping GN removal')
        return s
    anchor = '  if (enable_brave_stats_updater) {\n    sources += [\n'
    if s.count(params) != 1 or s.count(anchor) != 1:
        raise RuntimeError('unexpected pinned usage-ping GN anchors')
    s = s.replace(params, '', 1)
    return s.replace(anchor, '  ' + marker + '\n' + anchor + params, 1)


def apply(core):
    transforms = {JAVA: transform_java, NATIVE: transform_native, GN: transform_gn}
    # Compute every change first: an anchor failure must not partially patch files.
    changed = {p: fn((core / p).read_text()) for p, fn in transforms.items()}
    if ('getSafeBrowsingApiKey' not in changed[JAVA]
            or 'JNI_BraveActivity_GetSafeBrowsingApiKey' not in changed[NATIVE]):
        raise RuntimeError('Safe Browsing JNI preservation check failed')
    for p, value in changed.items():
        (core / p).write_text(value)
    print('SANDIUM_REPORTING_REMOVAL=usage_ping_android_wiring_ready requires_GN_enable_brave_stats_updater_false')



P3A_MARKER = '// Sandium: P3A remote reporting implementation is not built.'
P3A_HEADER = """// Copyright (c) 2019 The Brave Authors. All rights reserved.
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. https://mozilla.org/MPL/2.0/.
// Sandium: P3A remote reporting implementation is not built.
#ifndef BRAVE_COMPONENTS_P3A_P3A_SERVICE_H_
#define BRAVE_COMPONENTS_P3A_P3A_SERVICE_H_
#include <string>
#include "base/callback_list.h"
#include "base/functional/callback.h"
#include "brave/components/p3a/metric_log_type.h"
#include "brave/components/p3a/pref_names.h"
#include "components/prefs/pref_registry_simple.h"
namespace p3a {
// Compile-time compatibility surface only. No object, observers, scheduler,
// uploader, remote config, measurement storage, or component is instantiated.
class P3AService {
 public:
  static void RegisterPrefs(PrefRegistrySimple* registry, bool first_run) {
    registry->RegisterBooleanPref(kP3AEnabled, false);
    registry->RegisterBooleanPref(kP3ANoticeAcknowledged, first_run);
    registry->RegisterDictionaryPref(kCustomAttributesDictPref);
    registry->RegisterDictionaryPref(kDynamicMetricsDictPref);
    registry->RegisterDictionaryPref(kActivationDatesDictPref);
  }
  base::CallbackListSubscription RegisterRotationCallback(
      base::RepeatingCallback<void(MetricLogType)> callback) { return {}; }
  base::CallbackListSubscription RegisterMetricCycledCallback(
      base::RepeatingCallback<void(const std::string&)> callback) { return {}; }
};
}  // namespace p3a
#endif
"""
P3A_BUILD = """# Sandium: reporting engine excluded; compatibility types only.
static_library("p3a") {
  sources = [ "metric_log_type.cc", "metric_log_type.h", "p3a_service.h", "pref_names.h", "utils.h" ]
  public_deps = [ "//base", "//components/prefs", "//brave/components/p3a_utils" ]
}

"""


def remove_required(s, old, label):
    if old not in s:
        raise RuntimeError('missing P3A anchor: ' + label)
    return s.replace(old, '')


def replace_function(s, signature, replacement):
    start = s.index(signature)
    brace = s.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}')
        end += 1
    return s[:start] + replacement + s[end:]


def p3a_transform(path, s):
    marker = P3A_MARKER.replace('//', '#', 1) if path.endswith(('.gn', '.gni')) else P3A_MARKER
    if marker in s:
        return s
    if path == 'components/p3a/p3a_service.h':
        if 'class P3AService : public base::RefCountedThreadSafe' not in s:
            raise RuntimeError('unknown P3A service API')
        return P3A_HEADER
    if path == 'components/p3a/BUILD.gn':
        start = s.index('static_library("p3a") {')
        end = s.index('source_set("unit_tests")', start)
        s = s[:start] + P3A_BUILD + s[end:]
    elif path == 'browser/brave_browser_process_impl.cc':
        for inc in ('histograms_braveizer.h', 'p3a_config.h'):
            s = remove_required(s, '#include "brave/components/p3a/' + inc + '"\n', inc)
        s = remove_required(s, '  if (p3a_service_) {\n    p3a_service_->StartTeardown();\n  }\n', 'teardown')
        s = remove_required(s, '  p3a_service();\n  histogram_braveizer_ = p3a::HistogramsBraveizer::Create();\n', 'startup')
        s = remove_required(s, '  process_misc_metrics()->serp_metrics_p3a()->Init(\n      p3a_service(), profile_manager()->GetProfileAttributesStorage());\n', 'serp-init')
        s = remove_required(s, '    if (p3a_service_) {\n      p3a_service_->SetDefaultBrowserMonitor(\n          process_misc_metrics_->default_browser_monitor());\n    }\n', 'monitor')
        s = replace_function(s, 'p3a::P3AService* BraveBrowserProcessImpl::p3a_service()',
                             'p3a::P3AService* BraveBrowserProcessImpl::p3a_service() {\n  return nullptr;\n}')
    elif path == 'browser/brave_browser_process_impl.h':
        s = remove_required(s, '  scoped_refptr<p3a::P3AService> p3a_service_;\n', 'service-member')
        s = remove_required(s, '  scoped_refptr<p3a::HistogramsBraveizer> histogram_braveizer_;\n', 'observer-member')
    elif path == 'browser/brave_browser_main_extra_parts.cc':
        start = s.index('  if (g_brave_browser_process->p3a_service() != nullptr) {')
        end = s.index('\n  RecordInitialP3AValues();', start)
        s = s[:start] + s[end:]
        s = s.replace('  RecordInitialP3AValues();\n', '')
        s = s.replace('#include "brave/components/p3a/p3a_service.h"\n', '')
    elif path == 'chromium_src/chrome/browser/component_updater/registration.cc':
        s = remove_required(s, '  p3a::MaybeToggleP3AComponent(cus, g_brave_browser_process->p3a_service());\n', 'component')
        s = s.replace('#include "brave/components/p3a/component_installer.h"\n', '')
        s = s.replace('#include "brave/components/p3a/p3a_service.h"\n', '')
    elif path in ('browser/brave_local_state_prefs.cc', 'chromium_src/chrome/browser/prefs/browser_prefs.cc'):
        # These only clear old P3A storage. Retain old data inert rather than
        # requiring/reporting code or silently deleting it during this change.
        for cls, header in (('MetricLogStore', 'metric_log_store.h'), ('RotationScheduler', 'rotation_scheduler.h')):
            s = remove_required(s, '#include "brave/components/p3a/' + header + '"\n', header)
            method, arg = ('RegisterLocalStatePrefsForMigration', 'registry') if path.startswith('browser/') else ('MigrateObsoleteLocalStatePrefs', 'local_state')
            s = remove_required(s, '  p3a::' + cls + '::' + method + '(' + arg + ');\n', cls)
    else:
        raise RuntimeError('unexpected P3A path ' + path)
    return marker + '\n' + s


P3A_FILES = ('components/p3a/p3a_service.h', 'components/p3a/BUILD.gn',
             'browser/brave_browser_process_impl.cc', 'browser/brave_browser_process_impl.h',
             'browser/brave_browser_main_extra_parts.cc',
             'chromium_src/chrome/browser/component_updater/registration.cc',
             'browser/brave_local_state_prefs.cc', 'chromium_src/chrome/browser/prefs/browser_prefs.cc')


def apply_p3a(core):
    values = {p: p3a_transform(p, (core/p).read_text()) for p in P3A_FILES}
    for p, value in values.items():
        (core/p).write_text(value)
    print('SANDIUM_P3A_REMOVAL=reporting_library_excluded compatibility_preferences_retained')



CRASH_MARKER = '// Sandium: remote crash-upload implementation excluded; local diagnostics retained.'
CRASH_UPLOADER_REL = 'components/minidump_uploader/android/java/src/org/chromium/components/minidump_uploader/MinidumpUploader.java'
CRASH_SERVICE_REL = 'chrome/android/java/src/org/chromium/chrome/browser/crash/MinidumpUploadServiceImpl.java'
CRASH_JOB_REL = 'chrome/android/java/src/org/chromium/chrome/browser/crash/ChromeMinidumpUploadJobServiceImpl.java'
CRASH_UPLOADER = """// Copyright 2016 The Chromium Authors
// BSD-style license: see Chromium LICENSE.
// Sandium: remote crash-upload implementation excluded; local diagnostics retained.
package org.chromium.components.minidump_uploader;
import java.io.File;
import org.chromium.build.annotations.NullMarked;
import org.chromium.build.annotations.Nullable;
import org.chromium.components.minidump_uploader.util.HttpURLConnectionFactory;
@NullMarked
public class MinidumpUploader {
    public static @Nullable String setCrashUrlStringForTesting(@Nullable String url) { return null; }
    public static final class Result {
        private final int mErrorCode;
        private final String mResult;
        private Result(int errorCode, String result) { mErrorCode = errorCode; mResult = result; }
        public boolean isSuccess() { return mErrorCode == 0; }
        public boolean isUploadError() { return mErrorCode > 0; }
        public boolean isFailure() { return mErrorCode < 0; }
        public int errorCode() { return mErrorCode; }
        public String message() { return mResult; }
        static Result failure(String result) { return new Result(-1, result); }
        static Result uploadError(int status, String result) { return new Result(status, result); }
        static Result success(String result) { return new Result(0, result); }
    }
    public MinidumpUploader() {}
    public MinidumpUploader(HttpURLConnectionFactory unused) {}
    public Result upload(File unused) {
        return Result.failure("Remote crash upload is not included in Sandium");
    }
}
"""
CRASH_JOB = """// Copyright 2017 The Chromium Authors
// BSD-style license: see Chromium LICENSE.
// Sandium: remote crash-upload implementation excluded; local diagnostics retained.
package org.chromium.chrome.browser.crash;
import android.os.PersistableBundle;
import org.chromium.build.annotations.NullMarked;
import org.chromium.chrome.browser.base.SplitCompatMinidumpUploadJobService;
import org.chromium.components.minidump_uploader.MinidumpUploadJob;
@NullMarked
public class ChromeMinidumpUploadJobServiceImpl extends SplitCompatMinidumpUploadJobService.Impl {
    @Override
    protected MinidumpUploadJob createMinidumpUploadJob(PersistableBundle permissions) {
        // Safely finish jobs queued by an older install, without reading/deleting
        // local dumps, uploading or rescheduling them.
        return new MinidumpUploadJob() {
            @Override
            public void uploadAllMinidumps(UploadsFinishedCallback callback) {
                callback.uploadsFinished(false);
            }
            @Override
            public boolean cancelUploads() { return false; }
        };
    }
}
"""


def transform_crash_service(s):
    if CRASH_MARKER in s:
        return s
    for signature in ('public static void scheduleUploadJob()',
                      'protected void onHandleIntent(@Nullable Intent intent)',
                      'static void tryUploadCrashDumpNow(File minidumpFile)',
                      'public static void tryUploadCrashDumpWithLocalId(@JniType("std::string") String localId)'):
        s = replace_function(s, signature, signature + ' {\n        // Remote uploader is not part of this product. Keep local diagnostics.\n    }')
    return CRASH_MARKER + '\n' + s


def transform_crash_gn(s):
    if CRASH_MARKER.replace('//', '#') in s:
        return s
    original = '"android/java/src/org/chromium/components/minidump_uploader/MinidumpUploader.java"'
    if s.count(original) != 1:
        raise RuntimeError('missing original minidump uploader GN source')
    s = s.replace(original, '"//brave/' + CRASH_UPLOADER_REL + '"')
    factory = '    "android/java/src/org/chromium/components/minidump_uploader/util/HttpURLConnectionFactoryImpl.java",\n'
    s = remove_required(s, factory, 'crash HTTP factory')
    return CRASH_MARKER.replace('//', '#') + '\n' + s


def apply_crash(core, src):
    # Verify all anchors before writes. Keep upstream source for provenance but
    # exclude its network upload implementation from the Java build target.
    gn_path = src/'components/minidump_uploader/BUILD.gn'
    gn = transform_crash_gn(gn_path.read_text())
    service = transform_crash_service((src/CRASH_SERVICE_REL).read_text())
    old_job = (src/CRASH_JOB_REL).read_text()
    if CRASH_MARKER not in old_job and 'new MinidumpUploadJobImpl(' not in old_job:
        raise RuntimeError('unknown crash job implementation')
    sources_path = core/'components/minidump_uploader/sources.gni'
    sources = sources_path.read_text()
    if 'brave_components_minidump_uploader_util_java_sources' not in sources:
        raise RuntimeError('missing Brave crash uploader source contract')
    gn_path.write_text(gn)
    (src/CRASH_SERVICE_REL).write_text(service)
    (src/CRASH_JOB_REL).write_text(CRASH_JOB)
    (core/CRASH_UPLOADER_REL).parent.mkdir(parents=True, exist_ok=True)
    (core/CRASH_UPLOADER_REL).write_text(CRASH_UPLOADER)
    sources_path.write_text('# Sandium: no remote crash HTTP factory in the APK.\n'
                           'brave_components_minidump_uploader_util_java_sources = []\n'
                           'brave_components_minidump_uploader_util_java_deps = []\n')
    print('SANDIUM_CRASH_UPLOAD_REMOVAL=network_uploader_excluded local_dumps_preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--include-p3a', action='store_true')
    parser.add_argument('--src', type=Path)
    parser.add_argument('--include-crash-upload', action='store_true')
    args = parser.parse_args()
    apply(args.core)
    if args.include_p3a:
        apply_p3a(args.core)
    if args.include_crash_upload:
        if not args.src:
            parser.error("--include-crash-upload requires --src")
        apply_crash(args.core, args.src)
