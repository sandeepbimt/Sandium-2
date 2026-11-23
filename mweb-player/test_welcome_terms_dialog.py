"""Verification of the admitted Welcome terms-only change."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from xml.etree import ElementTree

import seal
import welcome_terms_dialog as d

ROOT = Path(__file__).resolve().parents[1]


class WelcomeTermsDialogTest(unittest.TestCase):
    def read_pair(self):
        recipe = json.loads((ROOT / seal.RECIPE).read_bytes())['files']
        def load(name):
            return (ROOT / seal.IMAGE / recipe[name]['after_sha256']).read_text()
        return load(d.WELCOME), load(d.STRINGS)

    def test_exact_two_owners_and_no_inline_terms_or_account(self):
        read = lambda name: seal.git('show', d.BASE + ':' + name)
        patch = seal.plan(read, d.OWNERS, d.MAN, d.PROOF, d.transform)
        for name, data in patch.items():
            self.assertEqual((ROOT / name).read_bytes(), data)
        welcome, strings = self.read_pair()
        self.assertNotIn('By selecting Start Browsing or Quick Restart', strings)
        self.assertNotIn('body.addView(terms)', welcome)
        self.assertNotIn('TermsDisclosureShown', welcome)
        self.assertNotIn('Add Account', welcome)
        keys = {x.attrib['name']: x.text for x in ElementTree.fromstring(strings)}
        self.assertEqual(keys['raws_setup_terms_agree'], 'Agree and continue')
        self.assertIn('<TOS_LINK>Terms of Service</TOS_LINK>', keys['raws_setup_terms_consent'])

    def test_native_acceptance_after_explicit_current_successful_settings(self):
        welcome, _ = self.read_pair()
        start = welcome.index('    private void finishSetup()')
        end = welcome.index('    private void showSaveFailure()', start)
        method = welcome[start:end]
        steps = ['if (!isResumed()', 'activity.isRawSSetupCurrent()',
                 '!FirstRunUtils.isFirstRunEulaAccepted() && !mTermsConsentForSetup',
                 'if (!protectionReady())', 'persistAcceptedAdsChoice(profile)',
                 'RawSDarkPages.setGlobal(profile, mStagedDarkPages)',
                 'commitBlurLevel(mStagedBlur)', 'if (!next.commit())', 'mConfirmed = true',
                 'delegate.acceptTermsOfService(/* allowMetricsAndCrashUploading= */ false)',
                 'delegate.advanceToNextPage()']
        positions = [method.index(x) for x in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(welcome.count('acceptTermsOfService('), 1)
        self.assertIn('public void onPause() {\n        clearTermsAttempt();', welcome)
        self.assertIn('public void onDestroyView() {\n        clearTermsAttempt();', welcome)
        self.assertIn('private void showSaveFailure() {\n        mTermsConsentForSetup = false;',
                      welcome)
        self.assertNotIn('state.putBoolean("terms', welcome)

    def test_production_dialog_callbacks_reject_cancel_back_and_stale(self):
        java = shutil.which('java')
        if java is None:
            self.skipTest('Java source launcher absent')
        welcome, _ = self.read_pair()
        start = welcome.index('    private boolean canStartSetupAttempt()')
        end = welcome.index('    private void beginCountdown()', start)
        methods = welcome[start:end]
        fixture = r"""
