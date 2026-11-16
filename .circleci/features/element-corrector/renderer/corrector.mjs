// Copyright 2026 Sandium Authors. BSD-style license.
// Isolated-world renderer core. Not enabled until the native session/sheet bridge lands.
// No persistence or page-owned confirmation controls belong in this module.
const MAX_DEPTH = 24;
const MAX_RULES = 32;
const EXCLUDED = new Set(['HTML', 'BODY', 'IFRAME', 'FRAME', 'CANVAS', 'VIDEO',
  'AUDIO', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'SCRIPT', 'STYLE', 'LINK',
  'META', 'OBJECT', 'EMBED', 'BUTTON', 'FORM']);
const HTML_NS = 'http://www.w3.org/1999/xhtml';
const PROPERTIES = Object.freeze({foreground: 'color', background: 'background-color', image: 'image-foreground'});
function validToken(value) { return typeof value === 'string' && /^[a-z0-9-]{1,64}$/.test(value); }
function fingerprint(element) {
  const id = element.getAttribute('id') || '';
  const role = element.getAttribute('role') || '';
  // Identity only, never interpolated in stylesheet or sent as arbitrary CSS.
  if (id.length > 128 || role.length > 64 || /[\x00-\x1f\x7f]/.test(id + role)) return null;
  return {id, role};
}
function allowed(element, doc) {
  return !!element && element.ownerDocument === doc && element.isConnected &&
    element.namespaceURI === HTML_NS && !EXCLUDED.has(element.tagName) &&
    element.getRootNode() === doc && !element.isContentEditable &&
    !element.closest?.('form, button, [contenteditable]') && validToken(element.localName);
}
export function captureTarget(element, doc) {
  if (!allowed(element, doc)) throw new Error('Unsupported target');
  const path = [];
  for (let cursor = element; cursor && cursor !== doc.documentElement; cursor = cursor.parentElement) {
    if (path.length >= MAX_DEPTH || !cursor.parentElement || cursor.namespaceURI !== HTML_NS)
      throw new Error('Unsupported path');
    const identity = fingerprint(cursor);
    if (!identity) throw new Error('Unsupported identity');
    const index = Array.prototype.indexOf.call(cursor.parentElement.children, cursor) + 1;
    if (index < 1 || index > 4096 || !validToken(cursor.localName)) throw new Error('Unsupported index');
    path.unshift({tag: cursor.localName, index, ...identity});
  }
  if (path.length < 2 || path[0].tag !== 'body') throw new Error('Unsupported root');
  return path;
}
function validatePath(path) {
  if (!Array.isArray(path) || path.length < 2 || path.length > MAX_DEPTH || path[0].tag !== 'body')
    throw new Error('Invalid path');
  for (const part of path) {
    if (!part || !validToken(part.tag) || !Number.isInteger(part.index) || part.index < 1 ||
        part.index > 4096 || typeof part.id !== 'string' || part.id.length > 128 ||
        typeof part.role !== 'string' || part.role.length > 64 || /[\x00-\x1f\x7f]/.test(part.id + part.role))
      throw new Error('Invalid path');
  }
}
export function resolveTarget(path, doc) {
  validatePath(path);
  let cursor = doc.documentElement;
  for (const part of path) {
    cursor = cursor?.children[part.index - 1];
    if (!cursor || cursor.localName !== part.tag || cursor.getAttribute('id') !== (part.id || null) ||
        cursor.getAttribute('role') !== (part.role || null)) return null;
  }
  return allowed(cursor, doc) ? cursor : null;
}
export function validateRule(rule, doc) {
  if (!rule || !Object.hasOwn(PROPERTIES, rule.property) ||
      !Number.isInteger(rule.rgb) || rule.rgb < 0 || rule.rgb > 0xffffff)
    throw new Error('Invalid color rule');
  const target = resolveTarget(rule.path, doc);
  if (!target || (rule.property === 'image' && target.localName !== 'img')) return null;
  return true;
}
// Typed site rules: prefer unique IDs, otherwise retain a bounded structural
// selector to the document root. No text, URLs or executable CSS is captured.
function stableStep(node) {
  const classes = (node.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).sort();
  if (classes.length > 12 || classes.some(x => x.length>64 || /[\x00-\x1f\x7f]/.test(x)))
    throw new Error('Unstable classes');
  return {tag:node.localName, role:node.getAttribute('role') || '', classes};
}
function sameStepValue(a, b) {
  return !!a && !!b && a.tag===b.tag && a.role===b.role &&
    Array.isArray(a.classes) && Array.isArray(b.classes) && a.classes.length===b.classes.length &&
    a.classes.every((value,index)=>value===b.classes[index]);
}
function sameStep(node, step) {
  try { return sameStepValue(stableStep(node),step); } catch { return false; }
}
function sameAncestors(a,b) {
  return a.length===b.length && a.every((part,index)=>
    !!b[index] && part.tag===b[index].tag && part.id===b[index].id);
}
function sameLocator(a,b) {
  if (!a || !b) return !a && !b;
  return a.anchor===b.anchor && Array.isArray(b.steps) && a.steps.length===b.steps.length &&
    a.steps.every((step,index)=>sameStepValue(step,b.steps[index]) &&
      step.ordinal===b.steps[index].ordinal && step.count===b.steps[index].count);
}
function uniqueId(doc, id) {
  const nodes = doc.querySelectorAll('[id]');
  if (nodes.length > 4096) throw new Error('Document limit');
  const matches = Array.from(nodes).filter(node => node.getAttribute('id') === id);
  if (matches.length !== 1) throw new Error('Ambiguous identity');
  return matches[0];
}
export function captureDescriptor(element, doc) {
  const path = captureTarget(element, doc);
  const own = path.at(-1);
  const result = {tag:own.tag, id:own.id, role:own.role,
    ancestors:path.slice(0,-1).map(part => ({tag:part.tag,id:part.id}))};
  if (own.id) {
    try { uniqueId(doc,own.id); return result; } catch { result.id=''; }
  }
  const steps=[];
  let cursor=element, anchor='';
  while (cursor && cursor !== doc.documentElement) {
    if (cursor!==element && cursor.getAttribute('id')) {
      try { uniqueId(doc,cursor.getAttribute('id')); anchor=cursor.getAttribute('id'); break; }
      catch { /* Duplicate ID: retain a structural path instead. */ }
    }
    const step=stableStep(cursor);
    const siblings=Array.from(cursor.parentElement?.children || []).filter(n => sameStep(n,step));
    if (!siblings.length || siblings.length>4096) throw new Error('Unsupported siblings');
    if (siblings.length>1) {
      step.ordinal=siblings.indexOf(cursor)+1;step.count=siblings.length;
    }
    steps.unshift(step);cursor=cursor.parentElement;
  }
  if (anchor.length>128 || /[\x00-\x1f\x7f]/.test(anchor) || !steps.length || steps.length>24)
    throw new Error('Unsupported path');
  result.locator={anchor,steps};
  return result;
}
export function matchRemembered(rule, doc) {
  if (!rule || !validToken(rule.tag) || typeof rule.id !== 'string' || (!rule.id && !rule.locator) ||
      rule.id.length > 128 || typeof rule.role !== 'string' || rule.role.length > 64 ||
      !Array.isArray(rule.ancestors) || rule.ancestors.length > 23 ||
      (rule.property!==0 && rule.property!==1 && rule.property!==2) || !Number.isInteger(rule.rgb) ||
      rule.rgb < 0 || rule.rgb > 0xffffff || (rule.property===2 && rule.tag!=='img')) return null;
  try {
    let target;
    if (rule.id) target=uniqueId(doc,rule.id);
    else {
      const locator=rule.locator;
      if (!locator || typeof locator.anchor!=='string' || locator.anchor.length>128 ||
          !Array.isArray(locator.steps) || !locator.steps.length || locator.steps.length>24) return null;
      target=locator.anchor ? uniqueId(doc,locator.anchor) : doc.documentElement;
      for (const step of locator.steps) {
        const children=Array.from(target.children).filter(node=>sameStep(node,step));
        if (step.ordinal!==undefined || step.count!==undefined) {
          if (!Number.isInteger(step.ordinal) || !Number.isInteger(step.count) ||
              step.ordinal<1 || step.count<2 || step.count>4096 || step.ordinal>step.count ||
              children.length!==step.count) return null;
          target=children[step.ordinal-1];
        } else { if(children.length!==1)return null;target=children[0]; }
      }
    }
    const descriptor=captureDescriptor(target,doc);
    if (descriptor.tag!==rule.tag || descriptor.role!==rule.role ||
        !sameAncestors(descriptor.ancestors,rule.ancestors) ||
        !sameLocator(descriptor.locator,rule.locator)) return null;
    return target;
  } catch { return null; }
}
// Keep absent rules pending for late-loaded DOM nodes. Bind each rule once per
// restore session; later node replacement does not acquire an existing binding.
export function createRememberedRestorer(doc,rules,apply) {
  if (!Array.isArray(rules) || rules.length>MAX_RULES) throw new Error('Rule limit');
  const pending=new Map(rules.map((rule,index)=>[index,rule]));
  let stopped=false;
  return {
    retry() {
      if(stopped)return 0;
      for(const [index,rule] of pending) {
        const node=matchRemembered(rule,doc);
        if(node && apply(node,index)!==false)pending.delete(index);
      }
      return pending.size;
    },
    stop() { stopped=true;pending.clear(); },
  };
}
export function watchRememberedRules(doc,rules,apply) {
  globalThis.__sandiumCancelRestore?.();
  const restorer=createRememberedRestorer(doc,rules,apply);
  let timer=null, observer=null, stopped=false;
  const stop=()=>{
    stopped=true;observer?.disconnect();if(timer!==null)clearTimeout(timer);
    timer=null;restorer.stop();
    if(globalThis.__sandiumCancelRestore===stop)delete globalThis.__sandiumCancelRestore;
  };
  globalThis.__sandiumCancelRestore=stop;
  if(!restorer.retry()){stop();return;}
  observer=new MutationObserver(()=>{
    if(stopped || timer!==null)return;
    timer=setTimeout(()=>{timer=null;if(!restorer.retry())stop();},200);
  });
  observer.observe(doc,{childList:true,subtree:true,attributes:true,
    attributeFilter:['id','class','role']});
}
/** Unenabled native contract: overrides MUST bind to the exact DOM node, not a
 * selector or a mutable DOM attribute. Browser validates current session/document.
 * A CSS-sheet-only consumer cannot satisfy this contract and must not enable it.
 * Native Save remains a separate browser-owned action. */
