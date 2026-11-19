"""Source-phase adapter of existing Full hardlink snapshot/eight-shard transport."""
import importlib.util,json,os,sys,time,uuid
from pathlib import Path
import protocol as p
spec=importlib.util.spec_from_file_location('full_u_native_shards',Path(__file__).resolve().parents[1]/'scripts/sandium-checkpoint-shards.py')
native=importlib.util.module_from_spec(spec);sys.modules[spec.name]=native;spec.loader.exec_module(native)
native.SHARD_DIR_NAME='full-u-workspace.shards';native.MANIFEST_NAME='full-u-workspace.manifest.json'

SOURCE_ONLY=False
def discover(root,work):
 if not (work/'.sandium/full-u-owner.json').is_file():raise p.ProtocolError('unowned snapshot')
 roots=[];structural=[work]
 for item in native.children(work):
  if item.is_dir() and not item.is_symlink() and native.children(item):
   structural.append(item);roots.extend(x for x in native.children(item) if not (SOURCE_ONLY and x==work/'src/out'))
  else:roots.append(item)
 return roots,structural
native.discover_candidates=discover

def metadata(manifest,scope):
 data=manifest['checkpoint_manifest']
 if data.get('FULL_U_SCOPE')!=scope or data.get('FULL_U_PHASE') not in p.PHASES:raise p.ProtocolError('archive scope/phase mismatch')
 return data['FULL_U_PHASE']

def capture(root,scope,phase,outcome,pipeline,revision,validator,apk_sha256=None,source_only=False):
 global SOURCE_ONLY
 SOURCE_ONLY=source_only
 root=Path(root);work=p.owned(root/'brave-work',scope)
 if phase not in p.PHASES:raise p.ProtocolError('unknown phase')
 if phase!='source-acquiring':validator(phase,work)
 if native.find_open_writers(work):raise p.ProtocolError('source still has open writers')
 marker=work/'.sandium/checkpoint-manifest.txt'
 values=native.parse_checkpoint_manifest(marker) if marker.exists() else {}
 values.update(FULL_U_SCOPE=scope,FULL_U_PHASE=phase)
 # Do not turn a source-only checkpoint into legacy APK/reference proof.
 if phase!='build-ready':values.update(APK_VALIDATED='false',REFERENCE_READY='false')
 marker.write_text(''.join(k+'='+v+'\n' for k,v in sorted(values.items())))
 native.archive(root,8)
 manifest=native.verify(root,zstd_test=True,workers=8)
 if metadata(manifest,scope)!=phase:raise p.ProtocolError('captured phase mismatch')
 if phase!='source-acquiring':validator(phase,work)
 h=p.digest((root/native.MANIFEST_NAME).read_bytes());generation=uuid.uuid4().hex
 payload=dict(schema=1,scope=scope,phase=phase,outcome=outcome,pipeline=pipeline,revision=revision,
              created_epoch=int(time.time()),generation=generation,manifest_sha256=h,
              archive_key=scope+'-'+generation+'-'+h,readback_verified=False,apk_sha256=apk_sha256,source_only=source_only)
 result=p.envelope(payload);p.verify(result,scope);return result

def restore_candidate(root,receipt,scope,validator,apk_validator=None):
 root=Path(root);data=p.verify(receipt,scope)
 if (root/'brave-work').exists():raise p.ProtocolError('fresh restore requires absent workspace')
 if p.digest((root/native.MANIFEST_NAME).read_bytes())!=data['manifest_sha256']:raise p.ProtocolError('wrong archive manifest')
 # Native restore hashes every shard before extraction and validates zstd during extraction.
 manifest=native.load_manifest(root)[0]
 if metadata(manifest,scope)!=data['phase']:raise p.ProtocolError('wrong archive phase')
 native.restore(root,8);work=p.owned(root/'brave-work',scope)
 if data.get('source_only') and (work/'src/out').exists():raise p.ProtocolError('source-only archive contains compiled output')
 if data['phase']!='source-acquiring':validator(data['phase'],work)
 if data['apk_sha256'] is not None:
  if apk_validator is None or apk_validator(work)!=data['apk_sha256']:raise p.ProtocolError('restored APK mismatch')
 p.atomic(root/'.full-u/fresh-restore-proof.json',{'receipt_id':receipt['id'],'scope':scope,'phase':data['phase'],'apk_sha256':data['apk_sha256']})
 return data

def accept_after_fresh_restore(receipt,scope,restored_root,output):
 # Caller must use restore_candidate on a genuinely fresh remote-restored directory.
 # Revalidate local ownership and manifest identity; never infer cloud publication.
 data=dict(p.verify(receipt,scope));root=Path(restored_root)
 p.owned(root/'brave-work',scope)
 proof=json.loads((root/'.full-u/fresh-restore-proof.json').read_text())
 if proof!={'receipt_id':receipt['id'],'scope':scope,'phase':data['phase'],'apk_sha256':data['apk_sha256']}:raise p.ProtocolError('missing fresh validation proof')
 if p.digest((root/native.MANIFEST_NAME).read_bytes())!=data['manifest_sha256']:raise p.ProtocolError('manifest changed after restore')
 if data['outcome']=='hard-failure':raise p.ProtocolError('quarantined failure cannot be accepted')
 data['readback_verified']=True;value=p.envelope(data)
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(p.encoded(value));f.flush();os.fsync(f.fileno())
 return value
