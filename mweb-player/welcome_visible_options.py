"""RawS #1520: always-visible Welcome options and explicit inline terms consent."""

import argparse
import hashlib
from pathlib import Path

from glue import once
import seal

BASE = '16f95596b9316caa1a464c36845668761758b0e9'
WELCOME = ('chrome/android/java/src/org/chromium/chrome/browser/firstrun/'
           'RawSSetupFirstRunFragment.java')
PALETTE = 'chrome/android/java/res/values/raws_welcome_palette.xml'
STRINGS = 'chrome/android/java/res/values/raws_main_settings_strings.xml'
OWNERS = {
    WELCOME: '7c80cf941aaa94c3062e2805ae16242f270b06271761aed896e419d9b86f96dc',
    PALETTE: '38c1e1c63e95d1b8ddc7656e87ba0c273634e00652ed3e620f475fddef2b37e0',
    STRINGS: '9b403197f413f407d660c8d0644de065f0920d9bb90fc9a95bff5953f70ee95e',
}


def transform(path, data):
    if OWNERS.get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError(f'unexpected Welcome preimage: {path}')
    text = data.decode()

    def edit(old, new=''):
        nonlocal text
        text = once(text, old, new)

    if path == PALETTE:
        edit('    <string name="raws_setup_more">More options</string>\n')
        edit('    <string name="raws_setup_fewer">Fewer options</string>\n')
        edit('    <string name="raws_setup_restart">Quick Restart</string>\n',
             '    <string name="raws_setup_restart">Quick Restart</string>\n'
             '    <string name="raws_setup_agree_start">Agree and start browsing</string>\n'
             '    <string name="raws_setup_agree_restart">Agree and restart</string>\n')
        return text.encode()
    if path == STRINGS:
        edit('    <string name="raws_setup_terms_title">Terms of Service</string>\n')
        edit('    <string name="raws_setup_terms_agree">Agree and continue</string>\n')
        return text.encode()

    for removed_import in ('android.graphics.Paint', 'android.graphics.Path',
                           'android.graphics.drawable.ShapeDrawable',
                           'android.graphics.drawable.shapes.PathShape',
                           'android.view.accessibility.AccessibilityNodeInfo'):
        edit(f'import {removed_import};\n')
    edit('    private @Nullable LinearLayout mOptions;\n')
    edit('    private @Nullable AlertDialog mTermsDialog;\n',
         '    private @Nullable TextView mTermsDisclosure;\n')

    start = '        Button more = rowButton(settings, R.string.raws_setup_more, () -> {});'
    end = '        addInlineDnsPicker(options, host);'
    edit(text[text.index(start):text.index(end)])
    edit('        addInlineDnsPicker(options, host);', '        addInlineDnsPicker(settings, host);')
    edit('''            divider(options);
            addSwitch(options, R.string.raws_setup_notifications,''',
         '''            divider(settings);
            addSwitch(settings, R.string.raws_setup_notifications,''')
    edit('''        divider(options);
        addSwitch(options, R.string.raws_setup_cookie_block,''',
         '''        divider(settings);
        addSwitch(settings, R.string.raws_setup_cookie_block,''')
    edit('''        if (mOptions != null) mOptions.animate().cancel();
        if (mTracer != null) mTracer.close();
        mOptions = null;''', '''        if (mTracer != null) mTracer.close();
        mTermsDisclosure = null;''')

    start = '    private void updateOptionsDisclosure(Button disclosure, boolean expanded) {'
    end = '    private Button rowButton(LinearLayout parent, int title, Runnable action) {'
    edit(text[text.index(start):text.index(end)])

    edit('''        body.addView(later);
        Button start = new Button(host);''', '''        body.addView(later);
        TextView terms = createTermsDisclosure();
        mTermsDisclosure = terms;
        body.addView(terms);
        Button start = new Button(host);''')
    edit('''        boolean ready = protectionReady();
        int label = ready ? (restartNeeded() ? R.string.raws_setup_restart
                                            : R.string.raws_setup_start)
                          : R.string.raws_setup_preparing_button;''', '''        boolean ready = protectionReady();
        boolean requiresConsent = !FirstRunUtils.isFirstRunEulaAccepted();
        TextView terms = mTermsDisclosure;
        if (terms != null) terms.setVisibility(requiresConsent ? View.VISIBLE : View.GONE);
        int label = ready ? readyActionLabel(requiresConsent, restartNeeded())
                          : R.string.raws_setup_preparing_button;''')

    start = '    private void requestSetupCompletion() {'
    end = '    private void beginCountdown() {'
    edit(text[text.index(start):text.index(end)], '''    private TextView createTermsDisclosure() {
        var context = requireContext();
        TextView terms = text(R.string.raws_setup_terms_consent, 13, SECONDARY);
        terms.setText(SpanApplier.applySpans(getString(R.string.raws_setup_terms_consent),
                new SpanApplier.SpanInfo("<TOS_LINK>", "</TOS_LINK>",
                        new ChromeClickableSpan(context, view -> {
                            var delegate = getPageDelegate();
                            if (mTermsDisclosure == view && isResumed() && !mConfirmed
                                    && mCountdownEnd == 0 && !mAdsWritePending && delegate != null) {
                                delegate.showInfoPage(R.string.google_terms_of_service_dark_mode_url);
                            }
                        }))));
        terms.setMovementMethod(LinkMovementMethod.getInstance());
        terms.setPadding(dp(4), dp(6), dp(4), dp(8));
        terms.setVisibility(FirstRunUtils.isFirstRunEulaAccepted() ? View.GONE : View.VISIBLE);
        return terms;
    }

    private static int readyActionLabel(boolean requiresConsent, boolean restart) {
        if (requiresConsent) {
            return restart ? R.string.raws_setup_agree_restart : R.string.raws_setup_agree_start;
        }
        return restart ? R.string.raws_setup_restart : R.string.raws_setup_start;
    }

    private void requestSetupCompletion() {
        dismissInlineDnsPicker();
        if (!canStartSetupAttempt()) return;
        Button start = mStart;
        if (start == null || !start.isEnabled() || !start.isAttachedToWindow()) return;
        boolean requiresConsent = !FirstRunUtils.isFirstRunEulaAccepted();
        if (requiresConsent) {
            TextView terms = mTermsDisclosure;
            int consentLabel = readyActionLabel(true, restartNeeded());
            // An already-rendered plain Start/Restart tap cannot be turned into consent.
            if (terms == null || !terms.isAttachedToWindow() || !terms.isShown()
                    || mRenderedButtonText != consentLabel
                    || !TextUtils.equals(start.getText(), getString(consentLabel))) {
                updateButton();
                return;
            }
        }
        mTermsConsentForSetup = requiresConsent;
        beginCountdown();
    }

    private void clearTermsAttempt() {
        mTermsConsentForSetup = false;
    }

''')
    return text.encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    read = lambda name: seal.git('show', BASE + ':' + name)
    output = seal.plan(read, owners=OWNERS, edit=transform, man=seal.digest(read(seal.RECIPE)),
                       proof=seal.digest(read(seal.ADMISSION)))
    if args.write:
        if Path.cwd() != Path(__file__).resolve().parents[1]:
            raise ValueError('run from checkout root')
        if seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
            raise ValueError('unexpected Welcome checkout base')
        for name, data in output.items():
            target = Path(name)
            if target.is_symlink() or (target.exists() and target.read_bytes() !=
                    (data if name.startswith(seal.IMAGE) else read(name))):
                raise ValueError('dirty or unsafe overlay path: ' + name)
        for name, data in output.items():
            Path(name).write_bytes(data)
    for name, data in sorted(output.items()):
        print(seal.digest(data), name)


if __name__ == '__main__':
    main()
