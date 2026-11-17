// Host-only: production bridge + persisted native/storage models + upstream uBO.
// Exact product URLs are real; their test payloads are controlled sentinel rules,
// NOT downloaded filter lists. No Android, JNI, SharedPreferences or device proof.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
const here=fileURLToPath(new URL('.',import.meta.url));
const root=fileURLToPath(new URL('../../../',import.meta.url));
const fixture=process.env.SANDIUM_UBO_ENGINE_FIXTURE || '/tmp/ubo-engine-validation';
const {StaticNetFilteringEngine,enableWASM}=await import(pathToFileURL(join(fixture,'engine/index.js')));
const provenance=JSON.parse(await readFile(join(fixture,'provenance.json'),'utf8'));
for(const [name,item] of Object.entries(provenance)){
 assert.equal(item.sourceMatchesRelease,true);
 assert.equal(createHash('sha256').update(await readFile(join(fixture,'engine/js',name))).digest('hex'),item.sha256);
}
const wasm=process.argv.includes('--wasm');
if(wasm)assert.equal(await enableWASM(),true);
const urls=JSON.parse(execFileSync('python3',['-c',`import importlib.util,json
s=importlib.util.spec_from_file_location('subs',${JSON.stringify(join(root,'.circleci/scripts/apply-sandium-filter-subscriptions.py'))})
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
print(json.dumps([url for url,title in m.FILTERS]))`],{encoding:'utf8'}));
assert.equal(urls.length,30);assert.equal(new Set(urls).size,30);
let source=await readFile(join(here,'sandium-bridge.js'),'utf8');
for(const file of ['sandium-user-filters.js','sandium-lists.js']){
 const code=await readFile(join(here,file),'utf8');
 source=source.replace(`./${file}`,`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}
const {startSandiumBridge}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const dir=await mkdtemp(join(tmpdir(),'sandium-retained-'));
const nativePath=join(dir,'native.json'),storePath=join(dir,'extension.json');
const read=async path=>JSON.parse(await readFile(path,'utf8'));
const write=async(path,value)=>writeFile(path,JSON.stringify(value));
const sentinel=url=>`||list${urls.indexOf(url)}.example^`;
let state={generation:1,entries:urls.map(url=>({id:url,url,enabled:true,kind:'subscription'})),rules:'||custom.example^\n@@||custom.example/allowed.js$script\nnews.example##.test-ad'};
await write(nativePath,state);await write(storePath,{});
let engine;
let observed,bridge,acks=[],reloads=0;
const snapshot=()=>({protocol:1,engineCutover:true,generation:state.generation,shields:[],ads:[],cosmetic:[],customFilters:state.rules,customFiltersSha256:`custom-${state.generation}`,lists:{ready:true,revision:`lists-${state.generation}`,entries:structuredClone(state.entries)}});
async function open(){
 if(engine)await StaticNetFilteringEngine.release();
 engine=await StaticNetFilteringEngine.create();
 state=await read(nativePath);let disk=await read(storePath);
 const storage={async set(v){disk={...disk,...v};await write(storePath,disk);},async get(){return read(storePath);}};
 const ubo={userFiltersPath:'user-filters',selectedFilterLists:disk.selected||[],userSettings:{importedLists:disk.importedLists||[]},
 async getAvailableLists(){return Object.fromEntries(urls.map(url=>[url,{content:'filters',contentURL:url,submitter:'user'}]));},
 async saveSelectedFilterLists(v){this.selectedFilterLists=v;await storage.set({selected:v});},
 async getCompiledFilterList(key){return {content:`controlled-source:${key}`};},
 async loadUserFilters(){return {content:(await read(storePath)).rules||''};},
 async saveUserFilters(value){await storage.set({rules:value});},
 async loadFilterLists(){
  const data=await read(storePath);
  await engine.useLists(this.selectedFilterLists.map(key=>({name:key,raw:key==='user-filters'?data.rules:sentinel(key)})));
  reloads++;
 }};
 const api={onSettingsChanged:{addListener(f){observed=f;},removeListener(){observed=null;}},
 getSettingsSnapshot(cb){cb(snapshot());},
 acknowledgeSettings(g,c,l,cb){const ok=g===state.generation&&c===`custom-${g}`&&l===`lists-${g}`;if(ok)acks.push(g);cb(ok);},
 reportReady(p,phase,cb){cb(p===1&&phase==='listeners-ready');}};
 bridge=await startSandiumBridge(api,ubo,storage);await bridge.reportListenersReady();
}
const match=url=>engine.matchRequest({url,originURL:'https://news.example/',type:'script'});
async function update(mutate){mutate(state);state.generation++;await write(nativePath,state);observed(state.generation);for(let i=0;i<1000&&acks.at(-1)!==state.generation;i++)await new Promise(r=>setTimeout(r,5));assert.equal(acks.at(-1),state.generation);}
async function verify(){
 const data=await read(storePath);
 assert.deepEqual(new Set(data.selected),new Set(['user-filters',...state.entries.filter(e=>e.enabled).map(e=>e.url)]));
 assert.equal(data.rules,state.rules.trim());
 for(let i=0;i<30;i++)assert.equal(match(`https://list${i}.example/ad.js`),state.entries.some(e=>e.url===urls[i]&&e.enabled)?1:0,`list ${i}`);
}
try{
 await open();await verify();assert.equal(match('https://custom.example/ad.js'),1);assert.equal(match('https://custom.example/allowed.js'),2);
 await update(s=>{s.entries[1].enabled=false;s.entries=s.entries.filter(e=>e.url!==urls[2]);s.rules+='\n||added.example^';});await verify();assert.equal(match('https://added.example/ad.js'),1);
 const retained=await read(nativePath);bridge.dispose();await open();assert.deepEqual(await read(nativePath),retained);await verify();assert.equal(match('https://added.example/ad.js'),1);
 // Refresh without changing selections must preserve disabled/deleted entries.
 await update(()=>{});await verify();assert.equal(state.entries.some(e=>e.url===urls[2]),false);
 await update(s=>{s.entries.forEach(e=>e.enabled=false);s.rules='';});await verify();assert.equal(match('https://custom.example/ad.js'),0);
 bridge.dispose();await open();await verify();assert.equal(state.entries.length,29);
 await update(s=>{s.entries[0].enabled=true;});await verify();
 console.log(JSON.stringify({test:'retained data',productURLs:30,wasm,reloads,acknowledgedGenerations:acks,realUpstreamStaticEngine:true,controlledSentinelListPayloads:true,androidVerified:false,actualDownloadedListsVerified:false,cosmeticDOMVerified:false}));
}finally{bridge?.dispose();await rm(dir,{recursive:true,force:true});}
