"""Android-only default, at Chromium's native DoH preference owner."""
from pathlib import Path

PATH = 'chrome/browser/net/default_dns_over_https_config_source.cc'
OLD = '''  if (set_up_pref_defaults) {
    local_state->SetDefaultPrefValue(prefs::kDnsOverHttpsMode,
                                     base::Value(SecureDnsConfig::ModeToString(
                                         net::SecureDnsMode::kAutomatic)));
  }'''
NEW = '''  if (set_up_pref_defaults) {
    // Sandium uses the platform-configured resolver until explicitly opted in.
    // Set a default only: an existing user or managed value still takes precedence.
#if BUILDFLAG(IS_ANDROID)
    constexpr auto default_mode = net::SecureDnsMode::kOff;
#else
    constexpr auto default_mode = net::SecureDnsMode::kAutomatic;
#endif
    local_state->SetDefaultPrefValue(
        prefs::kDnsOverHttpsMode,
        base::Value(SecureDnsConfig::ModeToString(default_mode)));
  }'''


def transform(source):
    if source.count(NEW) == 1 and OLD not in source:
        return source
    if source.count(OLD) != 1 or NEW in source:
        raise ValueError('Pinned Secure DNS default owner has changed')
    return source.replace(OLD, NEW, 1)


def plan(root):
    path = Path(root) / PATH
    return {path: transform(path.read_text())}
