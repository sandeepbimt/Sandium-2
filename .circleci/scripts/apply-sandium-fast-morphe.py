#!/usr/bin/env python3
"""Fast-Mode-only, pin-guarded Android adaptation of Morphe startup optimization."""
from pathlib import Path
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
PACKAGE = "com.brave.browser_default"
START = "        // SANDIUM_MORPHE_STARTUP_BEGIN"
END = "        // SANDIUM_MORPHE_STARTUP_END"

def sha(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

def replace_once(path, old, new, label):
    if not path.is_file():
        raise RuntimeError(f"{label}: missing source file {path}")
    data = path.read_text(encoding="utf-8")
    if START in data and END in data:
        a, b = data.index(START), data.index(END) + len(END)
        if b <= a or data.count(START) != 1 or data.count(END) != 1:
            raise RuntimeError(f"{label}: malformed or duplicate markers")
        line_a = data.rfind("\\n", 0, a) + 1
        line_b = data.find("\\n", b)
        line_b = len(data) if line_b < 0 else line_b + 1
        block = new
        updated = data[:line_a] + block + data[line_b:]
        # The original bug inserted the guard before the method declaration,
        # at class scope. Move it into initializeAsync(), immediately after
        # the opening brace, so the Java if statement is executable method code.
        if old in updated:
            anchor_at = updated.index(old)
            block_at = updated.index(START)
            if block_at < anchor_at:
                a2 = updated.index(START)
                b2 = updated.index(END) + len(END)
                line_a2 = updated.rfind("\\n", 0, a2) + 1
                line_b2 = updated.find("\\n", b2)
                line_b2 = len(updated) if line_b2 < 0 else line_b2 + 1
                misplaced = updated[line_a2:line_b2]
                updated = updated[:line_a2] + updated[line_b2:]
                if updated.count(old) != 1:
                    raise RuntimeError(f"{label}: method anchor missing after relocation")
                updated = updated.replace(old, old + misplaced, 1)
        status = "ALREADY_CURRENT" if updated == data else "RELOCATED_OR_UPDATED"
    elif START in data or END in data:
        raise RuntimeError(f"{label}: partial marker set")
    else:
        if data.count(old) != 1:
            raise RuntimeError(f"{label}: expected one exact insertion anchor, found {data.count(old)}")
        # Insert the guard inside initializeAsync(), not before its declaration.
        updated = data.replace(old, old + new, 1)
        status = "APPLIED"
    if updated != data:
        path.write_text(updated, encoding="utf-8")
    return status

def main():
    root = Path(sys.argv[1]).resolve()
    core = root / "brave"
    chromium_sha = sha(root)
    brave_sha = sha(core)
    if chromium_sha != CHROMIUM_SHA or brave_sha != BRAVE_SHA:
        raise RuntimeError(f"pin mismatch chromium={chromium_sha} brave={brave_sha}")
    partner = root / "chrome/browser/partnercustomizations/java/src/org/chromium/chrome/browser/partnercustomizations/PartnerBrowserCustomizations.java"
    anchor = "    void initializeAsync(final Context context, long timeoutMs) {\n"
    block = (
        START + "\n"
        "        // Sandium is a standalone consumer build, not an OEM preload. Avoid the\n"
        "        // provider lookup, background task and timeout on the first-start path.\n"
        f'        if ("{PACKAGE}".equals(context.getPackageName())\n'
        "                && (context.getApplicationInfo().flags & ApplicationInfo.FLAG_SYSTEM) == 0) {\n"
        "            if (mIsInitialized == null) {\n"
        "                mHomepage = null;\n"
        "                mIncognitoModeDisabled = false;\n"
        "                mBookmarksEditingDisabled = false;\n"
        "                mIsInitialized = true;\n"
        "                for (Runnable callback : mInitializeAsyncCallbacks) callback.run();\n"
        "                mInitializeAsyncCallbacks.clear();\n"
        "            }\n"
        "            return;\n"
        "        }\n"
        + END + "\n"
    )
    pstatus = replace_once(partner, anchor, block, "Morphe startup")
    print(f"MORPHE_STARTUP={pstatus} package={PACKAGE}")
    colors = core / "browser/ui/android/theme/java/src/org/chromium/chrome/browser/theme/BraveDynamicColors.java"
    old = (
        "    private static final CachedFlag sDynamicColorsDefaultFlag =\n"
        "            new CachedFlag(\n"
        "                    ChromeFeatureMap.getInstance(),\n"
        "                    BraveFeatureList.BRAVE_ANDROID_DYNAMIC_COLORS_BY_DEFAULT,\n"
        "                    true);"
    )
    new = (
        "    // SANDIUM_MORPHE_DYNAMIC_COLORS_BEGIN\n"
        "    // Keep the static theme as default; the existing user preference remains available.\n"
        "    private static final CachedFlag sDynamicColorsDefaultFlag =\n"
        "            new CachedFlag(\n"
        "                    ChromeFeatureMap.getInstance(),\n"
        "                    BraveFeatureList.BRAVE_ANDROID_DYNAMIC_COLORS_BY_DEFAULT,\n"
        "                    false);\n"
        "    // SANDIUM_MORPHE_DYNAMIC_COLORS_END"
    )
    if not colors.is_file():
        raise RuntimeError(f"Morphe dynamic colors: missing {colors}")
    data = colors.read_text(encoding="utf-8")
    s, e = "// SANDIUM_MORPHE_DYNAMIC_COLORS_BEGIN", "// SANDIUM_MORPHE_DYNAMIC_COLORS_END"
    if s in data and e in data:
        a, b = data.index(s), data.index(e) + len(e)
        line_a = data.rfind("\n", 0, a) + 1
        line_b = data.find("\n", b)
        line_b = len(data) if line_b < 0 else line_b + 1
        updated = data[:line_a] + new + "\n" + data[line_b:]
        cstatus = "ALREADY_CURRENT" if updated == data else "UPDATED"
    elif s in data or e in data:
        raise RuntimeError("Morphe dynamic colors: partial marker set")
    elif data.count(old) == 1:
        updated = data.replace(old, new, 1)
        cstatus = "APPLIED"
    else:
        raise RuntimeError("Morphe dynamic colors: exact CachedFlag anchor not found uniquely")
    if updated != data:
        colors.write_text(updated, encoding="utf-8")
    print(f"MORPHE_DYNAMIC_COLORS={cstatus} default=false")
    print("SANDIUM_FAST_MORPHE_OVERLAYS=PASS")
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_FAST_MORPHE_OVERLAYS=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
