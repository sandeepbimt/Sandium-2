from pathlib import Path
import sys, tempfile, subprocess, unittest, json, hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import stage

class SourceStage(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.repo=self.root/'repo';self.repo.mkdir();self.out=self.root/'out'
        self.git('init','-q');self.git('config','user.name','fixture');self.git('config','user.email','fixture@invalid')
        self.put(stage.BRIDGE+'/BUILD.gn',(stage.HERE/'fixture/bridge.BUILD.gn').read_text())
        self.put(stage.BRIDGE+'/rs/BUILD.gn','deps = [ "//brave/third_party/rust/adblock/v0_13:lib" ]')
        self.put(stage.RUST+'/adblock/v0_13/BUILD.gn','"//brave/'+stage.VENDOR+'/adblock-v0_13/src/lib.rs"\ncargo_pkg_version = "0.13.3"\n"//brave/third_party/rust/example/v1:lib"')
        self.put(stage.RUST+'/example/v1/BUILD.gn','"//brave/'+stage.VENDOR+'/example-v1/src/lib.rs"')
        self.put(stage.VENDOR+'/example-v1/src/lib.rs','// fixture')
        self.put(stage.VENDOR+'/adblock-v0_13/.cargo_vcs_info.json',json.dumps({'git':{'sha1':stage.PINS['adblock_upstream']}}))
        self.put('unrelated/product','must not enter overlay');self.rev=self.commit()
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.repo),*args]).decode().strip()
    def put(self,name,text):p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    def commit(self):self.git('add','.');self.git('commit','-qm','test');return self.git('rev-parse','HEAD')
    def test_selection_and_receipt(self):
        self.put(stage.BRIDGE+'/BUILD.gn','dirty worktree ignored');stage.prepare(self.repo,self.out,self.rev)
        receipt=json.loads((self.out/'source-receipt.json').read_text()); self.assertFalse((self.out/'brave/unrelated').exists()); self.assertIn(stage.VENDOR+'/example-v1',receipt['roots'])
        self.assertEqual(1,(self.out/'brave'/stage.BRIDGE/'BUILD.gn').read_text().count('//components/sandium_adblock:*'))
        for suffix in ('subresource_decision.h', 'subresource_decision.cc',
                       'document_subresource_factory.h', 'document_subresource_factory.cc'):
            self.assertIn('components/sandium_adblock/'+suffix, receipt['sha256'])
        for name,digest in receipt['sha256'].items():self.assertEqual(digest,hashlib.sha256((self.out/name).read_bytes()).hexdigest())
    def test_destination_protected(self):
        self.out.mkdir();(self.out/'old').write_text('safe');self.assertRaises(ValueError,stage.prepare,self.repo,self.out,self.rev);self.assertEqual('safe',(self.out/'old').read_text())
    def test_bridge_drift(self):
        self.put(stage.BRIDGE+'/BUILD.gn','change');self.assertRaises(ValueError,stage.prepare,self.repo,self.out,self.commit());self.assertFalse(self.out.exists())
    def test_wrong_vcs(self):
        self.put(stage.VENDOR+'/adblock-v0_13/.cargo_vcs_info.json','{"git":{"sha1":"other"}}');self.assertRaises(ValueError,stage.prepare,self.repo,self.out,self.commit());self.assertFalse(self.out.exists())
    def test_symlink_refused(self):
        (self.repo/stage.BRIDGE/'evil').symlink_to('/tmp');self.assertRaises(ValueError,stage.prepare,self.repo,self.out,self.commit());self.assertFalse(self.out.exists())

    def test_exact_inactive_cssparser_branch_is_not_a_vendor_root(self):
        source = (stage.HERE/'fixture/cssparser-v0_35.BUILD.gn').read_bytes()
        active = stage.gn_for_selection(stage.CSSPARSER_GN, source)
        old = stage.VENDOR + '/cssparser-v0_29'
        new = stage.VENDOR + '/cssparser-v0_35'
        self.assertIn(old, stage.VENDOR_DIR.findall(source.decode()))
        self.assertNotIn(old, stage.VENDOR_DIR.findall(active))
        self.assertIn(new, stage.VENDOR_DIR.findall(active))
        self.assertIn(old, stage.VENDOR_DIR.findall(
            stage.gn_for_selection('third_party/rust/other/v1/BUILD.gn', source)))
        with self.assertRaisesRegex(ValueError, 'unreviewed cssparser'):
            stage.gn_for_selection(stage.CSSPARSER_GN,
                                   source.replace(b'epoch = "0.35"', b'epoch = "0.29"'))

    def test_other_missing_vendor_roots_still_fail(self):
        self.put(stage.RUST+'/example/v1/BUILD.gn',
                 '"//brave/' + stage.VENDOR+'/nonexistent-v1/src/lib.rs"')
        with self.assertRaisesRegex(ValueError, 'missing source root: .*nonexistent-v1'):
            stage.prepare(self.repo, self.out, self.commit())
        self.assertFalse(self.out.exists())
