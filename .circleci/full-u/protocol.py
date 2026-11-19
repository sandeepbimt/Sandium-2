"""Target/recipe identity and owned source phases, separate from ordinary Full."""
import hashlib,json,os,re,tempfile,time
from pathlib import Path
PHASES=('source-acquiring','source-synced','product-preparing','build-ready')
class ProtocolError(ValueError):pass

def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
  f.write(encoded(value));f.flush();os.fsync(f.fileno());tmp=f.name
 os.replace(tmp,path)
def identity(profile,recipe):
 if not re.fullmatch('[0-9a-f]{64}',recipe):raise ProtocolError('invalid recipe')
 source=profile['source'];build=profile['build']
 for key in ('wrapper_sha','core_sha','chromium_sha'):
  if not re.fullmatch('[0-9a-f]{40}',source[key]):raise ProtocolError('missing exact requested pin')
 if build['is_official_build'] is not True or build['target_cpu']!='arm64':raise ProtocolError('unsupported build')
 payload=dict(schema=1,recipe=recipe,source={k:source[k] for k in ('wrapper_sha','core_sha','chromium_sha','chromium_version')},build=build)
 return 'full-u-v1-'+digest(encoded(payload))
def owned(work,scope):
 work=Path(work);marker=work/'.sandium/full-u-owner.json';expected=dict(schema=1,scope=scope)
 if work.is_symlink():raise ProtocolError('symlink source root')
 if work.exists():
  if not marker.is_file() or json.loads(marker.read_text())!=expected:raise ProtocolError('foreign source; no legacy fallback')
 else:atomic(marker,expected)
 return work

def envelope(p):return dict(id=digest(encoded(p)),payload=p)
def verify(receipt,scope,accepted=False,now=None):
 p=receipt['payload'];now=time.time() if now is None else now
 if receipt.get('id')!=digest(encoded(p)) or p.get('schema')!=1 or p.get('scope')!=scope:raise ProtocolError('receipt mismatch')
 if p.get('phase') not in PHASES:raise ProtocolError('unknown phase')
 if not 0<=now-p['created_epoch']<14*86400:raise ProtocolError('expired receipt')
 if not re.fullmatch('[0-9a-f]{64}',p.get('manifest_sha256','')):raise ProtocolError('bad manifest identity')
 if not re.fullmatch('[A-Za-z0-9_-]+',p.get('generation','')):raise ProtocolError('bad generation')
 if p.get('archive_key')!=scope+'-'+p['generation']+'-'+p['manifest_sha256']:raise ProtocolError('nonexact archive key')
 if type(p.get('pipeline')) is not int or p['pipeline']<1:raise ProtocolError('bad pipeline')
 if p.get('outcome') not in ('success','time-slice','reserve-exhausted','hard-failure','recovered-source'):raise ProtocolError('bad outcome')
 if p['outcome']=='recovered-source' and (p['phase']!='source-synced' or p.get('source_only') is not True):raise ProtocolError('invalid source recovery')
 if type(p.get('readback_verified')) is not bool:raise ProtocolError('bad readback status')
 if accepted and (not p['readback_verified'] or p['outcome']=='hard-failure'):raise ProtocolError('unaccepted/quarantined candidate')
 if p.get('apk_sha256') is not None and (p['phase']!='build-ready' or p['outcome']!='success' or not re.fullmatch('[0-9a-f]{64}',p['apk_sha256'])):raise ProtocolError('invalid APK claim')
 return p
