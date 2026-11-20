import gzip
import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import android_ui as ui


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests/fixtures/dark-pages/brave'


def load(rel):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdRedirectUiTests(unittest.TestCase):
    def test_compose_and_replay_on_frozen_shields(self):
        popup = load('.circleci/scripts/apply-sandium-shields-popup.py')
        dark = load('.circleci/scripts/apply-sandium-dark-pages.py')
        element = load('.circleci/features/element-corrector/android/apply.py')
        def compose(source):
            return element.layout(dark.layout(popup.layout(source)))
        layout = compose((FIXTURE / ui.PANEL_XML).read_text())
        handler = element.handler(dark.shields(popup.java((FIXTURE / ui.PANEL).read_text())))
        settings = element.blocking_settings_java((FIXTURE / ui.SETTINGS).read_text())
        xml = element.blocking_settings_xml((FIXTURE / ui.SETTINGS_XML).read_text())
        strings = gzip.decompress((ROOT / 'experiments/single-handoff/fixtures/native-blur-156'
                                   '/android_brave_strings.grd.gz').read_bytes()).decode()
        with tempfile.TemporaryDirectory() as temp:
            core = Path(temp)
            for name, contents in ((ui.PANEL_XML, layout), (ui.PANEL, handler), (ui.SETTINGS, settings),
                                   (ui.SETTINGS_XML, xml), (ui.STRINGS, strings)):
                path = core / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
            ui.apply(core)
            names = [ui.PANEL_XML, ui.PANEL, ui.SETTINGS, ui.SETTINGS_XML, ui.STRINGS]
            first = {name: (core / name).read_text() for name in names}
            ui.apply(core)
            self.assertEqual(first, {name: (core / name).read_text() for name in names})
            # Cached source preparation can replay the older panel stages before our final overlay.
            self.assertEqual(ui.panel_xml(compose(first[ui.PANEL_XML])), first[ui.PANEL_XML])
        popup.validate_layout(first[ui.PANEL_XML])
        tree = ET.fromstring(first[ui.PANEL_XML])
        card = tree.find(f".//*[@{ui.A}id='@+id/advanced_options_content']")
        names = [node.get(ui.A+'id') for node in card if node.get(ui.A+'id')]
        self.assertEqual(names[:3], ['@+id/trackers_item', '@+id/sandium_ad_redirects_item',
                                     '@+id/block_element_item'])
        self.assertEqual(card[2][0].get(ui.A+'text'), '@string/sandium_ad_redirects_title')
        self.assertEqual(card[0].get(ui.A+'minHeight'), card[2].get(ui.A+'minHeight'))
        row = ET.fromstring(first[ui.SETTINGS_XML]).find(f".//*[@{ui.A}key='sandium_block_ad_redirects']")
        self.assertTrue(row.tag.endswith('ChromeSwitchPreference'))
        self.assertEqual(row.get(ui.A+'persistent'), 'false')
        self.assertLess(first[ui.SETTINGS].index('"sandium_block_ad_redirects",'),
                        first[ui.SETTINGS].index('        PREF_DE_AMP,'))
        self.assertIn('setAdRedirectBlockingEnabled(getProfile(), (boolean) value)', first[ui.SETTINGS])
        self.assertIn('isAdRedirectBlockingEnabled(getProfile())', first[ui.SETTINGS])
        messages = ET.fromstring(first[ui.STRINGS]).find(".//messages[@fallback_to_english='true']")
        defined = {entry.get('name').lower().removeprefix('ids_') for entry in messages.iter('message')
                   if entry.get('name').startswith('IDS_SANDIUM_AD_REDIRECTS_')}
        source = '\n'.join(first[name] for name in (ui.SETTINGS_XML, ui.PANEL_XML, ui.SETTINGS, ui.PANEL))
        self.assertEqual(defined, set(re.findall(r'(?:R\.string\.|@string/)(sandium_ad_redirects_\w+)', source)))

    def test_site_choices_and_stale_dialog_callback(self):
        # Execute the emitted listener with host stand-ins for the views and profile bridge.
        source = """import java.net.URI;
import java.util.Arrays;
import java.util.function.Consumer;

class SiteDialogTest {
    record GURL(String value) {
        String getHost() { return URI.create(value).getHost(); }
        String getScheme() { return URI.create(value).getScheme(); }
        boolean isValid() { return true; }
        GURL getOrigin() { return new GURL(getScheme() + "://" + getHost()); }
    }
    static class WebContents {
        GURL url = new GURL("https://top.example/a");
        GURL getLastCommittedUrl() { return url; }
        boolean isDestroyed() { return false; }
    }
    static class Tab {
        WebContents contents = new WebContents();
        WebContents getWebContents() { return contents; }
        boolean isDestroyed() { return false; }
    }
    static class Profile { boolean shutdownStarted() { return false; } }
    static class View {
        boolean enabled = true;
        Consumer<View> click;
        void setEnabled(boolean v) { enabled = v; }
        void setOnClickListener(Consumer<View> l) { click = l; }
    }
    static class Context {
        String getText(int id) { return Integer.toString(id); }
        String getString(int id, String site) { return site; }
    }
    static class R {
        static class string {
            static final int sandium_ad_redirects_default_on=10, sandium_ad_redirects_default_off=11,
                sandium_ad_redirects_block=12, sandium_ad_redirects_allow=13,
                sandium_ad_redirects_site_title=14, brave_cancel=15;
        }
    }
    static class BravePrefServiceBridge {
        static final int AD_REDIRECT_DEFAULT=0, AD_REDIRECT_BLOCK=1, AD_REDIRECT_ALLOW=2;
        static boolean global = false;
        static int setting, writes;
        static GURL savedUrl;
        static Profile savedProfile;
        static boolean isAdRedirectBlockingEnabled(Profile p) { return global; }
        static int getAdRedirectSiteSetting(Profile p, GURL u) { return setting; }
        static void setAdRedirectSiteSetting(Profile p, GURL u, int value) {
            setting = value; savedProfile = p; savedUrl = u; writes++;
        }
    }
    static class AlertDialog {
        interface Listener { void select(AlertDialog dialog, int which); }
        static class Builder {
            static Builder shown;
            int selected;
            CharSequence[] labels;
            Listener listener;
            Builder(Context c) {}
            Builder setTitle(String title) { return this; }
            Builder setSingleChoiceItems(CharSequence[] labels, int index, Listener callback) {
                this.labels = labels; selected = index; listener = callback; return this;
            }
            Builder setNegativeButton(int id, Listener l) { return this; }
            void show() { shown = this; }
        }
        void dismiss() {}
    }
    Tab mCurrentTab = new Tab();
    Profile mProfile = new Profile();
    Context mContext = new Context();
""" + ui.BIND_SITE + """
    public static void main(String[] args) {
        var screen = new SiteDialogTest();
        var contents = screen.mCurrentTab.contents;
        var row = new View();
        screen.bindSandiumAdRedirects(row);
        for (int choice : new int[]{1, 2, 0}) {
            row.click.accept(row);
            var dialog = AlertDialog.Builder.shown;
            assert dialog.selected == BravePrefServiceBridge.setting;
            assert Arrays.equals(dialog.labels, new String[]{
                    BravePrefServiceBridge.global ? "10" : "11", "12", "13"});
            dialog.listener.select(new AlertDialog(), choice);
            assert BravePrefServiceBridge.setting == choice;
            assert BravePrefServiceBridge.savedProfile == screen.mProfile;
            assert BravePrefServiceBridge.savedUrl.equals(contents.url);
            BravePrefServiceBridge.global = !BravePrefServiceBridge.global;
        }
        row.click.accept(row);
        var stale = AlertDialog.Builder.shown;
        contents.url = new GURL("https://different.example/");
        stale.listener.select(new AlertDialog(), 1);
        assert BravePrefServiceBridge.writes == 3;
        contents.url = new GURL("chrome://newtab/");
        var internal = new View();
        screen.bindSandiumAdRedirects(internal);
        assert !internal.enabled && internal.click == null;
    }
}
"""
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'SiteDialogTest.java'
            file.write_text(source)
            subprocess.run(['java', '-ea', str(file)], capture_output=True, text=True, check=True)


if __name__ == '__main__':
    unittest.main()