class Check {
  static void ok(boolean v) { if (!v) throw new AssertionError(); }
  public static void main(String[] args) {
    RawSetup setup = new RawSetup();
    setup.requestSetupCompletion();
    ok(setup.mTermsDialog != null && setup.started == 0 && !setup.mTermsConsentForSetup);
    var stale = setup.mTermsDialog;
    var link = stale.view.text.clickable();
    link.onClick(null);
    ok(setup.delegate.pageViews == 1 && !setup.mTermsConsentForSetup);
    setup.requestSetupCompletion();
    ok(setup.mTermsDialog == stale);
    stale.dismiss(); // Back/Cancel just dismiss the dialog.
    ok(setup.mTermsDialog == null && setup.started == 0 && !setup.mTermsConsentForSetup);
    stale.agree();
    ok(setup.started == 0);
    setup.requestSetupCompletion();
    var interrupted = setup.mTermsDialog;
    setup.clearTermsAttempt();
    interrupted.agree();
    ok(setup.started == 0 && !setup.mTermsConsentForSetup);
    setup.requestSetupCompletion();
    setup.activity.active = false;
    setup.mTermsDialog.agree();
    ok(setup.started == 0 && !setup.mTermsConsentForSetup);
    setup.activity.active = true;
    setup.requestSetupCompletion();
    var accept = setup.mTermsDialog;
    accept.agree();
    ok(setup.started == 1 && setup.mTermsConsentForSetup && setup.mTermsDialog == null);
    accept.agree();
    ok(setup.started == 1);
    var exempt = new RawSetup();
    FirstRunUtils.accepted = true;
    exempt.requestSetupCompletion();
    ok(exempt.started == 1 && exempt.mTermsDialog == null && !exempt.mTermsConsentForSetup);
  }
}
class RawSetup {
  AlertDialog mTermsDialog;
  boolean mTermsConsentForSetup, mConfirmed, mAdsWritePending, resumed = true;
  long mCountdownEnd;
  int started;
  Object mStart = new Object();
  FirstRunActivity activity = new FirstRunActivity();
  Delegate delegate = new Delegate();
  static final int PRIMARY_TEXT = 0;
  Object getActivity() { return activity; }
  boolean isResumed() { return resumed; }
  boolean protectionReady() { return true; }
  void dismissInlineDnsPicker() {}
  Object requireContext() { return this; }
  String getString(int id) { return "fixture"; }
  TextView text(int id, int size, int color) { return new TextView(); }
  int dp(int x) { return x; }
  Delegate getPageDelegate() { return delegate; }
  void beginCountdown() { started++; }
  // Package-private only in the fixture so the driver can invoke callbacks.
  METHODS
}
class R {
  static class string {
    static final int raws_setup_terms_consent = 1, raws_setup_terms_title = 2,
        raws_setup_terms_agree = 3, google_terms_of_service_dark_mode_url = 4;
  }
}
class android { static class R { static class string { static final int cancel = 5; } } }
class FirstRunUtils {
  static boolean accepted;
  static boolean isFirstRunEulaAccepted() { return accepted; }
}
class FirstRunActivity {
  boolean active = true;
  boolean isRawSSetupCurrent() { return active; }
}
class Delegate {
  int pageViews;
  void showInfoPage(int url) { if (url != 4) throw new AssertionError(); pageViews++; }
}
class TextView {
  SpanApplier.SpanInfo text;
  void setText(SpanApplier.SpanInfo x) { text = x; }
  void setMovementMethod(Object x) {}
  void setPadding(int a, int b, int c, int d) {}
}
class LinkMovementMethod { static Object getInstance() { return new Object(); } }
class ChromeClickableSpan {
  java.util.function.Consumer<Object> callback;
  ChromeClickableSpan(Object context, java.util.function.Consumer<Object> callback) {
    this.callback = callback;
  }
  void onClick(Object view) { callback.accept(view); }
}
class SpanApplier {
  record SpanInfo(String open, String close, ChromeClickableSpan clickable) {}
  static SpanInfo applySpans(String text, SpanInfo info) { return info; }
}
class AlertDialog {
  interface ButtonClick { void click(AlertDialog dialog, int which); }
  interface Dismiss { void done(AlertDialog dialog); }
  ButtonClick positive;
  Dismiss onDismiss;
  TextView view;
  boolean showing;
  void setOnDismissListener(Dismiss d) { onDismiss = d; }
  void show() { showing = true; }
  void dismiss() {
    if (showing) { showing = false; if (onDismiss != null) onDismiss.done(this); }
  }
  void agree() { positive.click(this, 0); dismiss(); }
  static class Builder {
    AlertDialog dialog = new AlertDialog();
    Builder(Object context) {}
    Builder setTitle(int res) { return this; }
    Builder setView(TextView view) { dialog.view = view; return this; }
    Builder setNegativeButton(int res, ButtonClick action) { return this; }
    Builder setPositiveButton(int res, ButtonClick action) { dialog.positive = action; return this; }
    AlertDialog create() { return dialog; }
  }
}
"""
        fixture = fixture.replace('METHODS', methods.replace('    private ', '    '))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'Check.java'
                p.write_text(fixture)
                subprocess.run([java, str(p)], check=True)
        except subprocess.CalledProcessError:
            self.fail('Java execution of the extracted production dialog callbacks failed')


if __name__ == '__main__':
    unittest.main()
