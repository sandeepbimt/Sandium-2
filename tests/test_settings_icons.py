"""Presentation-only Appearance icons; no preference behavior or renderer changes."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
DARK=load('settings_icons_dark','.circleci/scripts/apply-sandium-dark-pages.py')
TEXT=load('settings_icons_text','.circleci/features/page-text/android/apply.py')

class SettingsIcons(unittest.TestCase):
    def test_same_registered_icon_family(self):
        # Pinned Brave44a84b1 android/nala/icons.gni. Already shipped through
        # chrome.R; no guessed asset names or new resource dependency.
        inventory=(ROOT/'tests/fixtures/settings-icons/icons.gni').read_text().split('nala_icons = [',1)[1]
        for name in ('ic_tune','ic_appearance','ic_browser_group','ic_arrow_undo','ic_theme_dark'):
            self.assertIn('"'+name+'.xml"',inventory)

    def test_general_rows_and_replay(self):
        source=(ROOT/'tests/fixtures/dark-pages/brave'/DARK.APPEARANCE).read_text()
        out=DARK.appearance(source)
        for fragment in ('findPreference("brave_enable_tab_groups")',
                         'findPreference("show_undo_when_tabs_closed")',
                         'sandiumGroupLinksIcon.setIcon(R.drawable.ic_browser_group)',
                         'sandiumUndoTabsIcon.setIcon(R.drawable.ic_arrow_undo)',
                         'savedRules.setIcon(R.drawable.ic_appearance)'):
            self.assertEqual(out.count(fragment),1)
        self.assertEqual(out,DARK.appearance(out))
        # Prior checkpoints gain icons without duplicate preferences.
        old=out.replace(DARK.APPEARANCE_GENERAL_ICONS,'').replace(
            '        savedRules.setIcon(R.drawable.ic_appearance);\n','')
        self.assertEqual(out,DARK.appearance(old))
        self.assertEqual(out.count('new androidx.preference.Preference(requireContext())'),1)
        self.assertIn('if (sandiumGroupLinksIcon != null)',out)
        self.assertIn('if (sandiumUndoTabsIcon != null)',out)

    def test_page_text_icon_and_handler_unchanged(self):
        source='        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n'
        out=TEXT.appearance(source)
        self.assertEqual(out,TEXT.appearance(out))
        self.assertEqual(out.count('pageText.setIcon(R.drawable.ic_tune)'),1)
        self.assertIn('SandiumPageTextUi.showGlobal(',out)
        self.assertIn('requireContext(), getProfile()',out)
        self.assertIn('pageText.setKey("sandium_page_text")',out)
        old=out.replace('        pageText.setIcon(R.drawable.ic_tune);\n','')
        self.assertEqual(out,TEXT.appearance(old))

    def test_icons_do_not_change_state_or_geometry(self):
        block=DARK.APPEARANCE_GENERAL_ICONS
        for forbidden in ('setChecked','setVisible','setEnabled','setSummary','setTitle',
                          'setOrder','setIconSize','setOnPreference','setPadding'):
            self.assertNotIn(forbidden,block)

if __name__=='__main__':unittest.main()
