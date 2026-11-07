#!/usr/bin/env python3
"""Regression tests for SHE classification, failure gating and the AI Chat repair."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / ".circleci/scripts/sandium-self-heal.py"
REPAIR = ROOT / ".circleci/scripts/repair-ai-chat-android.py"
spec = importlib.util.spec_from_file_location("sandium_she", ENGINE)
she = importlib.util.module_from_spec(spec)
spec.loader.exec_module(she)

def run_case(name, expected, log="", rc=1, elapsed=10, budget=1200,
             targets="", commands="", metrics=""):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        for filename, data in (("log", log), ("targets", targets), ("commands", commands), ("metrics", metrics)):
            (p / filename).write_text(data, encoding="utf-8")
        args = type("Args", (), {
            "log": str(p / "log"), "failed_targets": str(p / "targets"),
            "failed_commands": str(p / "commands"), "metrics": str(p / "metrics"),
            "exit_code": rc, "elapsed": elapsed, "budget": budget
        })()
        result = she.classify(args)
        assert result["classification"] == expected, (name, result)
        return result

assert run_case("clean success", "SUCCESS", rc=0)["build_handoff_allowed"]
assert run_case("real bounded timeout", "TIME_SLICE_COMPLETE", rc=124, elapsed=1200)["build_handoff_allowed"]
assert run_case("timeout interruption banner is not a compiler failure", "TIME_SLICE_COMPLETE",
                "ninja: build stopped: interrupted by user\n", rc=124, elapsed=1200)["build_handoff_allowed"]
assert run_case("compiler error wins over timeout", "FAILURE",
                "foo.cc:4:1: error: unknown type\nninja: build stopped: interrupted by user\n",
                rc=124, elapsed=1200)["build_handoff_allowed"] is False
assert run_case("early timeout is failure", "FAILURE", rc=124, elapsed=300)["build_handoff_allowed"] is False
assert run_case("masked compiler failure despite exit zero", "FAILURE",
                "FAILED: obj/foo.o\nfoo.cc:7:2: error: unknown type name\n", rc=0)["build_handoff_allowed"] is False
assert run_case("masked failed-target file", "FAILURE", rc=0, targets="obj/foo.o\n")["failed_target_count"] == 1
assert run_case("failed command script", "FAILURE", rc=0, commands="#!/bin/sh\nexit 1\n")["failed_commands_present"]
assert run_case("failed Siso metric", "FAILURE", rc=0,
                metrics=json.dumps({"step_id":"x","err":True})+"\n")["metrics_failure_count"] == 1
assert run_case("remote transport retry", "RETRYABLE_INFRA",
                "rpc error: code = Unavailable desc = reset\n", rc=1)["repair_action"] == "RETRY_REMOTE_REDUCED"
assert run_case("missing CAS recovery", "RETRYABLE_INFRA",
                "rpc error: code = FailedPrecondition desc = download inputs: could not fetch inputs: Digest hash: abc not found\n",
                rc=1)["repair_action"] == "RECOVER_CAS_INPUTS"
assert run_case("AI Chat repair routing", "FAILURE",
                "error: invalid application of 'sizeof' to an incomplete type 'ai_chat::WebMcpInjector'\n",
                rc=1)["repair_action"] == "REAPPLY_AI_CHAT_ANDROID_GUARDS"

with tempfile.TemporaryDirectory() as tmp:
    core = Path(tmp)
    android = core / "browser/android"
    android.mkdir(parents=True)
    (android / "brave_tab_features.h").write_text(
        '#include <memory>\nnamespace ai_chat {\nclass TabDataWebContentsObserver;\nclass WebMcpInjector;\n}  // namespace ai_chat\n'
        'class BraveTabFeatures {\n  std::unique_ptr<ai_chat::TabDataWebContentsObserver> tab_data_observer_;\n'
        '  std::unique_ptr<ai_chat::WebMcpInjector> web_mcp_injector_;\n};\n', encoding="utf-8")
    (android / "brave_tab_features.cc").write_text(
        '#include "base/feature_list.h"\n'
        '#include "brave/browser/ai_chat/ai_chat_utils.h"\n'
        '#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"\n'
        '#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"\n'
        'void F() {\n  if (ai_chat::IsAllowedForContext(profile)) {\n'
        '    tab_data_observer_ = std::make_unique<ai_chat::TabDataWebContentsObserver>(\n'
        '        TabAndroid::FromWebContents(web_contents)->GetAndroidId(),\n'
        '        web_contents);\n'
        '    // Injects Brave-provided WebMCP tools into matching pages; see\n'
        '    // WebMcpInjector. Null when WebMCP is disabled or has no rules.\n'
        '    web_mcp_injector_ = ai_chat::WebMcpInjector::MaybeCreate(web_contents);\n'
        '  }\n}\n', encoding="utf-8")
    (android / "BUILD.gn").write_text(
        'import("//brave/components/brave_ads/buildflags/buildflags.gni")\n'
        'source_set("tabs_impl") {\n'
        '  public_deps = [ "//chrome/browser/android:tabs_public" ]\n'
        '  deps = [\n    "//content/public/browser",\n    "//brave/browser/ai_chat",\n  ]\n}\n',
        encoding="utf-8")
    subprocess.run([sys.executable, str(REPAIR), str(core)], check=True, capture_output=True, text=True)
    before = [(android / n).read_text(encoding="utf-8") for n in ("brave_tab_features.h", "brave_tab_features.cc", "BUILD.gn")]
    subprocess.run([sys.executable, str(REPAIR), str(core)], check=True, capture_output=True, text=True)
    after = [(android / n).read_text(encoding="utf-8") for n in ("brave_tab_features.h", "brave_tab_features.cc", "BUILD.gn")]
    assert before == after, "repair is not idempotent"
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)' in after[0]
    assert 'if (enable_ai_chat)' in after[2]

feature_failure = run_case("Wallet and DNS generated Java dependency failure", "FAILURE",
                "Foo.java:10: error: symbol not found org.chromium.brave_wallet.mojom.BlockchainRegistry\\n"
                "Bar.java:20: error: symbol not found org.chromium.chrome.browser.decentralized_dns.ResolveMethodTypes\\n", rc=1)
assert feature_failure["category"] == "FEATURE_SUPPRESSION_MISSING_GENERATED_JAVA"
assert feature_failure["repair_action"] == "REPAIR_WALLET_JAVA_COMPILE_CONTRACT"
assert not feature_failure["build_handoff_allowed"]

print("SANDIUM_SHE_TEST=PASS failure detection, timeout discrimination, repair routing and idempotent AI Chat repair")

wallet_activity_failure = run_case("BraveActivity missing Wallet Mojo Java types", "FAILURE",
                "BraveActivity.java:91: error: symbol not found org.chromium.brave_wallet.mojom.CoinType\\n"
                "BraveActivity.java:325: error: could not resolve BraveWalletService\\n", rc=1)
assert wallet_activity_failure["category"] == "FEATURE_SUPPRESSION_MISSING_GENERATED_JAVA"
assert wallet_activity_failure["repair_action"] == "REPAIR_WALLET_JAVA_COMPILE_CONTRACT"
assert not wallet_activity_failure["build_handoff_allowed"]
