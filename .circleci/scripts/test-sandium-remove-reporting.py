#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reporting', ROOT / 'scripts/apply-sandium-remove-reporting.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FIX = ROOT / 'tests/fixtures/reporting-pinned'

class ReportingRemovalTest(unittest.TestCase):
    def test_java_paired_removal_and_safe_browsing(self):
        value = m.transform_java((FIX/'BraveActivity.snippet.java').read_text())
        self.assertNotIn('restartStatsUpdater', value)
        self.assertIn('String getSafeBrowsingApiKey();', value)
        self.assertEqual(value, m.transform_java(value))

    def test_native_paired_removal_and_safe_browsing(self):
        value = m.transform_native((FIX/'brave_init_android.cc').read_text())
        self.assertNotIn('RestartStatsUpdater', value)
        self.assertNotIn('brave_stats_updater.h', value)
        self.assertIn('JNI_BraveActivity_GetSafeBrowsingApiKey', value)
        self.assertEqual(value, m.transform_native(value))

    def test_params_excluded_by_gn_flag(self):
        value = m.transform_gn((FIX/'brave_stats.BUILD.gn').read_text())
        begin = value.index('source_set("brave_stats")')
        flag = value.index('  if (enable_brave_stats_updater)', begin)
        self.assertNotIn('brave_stats_updater_params', value[begin:flag])
        end = value.index('\n  }', flag)
        self.assertIn('brave_stats_updater_params.cc', value[flag:end])
        self.assertIn('brave_stats_updater.cc', value[flag:end])
        self.assertEqual(value, m.transform_gn(value))

    def test_unexpected_source_fails_closed(self):
        with self.assertRaises(RuntimeError):
            m.transform_java('void restartStatsUpdater();')
        with self.assertRaises(RuntimeError):
            m.transform_native('')
        with self.assertRaises(RuntimeError):
            m.transform_gn('')

    def test_all_anchors_checked_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            core = Path(directory)
            inputs = {m.JAVA: (FIX/'BraveActivity.snippet.java').read_text(),
                      m.NATIVE: (FIX/'brave_init_android.cc').read_text(),
                      m.GN: 'invalid'}
            for path, value in inputs.items():
                (core/path).parent.mkdir(parents=True, exist_ok=True)
                (core/path).write_text(value)
            with self.assertRaises(RuntimeError):
                m.apply(core)
            for path, value in inputs.items():
                self.assertEqual(value, (core/path).read_text())

    def test_safe_browsing_checked_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            core = Path(directory)
            inputs = {m.JAVA: (FIX/'BraveActivity.snippet.java').read_text().replace('getSafeBrowsingApiKey', 'missingSafeBrowsingApiKey'),
                      m.NATIVE: (FIX/'brave_init_android.cc').read_text(),
                      m.GN: (FIX/'brave_stats.BUILD.gn').read_text()}
            for path, value in inputs.items():
                (core/path).parent.mkdir(parents=True, exist_ok=True)
                (core/path).write_text(value)
            with self.assertRaisesRegex(RuntimeError, 'Safe Browsing'):
                m.apply(core)
            for path, value in inputs.items():
                self.assertEqual(value, (core/path).read_text())

