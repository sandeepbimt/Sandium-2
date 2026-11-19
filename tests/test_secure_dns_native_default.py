"""Exact pinned native owner and platform split; no live DNS requests."""
import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/secure-dns'
spec = importlib.util.spec_from_file_location('dns_default', BASE / 'default_mode.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class DnsNativeDefault(unittest.TestCase):
    def test_exact_pinned_transform_replays_and_preserves_default_precedence(self):
        raw = (BASE / 'fixtures/default_dns_over_https_config_source.cc').read_bytes()
        identity = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.assertEqual(identity, 'e5a2aadcc85f6e4d6e2862eee1007b7e3abcdcce')
        source = raw.decode()
        result = mod.transform(source)
        self.assertEqual(result, mod.transform(result))
        self.assertEqual(source, result.replace(mod.NEW, mod.OLD))
        self.assertIn('#if BUILDFLAG(IS_ANDROID)\n    constexpr auto default_mode = net::SecureDnsMode::kOff;', mod.NEW)
        self.assertIn('#else\n    constexpr auto default_mode = net::SecureDnsMode::kAutomatic;', mod.NEW)
        self.assertEqual(mod.NEW.count('SetDefaultPrefValue'), 1)
        self.assertNotIn('SetString', mod.NEW)
        self.assertNotIn('ClearPref', mod.NEW)

    @unittest.skipUnless(shutil.which('g++'), 'C++ compiler unavailable')
    def test_emitted_android_and_non_android_initialization(self):
        harness = r'''
#include <cassert>
#include <optional>
#define BUILDFLAG(x) (x)
namespace net { enum class SecureDnsMode { kOff, kAutomatic, kSecure }; }
namespace prefs { constexpr int kDnsOverHttpsMode = 1; }
namespace base { struct Value { net::SecureDnsMode mode; }; }
struct SecureDnsConfig {
    static net::SecureDnsMode ModeToString(net::SecureDnsMode mode) { return mode; }
};
struct PrefService {
    net::SecureDnsMode def = net::SecureDnsMode::kSecure;
    std::optional<net::SecureDnsMode> managed, explicit_user;
    void SetDefaultPrefValue(int, base::Value value) { def = value.mode; }
    net::SecureDnsMode Effective() const {
        return managed.value_or(explicit_user.value_or(def));
    }
};
void Initialize(PrefService* local_state, bool set_up_pref_defaults) {
DEFAULT_BODY
}
int main() {
    using Mode = net::SecureDnsMode;
    PrefService prefs;
    Initialize(&prefs, false);
    assert(prefs.Effective() == Mode::kSecure);
    Initialize(&prefs, true);
#if IS_ANDROID
    assert(prefs.Effective() == Mode::kOff);
#else
    assert(prefs.Effective() == Mode::kAutomatic);
#endif
    prefs.explicit_user = Mode::kSecure;
    Initialize(&prefs, true);
    assert(prefs.Effective() == Mode::kSecure);
    prefs.managed = Mode::kAutomatic;
    Initialize(&prefs, true);
    assert(prefs.Effective() == Mode::kAutomatic);
}
'''.replace('DEFAULT_BODY', mod.NEW)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'dns_default_test.cc'
            target = Path(directory) / 'test'
            source.write_text(harness)
            for android in ('0', '1'):
                subprocess.run(['g++', '-std=c++20', '-DIS_ANDROID=' + android,
                                str(source), '-o', str(target)], check=True)
                subprocess.run([str(target)], check=True)

    def test_fail_closed_on_unknown_owner(self):
        with self.assertRaises(ValueError):
            mod.transform(mod.OLD.replace('kAutomatic', 'kSecure'))


if __name__ == '__main__':
    unittest.main()
