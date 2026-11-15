// Copyright 2026 Sandium Authors. BSD-style license.
// Isolated-world renderer core. Not enabled until the native session/sheet bridge lands.
// No persistence or page-owned confirmation controls belong in this module.
const MAX_DEPTH = 24;
const MAX_RULES = 32;
const EXCLUDED = new Set(['HTML', 'BODY', 'IFRAME', 'FRAME', 'CANVAS', 'VIDEO',
  'AUDIO', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'SCRIPT', 'STYLE', 'LINK',
  'META', 'OBJECT', 'EMBED', 'BUTTON', 'FORM']);
const HTML_NS = 'http://www.w3.org/1999/xhtml';
const PROPERTIES = Object.freeze({foreground: 'color', background: 'background-color'});
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
  if (!resolveTarget(rule.path, doc)) return null;
  return true;
}
// Only stable, unique-ID descriptors may be remembered. No text, source URLs,
// CSS selectors or image bytes are captured. An exact match is still heuristic.
export function captureDescriptor(element, doc) {
  const path = captureTarget(element, doc);
  const own = path.at(-1);
  if (!own.id) throw new Error('Visit-only target');
  const tagged = doc.querySelectorAll('[id]'); // Constant selector, never site input.
  if (tagged.length > 4096) throw new Error('Document limit');
  if (Array.from(tagged).filter(node => node.getAttribute('id') === own.id).length !== 1)
    throw new Error('Ambiguous identity');
  return {tag: own.tag, id: own.id, role: own.role,
    ancestors: path.slice(0,-1).map(part => ({tag:part.tag,id:part.id}))};
}
export function matchRemembered(rule, doc) {
  if (!rule || !validToken(rule.tag) || typeof rule.id !== 'string' || !rule.id ||
      rule.id.length > 128 || typeof rule.role !== 'string' || rule.role.length > 64 ||
      !Array.isArray(rule.ancestors) || rule.ancestors.length > 23 ||
      (rule.property!==0 && rule.property!==1) || !Number.isInteger(rule.rgb) ||
      rule.rgb < 0 || rule.rgb > 0xffffff) return null;
  const tagged = doc.querySelectorAll('[id]');
  if (tagged.length > 4096) return null;
  const matches=Array.from(tagged).filter(node => node.getAttribute('id')===rule.id);
  if (matches.length!==1) return null;
  try {
    const descriptor=captureDescriptor(matches[0],doc);
    if (descriptor.tag!==rule.tag || descriptor.role!==rule.role ||
        JSON.stringify(descriptor.ancestors)!==JSON.stringify(rule.ancestors)) return null;
    return matches[0];
  } catch { return null; }
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
        if (node) restored.push({node,rule:{path:captureTarget(node,doc),property:rule.property===0?'foreground':'background',rgb:rule.rgb}});
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