class P3ARemovalTest(unittest.TestCase):
    def test_all_transforms_exact_pin_and_repeat(self):
        for path in m.P3A_FILES:
            original = (FIX/'brave'/path).read_text()
            with self.subTest(path=path):
                result = m.p3a_transform(path, original)
                self.assertEqual(result, m.p3a_transform(path, result))

    def test_gn_marker_uses_gn_comment_syntax(self):
        path = 'components/p3a/BUILD.gn'
        result = m.p3a_transform(path, (FIX/'brave'/path).read_text())
        self.assertTrue(result.startswith('# Sandium:'))
        self.assertFalse(any(line.lstrip().startswith('//') for line in result.splitlines()))
        self.assertEqual(result, m.p3a_transform(path, result))

    def test_reporting_sources_not_in_shipping_target(self):
        result = m.p3a_transform('components/p3a/BUILD.gn', (FIX/'brave/components/p3a/BUILD.gn').read_text())
        shipping = result[:result.index('source_set("unit_tests")')]
        for forbidden in ('uploader.cc', 'scheduler.cc', 'p3a_service.cc', 'message_manager.cc', 'remote_config_manager.cc', 'constellation/rs', 'network_service'):
            self.assertNotIn(forbidden, shipping)
        self.assertIn('metric_log_type.cc', shipping)

    def test_no_service_or_component_instantiation(self):
        path = 'browser/brave_browser_process_impl.cc'
        result = m.p3a_transform(path, (FIX/'brave'/path).read_text())
        self.assertNotIn('base::MakeRefCounted<p3a::P3AService>', result)
        self.assertNotIn('p3a_service_', result)
        self.assertNotIn('HistogramsBraveizer::Create', result)
        path = 'chromium_src/chrome/browser/component_updater/registration.cc'
        result = m.p3a_transform(path, (FIX/'brave'/path).read_text())
        self.assertNotIn('MaybeToggleP3AComponent', result)
        self.assertIn('RegisterQueryFilterComponent', result)

    def test_initial_reporting_helper_removed_and_lifecycle_preserved(self):
        path = 'browser/brave_browser_main_extra_parts.cc'
        result = m.p3a_transform(path, (FIX/'brave'/path).read_text())
        self.assertNotIn('RecordInitialP3AValues', result)
        self.assertNotIn('MaybeRecordShieldsUsageP3A', result)
        self.assertNotIn('Brave.Core.CrashReportsEnabled', result)
        for retained in ('StartBraveServices()', 'brave_referrals_service()',
                         'uptime_monitor()->Init()', 'BraveWindowTracker::CreateInstance',
                         'BraveWindowTracker::ClearInstance'):
            self.assertIn(retained, result)

    def test_compatibility_header_has_no_network_or_observer(self):
        for forbidden in ('URLLoader', 'MessageManager', 'ScopedObservation', 'statistics_recorder', 'RemoteConfigManager'):
            self.assertNotIn(forbidden, m.P3A_HEADER)
        self.assertIn('RegisterBooleanPref(kP3AEnabled, false)', m.P3A_HEADER)

class CrashRemovalTest(unittest.TestCase):
    def test_original_uploader_and_factory_excluded_from_build(self):
        result = m.transform_crash_gn((FIX/'chromium/components/minidump_uploader/BUILD.gn').read_text())
        self.assertIn('"//brave/' + m.CRASH_UPLOADER_REL + '"', result)
        self.assertNotIn('"android/java/src/org/chromium/components/minidump_uploader/MinidumpUploader.java"', result)
        self.assertNotIn('HttpURLConnectionFactoryImpl.java', result)
        self.assertEqual(result, m.transform_crash_gn(result))

    def test_scheduling_removed_local_metrics_remain(self):
        result = m.transform_crash_service((FIX/'chromium'/m.CRASH_SERVICE_REL).read_text())
        self.assertEqual(result, m.transform_crash_service(result))
        self.assertNotIn('MinidumpUploadJobService.scheduleUpload(builder)', result)
        self.assertNotIn('new JobInfo.Builder(', result)
        self.assertIn('didBrowserCrashRecently()', result)
        self.assertIn('browserCrashMetricsInitialized()', result)
        self.assertIn('tryUploadCrashDumpWithLocalId', result)

    def test_fallback_shell_cannot_send_or_delete_data(self):
        for forbidden in ('java.net.', 'getOutputStream', 'createHttpURLConnection', 'delete(', 'new MinidumpUploadJobImpl'):
            self.assertNotIn(forbidden, m.CRASH_UPLOADER + m.CRASH_JOB)
        self.assertIn('callback.uploadsFinished(false)', m.CRASH_JOB)
        self.assertIn('Result.failure(', m.CRASH_UPLOADER)

    def test_full_crash_apply_repeat(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            src=Path(directory);core=src/'brave'
            for rel in (m.CRASH_SERVICE_REL,m.CRASH_JOB_REL,'components/minidump_uploader/BUILD.gn'):
                (src/rel).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(FIX/'chromium'/rel,src/rel)
            rel='components/minidump_uploader/sources.gni'
            (core/rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(FIX/'brave'/rel,core/rel)
            m.apply_crash(core,src);m.apply_crash(core,src)
            self.assertIn('util_java_sources = []',(core/rel).read_text())

if __name__ == '__main__':
    unittest.main()
