import test from 'node:test';
import assert from 'node:assert/strict';
import {captureTarget, createRememberedRestorer, watchRememberedRules, captureDescriptor, matchRemembered, validateRule, createCorrector, resolveTarget} from '../renderer/corrector.mjs';
function fixture() {
  const doc = {};
  function el(tag, parent, attrs = {}) {
    const value = {localName:tag, tagName:tag.toUpperCase(), namespaceURI:'http://www.w3.org/1999/xhtml',
      children:[], parentElement:parent, ownerDocument:doc, isConnected:true,
      getAttribute:key => attrs[key] ?? null, getRootNode:() => doc};
    if (parent) parent.children.push(value);
    return value;
  }
  doc.documentElement = el('html', null);
  const head = el('head', doc.documentElement);
  const body = el('body', doc.documentElement);
  const header = el('header', body, {id:'masthead'});
  const logo = el('img', header, {id:'logo'});
  doc.querySelectorAll=()=>{const nodes=[];function visit(n){if(n.getAttribute('id')!==null)nodes.push(n);for(const child of n.children)visit(child);}visit(doc.documentElement);return nodes;};
  return {doc, el, head, body, header, logo};
}
function rule(f) { return {path:captureTarget(f.header,f.doc), property:'background',rgb:0x1a1a1a}; }
test('bounded selector and typed color validation', () => {
  const f=fixture(); assert.equal(validateRule(rule(f),f.doc),true);
});
test('blocked active/embedded/root targets',()=>{ const f=fixture();
  for(const tag of ['iframe','video','canvas','input','script']) assert.throws(()=>captureTarget(f.el(tag,f.body),f.doc));
  assert.throws(()=>captureTarget(f.body,f.doc));
});
test('cross document, shadow and svg rejected',()=>{ const f=fixture(); const a=f.el('span',f.body);
  a.ownerDocument={}; assert.throws(()=>captureTarget(a,f.doc)); a.ownerDocument=f.doc;
  a.getRootNode=()=>({}); assert.throws(()=>captureTarget(a,f.doc)); a.getRootNode=()=>f.doc;
  a.namespaceURI='http://www.w3.org/2000/svg'; assert.throws(()=>captureTarget(a,f.doc));
});
test('CSS injection rejected in properties, color and tag',()=>{ const f=fixture();
  for(const property of ['background-image','color','__proto__','background;display']) assert.throws(()=>validateRule({...rule(f),property},f.doc));
  for(const rgb of [-1,0x1000000,NaN,1.1,'url(https://bad)']) assert.throws(()=>validateRule({...rule(f),rgb},f.doc));
  const r=rule(f);r.path[1].tag='header}body{';assert.throws(()=>validateRule(r,f.doc));
});
test('identity is never CSS interpolated',()=>{ const f=fixture(); const target=f.el('div',f.body,{id:'x}body{color:red'});
  const r={...rule(f),path:captureTarget(target,f.doc)};assert.equal(validateRule(r,f.doc),true);
});
test('changed identity and detached target fail closed',()=>{const f=fixture();const r=rule(f);
  f.header.getAttribute=()=> 'different';assert.equal(resolveTarget(r.path,f.doc),null);
});
test('limits enforced',()=>{const f=fixture();const r=rule(f);r.path[0].index=9000;assert.throws(()=>validateRule(r,f.doc));
  let parent=f.body;for(let i=0;i<25;i++)parent=f.el('div',parent);assert.throws(()=>captureTarget(parent,f.doc));
});
function runtime(f) { let current=true;const calls=[];const b={assertCurrent:()=>{if(!current)throw Error('Stale session');},
  replacePreviewNodes:x=>calls.push(['preview',x]), replaceSavedNodes:x=>calls.push(['saved',x]),
  commitSavedAndClearPreview:x=>calls.push(['commit',x]),restoreRememberedNodes:x=>calls.push(['restore',x]),disposeOverrides:()=>calls.push(['dispose'])};
  return {engine:createCorrector(f.doc,b),calls,invalidate:()=>current=false}; }
