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
            first.write_text(first.read_text().replace(RUNTIME.GUARD.format(statement="return;").rstrip("\n"), RUNTIME.GUARD.format(statement="// missing gate").rstrip("\n"), 1))
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

    def test_clang_aggressive_unreachable_regression(self):
        # Use the actual Clang frontend when no clang++ driver is installed.
        # This is syntax/diagnostic validation, not a Chromium native link.
        import ctypes
        import ctypes.util
        pinned_driver=ROOT/"brave-work/src/third_party/llvm-build/Release+Asserts/bin/clang++"
        driver=str(pinned_driver) if pinned_driver.is_file() else shutil.which("clang++")
        library=ctypes.util.find_library("clang-19")
        if not driver and not library:
            self.skipTest("Clang frontend unavailable")
        clang=ctypes.CDLL(library) if library else None; pointer=ctypes.c_void_p
        class CXString(ctypes.Structure):
            _fields_=[("data",pointer),("private_flags",ctypes.c_uint)]
        signatures={
            "clang_createIndex":(pointer,[ctypes.c_int,ctypes.c_int]),
            "clang_parseTranslationUnit":(pointer,[pointer,ctypes.c_char_p,ctypes.POINTER(ctypes.c_char_p),ctypes.c_int,pointer,ctypes.c_uint,ctypes.c_uint]),
            "clang_getNumDiagnostics":(ctypes.c_uint,[pointer]),
            "clang_getDiagnostic":(pointer,[pointer,ctypes.c_uint]),
            "clang_getDiagnosticSeverity":(ctypes.c_int,[pointer]),
            "clang_getDiagnosticSpelling":(CXString,[pointer]),
            "clang_getCString":(ctypes.c_char_p,[CXString]),
            "clang_disposeString":(None,[CXString]),
            "clang_disposeDiagnostic":(None,[pointer]),
            "clang_disposeTranslationUnit":(None,[pointer]),
            "clang_disposeIndex":(None,[pointer]),
        }
        if clang:
            for name,(result,args) in signatures.items():
                function=getattr(clang,name);function.restype=result;function.argtypes=args
        def diagnostics(source,android):
            with tempfile.TemporaryDirectory() as temp:
                file=Path(temp)/"strict.cc";file.write_text(source)
                args=["-std=c++17","-Wall","-Wextra","-Werror","-Wunreachable-code","-Wunreachable-code-aggressive",f"-DIS_ANDROID={android}"]
                if driver:
                    # This header-free test needs only the frontend. Driver mode
                    # probes the runner's GCC installations and can fail before
                    # parsing our fixture; do not relax any source diagnostics.
                    run=subprocess.run(
                        [driver, "-cc1", "-x", "c++", *args, "-fsyntax-only", str(file)],
                        capture_output=True, text=True)
                    messages=[(3,line.split("error:",1)[1]) for line in run.stderr.splitlines() if "error:" in line]
                    if run.returncode and not messages:
                        self.fail("Clang driver failed without diagnostics: "+run.stderr)
                    if not run.returncode:self.assertEqual(run.stderr, "")
                    return messages
                argv=(ctypes.c_char_p*len(args))(*(a.encode() for a in args))
                index=clang.clang_createIndex(0,0)
                unit=clang.clang_parseTranslationUnit(index,str(file).encode(),argv,len(args),None,0,0)
                self.assertTrue(unit)
                found=[]
                for i in range(clang.clang_getNumDiagnostics(unit)):
                    d=clang.clang_getDiagnostic(unit,i);message=clang.clang_getDiagnosticSpelling(d)
                    found.append((clang.clang_getDiagnosticSeverity(d),clang.clang_getCString(message).decode()))
                    clang.clang_disposeString(message);clang.clang_disposeDiagnostic(d)
                clang.clang_disposeTranslationUnit(unit);clang.clang_disposeIndex(index)
                return found
        fixture=json.loads(gzip.decompress((MODULE/"fixtures/runtime-pinned.json.gz").read_bytes()))
        fixed=[];broken=[]
        for rel,edits in RUNTIME.PATCHES.items():
            transformed=RUNTIME.transform(rel,fixture["files"][rel]["source"])
            for anchor,statement in edits:
                guard=RUNTIME.GUARD.format(statement=statement).rstrip("\n")
                self.assertIn(anchor+guard,transformed)
                i=len(fixed);result="bool" if statement=="return false;" else "void"
                tail="return true;" if result=="bool" else "++observed;"
                # Include an RAII parameter like the real OnAskForValuesToFillImpl.
                fixed.append(f"{result} f{i}(Cleanup) {{{guard}\n{tail}\n}}")
                broken.append(f"{result} f{i}(Cleanup) {{\n#if BUILDFLAG(IS_ANDROID)\n{statement}\n#endif\n{tail}\n}}")
        prefix="#define BUILDFLAG(x) x\nint observed; struct Cleanup { ~Cleanup(){++observed;} };\n"
        self.assertEqual(len(fixed),15)
        for android in (0,1):
            self.assertEqual(diagnostics(prefix+"\n".join(fixed),android),[])
        old=diagnostics(prefix+"\n".join(broken),1)
        self.assertEqual(sum(severity>=3 and "never be executed" in message for severity,message in old),15)

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
                production_guard = RUNTIME.GUARD.format(statement=statement).rstrip("\n")
                self.assertEqual(transformed[start:start+len(production_guard)],production_guard)
                guards.append((production_guard + "\n", statement))
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
