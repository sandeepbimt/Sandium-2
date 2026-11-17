import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
let source = await readFile(new URL('./sandium-bridge.js', import.meta.url), 'utf8');
const helper = await readFile(new URL('./sandium-user-filters.js', import.meta.url), 'utf8');
source = source.replace('./sandium-user-filters.js', `data:text/javascript;base64,${Buffer.from(helper).toString('base64')}`);
const listHelper = await readFile(new URL('./sandium-lists.js', import.meta.url),'utf8');
source = source.replace('./sandium-lists.js', `data:text/javascript;base64,${Buffer.from(listHelper).toString('base64')}`);
const { startSandiumBridge } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
assert.deepEqual(await startSandiumBridge(null), { available: false, cutover: false });
const calls = [];
const listeners = new Set();
const api = {
  onSettingsChanged: {addListener(fn) { listeners.add(fn); }, removeListener(fn) { listeners.delete(fn); }},
  getSettingsSnapshot(cb) { cb({protocol:1,engineCutover:false,generation:1,shields:[],ads:[],cosmetic:[]}); },
  reportReady(protocol, phase, callback) {
    calls.push([protocol, phase]); callback(true);
  },
  getSettings(url, callback) { callback({protocol: 1, engineCutover:false, shieldsEnabled:true}); },
};
const bridge = await startSandiumBridge(api);
assert.deepEqual(calls, []);
await bridge.reportListenersReady();
assert.deepEqual(calls, [[1,'listeners-ready']]);
assert.equal(bridge.cutover, false);
assert.equal(bridge.snapshot.generation,1);
for (const listener of listeners) listener(2);
assert.equal(bridge.snapshot,null);
await assert.rejects(bridge.refreshSnapshot(),/Settings changed/);
bridge.dispose();
assert.equal((await bridge.getSettings('https://example.test')).shieldsEnabled,true);
const rejected = await startSandiumBridge({...api, reportReady(p,s,cb) { cb(false); }});
await assert.rejects(rejected.reportListenersReady());
const wrong = await startSandiumBridge({...api, getSettings(u,cb) { cb({protocol:2,engineCutover:false}); }});
await assert.rejects(wrong.getSettings('https://example.test'));
globalThis.chrome = {runtime:{lastError:{message:'denied'}}};
await assert.rejects(startSandiumBridge(api), /denied/);
console.log('PASS bridge adapter: absent/rejected/version/error paths; no native runtime proof');
// Real adapter change path: a native generation event must reconcile and re-ACK
// rather than leaving the next navigation permanently waiting on stale state.
delete globalThis.chrome;
let generation=1;
let stored='';
let reloads=0;
let observed;
const acks=[];
const updates={
 onSettingsChanged:{addListener(f){observed=f;},removeListener(){}},
 getSettingsSnapshot(cb){cb({protocol:1,engineCutover:generation > 1,generation,shields:[],ads:[],cosmetic:[],customFilters:`example.test##.ad${generation}`,lists:{ready:true,revision:`lists${generation}`,entries:[]},customFiltersSha256:`digest${generation}`});},
 acknowledgeSettings(g,d,l,cb){acks.push([g,d]);cb(true);},
 reportReady(p,s,cb){cb(true);},
};
const engine={
 userSettings:{},async getAvailableLists(){return {};},userFiltersPath:'user-filters',selectedFilterLists:['user-filters'],
 async loadUserFilters(){return {content:stored};},async saveUserFilters(s){stored=s;},
 async saveSelectedFilterLists(){},async loadFilterLists(){reloads++;},
};
let listStorage={};
const live=await startSandiumBridge(updates,engine,{async set(v){listStorage=v;},async get(){return listStorage;}});
await live.reportListenersReady();
generation=2;observed(2);
await new Promise(resolve=>setTimeout(resolve,10));
assert.equal(reloads,2);
assert.equal(stored,'example.test##.ad2');
assert.equal(live.snapshot.engineCutover,true);
assert.equal(live.cutover,false); // snapshot is observation, never authority
assert.deepEqual(acks,[[1,'digest1'],[2,'digest2']]);
live.dispose();
console.log('Live generation reconcile/ACK PASS');
// Actual adapter + actual reconcilers, mocked browser API/storage/engine only.
// Cold migration must recover without disposing the extension or dropping lists.
let seedReady=false, seedGeneration=1, seedSnapshots=0, removed=0;
const seedListeners=new Set();
const selected=[];
const compiled=[];
const persisted={};
const retainedEntries=[
 {id:'https://one.test/list.txt',url:'https://one.test/list.txt',enabled:true,kind:'subscription'},
 {id:'https://off.test/list.txt',url:'https://off.test/list.txt',enabled:false,kind:'subscription'},
];
let rules='example.test##.retained';
const seedApi={...updates,
 onSettingsChanged:{addListener(f){seedListeners.add(f);},removeListener(f){removed++;seedListeners.delete(f);}},
 getSettingsSnapshot(cb){seedSnapshots++;cb({protocol:1,engineCutover:false,generation:seedGeneration,
 shields:[],ads:[],cosmetic:[],customFilters:rules,customFiltersSha256:'retained-digest',
 lists:{ready:seedReady,revision:`r${seedGeneration}`,entries:retainedEntries}});},
};
const seedEngine={...engine,
 async saveSelectedFilterLists(keys){selected.splice(0,selected.length,...keys);},
 async getCompiledFilterList(key){compiled.push(key);return {content:'compiled-filter'};},
};
const seedStorage={async set(v){Object.assign(persisted,v);},async get(){return persisted;}};
const starting=startSandiumBridge(seedApi,seedEngine,seedStorage);
await new Promise(r=>setTimeout(r,0));
assert.equal(seedListeners.size,1);assert.equal(removed,0);assert.equal(selected.length,0);
seedReady=true;seedGeneration=2;for(const f of seedListeners)f(2);
const recovered=await starting;
assert.ok(seedSnapshots>=2);
assert.deepEqual(selected,['user-filters','https://one.test/list.txt']);
assert.deepEqual(compiled,['https://one.test/list.txt']);assert.equal(stored,rules);
// Refresh: user disables/deletes selections and modifies custom rules. Empty is
// authoritative, not a reason to resurrect stock defaults or native seed URLs.
retainedEntries.length=0;rules='example.test##.changed';seedGeneration=3;
for(const f of seedListeners)f(3);
await new Promise(r=>setTimeout(r,10));
assert.deepEqual(selected,['user-filters']);assert.equal(stored,rules);
recovered.dispose();assert.equal(seedListeners.size,0);
const restarted=await startSandiumBridge(seedApi,seedEngine,seedStorage);
assert.deepEqual(selected,['user-filters']);assert.equal(stored,rules);
restarted.dispose();
// Bounded pending startup and caller cancellation both release the listener.
seedReady=false;
await assert.rejects(startSandiumBridge(seedApi,seedEngine,seedStorage,{readinessTimeoutMs:10}),/timed out/);
assert.equal(seedListeners.size,0);
const controller=new AbortController();
const aborted=startSandiumBridge(seedApi,seedEngine,seedStorage,{signal:controller.signal});
await new Promise(r=>setTimeout(r,0));controller.abort();
await assert.rejects(aborted,/disposed/);assert.equal(seedListeners.size,0);
console.log('Pending migration recovery, timeout/abort, retained selection/custom rules/restart PASS (host model, not device blocking proof)');