test('preview and cancel remove preview without touching saved',()=>{const f=fixture();const x=runtime(f);
  const h=x.engine.select(f.header);x.engine.preview(h,'background',0);x.engine.cancelPreview();
  assert.deepEqual(x.calls.at(-1),['preview',[]]);assert.equal(x.calls.length,2);
});
test('typed values validated before native invocation',()=>{const f=fixture();const x=runtime(f);
  const h=x.engine.select(f.header);assert.throws(()=>x.engine.preview(h,'background-image',0));
  assert.throws(()=>x.engine.applyConfirmed(h,'background','url(x)'));assert.equal(x.calls.length,0);
});
test('stale session rejects selection preview and saved application',()=>{const f=fixture();const x=runtime(f);x.invalidate();
  assert.throws(()=>x.engine.select(f.header));assert.throws(()=>x.engine.preview(1,'background',0));
  assert.throws(()=>x.engine.applyConfirmed(1,'background',0));x.engine.close();assert.deepEqual(x.calls,[['dispose']]);
});
test('close is idempotent and disables future work',()=>{const f=fixture();const x=runtime(f);x.engine.close();x.engine.close();
  assert.equal(x.calls.length,1);assert.throws(()=>x.engine.preview(1,'background',0));
});
test('same fingerprint replacement cannot preview old selection',()=>{const f=fixture();const x=runtime(f);
  const h=x.engine.select(f.header);const replacement=f.el('header',null,{id:'masthead'});
  replacement.parentElement=f.body;f.body.children[0]=replacement;f.header.isConnected=false;
  assert.throws(()=>x.engine.preview(h,'background',0),/Stale selection/);assert.equal(x.calls.length,0);
});
test('same fingerprint replacement cannot retain or reacquire correction',()=>{const f=fixture();const x=runtime(f);
  const h=x.engine.select(f.header);x.engine.preview(h,'background',0);x.engine.applyConfirmed(h,'background',0);
  assert.equal(x.calls[0][1][0].node,f.header);
  const replacement=f.el('header',null,{id:'masthead'});replacement.parentElement=f.body;
  f.body.children[0]=replacement;f.header.isConnected=false;x.engine.revalidate();
  assert.deepEqual(x.calls.at(-1),['saved',[]]);
  assert.throws(()=>x.engine.applyConfirmed(h,'background',0),/Unknown selection/);
});
test('forged handle and raw saved selector cannot initiate correction',()=>{const f=fixture();const x=runtime(f);
  assert.throws(()=>x.engine.preview({path:rule(f).path},'background',0));
  assert.equal(x.engine.applySaved,undefined);assert.equal(x.calls.length,0);
});
test('editable and form containers are excluded',()=>{const f=fixture();
  assert.throws(()=>captureTarget(f.el('button',f.body),f.doc));
  const target=f.el('div',f.body);target.isContentEditable=true;assert.throws(()=>captureTarget(target,f.doc));
  target.isContentEditable=false;target.closest=()=>({});assert.throws(()=>captureTarget(target,f.doc));
});

test('save replaces same property and atomically clears preview',()=>{const f=fixture();const x=runtime(f);
  const h=x.engine.select(f.header);x.engine.preview(h,'background',1);x.engine.applyConfirmed(h,'background',2);
  assert.equal(x.calls.at(-1)[0],'commit');assert.equal(x.calls.at(-1)[1][0].rgb,2);
  for(let i=0;i<40;i++)x.engine.applyConfirmed(h,'background',i);
  assert.equal(x.calls.at(-1)[1].length,1);
});

test('remembered exact unique identity binds once then never reacquires replacement',()=>{const f=fixture();const x=runtime(f);
 const rule={...captureDescriptor(f.header,f.doc),property:1,rgb:0};
 assert.equal(matchRemembered(rule,f.doc),f.header);assert.equal(x.engine.restoreRemembered([rule]),0);
 assert.throws(()=>x.engine.restoreRemembered([rule]),/Already attempted/);
 const replacement=f.el('header',null,{id:'masthead'});replacement.parentElement=f.body;
 f.body.children[0]=replacement;f.header.isConnected=false;x.engine.revalidate();
 assert.deepEqual(x.calls.at(-1),['saved',[]]);
});
test('ambiguous changed or absent remembered targets remain unchanged',()=>{const f=fixture();
 const rule={...captureDescriptor(f.header,f.doc),property:1,rgb:0};
 assert.equal(matchRemembered({...rule,tag:'div'},f.doc),null);
 assert.equal(matchRemembered({...rule,id:'missing'},f.doc),null);
 f.el('header',f.body,{id:'masthead'});assert.equal(matchRemembered(rule,f.doc),null);
});
test('anonymous without IDs now persists while document limit still applies',()=>{const f=fixture();
 const target=f.el('div',f.body);assert.equal(captureDescriptor(target,f.doc).locator.anchor,'');
 f.doc.querySelectorAll=()=>Array(4097).fill(f.header);
 assert.equal(matchRemembered({tag:'header',id:'masthead',role:'',ancestors:[],property:1,rgb:0},f.doc),null);
});

