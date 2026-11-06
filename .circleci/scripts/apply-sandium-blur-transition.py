#!/usr/bin/env python3
"""Enable Chromium's built-in Android navigation blur in Sandium Fast Mode.

This is a Java-only overlay. It deliberately refuses to run on any source pair
other than the already-pinned Sandium Brave/Chromium revisions.
"""
from pathlib import Path
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
FEATURE = "AndroidNavigationBlurTransitionAnimation"
TARGET = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/base/SplitCompatApplication.java"
)

IMPORT = "import org.chromium.base.CommandLine;\n"
IMPORT_ANCHOR = "import org.chromium.base.CommandLineInitUtil;\n"
INIT_ANCHOR = (
    "            CommandLineInitUtil.initCommandLine(\n"
    "                    COMMAND_LINE_FILE, SplitCompatApplication::shouldUseDebugFlags);\n"
)
OUTER_ON_CREATE_ANCHOR = "    @Override\n    public void onCreate() {\n"

RUNTIME_BEGIN = "            // SANDIUM_FAST_BLUR_TRANSITION_BEGIN"
RUNTIME_END = "            // SANDIUM_FAST_BLUR_TRANSITION_END"
RUNTIME_BLOCK = (
    RUNTIME_BEGIN + "\n"
    "            // Apply before any browser-process native library/FeatureList startup.\n"
    "            enableSandiumNavigationBlurTransition();\n"
    + RUNTIME_END + "\n"
)

HELPER_BEGIN = "    // SANDIUM_FAST_BLUR_HELPER_BEGIN"
HELPER_END = "    // SANDIUM_FAST_BLUR_HELPER_END"
HELPER_BLOCK = (
    HELPER_BEGIN + "\n"
    "    private static void enableSandiumNavigationBlurTransition() {\n"
    "        final CommandLine commandLine = CommandLine.getInstance();\n"
    f'        final String feature = "{FEATURE}";\n'
    "\n"
    "        // Respect an explicit debugging/operator opt-out.\n"
    '        final String disabled = commandLine.getSwitchValue("disable-features", "");\n'
    "        if (containsSandiumFeature(disabled, feature)) {\n"
    "            return;\n"
    "        }\n"
    "\n"
    '        final String enabled = commandLine.getSwitchValue("enable-features", "");\n'
    "        if (containsSandiumFeature(enabled, feature)) {\n"
    "            return;\n"
    "        }\n"
    "\n"
    "        // Preserve every pre-existing enabled feature and append this one once.\n"
    '        final String separator = enabled.isEmpty() || enabled.endsWith(",") ? "" : ",";\n'
    '        commandLine.appendSwitchWithValue("enable-features", enabled + separator + feature);\n'
    "    }\n"
    "\n"
    "    private static boolean containsSandiumFeature(String featureList, String expected) {\n"
    '        if (featureList.isEmpty()) {\n'
    '            return false;\n'
    '        }\n'
    '        for (String entry : featureList.split(",")) {\n'
    "            String name = entry.trim();\n"
    "            int modifier = name.indexOf('<');\n"
    "            if (modifier < 0) {\n"
    "                modifier = name.indexOf(':');\n"
    "            }\n"
    "            if (modifier >= 0) {\n"
    "                name = name.substring(0, modifier);\n"
    "            }\n"
    "            if (expected.equals(name)) {\n"
    "                return true;\n"
    "            }\n"
    "        }\n"
    "        return false;\n"
    "    }\n"
    + HELPER_END + "\n"
)


def git_sha(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def insert_marked_block(source: str, begin: str, end: str, block: str,
                        anchor: str, label: str, *, before: bool = False) -> str:
    begin_count, end_count = source.count(begin), source.count(end)
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1:
            raise RuntimeError(f"{label}: partial or duplicate marker set")
        start, finish = source.index(begin), source.index(end)
        if finish <= start:
            raise RuntimeError(f"{label}: marker order is malformed")
        line_start = source.rfind("\n", 0, start) + 1
        line_end = source.find("\n", finish)
        line_end = len(source) if line_end < 0 else line_end + 1
        return source[:line_start] + block + source[line_end:]

    if source.count(anchor) != 1:
        raise RuntimeError(
            f"{label}: expected one exact insertion anchor; found {source.count(anchor)}"
        )
    replacement = block + anchor if before else anchor + block
    return source.replace(anchor, replacement, 1)


def transform_source(source: str) -> str:
    if source.count(IMPORT) > 1:
        raise RuntimeError("CommandLine import is duplicated")
    if IMPORT not in source:
        if source.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("CommandLineInitUtil import anchor not found uniquely")
        source = source.replace(IMPORT_ANCHOR, IMPORT + IMPORT_ANCHOR, 1)

    source = insert_marked_block(
        source, RUNTIME_BEGIN, RUNTIME_END, RUNTIME_BLOCK,
        INIT_ANCHOR, "blur runtime activation",
    )
    source = insert_marked_block(
        source, HELPER_BEGIN, HELPER_END, HELPER_BLOCK,
        OUTER_ON_CREATE_ANCHOR, "blur helper methods", before=True,
    )

    if source.count(IMPORT) != 1:
        raise RuntimeError("post-write validation: CommandLine import count is not one")
    for marker in (RUNTIME_BEGIN, RUNTIME_END, HELPER_BEGIN, HELPER_END):
        if source.count(marker) != 1:
            raise RuntimeError(f"post-write validation: marker count is invalid: {marker}")
    if source.index(INIT_ANCHOR) > source.index("enableSandiumNavigationBlurTransition();"):
        raise RuntimeError(
            "post-write validation: activation is not after command-line initialization"
        )
    if source.index("enableSandiumNavigationBlurTransition();") > source.index(
        "PathUtils.setPrivateDataDirectorySuffix"
    ):
        raise RuntimeError(
            "post-write validation: activation is not before browser preloading"
        )
    if source.index(HELPER_BEGIN) > source.index(OUTER_ON_CREATE_ANCHOR):
        raise RuntimeError(
            "post-write validation: helper block is not in the outer application class"
        )
    if source.count(FEATURE) != 1:
        raise RuntimeError("post-write validation: feature identifier count is not one")
    return source


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} <chromium-src-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "brave"
    actual_chromium, actual_brave = git_sha(root), git_sha(core)
    if actual_chromium != CHROMIUM_SHA or actual_brave != BRAVE_SHA:
        raise RuntimeError(
            "pinned source mismatch; refusing Fast Mode overlay: "
            f"chromium={actual_chromium} expected={CHROMIUM_SHA}; "
            f"brave={actual_brave} expected={BRAVE_SHA}"
        )

    path = root / TARGET
    if not path.is_file():
        raise RuntimeError(f"missing pinned Chromium Android application source: {path}")
    original = path.read_text(encoding="utf-8")
    updated = transform_source(original)
    if updated == original:
        print(f"SANDIUM_BLUR_TRANSITION=ALREADY_APPLIED feature={FEATURE}")
    else:
        path.write_text(updated, encoding="utf-8")
        # Verify the write from disk rather than trusting the in-memory string.
        if path.read_text(encoding="utf-8") != updated:
            raise RuntimeError("post-write file verification failed")
        print(f"SANDIUM_BLUR_TRANSITION=APPLIED feature={FEATURE}")
    print("SANDIUM_BLUR_TRANSITION_MODE=JAVA_COMMAND_LINE_ONLY; native source unchanged")
    print("SANDIUM_BLUR_TRANSITION_GATE=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_BLUR_TRANSITION_GATE=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
