from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import seal
import welcome_visible_options as change


def extract(text, name, until):
    return text[text.index(name):text.index(until, text.index(name))]


class WelcomeVisibleOptionsTest(unittest.TestCase):
    def setUp(self):
        self.base = lambda path: seal.git('show', change.BASE + ':' + path)
        self.before = {name: self.base(seal.IMAGE + digest)
                       for name, digest in change.OWNERS.items()}
        self.after = {name: change.transform(name, data)
                      for name, data in self.before.items()}
        self.source = self.after[change.WELCOME].decode()

    def test_welcome_rows_always_present_and_keep_handlers(self):
        source = self.source
        prior = self.before[change.WELCOME].decode()
        self.assertNotIn('updateOptionsDisclosure(', source)
        self.assertNotIn('mOptions', source)
        self.assertNotIn('ACTION_EXPAND', source)
        self.assertNotIn('ACTION_COLLAPSE', source)
        self.assertIn('addInlineDnsPicker(settings, host);', source)
        rows = ('R.string.raws_setup_ads,', 'R.string.raws_setup_night,',
                'R.string.raws_setup_blur,', 'addInlineDnsPicker(settings, host);',
                'R.string.raws_setup_notifications,', 'R.string.raws_setup_cookie_block,')
        self.assertEqual(sorted(source.index(row) for row in rows),
                         [source.index(row) for row in rows])
        span = lambda text: extract(text, '        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU',
                                          '        TextView later =')
        self.assertEqual(span(source), span(prior).replace('(options', '(settings'))
        for a,b in (
                ('    private void addInlineDnsPicker(', '    private void divider('),
                ('    private Switch addSwitch(', '\n}'),
                ('    private void beginCountdown()', '    private static int remainingCountdownSteps'),
                ('    private void finishSetup()', '    private void showSaveFailure()')):
            self.assertEqual(extract(source,a,b), extract(prior,a,b))
        self.assertEqual(source.count('delegate.acceptTermsOfService('), 1)
        self.assertNotIn('mTermsDialog', source)

    def test_resource_diff_and_exact_overlay_seal(self):
        known = json.loads(Path(seal.RECIPE).read_text())['files']
        for path, output in self.after.items():
            self.assertEqual(known[path]['after_sha256'], hashlib.sha256(output).hexdigest())
            self.assertEqual(Path(seal.IMAGE, known[path]['after_sha256']).read_bytes(), output)
        def resources(name, state):
            return {item.attrib['name']: item.text for item in ET.fromstring(state[name])}
        before, after = [resources(change.PALETTE, files) for files in (self.before, self.after)]
        self.assertEqual(set(before) - set(after), {'raws_setup_more', 'raws_setup_fewer'})
        self.assertEqual(set(after) - set(before), {'raws_setup_agree_start', 'raws_setup_agree_restart'})
        self.assertEqual({k: before[k] for k in before.keys() & after.keys()},
                         {k: after[k] for k in before.keys() & after.keys()})
        before, after = [resources(change.STRINGS, files) for files in (self.before, self.after)]
        self.assertEqual(set(before) - set(after), {'raws_setup_terms_title', 'raws_setup_terms_agree'})
        self.assertEqual({k: before[k] for k in after}, after)
        self.assertIn('<TOS_LINK>Terms of Service</TOS_LINK>', after['raws_setup_terms_consent'])

    def test_actual_cta_source_preserves_explicit_linked_consent(self):
        if not shutil.which('java'): self.skipTest('JDK unavailable')
        source = self.source
        self.assertIn('mTermsDisclosure = terms;\n        body.addView(terms);\n        Button start', source)
        self.assertIn('mTermsDisclosure == view && isResumed()', source)
        self.assertIn('delegate.showInfoPage(R.string.google_terms_of_service_dark_mode_url)', source)
        self.assertIn('if (terms != null) terms.setVisibility(requiresConsent ? View.VISIBLE : View.GONE);', source)
        methods = extract(source, '    private static int readyActionLabel(', '    private void beginCountdown()')
        with tempfile.TemporaryDirectory() as td:
            java = Path(td, 'ConsentCtaTest.java')
            java.write_text(JAVA_HEAD + methods + JAVA_TEST)
            subprocess.run(['java', java], check=True)


JAVA_HEAD = r"""
class ConsentCtaTest {
    static class FirstRunUtils {
        static boolean accepted;
        static boolean isFirstRunEulaAccepted(){ return accepted; }
    }
    static class TextView {
        boolean attached=true, shown=true;
        boolean isAttachedToWindow(){ return attached; }
        boolean isShown(){ return shown; }
    }
    static class Button extends TextView {
        boolean enabled=true;
        String text;
        boolean isEnabled(){ return enabled; }
        String getText(){ return text; }
    }
    static class TextUtils {
        static boolean equals(CharSequence a, CharSequence b){ return java.util.Objects.equals(a,b); }
    }
    static class R { static class string {
        static int raws_setup_agree_start=1, raws_setup_agree_restart=2,
            raws_setup_start=3, raws_setup_restart=4;
    }}
    Button mStart = new Button();
    TextView mTermsDisclosure = new TextView();
    boolean mTermsConsentForSetup, ready=true, restart;
    int mRenderedButtonText, started, refreshed;
    void dismissInlineDnsPicker(){}
    boolean canStartSetupAttempt(){return ready;}
    boolean restartNeeded(){return restart;}
    String getString(int id){return "Label "+id;}
    void updateButton(){refreshed++;}
    void beginCountdown(){started++;}
"""

JAVA_TEST = r"""
    void check(boolean b){if(!b)throw new AssertionError();}
    void label(int id){mRenderedButtonText=id; mStart.text=getString(id);}
    public static void main(String... args){
        var a=new ConsentCtaTest();
        a.label(3);
        a.requestSetupCompletion();
        a.check(a.started==0 && a.refreshed==1 && !a.mTermsConsentForSetup);
        a.label(1);
        a.mTermsDisclosure.shown=false;
        a.requestSetupCompletion(); a.check(a.started==0);
        a.mTermsDisclosure.shown=true;
        a.mStart.text="stale visible text";
        a.requestSetupCompletion(); a.check(a.started==0);
        a.label(1);
        a.ready=false;
        a.requestSetupCompletion(); a.check(a.started==0);
        a.ready=true;
        a.mStart.enabled=false;
        a.requestSetupCompletion(); a.check(a.started==0);
        a.mStart.enabled=true;
        a.requestSetupCompletion();
        a.check(a.started==1 && a.mTermsConsentForSetup);
        a.clearTermsAttempt(); a.check(!a.mTermsConsentForSetup);
        a.restart=true;
        a.requestSetupCompletion(); a.check(a.started==1);
        a.label(2);
        a.requestSetupCompletion(); a.check(a.started==2 && a.mTermsConsentForSetup);
        FirstRunUtils.accepted=true;
        a.mTermsDisclosure=null; a.label(4);
        a.requestSetupCompletion(); a.check(a.started==3 && !a.mTermsConsentForSetup);
        a.check(readyActionLabel(false,false)==3 && readyActionLabel(false,true)==4);
    }
}
"""

if __name__ == '__main__':
    unittest.main()