test('native integer wire schema round trips without string-property mismatch',()=>{const f=fixture();
 const native=JSON.parse(JSON.stringify({...captureDescriptor(f.header,f.doc),property:0,rgb:16777215}));
 assert.equal(matchRemembered(native,f.doc),f.header);
 assert.equal(matchRemembered({...native,property:'foreground'},f.doc),null);
});
test('image artwork is explicit and limited to img elements',()=>{
 const f=fixture();const x=runtime(f);const h=x.engine.select(f.logo);
 assert.equal(validateRule({path:captureTarget(f.logo,f.doc),property:'image',rgb:0xeeeeee},f.doc),true);
 assert.equal(validateRule({...rule(f),property:'image'},f.doc),null);
 assert.equal(x.calls.length,0); // Selection alone never changes colors.
 x.engine.preview(h,'image',0xeeeeee);
 assert.equal(x.calls.at(-1)[1][0].property,'image');
 x.engine.cancelPreview();assert.deepEqual(x.calls.at(-1),['preview',[]]);
 const remembered={...captureDescriptor(f.logo,f.doc),property:2,rgb:0xeeeeee};
 assert.equal(matchRemembered(remembered,f.doc),f.logo);
 assert.equal(matchRemembered({...captureDescriptor(f.header,f.doc),property:2,rgb:0},f.doc),null);
 assert.equal(matchRemembered({...remembered,property:3},f.doc),null);
});

test('anonymous image text and background restore after fresh document restart',()=>{
  const saved=fixture();const image=saved.el('img',saved.header,{class:'brand logo'});
  const label=saved.el('span',saved.header,{class:'title'});
  const rules=[{...captureDescriptor(image,saved.doc),property:2,rgb:0xffffff},
    {...captureDescriptor(label,saved.doc),property:0,rgb:0xeeeeee},
    {...captureDescriptor(label,saved.doc),property:1,rgb:0x111111}];
  const disk=JSON.stringify(nativeDict(rules));
  const reopened=fixture();const newImage=reopened.el('img',reopened.header,{class:'logo brand'});
  const newLabel=reopened.el('span',reopened.header,{class:'title'});
  const restored=JSON.parse(disk);
  assert.equal(matchRemembered(restored[0],reopened.doc),newImage);
  assert.equal(matchRemembered(restored[1],reopened.doc),newLabel);
  const runtime2=runtime(reopened);assert.equal(runtime2.engine.restoreRemembered(restored),0);
  assert.equal(runtime2.calls[0][1].length,3);
});
test('anonymous persistence rejects ambiguous and changed structure',()=>{
  const f=fixture(), image=f.el('img',f.header,{class:'brand'});
  const r={...captureDescriptor(image,f.doc),property:2,rgb:1};
  f.el('img',f.header,{class:'brand'});
  assert.equal(matchRemembered(r,f.doc),null);
  assert.equal(captureDescriptor(image,f.doc).locator.steps.at(-1).count,2);
  const other=fixture();other.el('img',other.header,{class:'changed'});
  assert.equal(matchRemembered(r,other.doc),null);
  const missing=fixture();missing.header.getAttribute=()=>null;
  assert.equal(matchRemembered(r,missing.doc),null);
});
test('malformed locator cannot broaden stored identity',()=>{
  const f=fixture(), image=f.el('img',f.header,{class:'brand'});
  const r={...captureDescriptor(image,f.doc),property:2,rgb:1};
  for(const locator of [{anchor:'masthead',steps:[]},{anchor:'masthead',steps:[{}]},
    {anchor:'masthead',steps:[{tag:'img',role:'',classes:[]}]}])
    assert.equal(matchRemembered({...r,locator},f.doc),null);
});

// base::DictValue serializes object keys in lexicographic order, not insertion order.
function nativeDict(value) {
  if(Array.isArray(value))return value.map(nativeDict);
  if(value && typeof value==='object')return Object.fromEntries(
    Object.keys(value).sort().map(key=>[key,nativeDict(value[key])]));
  return value;
}
test('native sorted-key persistence restores legacy unique-ID rules after restart',()=>{
  const first=fixture();const rule={...captureDescriptor(first.logo,first.doc),property:2,rgb:123};
  const disk=JSON.stringify(nativeDict(rule));
  assert.notEqual(disk,JSON.stringify(rule));
  const second=fixture();assert.equal(matchRemembered(JSON.parse(disk),second.doc),second.logo);
});

