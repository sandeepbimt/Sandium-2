# Exact pinned compiler regression fixture

`pinned_feature_compiler.py` is unchanged Chromium source from:
https://chromium.googlesource.com/chromium/src/+/d331de35ca8ab1358c7a17e4bd41627d55eaef51/tools/json_schema_compiler/feature_compiler.py

SHA-256: `f0eabfd292119c2c5e99138d3d206291cf74c943c27a01021f1c0a4bfe2f08a3`

Chromium copyright and BSD-style source license apply. The test executes actual Feature.Parse, Feature.Validate, FeatureCompiler.Compile
and FeatureCompiler.Write, emitting the C++ feature provider and header. Only
JSON file loading is bypassed: the exact production metadata is supplied as a
dict. This is not represented as native Android compile validation.

`code_util.py` is unchanged tools/json_schema_compiler/code_util.py from the same
pin and is used by the real C++ emitter.

`pinned_feature.cc` is exact `extensions/common/features/feature.cc` from the
same revision. Its GetCurrentPlatform selects DESKTOP_ANDROID_PLATFORM only with
ENABLE_DESKTOP_ANDROID_EXTENSIONS. Sandium enables extensions_core without that
flag, so substituting desktop_android would compile but deny the bridge. The
metadata therefore omits platforms, and the actual native capability helper
rejects non-Android builds explicitly in addition to all identity checks.
