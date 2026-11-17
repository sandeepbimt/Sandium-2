import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
let source = await readFile(new URL('./sandium-bridge.js', import.meta.url), 'utf8');
const helper = await readFile(new URL('./sandium-user-filters.js', import.meta.url), 'utf8');
source = source.replace('./sandium-user-filters.js', `data:text/javascript;base64,${Buffer.from(helper).toString('base64')}`);
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
