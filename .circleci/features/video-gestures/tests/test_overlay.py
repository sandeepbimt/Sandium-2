"""Pinned anchor test. Explicit Brave checkout argument; never modifies that checkout."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

repo = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('video', repo / '.circleci/scripts/apply-sandium-video-gestures.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
core = Path(sys.argv[1])
def blob(path):
    return subprocess.check_output(['git', '-C', str(core), 'show', v.BRAVE_PIN + ':' + path], text=True)
source = blob(v.ACTIVITY)
patched = v.activity(source)
assert v.activity(patched) == patched
assert patched.count('new org.chromium.chrome.browser.sandium.video.SandiumVideoController(') == 1
assert patched.count('mSandiumVideo.setResumed(false);') == 1
source = blob('android/brave_java_sources.gni')
entries = ['../../brave/android/java/' + v.PACKAGE + p.name
           for p in (repo / '.circleci/features/video-gestures/java' / v.PACKAGE).glob('*.java')]
patched = v.register(source, 'brave_java_sources', entries)
assert v.register(patched, 'brave_java_sources', entries) == patched
for entry in entries: assert patched.count('"'+entry+'"') == 1
source = blob('android/BUILD.gn')
a = '    "java/brave-res/values/brave_ids.xml",\n'
b = a + '    "java/brave-res/values/sandium_video_strings.xml",\n'
assert v.once(v.once(source,a,b),a,b) == v.once(source,a,b)
strings = ET.parse(repo / '.circleci/features/video-gestures/res/values/sandium_video_strings.xml').getroot()
assert len({node.get('name') for node in strings}) == len(strings)
try: v.activity('wrong source')
except ValueError: pass
else: raise AssertionError('Drift not rejected')
print('Pinned video source transforms/idempotence/resource uniqueness/drift tests passed')

# Exercise complete apply/readback using exact pinned Brave fixture bytes. The isolated
# fixture has no git history; only rev-parse is mocked, not file content or transforms.
import tempfile
from unittest.mock import patch
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp)
    fixture = src / 'brave'
    for path in (v.ACTIVITY, 'android/brave_java_sources.gni', 'android/BUILD.gn',
                 'browser/brave_tab_helpers.cc', 'browser/sources.gni'):
        dest = fixture / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(blob(path))
    def revision(cmd, **kwargs):
        assert cmd[:2] == ['git', '-C'] and cmd[-2:] == ['rev-parse', 'HEAD']
        return (v.BRAVE_PIN if cmd[2] == str(fixture) else v.CHROMIUM_PIN) + '\n'
    with patch.object(v.subprocess, 'check_output', side_effect=revision):
        v.apply(src, repo)
        first = {str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
        v.apply(src, repo)
        v.apply(src, repo, True)
        assert first == {str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
    assert not (fixture / 'browser/android/sandium_video').exists()
    assert (fixture / 'browser/brave_tab_helpers.cc').read_text() == blob('browser/brave_tab_helpers.cc')
    assert (fixture / 'browser/sources.gni').read_text() == blob('browser/sources.gni')
    helper=fixture / 'browser/brave_tab_helpers.cc'
    helper.write_text(helper.read_text()+'\n// SandiumVideoTabHelper stale test\n')
    with patch.object(v.subprocess, 'check_output', side_effect=revision):
        try: v.apply(src, repo)
        except ValueError as error: assert 'clean source checkpoint' in str(error)
        else: raise AssertionError('Stale experimental helper not rejected')
print('Fullscreen-only Java overlay replay/readback and experimental exclusion passed (no native compilation)')
