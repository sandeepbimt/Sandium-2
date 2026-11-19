import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "experiments" / "autofill-off"
SPEC = importlib.util.spec_from_file_location("sandium_autofill_runtime", MODULE / "runtime.py")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class AutofillRuntimeTest(unittest.TestCase):
    def test_pinned_complete_source_plan_replays_and_refuses_partial(self):
        fixture = json.loads(gzip.decompress((MODULE / "fixtures" / "runtime-pinned.json.gz").read_bytes()))
        self.assertEqual(fixture["revision"], "d331de35ca8ab1358c7a17e4bd41627d55eaef51")
        self.assertEqual(set(fixture["files"]), set(RUNTIME.PATCHES))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for rel, record in fixture["files"].items():
                self.assertEqual(hashlib.sha256(record["source"].encode()).hexdigest(), record["sha256"])
                file = root / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(record["source"])
            planned = RUNTIME.plan(root)
            for file, transformed in planned.items():
                rel = str(file.relative_to(root))
                self.assertEqual(transformed.count(RUNTIME.MARKER), len(RUNTIME.PATCHES[rel]))
                self.assertEqual(file.read_text(), fixture["files"][rel]["source"])
                file.write_text(transformed)
            self.assertEqual(planned, RUNTIME.plan(root))
            first = root / RUNTIME.BROWSER_MANAGER
            first.write_text(first.read_text().replace("  return;\n#endif", "  // missing gate\n#endif", 1))
            with self.assertRaises(SystemExit):
                RUNTIME.plan(root)

    def test_native_service_preserves_secure_tab_helpers_and_preference(self):
        fixture = json.loads(gzip.decompress((MODULE / "fixtures" / "runtime-pinned.json.gz").read_bytes()))
        records = fixture["routing_evidence"]
        for record in records.values():
            self.assertEqual(hashlib.sha256(record["source"].encode()).hexdigest(), record["sha256"])
        prefs = records["components/autofill/core/common/autofill_prefs.cc"]["source"]
        self.assertIn("registry->RegisterBooleanPref(kAutofillUsingPlatformAutofill, false);", prefs)
        provider = records["chrome/browser/ui/autofill/autofill_client_provider.cc"]["source"]
        self.assertIn("AndroidAutofillClient::CreateForWebContents(web_contents)", provider)
        self.assertIn("ChromeAutofillClient::CreateForWebContents(web_contents)", provider)
        self.assertIn("availability == AndroidAutofillAvailabilityStatus::kAvailable", provider)
        android = records["components/android_autofill/browser/android_autofill_client.cc"]["source"]
        self.assertIn("new autofill::AndroidAutofillManager(&driver)", android)
        self.assertIn("ThirdPartyCredentialManagerImpl", android)
        tabs = records["chrome/browser/ui/tab_helpers.cc"]["source"]
        self.assertIn(
            "if (!autofill_client_provider.uses_platform_autofill()) {\n"
            "      ChromePasswordManagerClient::CreateForWebContents(web_contents);",
            tabs,
        )
        for evidence in ("AndroidSensitiveContentClient::CreateForWebContents",
                         "SafeBrowsingTabObserver::CreateForWebContents",
                         "ChromePasswordReuseDetectionManagerClient::CreateForWebContents"):
            self.assertIn(evidence, tabs)
        credentials = records["components/password_manager/core/browser/credential_manager_impl.cc"]["source"]
        self.assertIn("!client_->IsSavingAndFillingEnabled(origin)", credentials)
        self.assertIn("!client_->IsFillingEnabled(GetOrigin())", credentials)
        manual = fixture["files"][RUNTIME.MANUAL_ACCESSORY]["source"]
        transformed_manual = RUNTIME.transform(RUNTIME.MANUAL_ACCESSORY, manual)
        start = "void ManualFillingControllerImpl::OnPasskeySelected("
        stop = "controller->OnPasskeySelected(passkey_id);"
        for source in (manual, transformed_manual):
            self.assertIn(stop, source[source.index(start):])
        self.assertTrue(set(records).isdisjoint(RUNTIME.PATCHES))

    @unittest.skipUnless(shutil.which("c++"), "C++ compiler unavailable")
    def test_actual_guard_bodies_android_vs_other_platform(self):
        fixture = json.loads(gzip.decompress((MODULE / "fixtures" / "runtime-pinned.json.gz").read_bytes()))
        definitions = []
        checks = []
        guards = []
        for rel, edits in RUNTIME.PATCHES.items():
            transformed = RUNTIME.transform(rel, fixture["files"][rel]["source"])
            for anchor, statement in edits:
                start = transformed.index(anchor) + len(anchor)
                stop = transformed.index("#endif", start) + len("#endif")
                guards.append((transformed[start:stop] + "\n", statement))
        for i, (production_guard, statement) in enumerate(guards):
            flag = f"hit{i}"
            name = f"run{i}"
            returning_value = statement == "return false;"
            result_type = "bool" if returning_value else "void"
            end = "return true;" if returning_value else ""
            definitions.append(f"bool {flag} = false;\n{result_type} {name}() {{{production_guard}"
                               f"  {flag} = true; {end} }}")
            if returning_value:
                checks.append(f"assert({name}() == !IS_ANDROID);")
            else:
                checks.append(f"{name}();")
            checks.append(f"assert({flag} == !IS_ANDROID);")
        source = "#include <cassert>\n#define BUILDFLAG(x) x\n" + "\n".join(definitions)
        source += "\nint main() {\n" + "\n".join(checks) + "\n}\n"
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "guards.cc"
            file.write_text(source)
            for android in (0, 1):
                binary = Path(temp) / "guards"
                subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                                f"-DIS_ANDROID={android}", str(file), "-o", str(binary)], check=True)
                subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
