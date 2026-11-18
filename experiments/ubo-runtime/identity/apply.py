"""Fail closed for unsupported interactive OAuth UI in the core-only experiment."""
import hashlib
PATH = 'chrome/browser/extensions/api/identity/web_auth_flow.cc'
PINNED_SHA = '5f5d505fc60f579f180fcb8a874102b379dffe56eda81a55d67d096ad0ea13a3'
def transform(raw):
    if hashlib.sha256(raw).hexdigest() != PINNED_SHA:
        raise ValueError('Unexpected pinned web auth flow source')
    text = raw.decode()
    for indent in ('', '  '):
        old = '#else\n' + indent + 'static_assert(BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS));'
        if text.count(old) != 1:
            raise ValueError('Web auth UI guard drift')
        text = text.replace(old, '#elif BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS)', 1)
    old = '  CreateBrowserWindow(std::move(params), std::move(callback));\n#endif'
    if text.count(old) != 1:
        raise ValueError('Web auth popup anchor drift')
    text = text.replace(old, '''  CreateBrowserWindow(std::move(params), std::move(callback));
#else
  // SANDIUM_CORE_ONLY_AUTH_UI: no desktop window host in this experiment.
  // The caller reports CANNOT_CREATE_WINDOW; never pretend the popup opened.
  return false;
#endif''', 1)
    text = text.replace('  browser->GetWindow()->Show();\n#elif', '  browser->GetWindow()->Show();\n  return true;\n#elif', 1)
    text = text.replace('  CreateBrowserWindow(std::move(params), std::move(callback));\n#else', '  CreateBrowserWindow(std::move(params), std::move(callback));\n  return true;\n#else', 1)
    text = text.replace('#endif\n\n  return true;\n}', '#endif\n}', 1)
    text = text.replace('      user_gesture_(user_gesture),', '#if BUILDFLAG(ENABLE_EXTENSIONS) || BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS)\n      user_gesture_(user_gesture),\n#endif', 1)
    return text.encode()

HEADER_PATH = 'chrome/browser/extensions/api/identity/web_auth_flow.h'
HEADER_SHA = '177cc5e7d364470b40a25bded701d26dd272955d75acd935269832da7d80ea5d'
def transform_header(raw):
    if hashlib.sha256(raw).hexdigest() != HEADER_SHA:
        raise ValueError('Unexpected pinned web auth header')
    text = raw.decode()
    old = '  const bool user_gesture_;'
    if text.count(old) != 1:
        raise ValueError('Web auth gesture member drift')
    return text.replace(old, '#if BUILDFLAG(ENABLE_EXTENSIONS) || BUILDFLAG(ENABLE_DESKTOP_ANDROID_EXTENSIONS)\n' + old + '\n#endif', 1).encode()
