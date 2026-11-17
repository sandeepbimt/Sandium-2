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
