// SPDX-License-Identifier: MPL-2.0
// Fixed, unprivileged page-world code. No list text, URLs from IPC or user data
// are interpolated. The native caller supplies one compiled origin and the site-policy boolean.
((enabled, expectedOrigin) => {
  'use strict';
  if (self !== top || location.origin !== expectedOrigin ||
      document.contentType !== 'text/html') return;
  const key = Symbol.for('raws.mweb.player-json.v1');
  const existing = Object.getOwnPropertyDescriptor(self, key);
  if (existing) {
    if (!enabled && typeof existing.value === 'function') existing.value();
    return;
  }
  if (!enabled) return;

  const parse = Object.getOwnPropertyDescriptor(JSON, 'parse');
  const body = Object.getOwnPropertyDescriptor(Response.prototype, 'json');
  if (!parse?.configurable || !body?.configurable ||
      typeof parse.value !== 'function' || typeof body.value !== 'function') return;
  const own = Object.hasOwn;
  const array = Array.isArray;
  let active = true;
  // Both callers supply freshly decoded JSON without a reviver. Never recurse
  // through unrelated objects, inspect a media URL, or change an access error.
  function scrub(p) {
    if (!p || typeof p !== 'object' || !own(p, 'playabilityStatus') ||
        p.playabilityStatus?.status !== 'OK' || !own(p, 'videoDetails') ||
        typeof p.videoDetails?.videoId !== 'string' || !p.videoDetails.videoId ||
        !own(p, 'streamingData')) return;
    const streams = p.streamingData;
    if (!(array(streams?.formats) && streams.formats.length) &&
        !(array(streams?.adaptiveFormats) && streams.adaptiveFormats.length) &&
        !(typeof streams?.serverAbrStreamingUrl === 'string' && streams.serverAbrStreamingUrl)) return;
    for (const k of ['adPlacements', 'playerAds', 'adSlots']) {
      if (own(p, k) && array(p[k])) Reflect.deleteProperty(p, k);
    }
  }
  function after(obj) {
    if (active && obj && typeof obj === 'object') {
      scrub(obj);
      if (own(obj, 'playerResponse')) scrub(obj.playerResponse);
    }
    return obj;
  }
  const parsed = new Proxy(parse.value, { apply(fn, receiver, args) {
    const obj = Reflect.apply(fn, receiver, args); // native exceptions/reviver semantics
    return active && typeof args[1] !== 'function' ? after(obj) : obj;
  }});
  const decoded = new Proxy(body.value, { apply(fn, receiver, args) {
    const result = Reflect.apply(fn, receiver, args);
    // Do not fetch, clone or read a second time. Non-target calls even retain
    // their original promise. Non-HTTP synthetic responses have an empty URL.
    if (!active || !(receiver instanceof Response) || !receiver.ok ||
        receiver.redirected || !/^application\/json(?:\s*;|$)/i.test(receiver.headers.get('content-type') || '') ||
        receiver.url.split(/[?#]/, 1)[0] !== expectedOrigin + '/youtubei/v1/player') return result;
    return result.then(after);
  }});
  // Only watch a not-yet-owned bootstrap global. Leave existing page
  // descriptors and lexical variables alone. Disabling stops future pruning;
  // it cannot restore fields already consumed by the current player.
  const bootstrap = 'ytInitialPlayerResponse';
  let bootstrapValue, bootstrapWritten = false;
  const getBootstrap = () => bootstrapValue;
  const setBootstrap = value => {
    bootstrapWritten = true;
    if (active) {
      try { scrub(value); } catch { /* Preserve the page's assignment. */ }
    }
    bootstrapValue = value;
  };
  const stop = () => {
    active = false; // also covers saved wrappers and pending body reads
    if (JSON.parse === parsed) Object.defineProperty(JSON, 'parse', parse);
    if (Response.prototype.json === decoded) Object.defineProperty(Response.prototype, 'json', body);
    const currentBootstrap = Object.getOwnPropertyDescriptor(self, bootstrap);
    if (currentBootstrap?.configurable &&
        currentBootstrap.get === getBootstrap && currentBootstrap.set === setBootstrap) {
      if (bootstrapWritten) {
        Object.defineProperty(self, bootstrap, {
          value: bootstrapValue, configurable: true, enumerable: true, writable: true
        });
      } else {
        delete self[bootstrap];
      }
    }
    if (Object.getOwnPropertyDescriptor(self, key)?.value === stop) delete self[key];
  };
  try {
    Object.defineProperty(self, key, {value: stop, configurable: true});
    Object.defineProperty(JSON, 'parse', {...parse, value: parsed});
    Object.defineProperty(Response.prototype, 'json', {...body, value: decoded});
    if (!Object.getOwnPropertyDescriptor(self, bootstrap)) {
      Object.defineProperty(self, bootstrap, {
        get: getBootstrap, set: setBootstrap, configurable: true, enumerable: true
      });
    }
  } catch { stop(); }
})
