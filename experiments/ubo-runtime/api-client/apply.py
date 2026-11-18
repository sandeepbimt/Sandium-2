"""Use Chromium's fail-closed Android USB prompt stub in the core-only port."""
import hashlib
PATH = 'chrome/browser/extensions/api/chrome_extensions_api_client_android.cc'
PINNED_SHA = 'd868c7fb413eb98f3e362ec6dbbca624faba729268c6ef5eb668da276d860728'
def transform(raw):
    if hashlib.sha256(raw).hexdigest() != PINNED_SHA:
        raise ValueError('Unexpected pinned Android extensions API client')
    text = raw.decode()
    text = text.replace('#include "base/notimplemented.h"', '#include "base/notimplemented.h"\n#include "build/build_config.h"', 1)
    old = 'static_assert(BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS));'
    if text.count(old) != 1:
        raise ValueError('Android API client guard drift')
    text = text.replace(old, '// SANDIUM_CORE_ONLY_API_CLIENT: same fail-closed Android USB prompt.\nstatic_assert(BUILDFLAG(IS_ANDROID) && BUILDFLAG(ENABLE_EXTENSIONS_CORE));', 1)
    return text.encode()
