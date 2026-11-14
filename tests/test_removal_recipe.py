import importlib.util,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'.circleci/scripts/sandium-removal-recipe.py'
spec=importlib.util.spec_from_file_location('removal',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Recipe(unittest.TestCase):
 def test_composition_gate_precedes_actual_apply(self):
  script=(P.parents[1]/'experimental-steps/product-overlay-30-0.sh').read_text()
  self.assertLess(script.index('test-sandium-removal-composition.py'),script.index('sandium-removal-recipe.py'))
  self.assertIn('--source "$CORE"',script)
 def test_checkpoint_core_reset_precedes_branding_without_new_upstream_replay(self):
  script=(P.parent/'prepare-brave-source.sh').read_text()
  reused=script.index('SOURCE_REUSE=true')
  reset=script.index('--phase reset-core',reused)
  patches=script.index('pnpm run apply_patches',reused)
  branding=script.index('apply-sandium-branding.sh')
  self.assertLess(reset,patches);self.assertLess(patches,branding)
  fresh=script.index('pnpm run init --target_os=android')
  self.assertLess(script.index('--phase reset-core',fresh),branding)
  self.assertEqual(script.count('pnpm run apply_patches'),1)
  self.assertIn('--phase reset',script[branding:])
  self.assertIn('android/java/org/chromium/chrome/browser/ntp_background_images/NTPBackgroundImagesBridge.java',m.load()['core_restore'])
 def test_early_core_reset_does_not_touch_chromium_or_gn_args(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);core=root/'core';src=root/'src';out=root/'out'
   for p in (core,src,out):p.mkdir()
   (core/'file').write_text('removed checkpoint');(src/'file').write_text('chromium overlay')
   (out/'args.gn').write_text('enable_brave_wallet = false\n')
   recipe={'brave_pin':'brave','chromium_pin':'chrome','core_restore':['file'],'chromium_restore':['file'],'gn_args':{'enable_brave_wallet':False}}
   def git(args,**kwargs):
    if 'rev-parse' in args:return 'brave' if args[2]==str(core) else 'chrome'
    return b'pinned core'
   with patch.object(m.subprocess,'check_output',side_effect=git):m.reset(recipe,core,src,out,core_only=True)
   self.assertEqual((core/'file').read_bytes(),b'pinned core')
   self.assertEqual((src/'file').read_text(),'chromium overlay')
   self.assertEqual((out/'args.gn').read_text(),'enable_brave_wallet = false\n')
 def test_gn_preserves_toolchain_and_import(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'args.gn').write_text('import("args_generated.gni")\nuse_siso = true\nenable_brave_wallet = true\n')
   recipe={'gn_args':{'enable_brave_wallet':False,'enable_playlist':False}}
   m.configure_gn(recipe,p);first=(p/'args.gn').read_text();m.configure_gn(recipe,p)
   self.assertEqual(first,(p/'args.gn').read_text());self.assertIn('use_siso = true',first);self.assertIn('import(',first);self.assertEqual(first.count('enable_brave_wallet = false'),1)
 def test_unsafe_manifest_path_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'m.json';p.write_text(json.dumps({'schema':1,'groups':list(range(13)),'core_restore':['../escape'],'chromium_restore':[]}))
   with self.assertRaises(ValueError):m.load(p)
 def test_missing_gn_not_created(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):m.configure_gn({'gn_args':{}},Path(d))
if __name__=='__main__':unittest.main()
