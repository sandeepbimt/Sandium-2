#!/usr/bin/env python3
"""Offline contract tests; no cache, archive, network or build operations."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from sandium_checkpoint_contract import BASE,Invalid,load,select
BRAVE="44a84b1f89d9a35287289d6a3d493e362f5a5123"; CHROME="d331de35ca8ab1358c7a17e4bd41627d55eaef51"
class Tests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
 def tearDown(self): self.tmp.cleanup()
 def make(self,name,kind="pinned_source",created="2026-11-12T10:00:00Z",**kw):
  folder=self.root/name; folder.mkdir(); payload=b"verified"; (folder/"payload").write_bytes(payload)
  data={"schema_version":1,"checkpoint_id":name,"checkpoint_kind":kind,"status":"READY","created_at":created,"base_reference":BASE,"branch":"test-branch","source":{"brave_tag":"v1.98.62","brave_sha":BRAVE,"chromium_tag":"156.0.8078.74","chromium_sha":CHROME,"gclient_sha256":"a"*64},"build_identity":{},"files":[{"path":"payload","size_bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest()}]}
  if kind=="compiled_build": data["build_identity"]={"target":"android-arm64","build_type":"Release","gn_args_sha256":"b"*64,"toolchain_fingerprint":"clang-pinned"}
  for key,value in kw.items(): data[key].update(value) if key in ("source","build_identity") else data.update({key:value})
  (folder/"manifest.json").write_text(json.dumps(data)); return folder
 def expected(self,kind="pinned_source"):
  result={"checkpoint_kind":kind,"branch":"test-branch","base_reference":BASE,"brave_tag":"v1.98.62","brave_sha":BRAVE,"chromium_tag":"156.0.8078.74","chromium_sha":CHROME,"gclient_sha256":"a"*64}
  if kind=="compiled_build": result.update(target="android-arm64",build_type="Release",gn_args_sha256="b"*64,toolchain_fingerprint="clang-pinned")
  return result
 def test_latest_compatible_only(self):
  old=self.make("old",created="2026-11-10T10:00:00Z"); new=self.make("new",created="2026-11-11T10:00:00Z"); bad=self.make("bad",source={"chromium_sha":"f"*40})
  path,_=select([old,new,bad],"pinned_source",self.expected()); self.assertEqual(path.parent.name,"new")
 def test_source_cannot_satisfy_build(self):
  with self.assertRaises(Invalid): select([self.make("src")],"compiled_build",self.expected("compiled_build"))
 def test_checksum_mismatch(self):
  folder=self.make("corrupt"); (folder/"payload").write_bytes(b"tampered")
  with self.assertRaises(Invalid): load(folder/"manifest.json")
 def test_incomplete_and_wrong_base_rejected(self):
  with self.assertRaises(Invalid): load(self.make("partial",status="IN_PROGRESS")/"manifest.json")
  with self.assertRaises(Invalid): load(self.make("wrong",base_reference="deadbeef")/"manifest.json")
if __name__=="__main__": unittest.main(verbosity=2)
