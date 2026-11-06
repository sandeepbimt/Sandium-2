#!/usr/bin/env python3
"""Offline tests for the pin-guarded Sandium Fast Mode blur overlay."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-sandium-blur-transition.py")
SPEC = importlib.util.spec_from_file_location("sandium_blur_overlay", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FIXTURE = """package org.chromium.chrome.browser.base;

import org.chromium.base.CommandLineInitUtil;
import org.chromium.base.PathUtils;

public class SplitCompatApplication {
    void attachBrowser() {
        if (isBrowserProcess) {
            CommandLineInitUtil.initCommandLine(
                    COMMAND_LINE_FILE, SplitCompatApplication::shouldUseDebugFlags);
            PathUtils.setPrivateDataDirectorySuffix(PRIVATE_DATA_DIRECTORY_SUFFIX);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
    }
}
"""


def main() -> None:
    once = MODULE.transform_source(FIXTURE)
    twice = MODULE.transform_source(once)
    assert once == twice, "overlay must be idempotent"
    assert once.count("import org.chromium.base.CommandLine;") == 1
    assert once.count(MODULE.RUNTIME_BEGIN) == 1
    assert once.count(MODULE.HELPER_BEGIN) == 1
    assert once.index("CommandLineInitUtil.initCommandLine(") < once.index(
        "enableSandiumNavigationBlurTransition();"
    ) < once.index("PathUtils.setPrivateDataDirectorySuffix")
    assert once.index(MODULE.HELPER_BEGIN) < once.index("public void onCreate()")
    assert "getSwitchValue(\"disable-features\", \"\")" in once
    assert "getSwitchValue(\"enable-features\", \"\")" in once
    assert "appendSwitchWithValue(\"enable-features\"" in once
    assert once.count(MODULE.FEATURE) == 1

    # A partial marker set is a hard error; never silently stack or guess.
    try:
        MODULE.insert_marked_block(
            MODULE.RUNTIME_BEGIN + "\n",
            MODULE.RUNTIME_BEGIN,
            MODULE.RUNTIME_END,
            MODULE.RUNTIME_BLOCK,
            MODULE.INIT_ANCHOR,
            "partial-marker-test",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("partial marker set was accepted")

    # A source drift must be rejected rather than patched at an approximate location.
    try:
        MODULE.transform_source(FIXTURE.replace(MODULE.INIT_ANCHOR, "", 1))
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing exact insertion anchor was accepted")

    print("SANDIUM_BLUR_TRANSITION_TESTS=PASS")


if __name__ == "__main__":
    main()
