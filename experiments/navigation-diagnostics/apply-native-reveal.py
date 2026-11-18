"""Bounded native reveal geometry; preserves the pinned native alpha delegate."""
from pathlib import Path
PATH='chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java'
HELPER=Path(__file__).with_name('native-reveal-helper.java').read_text()
ANCHOR='    private @Nullable NtpSmoothTransitionDelegate mSmoothTransitionDelegate;'
RETURN='        return mSmoothTransitionDelegate;'
WRAPPER='''        // Do not wrap or retain a probe outside an opted-in recording.
        if (!sandiumRevealEnabled()) {
            return mSmoothTransitionDelegate;
        }
        final NtpSmoothTransitionDelegate delegate = mSmoothTransitionDelegate;
        return new SmoothTransitionDelegate() {
            @Override public void prepare() {
                stopSandiumReveal(4);
                delegate.prepare();
            }
            @Override public void start(Runnable onEnd) {
                beginSandiumReveal();
                if (mSandiumRevealProbe != null) mSandiumRevealProbe.sample(1);
                final SandiumRevealProbe probe = mSandiumRevealProbe;
                delegate.start(() -> {
                    if (probe != null) probe.sample(3);
                    try {
                        onEnd.run();
                    } finally {
                        if (probe != null) probe.afterReveal();
                    }
                });
            }
            @Override public void cancel() {
                stopSandiumReveal(4);
                delegate.cancel();
            }
        };'''
def transform(s):
 if HELPER in s and WRAPPER in s:return s
 if 'SANDIUM_NATIVE_REVEAL_V1' in s:raise ValueError('Unknown native reveal producer')
 if s.count(ANCHOR)!=1:raise ValueError('Native delegate field drift')
 # Testing getter also returns this field; replace only within enable method.
 start=s.index('    public SmoothTransitionDelegate enableSmoothTransition() {')
 end=s.index('\n    public @Nullable SmoothTransitionDelegate getSmoothTransitionDelegateForTesting()',start)
 part=s[start:end]
 if part.count(RETURN)!=1:raise ValueError('Native delegate return drift')
 s=s[:start]+part.replace(RETURN,WRAPPER,1)+s[end:]
 return s.replace(ANCHOR,ANCHOR+'\n'+HELPER,1)
