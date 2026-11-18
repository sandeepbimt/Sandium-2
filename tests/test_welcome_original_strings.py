"""Lint extraction preserves the original #1394 UI text, not upgrade UI."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
class OriginalWelcomeStrings(unittest.TestCase):
    def test_exact_original_labels_and_status(self):
        strings = {e.attrib['name'].removeprefix('sandium_welcome_'): e.text.strip('"') for e in ET.parse(ROOT/'android/java/brave-res/values/sandium_welcome_strings.xml').getroot()}
        self.assertEqual(strings, {
            'start': 'Start browsing', 'fewer_options': 'Fewer options', 'more_options': 'More options',
            'expanded_glyph': '⌄', 'collapsed_glyph': '›', 'restarting': 'Restarting',
            'restarting_moment': 'Restarting in a moment…',
            'status_retry': '○   Unable to read filter status. Retrying...',
            'engine_ready': '✓   Ad blocker engine: Ready', 'engine_activating': '○   Ad blocker engine: Activating',
            'engine_waiting': '○   Ad blocker engine: Waiting for enabled filters',
            'protection_complete': 'Ad-blocking protection completed', 'protection_preparing': 'Preparing ad-blocking protection...',
            'downloads_ready': 'Downloads and native engine ready', 'downloads_waiting': 'Waiting for downloads and native engine',
            'ready_glyph': '✓', 'waiting_glyph': '⟳', 'final_complete': '✓   Finalizing: Complete',
            'final_activating': '○   Finalizing: Activating the native engine...',
            'subscriptions_waiting': '○   Waiting for enabled filter subscriptions...',
            'downloads_remaining': '○   Waiting for remaining downloads; check your connection.',
            'percent': '%1$d%%', 'filters_ready': '✓   Filters: %1$d of %2$d loaded',
            'filters_waiting': '○   Filters: %1$d of %2$d loaded',
        })
if __name__ == '__main__': unittest.main()
