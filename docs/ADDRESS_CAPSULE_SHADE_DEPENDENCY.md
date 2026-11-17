# Lighter capsule compile dependency

The lighter capsule introduced in c93f59c calls BraveDynamicColors to preserve
user-selected dynamic colors. ToolbarPhone is compiled by
`//chrome/browser/ui/android/toolbar:core_java`; the dependency from the separate
`//chrome/android:chrome_java` target is not sufficient for its compile classpath.

The refinement overlay now adds
`//brave/browser/ui/android/theme:dynamic_colors_java` directly to core_java.
No Java behavior, private/light/custom-tab gates, geometry or animation changes.
The target is public and its dependency list in pinned Brave
44a84b1f89d9a35287289d6a3d493e362f5a5123 does not depend on toolbar.

Fixture BUILD.gn is unmodified Chromium source at
 d331de35ca8ab1358c7a17e4bd41627d55eaef51:
https://raw.githubusercontent.com/chromium/chromium/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/browser/ui/android/toolbar/BUILD.gn

Validation: toolbar refinements 14 tests, unified address 11 tests; dependency
insertion is scoped, idempotent, fail-closed, and compatible with Brave's source
hook. These are source-contract tests, not Android javac or device validation.
Transparent surrounding toolbar padding remains outside this change.
