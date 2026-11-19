import gzip,importlib.util,json,pathlib,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1];D=R/'experiments/autofill-off'
s=importlib.util.spec_from_file_location('autofill_apply',D/'apply.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_all_inputs_validate_before_writes_and_reset_inventory(self):
  ui=m.load('ui');f=json.loads(gzip.decompress((D/'ui-fixtures.json.gz').read_bytes()))['files']
  files={p:f[pathlib.Path(p).name] for p in (ui.FRAGMENT,ui.BINDER,ui.XML)}
  for p,item in json.loads(gzip.decompress((D/'fixtures/runtime-pinned.json.gz').read_bytes()))['files'].items():files[p]=item['source']
  inventory=json.loads((D/'integration-plan.json').read_text())['chromium_restore'];self.assertTrue(set(files)<=set(inventory))
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   for p,t in files.items():
    q=root/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(t)
   victim=root/m.load('runtime').PASSWORD_CLIENT;original=victim.read_text();victim.write_text('drift')
   before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
   with self.assertRaises(SystemExit):m.execute(root)
   self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
   victim.write_text(original);self.assertEqual(m.execute(root),len(files));m.execute(root,True);m.execute(root)
   # A pinned source reset may restore a subset; replay handles only known pre/postimages.
   first=next(iter(files));(root/first).write_text(files[first]);m.execute(root)
   m.execute(root,off=True)
   self.assertEqual(files,{str(p.relative_to(root)):p.read_text() for p in root.rglob('*') if p.is_file()})
   m.execute(root);(root/m.JOURNAL).unlink()
   with self.assertRaises(ValueError):m.execute(root)
   for rel,raw in files.items():(root/rel).write_text(raw)
   m.execute(root);victim.write_text(victim.read_text()+'// unrelated edit')
   with self.assertRaises(ValueError):m.execute(root,off=True)
if __name__=='__main__':unittest.main()