export function createCorrector(doc, bridge) {
  let closed = false;
  let sequence = 0;
  let preview = null;
  let saved = [];
  let rememberedAttempted = false;
  const selections = new Map();
  const check = () => { if (closed) throw new Error('Closed'); bridge.assertCurrent(); };
  const live = binding => allowed(binding.node, doc) &&
    resolveTarget(binding.rule.path, doc) === binding.node;
  const update = (method, bindings) => bridge[method](bindings.map(binding => ({
    node: binding.node, property: binding.rule.property, rgb: binding.rule.rgb,
  })));
  return Object.freeze({
    select(element) {
      check();
      if (selections.size >= 64) throw new Error('Selection limit');
      const path = captureTarget(element, doc);
      const handle = ++sequence;
      selections.set(handle, {node: element, path});
      return handle;
    },
    preview(handle, property, rgb) {
      check();
      const selection = selections.get(handle);
      if (!selection) throw new Error('Unknown selection');
      const rule = {path: selection.path, property, rgb};
      const binding = {node: selection.node, rule};
      // Validate typed values, then retained object identity. Equal ID is not identity.
      if (validateRule(rule, doc) === null || !live(binding)) throw new Error('Stale selection');
      update('replacePreviewNodes', [binding]);
      preview = binding;
    },
    cancelPreview() { check(); update('replacePreviewNodes', []); preview = null; },
    // Rebinding persisted rules needs user confirmation in each new document.
    // The browser may offer remembered values, but this API never auto-rebinds paths.
    applyConfirmed(handle, property, rgb) {
      check();
      const selection = selections.get(handle);
      if (!selection) throw new Error('Unknown selection');
      const rule = {path: selection.path, property, rgb};
      const binding = {node: selection.node, rule};
      if (validateRule(rule, doc) === null || !live(binding)) throw new Error('Stale selection');
      const next = [...saved.filter(item => live(item) &&
        !(item.node === binding.node && item.rule.property === property)), binding];
      if (next.length > MAX_RULES) throw new Error('Rule limit');
      // Native transaction commits saved overrides AND clears preview atomically.
      // On failure it must change neither; JS state remains unchanged on throw.
      update('commitSavedAndClearPreview', next);
      saved = next;
      preview = null;
    },
    // Browser calls once with its exact-origin profile rules after DOM readiness.
    // Never retry absent/ambiguous targets and never rematch after replacement.
    restoreRemembered(rules) {
      check();
      if (rememberedAttempted) throw new Error('Already attempted');
      if (!Array.isArray(rules) || rules.length > MAX_RULES) throw new Error('Rule limit');
      rememberedAttempted = true;
      const restored=[];
      for (const rule of rules) {
        const node=matchRemembered(rule,doc);
        if (node) restored.push({node,rule:{path:captureTarget(node,doc),property:rule.property===0?'foreground':rule.property===1?'background':'image',rgb:rule.rgb}});
      }
      update('restoreRememberedNodes',restored);
      saved=restored;
      return rules.length-restored.length;
    },
    revalidate() {
      check();
      if (preview && !live(preview)) {
        update('replacePreviewNodes', []); preview = null;
      }
      saved = saved.filter(item => live(item));
      update('replaceSavedNodes', saved);
      for (const [handle, selection] of selections) {
        if (!allowed(selection.node, doc) || resolveTarget(selection.path, doc) !== selection.node)
          selections.delete(handle);
      }
    },
    close() {
      if (closed) return;
      // Cleanup remains allowed after browser invalidates the session.
      bridge.disposeOverrides(); preview = null; saved = []; selections.clear(); closed = true;
    },
  });
}
