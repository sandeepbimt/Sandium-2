"""Offline checkpoint-removal regressions; not an Android runtime smoke test."""
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.circleci/scripts'
spec = importlib.util.spec_from_file_location('vanilla', SCRIPTS / 'verify-sandium-vanilla-brave.py')
GATE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GATE)
TOOLBAR = 'android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java'
BUILD = 'android/BUILD.gn'
RESOURCE = 'android/java/brave-res/raw/sandium_reader_typography.js'

class RetiredTypography(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name);self.core=self.root/'core';self.src=self.root/'src'
        shutil.copytree(ROOT/'tests/fixtures/browser-crash-1073', self.core)
        self.src.mkdir();(self.src/'fixture').write_text('source fixture\n')
        for repo in (self.core,self.src):
            self.git(repo,'init','-q');self.git(repo,'add','.')
            self.git(repo,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Pinned files')
        self.oldpins=GATE.EXPECTED_CORE_SHA,GATE.EXPECTED_CHROMIUM_SHA
        # Fixture commits contain exact pinned toolbar/GN files, not a full tree.
        GATE.EXPECTED_CORE_SHA=self.git(self.core,'rev-parse','HEAD').strip()
        GATE.EXPECTED_CHROMIUM_SHA=self.git(self.src,'rev-parse','HEAD').strip()
        self.addCleanup(self.restore_pins)
    def restore_pins(self):
        GATE.EXPECTED_CORE_SHA,GATE.EXPECTED_CHROMIUM_SHA=self.oldpins
    def git(self,repo,*args):
        return subprocess.check_output(['git','-C',str(repo),*args],text=True,stderr=subprocess.PIPE)
    def gate(self,phase):
        with contextlib.redirect_stdout(io.StringIO()):
            GATE.apply_phase(self.core,self.src,self.root/'out',phase)
    def legacy_reader(self):
        p=self.core/TOOLBAR;text=p.read_text();fragments=GATE.RETIRED_READER
        text=text.replace('import java.net.URL;\n',fragments['imports']+'import java.net.URL;\n')
        for old,new in (('field_anchor','field'),('method_anchor','method'),('load_anchor','load_new'),('shown_anchor','shown_new')):
            self.assertEqual(text.count(fragments[old]),1)
            text=text.replace(fragments[old],fragments[new],1)
        p.write_text(text)
        p=self.core/BUILD;p.write_text(p.read_text()+fragments['resource_line'])
        p=self.core/RESOURCE;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('retired')
    def test_targeted_retirement_preserves_unrelated_checkpoint_edits(self):
        originals={p:(self.core/p).read_text() for p in (BUILD,TOOLBAR)}
        self.legacy_reader()
        for p in (BUILD,TOOLBAR):
            path=self.core/p;path.write_text(path.read_text()+'\n// unrelated Sandium feature\n')
        self.gate('retire-reader')
        for p,text in originals.items():self.assertEqual((self.core/p).read_text(),text+'\n// unrelated Sandium feature\n')
        self.assertFalse((self.core/RESOURCE).exists())
        self.gate('retire-reader')
        for p,text in originals.items():self.assertEqual((self.core/p).read_text(),text+'\n// unrelated Sandium feature\n')
    def test_unknown_reader_fragment_fails_before_source_writes(self):
        self.legacy_reader();p=self.core/TOOLBAR;p.write_text(p.read_text().replace('evaluateJavaScript(script, null)','evaluateJavaScript(script + "changed", null)'))
        before={x:(self.core/x).read_bytes() for x in (BUILD,TOOLBAR,RESOURCE)}
        with self.assertRaisesRegex(SystemExit,'unrecognized reader remnants'):self.gate('retire-reader')
        for x,data in before.items():self.assertEqual((self.core/x).read_bytes(),data)
    def test_active_recipe_executes_retirement_with_minimal_mode_false(self):
        source=(SCRIPTS/'prepare-brave-source.sh').read_text()
        start=source.index('  MINIMAL_VANILLA_BUILD=false')
        end=source.index('  if [ "$MINIMAL_VANILLA_BUILD" = true ]; then',start)
        recipe=source[start:end]
        # Execute the actual active shell recipe; stub only external Python
        # commands, recording their order. No shell condition is reimplemented.
        harness='set -eu\nROOT=/repo; CORE_DIR=/core; SRC_DIR=/src; OUT=/out\npython3() { printf "CALL %s\\n" "$*"; }\n'+recipe
        output=subprocess.check_output(['bash','-c',harness],text=True)
        self.assertLess(output.index('--phase retire-reader'),output.index('apply-sandium-full-overlays.py'))
        self.assertLess(source.index('--phase retire-reader'),source.index('pnpm run build Release'))
        # Continuations enter after the stage-1 fi, outside MINIMAL branches.
        start=source.index('# Sandium native Shields/uBlock-compatible filter backport.')
        end=source.index('EXPECTED_BRAVE_CORE_SHA=',start)
        continuation=source[start:end]
        output=subprocess.check_output(['bash','-c','set -eu\nROOT=/repo; MINIMAL_VANILLA_BUILD=false\npython3() { printf "CALL %s\\n" "$*"; }\n'+continuation],text=True)
        self.assertIn('--phase retire-reader',output)
    def test_restored_checkpoint_removes_all_reader_code_and_resource(self):
        originals={p:(self.core/p).read_bytes() for p in (BUILD,TOOLBAR)}
        p=self.core/BUILD;p.write_text(p.read_text()+'\n"java/brave-res/raw/sandium_reader_typography.js",\n')
        p=self.core/TOOLBAR;p.write_text(p.read_text()+'\n// SANDIUM_READER_TYPOGRAPHY_BEGIN\napplySandiumReaderTypography(tab);\n')
        p=self.core/RESOURCE;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('retired code')
        self.gate('prepare');self.gate('verify')
        self.assertFalse(p.exists())
        for p,data in originals.items():self.assertEqual((self.core/p).read_bytes(),data)
        self.gate('prepare');self.gate('verify')
        for p,data in originals.items():self.assertEqual((self.core/p).read_bytes(),data)
    def test_final_gate_rejects_each_restored_remnant(self):
        for relative,marker in ((BUILD,'sandium_reader_typography'),(TOOLBAR,'applySandiumReaderTypography(tab);'),(TOOLBAR,'sSandiumReaderTypographyScript'),(TOOLBAR,'SANDIUM_READER_TYPOGRAPHY_BEGIN')):
            with self.subTest(relative=relative,marker=marker):
                p=self.core/relative;before=p.read_text();p.write_text(before+'\n'+marker)
                with self.assertRaisesRegex(SystemExit,'typography integration remains'):
                    GATE.verify_reader_removed(self.core,ROOT)
                p.write_text(before)
        p=self.core/RESOURCE;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('retired')
        with self.assertRaisesRegex(SystemExit,'typography resource remains'):
            GATE.verify_reader_removed(self.core,ROOT)
    def test_repository_resource_cannot_be_reintroduced(self):
        fake=self.root/'repo';p=fake/RESOURCE;p.parent.mkdir(parents=True);p.write_text('retired')
        with self.assertRaisesRegex(SystemExit,'typography resource remains'):
            GATE.verify_reader_removed(self.core,fake)
    def test_missing_verification_input_fails_closed(self):
        (self.core/TOOLBAR).unlink()
        with self.assertRaisesRegex(SystemExit,'missing typography removal verification input'):
            GATE.verify_reader_removed(self.core,ROOT)
    def test_production_overlay_no_longer_adds_reader_or_unsafe_js(self):
        text=(SCRIPTS/'apply-sandium-full-overlays.py').read_text()
        for token in ('applySandiumReaderTypography','sandium_reader_typography','evaluateJavaScript','SANDIUM_READER_TYPOGRAPHY'):
            self.assertNotIn(token,text)
        self.assertFalse((ROOT/RESOURCE).exists())
        self.assertIn(TOOLBAR,GATE.BRAVE_RESTORE_PREFIXES)
        self.assertIn(BUILD,GATE.BRAVE_RESTORE_PREFIXES)
    def test_regressions_wired_before_cache_changes(self):
        text=(ROOT/'.circleci/config.yml').read_text()
        for name in ('test_browser_crash_regressions.py','test_settings_origin_crash.py'):
            self.assertLess(text.index(name),text.index('    - restore_cache:'))
            self.assertIn(name,(ROOT/'.github/workflows/sandium-pipeline-self-test.yml').read_text())

if __name__=='__main__':unittest.main()
