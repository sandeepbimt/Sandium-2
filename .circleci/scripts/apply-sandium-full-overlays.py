#!/usr/bin/env python3
"""Pin-guarded Sandium Full Mode overlays: Origin-equivalent feature removal and reader typography."""
from pathlib import Path
import argparse
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BEGIN = "// SANDIUM_ORIGIN_ANALYTICS_BEGIN"
END = "// SANDIUM_ORIGIN_ANALYTICS_END"
TYPO_BEGIN = "// SANDIUM_READER_TYPOGRAPHY_BEGIN"
TYPO_END = "// SANDIUM_READER_TYPOGRAPHY_END"

def git_sha(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

def replace_exact(path, old, new, label):
    if not path.is_file():
        raise RuntimeError(f"{label}: missing {path}")
    source = path.read_text(encoding="utf-8")
    if source.count(new) == 1 and old not in source:
        print(f"{label}=ALREADY_APPLIED")
        return
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected one exact source anchor; found {source.count(old)}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"{label}=APPLIED")

def replace_marked(path, begin, end, old, new, label):
    if not path.is_file():
        raise RuntimeError(f"{label}: missing {path}")
    source = path.read_text(encoding="utf-8")
    if begin in source and end in source:
        a, b = source.index(begin), source.index(end) + len(end)
        if b <= a:
            raise RuntimeError(f"{label}: malformed marker order")
        line_a = source.rfind("\n", 0, a) + 1
        line_b = source.find("\n", b)
        line_b = len(source) if line_b < 0 else line_b + 1
        updated = source[:line_a] + new + "\n" + source[line_b:]
        if updated != source:
            path.write_text(updated, encoding="utf-8")
            print(f"{label}=UPDATED")
        else:
            print(f"{label}=ALREADY_CURRENT")
        return
    if begin in source or end in source:
        raise RuntimeError(f"{label}: partial marker set")
    replace_exact(path, old, new, label)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--src", required=True, type=Path)
    args = parser.parse_args()
    core, src = args.core.resolve(), args.src.resolve()
    if git_sha(core) != BRAVE_SHA or git_sha(src) != CHROMIUM_SHA:
        raise RuntimeError(
            f"pin mismatch: brave={git_sha(core)} chromium={git_sha(src)}"
        )

    # Origin's two analytics controls map to P3A and statistics reporting.
    p3a = core / "components/p3a/p3a_service.cc"
    replace_exact(
        p3a,
        "  registry->RegisterBooleanPref(kP3AEnabled,\n"
        "                                !BUILDFLAG(IS_BRAVE_ORIGIN_BRANDED));",
        BEGIN + "\n"
        "  // Sandium has no P3A opt-in surface; keep privacy-preserving analytics off.\n"
        "  registry->RegisterBooleanPref(kP3AEnabled, false);\n" + END,
        "SANDIUM_P3A_DEFAULT",
    )
    replace_exact(
        p3a,
        "    component_updater::ComponentUpdateService* cus) {",
        "    component_updater::ComponentUpdateService* cus) {\n"
        "  // Do not allow a previously persisted profile preference to re-enable P3A.\n"
        "  local_state_->SetBoolean(kP3AEnabled, false);",
        "SANDIUM_P3A_RUNTIME",
    )
    stats = core / "browser/brave_local_state_prefs.cc"
    replace_exact(
        stats,
        "  registry->RegisterBooleanPref(kStatsReportingEnabled, true);",
        BEGIN + "\n"
        "  // Sandium ships without Brave Origin statistics reporting.\n"
        "  registry->RegisterBooleanPref(kStatsReportingEnabled, false);\n" + END,
        "SANDIUM_STATS_REPORTING_DEFAULT",
    )

    stats_updater = core / "browser/brave_stats/brave_stats_updater.cc"
    replace_exact(
        stats_updater,
        "      testing_url_loader_factory_(nullptr) {",
        "      testing_url_loader_factory_(nullptr) {\n"
        "  // Keep anonymous statistics reporting disabled for existing profiles too.\n"
        "  pref_service_->SetBoolean(kStatsReportingEnabled, false);",
        "SANDIUM_STATS_REPORTING_RUNTIME",
    )

    web_discovery = core / "components/web_discovery/buildflags/buildflags.gni"
    replace_exact(
        web_discovery,
        "  enable_web_discovery_native =\n"
        "      (is_win || is_mac || is_linux || is_android) && !is_brave_origin_branded",
        "  enable_web_discovery_native = false",
        "SANDIUM_WEB_DISCOVERY_NATIVE",
    )
    replace_exact(
        web_discovery,
        "  enable_web_discovery = (enable_web_discovery_native || enable_extensions) &&\n"
        "                         !is_brave_origin_branded",
        "  enable_web_discovery = false",
        "SANDIUM_WEB_DISCOVERY",
    )

    # Brave News is disabled in Sandium's Full Mode GN args. Its browser_tests
    # target is therefore absent from the Android deps list and must not remain
    # in android_test_exception_deps (GN list subtraction rejects missing items).
    android_tests = core / "android/android_browser_tests.gni"
    if not android_tests.is_file():
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: pinned Android browser test GN file missing")
    android_source = android_tests.read_text(encoding="utf-8")
    news_target = '"//brave/browser/brave_news:browser_tests"'
    lines = android_source.splitlines(keepends=True)
    declaration_index = next(
        (i for i, line in enumerate(lines) if line.strip() == "android_test_exception_deps = ["),
        None,
    )
    if declaration_index is None:
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: exception dependency list declaration missing")
    closing_index = next(
        (i for i in range(declaration_index + 1, len(lines)) if lines[i].strip() == "]"),
        None,
    )
    if closing_index is None:
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: exception dependency list is unterminated")
    kept = []
    removed_count = 0
    for line in lines[declaration_index + 1:closing_index]:
        if news_target in line:
            removed_count += 1
        else:
            kept.append(line)
    lines[declaration_index + 1:closing_index] = kept
    android_source = "".join(lines)
    if removed_count:
        print(f"SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD=REMOVED_FROM_EXCEPTION_LIST count={removed_count}")
    else:
        print("SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD=ALREADY_ABSENT")

    legacy_append = (
        'if (enable_brave_news) {\n'
        '  android_test_exception_deps += [ "//brave/browser/brave_news:browser_tests" ]\n'
        '}\n'
    )
    if legacy_append in android_source:
        android_source = android_source.replace(legacy_append, "", 1)
        print("SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD=REMOVED_LEGACY_APPEND")
    if news_target in android_source:
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: Brave News browser_tests still appears in Android exception GN file")

    import re
    pattern = re.compile(r'^(\s*)deps\s*-=\s*android_test_exception_deps\s*$', re.MULTILINE)
    matches = list(pattern.finditer(android_source))
    begin_marker = "SANDIUM_ANDROID_TEST_DEPS_BEGIN"
    end_marker = "SANDIUM_ANDROID_TEST_DEPS_END"
    loop_marker = "foreach(exception_dep, android_test_exception_deps)"
    has_begin = begin_marker in android_source
    has_end = end_marker in android_source
    has_loop = loop_marker in android_source

    if len(matches) > 1:
        raise RuntimeError(
            "SANDIUM_ANDROID_TEST_DEPS: expected at most one bulk subtraction; "
            f"found {len(matches)}"
        )
    if len(matches) == 1:
        if has_begin or has_end or has_loop:
            raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: mixed guarded and unguarded dependency logic")
        match = matches[0]
        indent = match.group(1)
        guarded = (
            indent + "# SANDIUM_ANDROID_TEST_DEPS_BEGIN\n"
            + indent + "foreach(exception_dep, android_test_exception_deps) {\n"
            + indent + "  if (exception_dep in deps) {\n"
            + indent + "    deps -= [ exception_dep ]\n"
            + indent + "  }\n"
            + indent + "}\n"
            + indent + "# SANDIUM_ANDROID_TEST_DEPS_END\n"
        )
        android_source = android_source[:match.start()] + guarded + android_source[match.end():]
        print("SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD=PATCHED guarded optional-dependency removal")
    elif has_begin and has_end and has_loop:
        if android_source.count(begin_marker) != 1 or android_source.count(end_marker) != 1 or android_source.count(loop_marker) != 1:
            raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: duplicate guarded dependency markers")
        if android_source.index(begin_marker) >= android_source.index(end_marker):
            raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: malformed guarded marker order")
        print("SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD=ALREADY_PATCHED")
    elif has_begin or has_end or has_loop:
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: incomplete guarded dependency patch")
    else:
        # Brave v1.98.62's pinned Android GN file declares the exception list
        # but does not subtract it from deps. There is nothing to guard here.
        if "android_test_exception_deps = [" not in android_source:
            raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: exception dependency list declaration missing")
        print("SANDIUM_ANDROID_NEWS_TEST_DEP_GUARD=NOT_REQUIRED pinned source has no bulk subtraction")

    if android_source != android_tests.read_text(encoding="utf-8"):
        android_tests.write_text(android_source, encoding="utf-8")

    verified_android = android_tests.read_text(encoding="utf-8")
    if re.search(r"^\s*deps\s*-\s*=\s*android_test_exception_deps\s*$", verified_android, re.MULTILINE):
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: unsafe bulk subtraction remains")
    verified_begin = begin_marker in verified_android
    verified_end = end_marker in verified_android
    verified_loop_count = verified_android.count(loop_marker)
    if verified_begin and verified_end and verified_loop_count == 1:
        if verified_android.index(begin_marker) >= verified_android.index(end_marker):
            raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: guarded marker order invalid")
        print("SANDIUM_ANDROID_TEST_DEPS_GATE=PASS mode=guarded_optional_removal")
    elif not verified_begin and not verified_end and verified_loop_count == 0 and "android_test_exception_deps = [" in verified_android:
        print("SANDIUM_ANDROID_TEST_DEPS_GATE=PASS mode=upstream_noop")
    else:
        raise RuntimeError("SANDIUM_ANDROID_TEST_DEPS: post-write state is inconsistent")
    
    email_flags = core / "components/email_aliases/buildflags/buildflags.gni"
    email_source = email_flags.read_text(encoding="utf-8")
    if "enable_email_aliases = !is_ios && !is_android && !is_brave_origin_branded" not in email_source:
        raise RuntimeError("SANDIUM_EMAIL_ALIASES: pinned Android default changed; inspect before proceeding")
    print("SANDIUM_EMAIL_ALIASES=DISABLED_BY_ANDROID_BUILD_DEFAULT")

    # Remove the Origin purchase entry; do not alter any entitlement checks.
    main_prefs = core / "android/java/brave-res/xml/brave_main_preferences.xml"
    old_origin_row = (
        '    <org.chromium.components.browser_ui.settings.ChromeBasePreference\n'
        '        android:key="brave_origin"\n'
        '        android:order="14"\n'
        '        android:icon="@drawable/ic_product_origin"\n'
        '        android:title="@string/menu_origin"/>\n'
    )
    replace_exact(main_prefs, old_origin_row, "    <!-- SANDIUM_ORIGIN_ENTRY_REMOVED -->\n", "SANDIUM_REMOVE_ORIGIN_ENTRY")

    # Add the supplied Universal Reader Typography v4 as an Android raw resource.
    build_gn = core / "android/BUILD.gn"
    resource_line = '    "java/brave-res/raw/sandium_reader_typography.js",\n'
    source = build_gn.read_text(encoding="utf-8")
    if resource_line.strip() in source:
        print("SANDIUM_READER_RESOURCE=ALREADY_REGISTERED")
    else:
        anchor = '    "java/brave-res/xml/brave_origin_preferences.xml",\n'
        if source.count(anchor) != 1:
            raise RuntimeError("SANDIUM_READER_RESOURCE: expected one java_resources XML anchor")
        build_gn.write_text(source.replace(anchor, anchor + resource_line, 1), encoding="utf-8")
        print("SANDIUM_READER_RESOURCE=REGISTERED")

    toolbar = core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java"
    if not toolbar.is_file():
        raise RuntimeError(f"SANDIUM_READER_INJECTION: missing {toolbar}")
    source = toolbar.read_text(encoding="utf-8")
    import_anchor = "import java.net.URL;\n"
    imports = (
        "import java.io.ByteArrayOutputStream;\n"
        "import java.io.IOException;\n"
        "import java.io.InputStream;\n"
        "import java.nio.charset.StandardCharsets;\n"
    )
    if "import java.io.InputStream;" not in source:
        if source.count(import_anchor) != 1:
            raise RuntimeError("SANDIUM_READER_INJECTION: import anchor not unique")
        source = source.replace(import_anchor, imports + import_anchor, 1)

    field_anchor = "    private PlaylistService mPlaylistService;\n"
    field = (
        field_anchor
        + "\n"
        + "    // SANDIUM_READER_TYPOGRAPHY_BEGIN\n"
        + "    private static volatile String sSandiumReaderTypographyScript;\n"
        + "    // SANDIUM_READER_TYPOGRAPHY_END\n"
    )
    if "sSandiumReaderTypographyScript" not in source:
        if source.count(field_anchor) != 1:
            raise RuntimeError("SANDIUM_READER_INJECTION: field anchor not unique")
        source = source.replace(field_anchor, field, 1)

    method_anchor = "    public void setTabModelSelector(TabModelSelector selector) {\n"
    method = (
        "    private void applySandiumReaderTypography(Tab tab) {\n"
        "        if (tab == null || tab.getWebContents() == null || tab.getUrl() == null) return;\n"
        "        String scheme = tab.getUrl().getScheme();\n"
        '        if (!"http".equals(scheme) && !"https".equals(scheme)) return;\n'
        "        try {\n"
        "            String script = sSandiumReaderTypographyScript;\n"
        "            if (script == null) {\n"
        "                synchronized (BraveToolbarLayoutImpl.class) {\n"
        "                    script = sSandiumReaderTypographyScript;\n"
        "                    if (script == null) {\n"
        "                        try (InputStream input = getContext().getResources().openRawResource(\n"
        "                                R.raw.sandium_reader_typography)) {\n"
        "                            ByteArrayOutputStream output = new ByteArrayOutputStream();\n"
        "                            byte[] buffer = new byte[8192];\n"
        "                            int count;\n"
        "                            while ((count = input.read(buffer)) != -1) {\n"
        "                                output.write(buffer, 0, count);\n"
        "                            }\n"
        "                            script = new String(output.toByteArray(), StandardCharsets.UTF_8);\n"
        "                        }\n"
        "                        sSandiumReaderTypographyScript = script;\n"
        "                    }\n"
        "                }\n"
        "            }\n"
        "            tab.getWebContents().evaluateJavaScript(script, null);\n"
        "        } catch (IOException | RuntimeException error) {\n"
        '            Log.w(TAG, "Unable to apply Sandium reader typography", error);\n'
        "        }\n"
        "    }\n\n"
        + method_anchor
    )
    if "private void applySandiumReaderTypography(Tab tab)" not in source:
        if source.count(method_anchor) != 1:
            raise RuntimeError("SANDIUM_READER_INJECTION: method anchor not unique")
        source = source.replace(method_anchor, method, 1)

    # Apply on finished loads and when a previously loaded tab becomes visible.
    load_anchor = "                    public void onPageLoadFinished(final Tab tab, GURL url) {\n"
    load_new = load_anchor + "                        applySandiumReaderTypography(tab);\n"
    if "applySandiumReaderTypography(tab);" not in source:
        if source.count(load_anchor) != 1:
            raise RuntimeError("SANDIUM_READER_INJECTION: page-load anchor not unique")
        source = source.replace(load_anchor, load_new, 1)
    shown_anchor = "                    public void onShown(Tab tab, @TabSelectionType int type) {\n"
    shown_new = shown_anchor + "                        applySandiumReaderTypography(tab);\n"
    if source.count(shown_anchor) == 1 and "applySandiumReaderTypography(tab);" not in source[source.index(shown_anchor):source.index(shown_anchor)+180]:
        source = source.replace(shown_anchor, shown_new, 1)
    toolbar.write_text(source, encoding="utf-8")
    print("SANDIUM_READER_INJECTION=PATCHED")

    # Keep the resource path and all user-provided v4 algorithm/CSS unchanged.
    repo_root = Path(__file__).resolve().parents[2]
    supplied_raw = repo_root / "android/java/brave-res/raw/sandium_reader_typography.js"
    raw = core / "android/java/brave-res/raw/sandium_reader_typography.js"
    if not supplied_raw.is_file() or supplied_raw.stat().st_size < 2500:
        raise RuntimeError(f"SANDIUM_READER_RESOURCE: supplied v4 script is missing or truncated: {supplied_raw}")
    raw.parent.mkdir(parents=True, exist_ok=True)
    supplied_bytes = supplied_raw.read_bytes()
    if raw.exists() and raw.read_bytes() != supplied_bytes:
        print("SANDIUM_READER_RESOURCE=REFRESHING_FROM_REPOSITORY_SOURCE")
    raw.write_bytes(supplied_bytes)
    if raw.read_bytes() != supplied_bytes:
        raise RuntimeError("SANDIUM_READER_RESOURCE: copy verification failed")
    print(f"SANDIUM_READER_RESOURCE=PASS bytes={raw.stat().st_size} exact_repository_copy=true")
    print("SANDIUM_FULL_OVERLAYS=PASS")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_FULL_OVERLAYS=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
