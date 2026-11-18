"""Use exact pinned EnvConfig resolver; logging dependency alone is stubbed."""
import gzip,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Services(unittest.TestCase):
 def test_pinned_resolver_preserves_existing_and_fills_only_missing(self):
  fixture=json.loads(gzip.decompress((ROOT/'tests/fixtures/official-reference/env-config.json.gz').read_bytes()))
  self.assertEqual(hashlib.sha256(fixture['source'].encode()).hexdigest(),fixture['sha256'])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'envConfig.ts').write_text(fixture['source'])
   (p/'log.ts').write_text('export function error(){throw new Error("upstream resolver error")}\n')
   helper=(ROOT/'.circleci/scripts/prepare-official-service-placeholders.mjs').as_uri()
   (p/'test.mjs').write_text('''import assert from 'node:assert/strict';
import fs from 'node:fs'; import path from 'node:path';
import EnvConfig from './envConfig.ts';
import {prepare,NAMES,PLACEHOLDER} from '''+json.dumps(helper)+''';
const root=process.argv[2];
function make(name,env,config={}) {const p=path.join(root,name);fs.mkdirSync(p);fs.writeFileSync(path.join(p,'package.json'),JSON.stringify({version:'1.0.0',config}));fs.writeFileSync(path.join(p,'.env'),env);return p;}
let logs=[];
const core=make('core','include_env=include.env\\nservice_key_stt=""\\nother=unchanged\\n',{service_key_aichat:'package-nonempty'});
fs.writeFileSync(path.join(core,'include.env'),'service_key_search=include-nonempty\\n');
prepare(core,EnvConfig,x=>logs.push(x));
let config=new EnvConfig(core);
assert.equal(config.getAny(['brave_services_key']),PLACEHOLDER);
assert.equal(config.getAny(['service_key_stt']),PLACEHOLDER);
assert.equal(config.getAny(['service_key_search']),'include-nonempty');
assert.equal(config.getAny(['service_key_aichat']),'package-nonempty');
assert.equal(config.getAny(['other']),'unchanged');
assert(!logs.join().includes('include-nonempty')); assert(!logs.join().includes('package-nonempty'));
const before=fs.readFileSync(path.join(core,'.env'),'utf8');
prepare(core,EnvConfig,()=>{});assert.equal(fs.readFileSync(path.join(core,'.env'),'utf8'),before);
const direct=make('direct',NAMES.map(n=>n+'=existing-'+n).join('\\n'));
const original=fs.readFileSync(path.join(direct,'.env'),'utf8');
prepare(direct,EnvConfig,()=>{});assert.equal(fs.readFileSync(path.join(direct,'.env'),'utf8'),original);
for(const n of NAMES) assert.equal(new EnvConfig(direct).getAny([n]),'existing-'+n);
const invalid=make('invalid','service_key_stt=true\\n');
const unchanged=fs.readFileSync(path.join(invalid,'.env'),'utf8');
assert.throws(()=>prepare(invalid,EnvConfig,()=>{}),/Invalid service configuration type/);
assert.equal(fs.readFileSync(path.join(invalid,'.env'),'utf8'),unchanged);
console.log('PINNED_ENV_CONFIG_PLACEHOLDERS_PASS');
''')
   result=subprocess.run(['node',str(p/'test.mjs'),str(p)],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('PINNED_ENV_CONFIG_PLACEHOLDERS_PASS',result.stdout)
 def test_no_feature_guard_or_endpoint_rewrite(self):
  helper=(ROOT/'.circleci/scripts/prepare-official-service-placeholders.mjs').read_text()
  self.assertNotIn('BUILD.gn',helper);self.assertNotIn('enable_',helper)
  self.assertIn('github.com/brave/brave-browser/wiki/Build-configuration',helper)
  self.assertNotIn('endpoint',helper)
if __name__=='__main__':unittest.main()
