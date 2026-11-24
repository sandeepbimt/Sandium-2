import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import vm from 'node:vm';
import { join } from 'node:path';
const input = process.argv[2];
const root = new URL('..', import.meta.url);
const recipe = JSON.parse(readFileSync(new URL('production-restore-recipe.json', root)));
const contents = name => input ?
    readFileSync(join(input, 'chrome/renderer', name), 'utf8') :
    readFileSync(new URL('production-postimages/' +
      recipe.files['chrome/renderer/' + name].after_sha256, root), 'utf8');
const js = (name, delimiter) => contents(name)
  .split('R"' + delimiter + '(')[1].split(')' + delimiter + '"')[0];
const runtime = js('raws_passive_procedural_runtime.h', 'RAWSPASS');
const schedule = js('raws_dynamic_cosmetic_scheduler.h', 'RAWSJS');
const href = 'https://fixture.invalid/news/';
const nonce = 'A'.repeat(32);
const mark = 'data-raws-passive-ad';
const row = (anchor, attribute) => JSON.stringify({
  selector: [{type:'css-selector',arg:anchor}, {type:'matches-attr',arg:attribute}],
  action:null
});
function fixture() {
  class Events {
    constructor(){ this.events = new Map(); }
    addEventListener(key, callback){ this.events.set(key, callback); }
    removeEventListener(key, callback){ if(this.events.get(key)===callback)this.events.delete(key); }
    dispatch(key){ this.events.get(key)?.(); }
  }
  const doc=new Events(), win=new Events();
  const timers=new Map();
  const active=new Set();
  let nextTimer=0;
  class Element {
    constructor(tag, attributes={}, text='Sponsored') {
      this.tag=tag;
      this.innerText=text;
      this.attrs=new Map(Object.entries(attributes));
      this.nodeType=1;
      this.ownerDocument=doc;
      this.parentElement=null;
      this.children=[];
    }
    getClientRects(){return [{width:40,height:20}];}
    get isConnected() { return doc.documentElement.contains(this); }
    get firstElementChild(){return this.children[0]??null;}
    get nextElementSibling(){
      const siblings=this.parentElement?.children;
      return siblings?.[siblings.indexOf(this)+1]??null;
    }
    append(child){child.parentElement=this;this.children.push(child);return child;}
    getAttribute(name){return this.attrs.get(name)??null;}
    hasAttribute(name){return this.attrs.has(name);}
    setAttribute(name,value){
      this.attrs.set(name,value); mutate(this,name);
    }
    removeAttribute(name){if(this.attrs.delete(name))mutate(this,name);}
    contains(el){for(;el;el=el.parentElement)if(el===this)return true;return false;}
    matches(css){
      if(css.startsWith('dialog[open]')) return this.attrs.get('role')==='dialog';
      if(css.includes(',')) return ['form','button','input','select','dialog'].includes(this.tag);
      const attr = /^(?:div)?\[([a-z-]+)(\^?=)(["'])([A-Za-z0-9_-]+)\3\]$/.exec(css);
      if(attr){
        const value=this.attrs.get(attr[1]);
        return typeof value === 'string' &&
            (attr[2] === '=' ? value === attr[4] : value.startsWith(attr[4]));
      }
      const atoms = css.split(' > ');
      for (let element = this, i = atoms.length - 1; i >= 0; --i, element = element?.parentElement) {
        if (!element) return false;
        const m = /^([a-z]*)(?:([.#])([a-z-]+))?$/.exec(atoms[i]);
        if (!m || (m[1] && m[1] !== element.tag)) return false;
        if (m[2] === '#' && element.getAttribute('id') !== m[3]) return false;
        if (m[2] === '.' && !element.getAttribute('class')?.split(/\s+/).includes(m[3])) return false;
      }
      return true;
    }
  }
  doc.defaultView=win; doc.location=new URL(href); doc.contentType='text/html'; doc.hidden=false;
  doc.documentElement=new Element('html');
  doc.body=doc.documentElement.append(new Element('body'));
  doc.createTreeWalker=(node, filter)=>{
    assert.ok(filter===1 || filter===4);
    const descendants = n=>n.children.flatMap(child=>[child,...descendants(child)]);
    const result=filter===1 ? descendants(node) : [node,...descendants(node)].map(n=>({length:n.innerText.length}));
    return {nextNode:()=>result.shift()??null};
  };
  win.document=doc; win.top=win; win.navigation=new Events();
  win.performance={now:()=>0};
  win.setTimeout=(action,delay)=>{
    assert.equal(delay,125);timers.set(++nextTimer,action);return nextTimer;
  };
  win.clearTimeout=id=>timers.delete(id);
  win.MutationObserver=class {
    constructor(callback){this.callback=callback;this.records=[];}
    observe(element,opts){this.el=element;this.opts=opts;active.add(this);}
    disconnect(){active.delete(this);this.records=[];}
  };
  function mutate(target,name){
    for(const o of active)
      if(o.opts.attributes && o.opts.attributeFilter.includes(name) &&
         (o.el===target || o.opts.subtree && o.el.contains(target)))
        o.records.push({type:'attributes',target,attributeName:name,addedNodes:[]});
  }
  function tick(){
    for(const o of active)
      if(o.records.length){
        const pending=o.records;o.records=[];o.callback(pending);
      }
    assert.ok(timers.size<=1);
    const item=timers.entries().next();
    if(item.done)return false;
    const [id,cb]=item.value;timers.delete(id);cb();return true;
  }
  const sandbox=vm.createContext({document:doc,href,nonce});
  function start(rules,exceptions=[], scheduled=true){
    sandbox.wire=JSON.stringify({schema:1,exceptions_complete:true,suppress_generic:false,
      rules,exceptions});
    vm.runInContext(runtime+'('+schedule+',wire,href,nonce)',sandbox);
    assert.equal(tick(),scheduled);
    assert.equal(tick(),false);
  }
  return {doc,win,Element,tick,start,rootFilter:()=>
    [...active].find(o=>o.el===doc.documentElement)?.opts.attributeFilter};
}

test('two-level anchor gains and loses a match on ancestor-only mutations', () => {
  const f = fixture();
  const wrapper = f.doc.body.append(new f.Element('section'));
  const group = wrapper.append(new f.Element('div', {class:'group'}));
  const ad = group.append(new f.Element('div', {class:'ad-card','data-ad-unit':'slot'}));
  const editorial = group.append(new f.Element('div', {class:'ad-card'}));
  f.start([row('section#above > div.group > div.ad-card','data-ad-unit=slot')]);
  assert.equal(ad.hasAttribute(mark),false);
  wrapper.setAttribute('id','above');
  assert.equal(f.tick(),true);
  assert.equal(ad.getAttribute(mark),nonce,'revisits the true descendant subject, not its ancestors');
  assert.equal(editorial.hasAttribute(mark),false,'still requires an admitted ad structure and proof');
  group.setAttribute('class','changed');
  assert.equal(f.tick(),true);
  assert.equal(ad.hasAttribute(mark),false,'loss of the exact compound revokes a live mark');
  group.setAttribute('class','group');
  assert.equal(f.tick(),true);
  assert.equal(ad.getAttribute(mark),nonce,'can reapply on the same route');
});

test('a matched single-level anchor is revoked if an outside ancestor changes class', () => {
  const f = fixture();
  const wrapper = f.doc.body.append(new f.Element('div', {class:'placements'}));
  const ad = wrapper.append(new f.Element('div', {class:'ad-card','data-ad-slot':'slot'}));
  f.start([row('div.placements > div.ad-card','data-ad-slot=slot')]);
  assert.equal(ad.getAttribute(mark),nonce);
  wrapper.removeAttribute('class');
  assert.equal(f.tick(),true);
  assert.equal(ad.hasAttribute(mark),false);
  assert.equal(f.tick(),false,'own paint mutation never triggers traversal');
});

test('anchor mutations respect exceptions and protected descendants', () => {
  const f = fixture();
  const parent = f.doc.body.append(new f.Element('div'));
  const target = parent.append(new f.Element('div',{class:'ad-card','data-ad-slot':'slot'}));
  target.append(new f.Element('button'));
  const filter = row('div.placements > div.ad-card','data-ad-slot=slot');
  f.start([filter]);
  parent.setAttribute('class','placements');
  assert.equal(f.tick(),true);
  assert.equal(target.hasAttribute(mark),false);
  f.start([filter],[filter],false);
  assert.equal(f.rootFilter(),undefined);
});

test('an implicit html ancestor can change direct-body matches without visiting beyond the two-edge path', () => {
  const f = fixture();
  f.doc.body.setAttribute('class','body-scope');
  const direct = f.doc.body.append(new f.Element('div',{class:'ad-card','data-ad-slot':'slot'}));
  const wrapper = f.doc.body.append(new f.Element('div'));
  const deep = wrapper.append(new f.Element('div',{class:'ad-card','data-ad-slot':'slot'}));
  f.start([row('.layout > .body-scope > div.ad-card','data-ad-slot=slot')]);
  let deepVisits = 0;
  const baseMatches = deep.matches.bind(deep);
  deep.matches = selector => { deepVisits++; return baseMatches(selector); };
  f.doc.documentElement.setAttribute('class','layout');
  assert.equal(f.tick(),true);
  assert.equal(direct.getAttribute(mark),nonce);
  assert.equal(deepVisits,0);
  f.doc.documentElement.removeAttribute('class');
  assert.equal(f.tick(),true);
  assert.equal(direct.hasAttribute(mark),false);
  assert.equal(deepVisits,0);
});
