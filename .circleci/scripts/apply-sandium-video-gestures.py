#!/usr/bin/env python3
"""Pinned opt-in native video controls. Apply after removals/UI; no CI trigger."""
import argparse
from pathlib import Path
import subprocess

CHROMIUM_PIN = '52bdd21723d5db0c9ab11716d38feac74828cf84'
BRAVE_PIN = 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
ACTIVITY = 'android/java/org/chromium/chrome/browser/app/BraveActivity.java'
PACKAGE = 'org/chromium/chrome/browser/sandium/video/'


def once(text, before, after):
    if after in text:
        return text
    if text.count(before) != 1:
        raise ValueError('Pinned video anchor changed: ' + before[:100])
    return text.replace(before, after, 1)


def activity(text):
    # Pause drops gesture UI/brightness; destruction drops all observer/page references.
    text = once(text, '    @Override\n    public void onResumeWithNative() {', '''    // SANDIUM_NATIVE_VIDEO_GESTURES_V1
    private org.chromium.chrome.browser.sandium.video.SandiumVideoController mSandiumVideo;

    private void closeSandiumVideo() {
        if (mSandiumVideo != null) {
            mSandiumVideo.close();
            mSandiumVideo = null;
        }
    }

    @Override
    public void onResumeWithNative() {''')
    text = once(text, '        super.onResumeWithNative();', '''        super.onResumeWithNative();
        if (mSandiumVideo == null) {
            mSandiumVideo = new org.chromium.chrome.browser.sandium.video.SandiumVideoController(
                    this, getActivityTabProvider());
        } else {
            mSandiumVideo.setResumed(true);
        }''')
    text = once(text, '    public void onPauseWithNative() {', '''    public void onPauseWithNative() {
        if (mSandiumVideo != null) mSandiumVideo.setResumed(false);''')
    text = once(text, '    protected void onDestroyInternal() {', '''    protected void onDestroyInternal() {
        closeSandiumVideo();''')
    return text


def register(text, variable, entries):
    anchor = variable + ' = [\n'
    missing = [entry for entry in entries if '"' + entry + '"' not in text]
    if not missing:
        return text
    if text.count(anchor) != 1:
        raise ValueError('Pinned GN anchor changed: ' + variable)
    return text.replace(anchor, anchor + ''.join('  "' + entry + '",\n' for entry in missing), 1)


def transformations(src, repo):
    core = src / "brave"
    feature = repo / '.circleci/features/video-gestures'
    # Keep the stage explicit: future experimental Java must not enter by glob.
    names = ['SandiumVideoController.java', 'SandiumVideoGestureState.java',
             'SandiumVideoGestureView.java', 'SandiumVideoSessionAdapter.java']
    outputs = {core / ACTIVITY: activity((core / ACTIVITY).read_text())}
    gni = core / 'android/brave_java_sources.gni'
    outputs[gni] = register(gni.read_text(), 'brave_java_sources',
            ['../../brave/android/java/' + PACKAGE + name for name in names])
    resources = core / 'android/BUILD.gn'
    anchor = '    "java/brave-res/values/brave_ids.xml",\n'
    entry = '    "java/brave-res/values/sandium_video_strings.xml",\n'
    current = resources.read_text()
    outputs[resources] = once(current, anchor, anchor + entry)
    for name in names:
        outputs[core / 'android/java' / PACKAGE / name] = (feature / 'java' / PACKAGE / name).read_text()
    outputs[core / 'android/java/brave-res/values/sandium_video_strings.xml'] = (
            feature / 'res/values/sandium_video_strings.xml').read_text()
    # First-stage release scope is Java fullscreen controls ONLY. Experimental
    # inline DOM/native bridges are intentionally excluded, not merely feature-off.
    # Do not silently reuse a checkout previously containing the DOM injection.
    for relative in ('browser/brave_tab_helpers.cc', 'browser/sources.gni'):
        existing=(core / relative).read_text()
        if 'sandium_video' in existing or 'SandiumVideoTabHelper' in existing:
            raise ValueError('Experimental video helper present; use clean source checkpoint')
    return outputs


def apply(src, repo, verify_only=False):
    core = src / 'brave'
    for path, pin in ((src, CHROMIUM_PIN), (core, BRAVE_PIN)):
        actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != pin:
            raise ValueError('Source pin mismatch: ' + str(path))
    outputs = transformations(src, repo)
    for path, expected in outputs.items():
        if verify_only:
            if not path.exists() or path.read_text() != expected:
                raise ValueError('Video source contract drift: ' + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected)
    print('SANDIUM_VIDEO_SOURCE_CONTRACT=PASS (not runtime verification)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('src', type=Path)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    apply(args.src, args.repo, args.verify_only)
