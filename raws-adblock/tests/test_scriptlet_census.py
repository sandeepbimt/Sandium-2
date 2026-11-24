"""The static metrics tool does not execute filter programs or parse DOMs."""
import importlib.util
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory

tool = Path(__file__).resolve().parents[1] / 'audit' / 'scriptlet_census.py'
spec = importlib.util.spec_from_file_location('scriptlet_census', tool)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class Census(unittest.TestCase):
    def test_lane_count_aliases_and_no_scopes(self):
        stats = audit.count(b"""
! heading
[a list header]
alpha.test##+js(remove-attr, data-ad-metadata)
alpha.test##+js(ra, onclick)
beta.test##+js(ra, href)
beta.test##+js(ra, checked)
beta.test#@#+js(remove-attr, data-ad-metadata)
beta.test#@#+js()
beta.test##+js()
beta.test#%#//scriptlet('remove-attr', 'data-example')
beta.test#@%#//scriptlet("remove-attr", "data-example")
""")
        self.assertEqual(stats['positive']['by_family'], {'ra': 4})
        self.assertEqual(stats['exception']['by_family'],
                         {'ra': 1, '(blanket exception)': 1})
        self.assertEqual(stats['adguard_positive']['lines'], 1)
        self.assertEqual(stats['adguard_exception']['lines'], 1)
        self.assertEqual(stats['other_shaped_lines'], 1)
        self.assertEqual(stats['remove_attr_first_argument_categories'],
                         {'custom_html_metadata': 1,
                          'event_handler_attribute': 1,
                          'link_or_frame_behavior': 1,
                          'other_dom_semantics': 1})
        self.assertNotIn('beta.test', str(stats))
        self.assertNotIn('data-example', str(stats))

    def test_unverified_body_rejected(self):
        with TemporaryDirectory() as d:
            fixture = Path(d) / 'filters.txt'
            fixture.write_bytes(b'alpha.test##+js(ra, data-ad-metadata)\n')
            with self.assertRaisesRegex(ValueError, 'Unverified source'):
                audit.verified(fixture, audit.ADS_ROOT)
