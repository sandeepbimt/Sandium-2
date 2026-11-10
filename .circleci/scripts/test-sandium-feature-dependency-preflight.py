#!/usr/bin/env python3
"""Unit tests for the deterministic dependency preflight transforms."""
from pathlib import Path
import importlib.util
import tempfile

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
    print("SANDIUM_FEATURE_DEPENDENCY_PREFLIGHT_TEST=PASS")

if __name__ == "__main__":
    main()
