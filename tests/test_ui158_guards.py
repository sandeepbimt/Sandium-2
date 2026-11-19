"""Pinned real-source UI replay, not a GN graph, Android compile or phone test.

Git HEAD lookup is mocked only because the fixture is a source subset. Every
input is independently Git-blob/SHA verified and all six relevant Brave patches
are executed by git apply, before any Sandium transform.
"""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
NAMES=('shields-popup','bottom-toolbar','paged-menu','search-choices','focus-follow','settings-fade','progress-diagnostics','suggestion-anchor','home-shortcuts','video-gestures')
def load(name):
    spec=importlib.util.spec_from_file_location('ui158_'+name,ROOT/'.circleci/scripts'/('apply-sandium-'+name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class Ui158(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.src=Path(self.temp.name)
        self.data=json.loads(gzip.decompress((ROOT/'tests/fixtures/ui158-guards.json.gz').read_bytes()))
        self.assertEqual(self.data['brave_pin'],'bd6d26d1bced03c17a98baa86d2cd3425d543d1b')
        self.assertEqual(self.data['chromium_pin'],'52bdd21723d5db0c9ab11716d38feac74828cf84')
        for rel,item in self.data['files'].items():
            data=item['text'].encode()
            self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
            self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),item['git_blob'])
            p=self.src/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        self.assertEqual(len(self.data['brave_patches']),6)
        for rel,pp in self.data['brave_patches'].items():
            subprocess.run(['git','apply','--unsafe-paths','--directory='+str(self.src),str(self.src/'brave'/pp)],check=True,capture_output=True)
    def git_head(self,args,**kwargs):
        self.assertEqual(args[:2],['git','-C'])
        self.assertEqual(args[3:],['rev-parse','HEAD'])
        return self.data['brave_pin'] if Path(args[2])==self.src/'brave' else self.data['chromium_pin']
    def invoke(self,name,verify=False):
        m=load(name)
        with patch.object(m.subprocess,'check_output',self.git_head):
            if name=='bottom-toolbar':m.apply(self.src,self.src/'brave')
            elif name=='settings-fade':m.apply(self.src,self.src/'brave',verify)
            elif name in ('focus-follow','progress-diagnostics'):m.apply(self.src,verify)
            elif name in ('home-shortcuts','video-gestures'):m.apply(self.src,ROOT,verify)
            elif name=='paged-menu':(m.verify if verify else m.apply)(self.src,ROOT)
            elif name=='search-choices':m.apply(self.src/'brave',verify)
            elif name=='shields-popup':m.apply(self.src/'brave')
            else:
                for p,text in m.plan(self.src).items():
                    if verify:self.assertEqual(p.read_text(),text)
                    else:p.write_text(text)
    def test_real_ordered_apply_reapply_and_readback(self):
        for name in NAMES:
            if name=='focus-follow':
                p=self.src/load(name).PATH;p.write_text(load('unified-address').position(p.read_text()))
            if name=='paged-menu':load('ui-prune').patch_customize_menu(self.src/'brave')
            if name=='settings-fade':
                p=self.src/'brave'/load(name).BRAVE_SETTINGS;p.write_text(load('native-theme').settings_motion(p.read_text()))
            self.invoke(name)
            before_component={p:p.read_bytes() for p in self.src.rglob("*") if p.is_file()}
            self.invoke(name,True)
            self.invoke(name)
            self.assertEqual(before_component,{p:p.read_bytes() for p in self.src.rglob("*") if p.is_file()})
        before={p:p.read_bytes() for p in self.src.rglob('*') if p.is_file()}
        # Full production replay resets upstream before replaying all owners.
        # Do not reapply an earlier adjacency-based BUILD.gn owner over later inserts.
        phone=(self.src/load('bottom-toolbar').PHONE).read_text()
        self.assertIn('tabSwitcherButtonCoordinator.setHasSpaceToShow(true);',phone)
        self.assertNotIn('!mIsHomeButtonEnabled || mIsToolbarUiRefactorEnabled',phone)
        menu=(self.src/'brave'/load('paged-menu').CUSTOMIZE).read_text()
        self.assertIn('|| R.id.info_menu_id == menuItemId',menu)
    def test_unreviewed_toolbar_and_menu_anchor_drift_rejected(self):
        m=load('bottom-toolbar');source=(self.src/m.PHONE).read_text()
        with self.assertRaises(ValueError):m.phone(source.replace('!mIsHomeButtonEnabled || mIsToolbarUiRefactorEnabled','unreviewedHomePolicy'))
        load('ui-prune').patch_customize_menu(self.src/'brave')
        m=load('paged-menu');source=(self.src/'brave'/m.CUSTOMIZE).read_text()
        with self.assertRaises(ValueError):m.customize(source.replace('// site controls menu id.','// unreviewed menu policy.'))
    def test_foreign_pin_rejected(self):
        for name in NAMES:
            m=load(name)
            if name in ('home-shortcuts','suggestion-anchor'):continue # CLI pin checks covered by exact source below.
            with patch.object(m.subprocess,'check_output',return_value='0'*40):
                with self.assertRaises(ValueError):
                    if name in ('bottom-toolbar','settings-fade'):m.apply(self.src,self.src/'brave')
                    elif name in ('focus-follow','progress-diagnostics'):m.apply(self.src)
                    elif name in ('paged-menu','video-gestures'):m.apply(self.src,ROOT)
                    else:m.apply(self.src/'brave')
        for name in ('home-shortcuts','suggestion-anchor'):
            self.assertIn(self.data['chromium_pin'],(ROOT/'.circleci/scripts'/('apply-sandium-'+name+'.py')).read_text())
if __name__=='__main__':unittest.main()
