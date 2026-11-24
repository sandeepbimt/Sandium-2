import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {test} from 'node:test';
import vm from 'node:vm';
import {join} from 'node:path';

const recipeRoot=new URL('../',import.meta.url);
const recipe=JSON.parse(readFileSync(new URL('production-restore-recipe.json',recipeRoot),'utf8'));
const owner='chrome/renderer/chrome_render_frame_observer.cc';
const candidate=readFileSync(process.argv[2] ? join(process.argv[2],owner) :
    new URL('production-postimages/'+recipe.files[owner].after_sha256,recipeRoot),'utf8');
const match=candidate.match(/constexpr char kRawSGenericDiscoveryRound\[\] = R"RAWSGEN\(([\s\S]+?)\)RAWSGEN";/);
assert.ok(match);
const script=new vm.Script(match[1]);
const list=recipe.files['chrome/browser/resources/raws/easylist.txt'].after_sha256;
const corpus=readFileSync(new URL('production-postimages/'+list,recipeRoot),'utf8');
const existing=corpus.split(/\r?\n/).find(s=>s==='##.ad_unit')?.slice(2);
assert.equal(existing,'.ad_unit','exact selector from the already packaged EasyList');

function fixture() {
  const docEvents = new Map(), winEvents = new Map();
  const doc={hidden:false,
    addEventListener(name, cb){docEvents.set(name, cb);},
    removeEventListener(name, cb){if(docEvents.get(name)===cb)docEvents.delete(name);}
  };
  const observers=[];
  class Element {
    nodeType=1;
    children=[];
    parentElement=null;
    constructor(localName, attrs={}) {this.localName=localName;this.attrs=new Map(Object.entries(attrs));}
    append(child) {child.parentElement=this;this.children.push(child);return child;}
    get isConnected(){for(let p=this;p;p=p.parentElement)if(p===doc.documentElement)return true;return false;}
    get firstElementChild(){return this.children[0]??null;}
    get nextElementSibling(){const siblings=this.parentElement?.children;return siblings?.[siblings.indexOf(this)+1]??null;}
    hasAttribute(n){return this.attrs.has(n);}
    getAttribute(n){return this.attrs.get(n)??null;}
    setAttribute(n,v){this.attrs.set(n,v);record(n,this);}
    removeAttribute(n){if(this.attrs.delete(n))record(n,this);}
  }
  doc.documentElement=new Element('html');
  doc.body=doc.documentElement.append(new Element('body'));
  function record(attributeName,target) {
    for(const o of observers){
      if(o.filter?.includes(attributeName))
        o.records.push({type:'attributes',attributeName,target});
    }
  }
  class MutationObserver {
    constructor(cb){this.cb=cb;this.records=[];observers.push(this);}
    observe(el,opts){assert.equal(el,doc.documentElement); this.filter=opts.attributeFilter;}
    disconnect(){this.filter=null;this.records=[];}
  }
  const context=vm.createContext({document:doc,MutationObserver,
    setTimeout(cb,delay){assert.equal(delay,30000);return 1;},
    clearTimeout(){},
    addEventListener(name,cb){winEvents.set(name,cb);},
    removeEventListener(name,cb){if(winEvents.get(name)===cb)winEvents.delete(name);}
  });
  function collect(){
    for(const o of observers)if(o.records.length){
      const pending=o.records.splice(0);o.cb(pending);
    }
    const data=script.runInContext(context);
    if(!data)return [];
    const [state,...keys]=data.split('\n');
    assert.ok(['0','1','2'].includes(state));
    assert.ok(keys.length<=64);
    return keys;
  }
  const dispatch=name=>winEvents.get(name)?.();
  return {doc,el:(tag,attrs)=>new Element(tag,attrs),collect,dispatch};
}

for(const [attr,value] of [['role','dialog'],['tabindex','0'],['contenteditable','true']]){
  test('recovers unchanged packaged selector after '+attr+' removal',()=>{
    const f=fixture(), holder=f.doc.body.append(f.el('div',{[attr]:value}));
    holder.append(f.el('div',{class:existing.slice(1)}));
    assert.deepEqual(f.collect(),[],'must not observe blocked subtree');
    holder.removeAttribute(attr);
    assert.deepEqual(f.collect(),[existing],'attribute alone can requalify subtree');
    assert.deepEqual(f.collect(),[],'same keys are not readmitted');
    f.dispatch('pagehide');
    holder.setAttribute('role','dialog');
    holder.removeAttribute('role');
    assert.deepEqual(f.collect(),[],'pagehide tombstone prevents restart');
  });
}

test('guard changes never admit elements that remain protected',()=>{
  for(const [tag,attrs,remove] of [
    ['div',{role:'dialog',tabindex:'0'},'role'],
    ['a',{role:'button'},'role'],
    ['form',{contenteditable:'true'},'contenteditable'],
  ]){
    const f=fixture(), holder=f.doc.body.append(f.el(tag,attrs));
    holder.append(f.el('div',{class:existing.slice(1)}));
    assert.deepEqual(f.collect(),[]);
    holder.removeAttribute(remove);
    assert.deepEqual(f.collect(),[]);
  }
});

test('if protection returns before the late traversal, no key is read',()=>{
  const f=fixture(), holder=f.doc.body.append(f.el('div',{role:'dialog'}));
  holder.append(f.el('div',{class:existing.slice(1)}));
  assert.deepEqual(f.collect(),[]);
  holder.removeAttribute('role');
  holder.setAttribute('role','dialog');
  assert.deepEqual(f.collect(),[]);
  holder.setAttribute('class','ad_unit');
  assert.deepEqual(f.collect(),[]);
});

test('attribute recovery preserves the 64-key wire cap',()=>{
  const f=fixture(), holder=f.doc.body.append(f.el('div',{role:'dialog'}));
  for(let i=0;i<125;++i)holder.append(f.el('div',{class:'ad_unit_'+i}));
  assert.deepEqual(f.collect(),[]);
  holder.removeAttribute('role');
  const first=f.collect(), next=f.collect();
  assert.equal(first.length,64);
  assert.equal(next.length,61);
  assert.equal(new Set([...first,...next]).size,125);
});


test('newly protected ancestor blocks a saved cursor before the next batch',()=>{
  const f=fixture(), holder=f.doc.body.append(f.el('div',{role:'dialog'}));
  for(let i=0;i<90;++i)holder.append(f.el('div',{class:'ad_unit_'+i}));
  assert.deepEqual(f.collect(),[]);
  holder.removeAttribute('role');
  assert.equal(f.collect().length,64);
  holder.setAttribute('role','dialog');
  assert.deepEqual(f.collect(),[],'resume must recheck the ancestor lease');
  holder.removeAttribute('role');
  const tail=f.collect();
  assert.equal(tail.length,26);
  assert.equal(tail[0],'.ad_unit_64');
});
