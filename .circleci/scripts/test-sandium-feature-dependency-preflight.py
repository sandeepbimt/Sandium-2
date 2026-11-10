#!/usr/bin/env python3
"""Unit tests for the deterministic dependency preflight transforms."""
from pathlib import Path
import importlib.util
import tempfile
from contextlib import redirect_stdout
from io import StringIO

SCRIPT = Path(__file__).with_name("sandium-feature-dependency-preflight.py")
spec = importlib.util.spec_from_file_location("sandium_preflight", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

def main():
    fixture = '''android_test_exception_deps = [
  "//brave/browser/brave_news:browser_tests",
  "//brave/browser/brave_wallet:browser_tests",
]
if (enable_brave_news) {
  android_test_exception_deps += [ "//brave/browser/brave_news:browser_tests" ]
}
deps -= android_test_exception_deps
'''
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "android_browser_tests.gni"
        p.write_text(fixture, encoding="utf-8")
        assert module.fix_news(p) is True
        fixed = p.read_text(encoding="utf-8")
        assert '"//brave/browser/brave_news:browser_tests"' not in fixed
        assert '"//brave/browser/brave_wallet:browser_tests"' in fixed
        assert "if (exception_dep in deps)" in fixed
        assert module.fix_news(p) is False
        assert p.read_text(encoding="utf-8") == fixed
    nested = '''if (!is_android) {
  if (enable_brave_news) {
    deps += [ "//brave/browser/ui/webui/brave_news" ]
  }
}
'''
    found = module.guards(nested, "//brave/browser/ui/webui/brave_news")
    assert len(found) == 1 and module.guarded(found[0][1], "enable_brave_news")
    assert any("!is_android" in g for g in found[0][1])
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "android").mkdir()
        gni = root / "android/brave_java_sources.gni"
        gni.write_text('''brave_java_sources = [
  "../../brave/android/java/org/chromium/chrome/browser/brave_leo/BraveLeoUtils.java",
  "../../brave/android/java/org/chromium/chrome/browser/brave_news/BraveNewsUtils.java",
  "../../brave/android/java/org/chromium/chrome/browser/crypto_wallet/BraveWalletActivity.java",
]
''', encoding="utf-8")
        try:
            module.audit_android_java_sources(root)
        except RuntimeError as error:
            assert "ANDROID_JAVA_SOURCE_CLOSURE" in str(error)
        else:
            raise AssertionError("unconditional feature Java source entries must fail")
        gni.write_text('''brave_java_sources = [
]
if (enable_ai_chat) {
  brave_java_sources += [ "../../brave/android/java/org/chromium/chrome/browser/brave_leo/BraveLeoUtils.java" ]
}
if (enable_brave_news) {
  brave_java_sources += [ "../../brave/android/java/org/chromium/chrome/browser/brave_news/BraveNewsUtils.java" ]
}
if (enable_brave_wallet) {
  brave_java_sources += [ "../../brave/android/java/org/chromium/chrome/browser/crypto_wallet/BraveWalletActivity.java" ]
}
''', encoding="utf-8")
        module.audit_android_java_sources(root)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        gni = root / "android/brave_java_sources.gni"
        gni.parent.mkdir(parents=True)
        gni.write_text('''brave_java_sources = [
  "../../brave/android/java/org/chromium/chrome/browser/brave_leo/BraveLeoMojomHelper.java",
]
''', encoding="utf-8")
        candidate = root / "android/java/org/chromium/chrome/browser/brave_leo/BraveLeoMojomHelper.java"
        caller = root / "android/java/org/chromium/chrome/browser/browsing_data/BraveClearBrowsingDataFragment.java"
        candidate.parent.mkdir(parents=True)
        caller.parent.mkdir(parents=True)
        candidate.write_text("class BraveLeoMojomHelper {}\\n", encoding="utf-8")
        caller.write_text("class BraveClearBrowsingDataFragment { BraveLeoMojomHelper helper; }\\n", encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            module.audit_android_java_source_references(root)
        assert "JAVA_EXTERNAL_REFERENCE_EDGES=1" in output.getvalue()
        assert "BraveClearBrowsingDataFragment.java" in output.getvalue()
    print("SANDIUM_FEATURE_DEPENDENCY_PREFLIGHT_TEST=PASS")

if __name__ == "__main__":
    main()
