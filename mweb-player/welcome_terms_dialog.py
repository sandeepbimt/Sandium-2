"""Replace inline RawS Welcome terms with explicit terms-only consent."""
import argparse
from pathlib import Path

from glue import once
import seal

BASE = 'b3f85cebb7e11c3f9641827f858d50a7f4958e73'
MAN = '8da84e15ba5806571a25b104459aa50f974d9b027d762be7e7e905dd92dd288e'
PROOF = 'f26a8f81bc6f7590166e9aa5608d2a80a92b4a9f8959e2c86b2d135b835ff226'
WELCOME = ('chrome/android/java/src/org/chromium/chrome/browser/firstrun/'
           'RawSSetupFirstRunFragment.java')
STRINGS = 'chrome/android/java/res/values/raws_main_settings_strings.xml'
OWNERS = {
    WELCOME: '4e188ab7839ef3deae2773931cca7194158ef630cb190587ac835e544e8ddab6',
    STRINGS: '137fb385311d00cbd3539fd80948ded61066519e2f0715e8789ffd01ad2cd27b',
}


def transform(path, raw):
    s = raw.decode()
    if path == STRINGS:
        return once(s, '    <string name="raws_setup_terms_consent">By selecting Start Browsing or '
                    'Quick Restart, you agree to the Google &lt;TOS_LINK&gt;Terms of Service'
                    '&lt;/TOS_LINK&gt;.</string>', '''
    <string name="raws_setup_terms_title">Terms of Service</string>
    <string name="raws_setup_terms_consent">To continue, read and agree to the Google &lt;TOS_LINK&gt;Terms of Service&lt;/TOS_LINK&gt;.</string>
    <string name="raws_setup_terms_agree">Agree and continue</string>'''.lstrip('\n')).encode()
    if path != WELCOME:
        raise ValueError(path)
    s = once(s, '    private boolean mTermsDisclosureShown;',
             '    private @Nullable AlertDialog mTermsDialog;\n'
             '    private boolean mTermsConsentForSetup;')
    start = '        mTermsDisclosureShown = !FirstRunUtils.isFirstRunEulaAccepted();\n'
    end = '        TextView later = text(R.string.raws_setup_later, 13, SECONDARY);'
    s = once(s, s[s.index(start):s.index(end)], '')
    s = once(s, '        start.setOnClickListener(v -> beginCountdown());',
                '        start.setOnClickListener(v -> requestSetupCompletion());')
    s = once(s, '    public void onPause() {\n        stopPreparingDots();',
                '    public void onPause() {\n        clearTermsAttempt();\n        stopPreparingDots();')
    s = once(s, '        mTermsDisclosureShown = false;',
                '        clearTermsAttempt();')
    s = once(s, '''            // A replacement generation or failed backend invalidates the user's acceptance.
            mCountdownEnd = 0;''', '''            // A replacement generation or failed backend invalidates this setup attempt.
            mTermsConsentForSetup = false;
            mCountdownEnd = 0;''')
    anchor = '''    private void beginCountdown() {
        dismissInlineDnsPicker();
        if (!isResumed() || mConfirmed || mAdsWritePending || mCountdownEnd != 0
                || !protectionReady()) {
            return;
        }
        Button start = mStart;'''
    replacement = '''    private boolean canStartSetupAttempt() {
        return isResumed() && !mConfirmed && !mAdsWritePending && mCountdownEnd == 0
                && mStart != null && protectionReady()
                && getActivity() instanceof FirstRunActivity activity
                && activity.isRawSSetupCurrent();
    }

    private void requestSetupCompletion() {
        dismissInlineDnsPicker();
        if (!canStartSetupAttempt() || mTermsDialog != null) return;
        if (FirstRunUtils.isFirstRunEulaAccepted()) {
            beginCountdown();
            return;
        }

        // This prompt has no account or metrics option and is shown only from the CTA.
        var context = requireContext();
        TextView terms = text(R.string.raws_setup_terms_consent, 14, PRIMARY_TEXT);
        terms.setText(SpanApplier.applySpans(getString(R.string.raws_setup_terms_consent),
                new SpanApplier.SpanInfo("<TOS_LINK>", "</TOS_LINK>",
                        new ChromeClickableSpan(context, view -> {
                            var delegate = getPageDelegate();
                            if (mTermsDialog != null && isResumed() && delegate != null) {
                                delegate.showInfoPage(R.string.google_terms_of_service_dark_mode_url);
                            }
                        }))));
        terms.setMovementMethod(LinkMovementMethod.getInstance());
        terms.setPadding(dp(24), dp(16), dp(24), dp(4));

        AlertDialog prompt = new AlertDialog.Builder(context)
                .setTitle(R.string.raws_setup_terms_title)
                .setView(terms)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.raws_setup_terms_agree, (dialog, which) -> {
                    if (dialog != mTermsDialog || !canStartSetupAttempt()) return;
                    mTermsDialog = null;
                    mTermsConsentForSetup = true;
                    beginCountdown();
                })
                .create();
        mTermsDialog = prompt;
        prompt.setOnDismissListener(dialog -> {
            if (mTermsDialog == prompt) {
                mTermsDialog = null;
                mTermsConsentForSetup = false;
            }
        });
        prompt.show();
    }

    private void clearTermsAttempt() {
        mTermsConsentForSetup = false;
        AlertDialog prompt = mTermsDialog;
        mTermsDialog = null;
        if (prompt != null) prompt.dismiss();
    }

    private void beginCountdown() {
        if (!canStartSetupAttempt()
                || (!FirstRunUtils.isFirstRunEulaAccepted() && !mTermsConsentForSetup)) {
            mTermsConsentForSetup = false;
            return;
        }
        Button start = mStart;'''
    s = once(s, anchor, replacement)
    s = once(s, '''    private void finishSetup() {
        if (mAdsWritePending || mConfirmed) return;''', '''    private void finishSetup() {
        if (!isResumed() || mAdsWritePending || mConfirmed) return;''')
    s = once(s, 'if (!FirstRunUtils.isFirstRunEulaAccepted() && !mTermsDisclosureShown)',
             'if (!FirstRunUtils.isFirstRunEulaAccepted() && !mTermsConsentForSetup)')
    s = once(s, '''        if (!protectionReady()) {
            mRenderedButtonText = 0;''', '''        if (!protectionReady()) {
            mTermsConsentForSetup = false;
            mRenderedButtonText = 0;''')
    s = once(s, '''        if (!FirstRunUtils.isFirstRunEulaAccepted()) {
            // Only the explicit, disclosed Start Browsing/Quick Restart action
            // reaches here. Use Chromium's ToS owner, never infer consent on load.
            delegate.acceptTermsOfService(/* allowMetricsAndCrashUploading= */ false);
        }
        mConfirmed = true;
        delegate.advanceToNextPage();''', '''        mConfirmed = true;
        mTermsConsentForSetup = false;
        if (!FirstRunUtils.isFirstRunEulaAccepted()) {
            // Explicit agreement, still-current setup, and successful settings writes
            // are all required. Preserve Chromium's single acceptance owner.
            delegate.acceptTermsOfService(/* allowMetricsAndCrashUploading= */ false);
        }
        delegate.advanceToNextPage();''')
    s = once(s, '''    private void showSaveFailure() {
        mSaveFailed = true;''', '''    private void showSaveFailure() {
        mTermsConsentForSetup = false;
        mSaveFailed = true;''')
    return s.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if Path.cwd() != Path(__file__).resolve().parents[1]:
        raise ValueError('run in checkout root')
    read = lambda name: seal.git('show', BASE + ':' + name)
    out = seal.plan(read, owners=OWNERS, edit=transform, man=MAN, proof=PROOF)
    if args.write:
        if seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
            raise ValueError('wrong checkout')
        for name, data in out.items():
            p = Path(name)
            if p.is_symlink() or (p.exists() and p.read_bytes() !=
                    (data if name.startswith(seal.IMAGE) else read(name))):
                raise ValueError('dirty or unsafe overlay path: ' + name)
    for name, data in sorted(out.items()):
        if args.write:
            Path(name).write_bytes(data)
        print(seal.digest(data), name)


if __name__ == '__main__':
    main()
