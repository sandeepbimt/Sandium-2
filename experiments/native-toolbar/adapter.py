"""Explicit opt-in paint adapter; never navigation, layout, or control ownership."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).parent
PHONE='chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java'
PROGRESS='chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarProgressBar.java'
SHA='52bdd21723d5db0c9ab11716d38feac74828cf84'
PAINT='''        // RawS paint follows native focus expansion; never change control geometry.
        if (!isIncognitoBranded() && !isLocationBarShownInNtp()) {
            int max = Math.max(Color.red(color), Math.max(Color.green(color), Color.blue(color)));
            int min = Math.min(Color.red(color), Math.min(Color.green(color), Color.blue(color)));
            float darkWeight = Math.max(0f, Math.min(1f, (96f - max) / 64f));
            float neutralWeight = Math.max(0f, 1f - (max - min) / 16f);
            float resting = 1f - getExpansionFractionForVisualState(mVisualState);
            int lift = Math.round(8f * darkWeight * neutralWeight * resting);
            color = Color.argb(Color.alpha(color), Color.red(color) + lift,
                    Color.green(color) + lift, Color.blue(color) + lift);
        }
'''
METHOD='''    private boolean mRawSandiumPhonePalette;

    /** Phone opt-in; all native theme refreshes keep the same palette owner. */
    public void setRawSandiumPhoneThemeColor(int color, boolean isIncognito) {
        mRawSandiumPhonePalette = true;
        setThemeColor(color, isIncognito);
    }

    private void applyRawSandiumPhonePalette(int color, boolean isIncognito) {
        if (mRawSandiumPhonePalette && !isIncognito
                && ColorUtils.shouldUseLightForegroundOnBackground(color)) {
            setForegroundColor(0xFFE8E6DF);
            setBackgroundColor(Color.TRANSPARENT);
            if (ChromeFeatureList.sAndroidProgressBarVisualUpdate.isEnabled()) {
                setProgressGapBackgroundColor(Color.TRANSPARENT);
            }
        }
    }

'''
def transform(path,text):
    if path==PHONE:
        anchor='    private void updateModernLocationBarColor(@ColorInt int color) {\n'
        assert text.count(anchor)==1
        assert text.count('getProgressBar().setThemeColor(')==2
        return text.replace(anchor,anchor+PAINT).replace('getProgressBar().setThemeColor(', 'getProgressBar().setRawSandiumPhoneThemeColor(')
    if path==PROGRESS:
        anchor='    public void setThemeColor(int color, boolean isIncognito) {'
        assert text.count(anchor)==1
        start=text.index(anchor);end=text.index('    @Override\n    public void setForegroundColor',start)
        method=text[start:end]
        if method.count('            return;')!=1:raise ValueError('Native progress early exits changed')
        method=method.replace('            return;', '            applyRawSandiumPhonePalette(color, isIncognito);\n            return;')
        tail='        }\n    }\n\n'
        if not method.endswith(tail):raise ValueError('Native progress exit changed')
        method=method[:-len(tail)]+ '        }\n        applyRawSandiumPhonePalette(color, isIncognito);\n    }\n\n'
        return text[:start]+METHOD+method+text[end:]
    raise ValueError('Unknown toolbar source')
def plan(src):
    src=Path(src)
    if (src/'.git').exists():
        import subprocess
        if subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()!=SHA:
            raise ValueError('Wrong Chromium revision')
    manifest=json.loads((HERE/'provenance.json').read_text())
    result={}
    for path in (PHONE,PROGRESS):
        fixture=(HERE/'fixtures'/Path(path).name).read_text()
        if hashlib.sha256(fixture.encode()).hexdigest()!=manifest['sha256'][Path(path).name]:raise ValueError('Fixture drift')
        target=src/path;actual=target.read_text();expected=transform(path,fixture)
        if actual not in (fixture,expected):raise ValueError('Unreviewed toolbar source: '+path)
        result[target]=expected
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    changes=plan(args.source)
    if args.apply:
        for path,text in changes.items():path.write_text(text)
    print('Reviewed toolbar files:',len(changes),'applied:',args.apply)
