import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const code=await readFile(new URL('./sandium-lists.js',import.meta.url),'utf8');
const {createListReconciler}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
let saved={};let selected=[];let compile=[];
const storage={async set(v){Object.assign(saved,v);},async get(){return structuredClone(saved);}};
const ubo={userFiltersPath:'user-filters',userSettings:{},async getAvailableLists(){return {easy:{content:'filters',contentURL:['https://original.test/easy.txt']}};},async saveSelectedFilterLists(v){selected=v;},async getCompiledFilterList(k){compile.push(k);return {content:'compiled actual rules'};}};
const snap={generation:1,lists:{ready:true,revision:'hash',entries:[
{id:'id1',kind:'regional',url:'https://original.test/easy.txt',enabled:true},
{id:'id2',kind:'subscription',url:'https://other.test/list.txt',enabled:true},
{id:'id3',kind:'regional',url:'invalid disabled',enabled:false},
]}};
const r=createListReconciler(ubo,storage);
assert.equal(await r.apply(snap),true);
assert.deepEqual(selected,['user-filters','easy','https://other.test/list.txt']);
assert.deepEqual(saved.importedLists,['https://other.test/list.txt']);
assert.equal(compile.length,2);
assert.equal(await r.apply({...snap,generation:2,lists:{...snap.lists,entries:[]}}),true);
assert.deepEqual(selected,['user-filters']);assert.deepEqual(saved.importedLists,[]);
await assert.rejects(r.apply({...snap,lists:{...snap.lists,ready:false}}));
await assert.rejects(r.apply({...snap,lists:{...snap.lists,entries:[{id:'bad',kind:'regional',enabled:true,url:'file:///tmp/list'}]}}));
const bad=createListReconciler({...ubo,async getCompiledFilterList(){return {content:'',error:'network'};}},storage);
await assert.rejects(bad.apply(snap),/unavailable/);
let release;const stale=createListReconciler({...ubo,async getAvailableLists(){await new Promise(r=>release=r);return {};}},storage);
const pending=stale.apply(snap);stale.invalidate(2);release();assert.equal(await pending,false);
console.log('List reconciliation exact mapping, removal, unavailable, stale generation PASS');
