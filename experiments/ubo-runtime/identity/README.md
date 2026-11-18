Core-only identity UI compatibility
=================================

Fixture: official Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51
https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/browser/extensions/api/identity/web_auth_flow.cc
SHA256: 5f5d505fc60f579f180fcb8a874102b379dffe56eda81a55d67d096ad0ea13a3

The uBO experiment enables extensions_core, not desktop extensions or desktop
Android extensions. Upstream assumed one of the two window UI implementations.
Keep both upstream implementations under their own matching feature guards and
return false for the unsupported interactive popup. The existing caller emits
CANNOT_CREATE_WINDOW. This does not implement OAuth popup support, enable a
permission, alter web-request blocking, or switch on desktop extension UI.
uBO does not need interactive extension OAuth.

source.py owns exact pinned on/off postimages, including reset before subsequent
source preparation. No live source is accepted as an input. The focused compiled
regression exercises the actual patched popup function with both UI flags off,
without declaring the missing desktop callback or weak factory.

Header fixture: same official Chromium revision, web_auth_flow.h in the same
source directory. SHA256:
177cc5e7d364470b40a25bded701d26dd272955d75acd935269832da7d80ea5d
The gesture member and its initializer exist only with an implemented popup UI.
Each supported popup branch returns true itself; the core-only branch returns
false without an unreachable trailing success return.

The warning regression uses installed libclang 19's real C++ frontend (via its
stable C API), with -Werror -Wunreachable-code-return -Wunused-private-field.
It checks the exact patched field/initializer in all three supported flag
combinations and the exact core-only popup body. Negative controls verify that
both original warning categories are diagnosed. This is a host semantic check,
not a complete Android compile or runtime claim.
