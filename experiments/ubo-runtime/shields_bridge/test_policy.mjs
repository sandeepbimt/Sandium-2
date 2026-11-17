import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source=await readFile(new URL('./sandium-policy.js',import.meta.url),'utf8');
const {allowsNetwork,allowsTab,allowsPopup}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const p={protocol:1,engineOwned:true,runtimeAvailable:true,shieldsEnabled:true,adControl:'block',cosmeticControl:'block'};
assert.equal(allowsNetwork({sandiumShields:p}),true);
for(const change of [{runtimeAvailable:undefined},{runtimeAvailable:false},{protocol:2},{engineOwned:false},{shieldsEnabled:false},{adControl:'allow'},{adControl:'unknown'}]) assert.equal(allowsNetwork({sandiumShields:{...p,...change}}),false);
assert.equal(allowsNetwork({}),false);
const api={getTabPolicy(t,f,u,cb){cb(p);},getPopupTargetPolicy(t,u,cb){cb(p);}};
assert.equal(await allowsTab(1,0,'https://example.test',true,api),true);
assert.equal(await allowsTab(1,0,'https://example.test',true,{getTabPolicy(t,f,u,cb){cb({...p,cosmeticControl:'allow'});}}),false);
assert.equal(await allowsTab(1,0,'https://example.test',true,{getTabPolicy(t,f,u,cb){cb({...p,runtimeAvailable:false});}}),false);
assert.equal(await allowsTab(-1,0,'https://example.test',false,api),false);
// Ads and cosmetic content settings are independent native controls.
const cosmeticOnly={getTabPolicy(t,f,u,cb){cb({...p,adControl:'allow'});}};
assert.equal(await allowsTab(1,0,'https://example.test',true,cosmeticOnly),true);
assert.equal(await allowsTab(1,0,'https://example.test',false,cosmeticOnly),false);
const opener={tabId:1,frameId:0,frameURL:'https://opener.test/'};
const target={tabId:2,url:'https://target.test/'};
assert.equal(await allowsPopup(opener,target,api),true);
for (const disabled of [{runtimeAvailable:undefined},{runtimeAvailable:false},{engineOwned:false},{shieldsEnabled:false},{adControl:'allow'}]) {
 for (const disabledTab of [1,2]) {
  const gate={getTabPolicy(t,f,u,cb){cb(t===disabledTab?{...p,...disabled}:p);},getPopupTargetPolicy(t,u,cb){cb(t===disabledTab?{...p,...disabled}:p);}};
  assert.equal(await allowsPopup(opener,target,gate),false);
 }
}
assert.equal(await allowsPopup(null,target,api),false);
for (const url of ['about:blank','data:text/html,x','',undefined])
 assert.equal(await allowsPopup(opener,{tabId:2,url},api),false);
assert.equal(await allowsPopup(opener,target,{...api,getPopupTargetPolicy(t,u,cb){cb(null);}}),false);
assert.equal(await allowsPopup(opener,target,{getTabPolicy:api.getTabPolicy}),false);
globalThis.chrome={runtime:{lastError:{message:'document changed'}}};
assert.equal(await allowsTab(1,0,'https://example.test',false,api),false);
console.log('Native-policy adapter gate tests PASS');
delete globalThis.chrome;
let docArgs;
const withDocument={getTabPolicy(...args){docArgs=args.slice(0,-1);args.at(-1)(p);}};
assert.equal(await allowsTab(1,0,'https://example.test/old',true,withDocument,'document-7'),true);
assert.deepEqual(docArgs,[1,0,'https://example.test/old','document-7']);
console.log('Document identity forwarded without URL rewriting PASS');
