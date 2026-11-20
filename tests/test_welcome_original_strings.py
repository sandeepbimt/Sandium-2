"""Lint extraction preserves the original #1394 UI text, not upgrade UI."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
class OriginalWelcomeStrings(unittest.TestCase):
    def test_exact_original_labels_and_status(self):
        strings = {e.attrib['name'].removeprefix('sandium_welcome_'): e.text.strip('"') for e in ET.parse(ROOT/'android/java/brave-res/values/sandium_welcome_strings.xml').getroot()}
        self.assertEqual(strings, {
            'notifications': 'App notifications', 'notifications_summary': 'Ask for notification permission after setup', 'save_failed': 'Could not save setup. Please try again.',
            'blur_low': 'Low', 'blur_medium': 'Medium', 'blur_high': 'High',
            'off': 'Off', 'native_blur_summary': 'Use the browser’s native navigation transition',
            'start': 'Start browsing', 'fewer_options': 'Fewer options', 'more_options': 'More options',
            'expanded_glyph': '⌄', 'collapsed_glyph': '›', 'quick_restart': 'Quick Restart', 'dots': '• • •',
            'restarting_countdown': 'Restarting…', 'starting_countdown': 'Starting…',
            'status_retry': '○   Unable to read filter status. Retrying…',
            'engine_ready': '✓   Ad blocker engine: Ready', 'engine_activating': '○   Ad blocker engine: Activating',
            'engine_waiting': '○   Ad blocker engine: Waiting for enabled filters',
            'protection_complete': 'Ad-blocking protection completed', 'protection_preparing': 'Preparing ad-blocking protection…',
            'downloads_ready': 'Downloads and native engine ready', 'downloads_waiting': 'Waiting for downloads and native engine',
            'ready_glyph': '✓', 'waiting_glyph': '⟳', 'final_complete': '✓   Finalizing: Complete',
            'final_activating': '○   Finalizing: Activating the native engine…',
            'subscriptions_waiting': '○   Waiting for enabled filter subscriptions…',
            'downloads_remaining': '○   Waiting for remaining downloads; check your connection.',
            'percent': '%1$d%%', 'filters_ready': '✓   Filters loaded: %1$d / %2$d',
            'filters_waiting': '○   Filters loaded: %1$d / %2$d',
        })
if __name__ == '__main__': unittest.main()
