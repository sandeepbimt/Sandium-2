import test from 'node:test';
import assert from 'node:assert/strict';
import {captureTarget, captureDescriptor, matchRemembered, validateRule, createCorrector, resolveTarget} from '../renderer/corrector.mjs';
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
test('anonymous and over-limit remembered selection rejected',()=>{const f=fixture();
 assert.throws(()=>captureDescriptor(f.el('div',f.body),f.doc),/Visit-only/);
 f.doc.querySelectorAll=()=>Array(4097).fill(f.header);
 assert.equal(matchRemembered({tag:'header',id:'masthead',role:'',ancestors:[],property:1,rgb:0},f.doc),null);
});

test('native integer wire schema round trips without string-property mismatch',()=>{const f=fixture();
 const native=JSON.parse(JSON.stringify({...captureDescriptor(f.header,f.doc),property:0,rgb:16777215}));
 assert.equal(matchRemembered(native,f.doc),f.header);
 assert.equal(matchRemembered({...native,property:'foreground'},f.doc),null);
});