test('root structural rule roundtrips anonymous text background and image without IDs',()=>{
 const first=fixture();first.header.getAttribute=()=>null;
 const image=first.el('img',first.header,{class:'logo md:wide'});
 const title=first.el('span',first.header);
 const rules=[{...captureDescriptor(image,first.doc),property:2,rgb:12},
  {...captureDescriptor(title,first.doc),property:0,rgb:13},
  {...captureDescriptor(title,first.doc),property:1,rgb:14}];
 assert.ok(rules.every(rule=>rule.locator.anchor===''));
 const second=fixture();second.header.getAttribute=()=>null;
 const image2=second.el('img',second.header,{class:'md:wide logo'}), title2=second.el('span',second.header);
 const persisted=JSON.parse(JSON.stringify(nativeDict(rules)));
 assert.equal(matchRemembered(persisted[0],second.doc),image2);
 assert.equal(matchRemembered(persisted[1],second.doc),title2);
 assert.equal(matchRemembered(persisted[2],second.doc),title2);
});
test('identical sibling selector stays precise and rejects count drift',()=>{
 const f=fixture();const one=f.el('span',f.header), two=f.el('span',f.header);
 const r={...captureDescriptor(two,f.doc),property:0,rgb:3};
 assert.equal(r.locator.steps.at(-1).ordinal,2);
 const next=fixture();next.el('span',next.header);const target=next.el('span',next.header);
 assert.equal(matchRemembered(nativeDict(r),next.doc),target);
 next.el('span',next.header);assert.equal(matchRemembered(r,next.doc),null);
});
test('pending rules restore late nodes once and never rematch replacements',()=>{
 const source=fixture();const target=source.el('span',source.header,{class:'late'});
 const r={...captureDescriptor(target,source.doc),property:0,rgb:1};
 const dest=fixture(),calls=[];
 const restorer=createRememberedRestorer(dest.doc,[nativeDict(r)],(node,index)=>calls.push([node,index]));
 assert.equal(restorer.retry(),1);assert.equal(calls.length,0);
 const late=dest.el('span',dest.header,{class:'late'});
 assert.equal(restorer.retry(),0);assert.equal(calls[0][0],late);
 late.isConnected=false;dest.header.children.pop();dest.el('span',dest.header,{class:'late'});
 assert.equal(restorer.retry(),0);assert.equal(calls.length,1);
});
test('stopping pending restoration prevents stale-document writes',()=>{
 const source=fixture(),target=source.el('span',source.header);
 const r={...captureDescriptor(target,source.doc),property:0,rgb:1};
 const dest=fixture(),calls=[];
 const restorer=createRememberedRestorer(dest.doc,[r],node=>calls.push(node));
 assert.equal(restorer.retry(),1);restorer.stop();dest.el('span',dest.header);
 assert.equal(restorer.retry(),0);assert.equal(calls.length,0);
});
test('watcher coalesces mutations and releases itself when all rules match',()=>{
 const f=fixture(),selected=f.el('span',f.header,{class:'late'});
 const rule={...captureDescriptor(selected,f.doc),property:0,rgb:1};
 f.header.children.pop();selected.isConnected=false;
 const original={MutationObserver:globalThis.MutationObserver,setTimeout:globalThis.setTimeout,
  clearTimeout:globalThis.clearTimeout};
 let trigger,scheduled,disconnected=false,apply=0;
 globalThis.MutationObserver=class {constructor(fn){trigger=fn;}observe(target){assert.equal(target,f.doc);}disconnect(){disconnected=true;}};
 globalThis.setTimeout=fn=>{assert.equal(scheduled,undefined);scheduled=fn;return 1;};
 globalThis.clearTimeout=()=>{scheduled=undefined;};
 try {
  watchRememberedRules(f.doc,[rule],()=>{apply++;return true;});
  trigger();trigger();assert.equal(apply,0);
  f.el('span',f.header,{class:'late'});const run=scheduled;scheduled=undefined;run();
  assert.equal(apply,1);assert.equal(disconnected,true);
  assert.equal(globalThis.__sandiumCancelRestore,undefined);
 } finally {globalThis.__sandiumCancelRestore?.();Object.assign(globalThis,original);}
});
