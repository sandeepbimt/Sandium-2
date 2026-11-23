// SPDX-License-Identifier: LGPL-3.0-only
// RawS adapter derived from AdGuard Disable AMP v1.0.76 (AdguardTeam).
// This source is embedded verbatim in a dedicated, unprivileged isolated world.
// Original paste and candidate edits are retained in the corresponding source.
(mode => {
  'use strict';
  const here = new URL(document.URL);
  if (here.protocol !== 'https:' || here.username || here.password || here.port ||
      window.top !== window.self || document.contentType !== 'text/html') return;
  const host = here.hostname;
  const path = here.pathname;
  const excluded = new Set([
    'translated.turbopages.org', 'www.eurasiantimes.com', 'www.orfonline.org',
    'tehnichka.pro', 'www.teluguone.com', 'teluguone.com', 'www.onmanorama.com',
    'xn----7sbbeeptbfadjdvm5ab9bqj.xn--p1ai', 'amp.dev'
  ]);
  if (excluded.has(host) ||
      (host === 'yandex.ru' && path.startsWith('/turbo/s/terrnews.com/'))) return;

  // Mirror user-script include routes, with the nested numeric amp leaf used
  // by public Mint articles. A URL shape alone never triggers direct navigation.
  const isAmpShape = u => u.hostname.startsWith('amp.') ||
    u.hostname.endsWith('.cdn.ampproject.org') ||
    /(?:\/amp(?:\/|$)|\/amp-[^/]+\/|\/amp-\d+\.html?$|\.amp|[-_]amp|=amp|[?&]amp|\/amp_articleshow\/|\/ampNews\/|\/NewsViewAmp\/|\/articleViewAmp|\/lite\/|\/articleAmp\/|\/\?noamp=)/.test(u.pathname + u.search);
  const parse = value => {
    if (typeof value !== 'string' || value.length > 4096) return null;
    try {
      const u = new URL(value);
      if (u.protocol !== 'https:' || u.username || u.password || u.port ||
          !u.hostname.includes('.') || !/[a-z]/i.test(u.hostname) ||
          u.hostname.endsWith('.') || u.hostname.endsWith('.localhost') ||
          u.hostname.startsWith('[') || /^\d+(\.\d+)+$/.test(u.hostname)) return null;
      return u;
    } catch { return null; }
  };
  const samePublisher = (from, to) => {
    if (from.origin === to.origin) return true;
    if (!from.hostname.startsWith('amp.')) return false;
    const rest = from.hostname.slice(4);
    return to.hostname === rest || to.hostname === 'www.' + rest;
  };
  const normal = candidate => {
    const dst = parse(candidate);
    if (!dst) return null;
    if (dst.searchParams.has('amp')) dst.searchParams.delete('amp');
    return isAmpShape(dst) ? null : dst;
  };
  if (mode === 3 || mode === 4) {
    const explicit = mode === 3 && isAmpShape(here) &&
        document.querySelector('script[src^="https://cdn.ampproject.org/"]');
    const turbo = mode === 4 && ((host === 'yandex.ru' && path.startsWith('/turbo/')) ||
        host.endsWith('.turbopages.org'));
    if (explicit || turbo) {
      const switcher = document.querySelector('#amp-mobile-version-switcher > a');
      const links = document.querySelectorAll('head > link[rel="canonical"]');
      const el = switcher || (links.length === 1 ? links[0] : null);
      const dst = normal(el?.href);
      if (dst && dst.href !== here.href &&
          (samePublisher(here, dst) || (turbo && switcher &&
              samePublisher(parse('https://' + (host === 'yandex.ru' ?
                  path.split('/')[3] : host.slice(0, -'.turbopages.org'.length))) || here, dst)))) {
        // Do not add a Back-loop entry; this is ordinary renderer navigation.
        location.replace(dst.href);
        return;
      }
    }
    if (!isAmpShape(here) && !turbo) return;
  }

  const modified = new WeakSet();
  let modifiedCount = 0;
  const mapped = new WeakMap();
  const observations = [];
  const stripped = ['ping', 'data-ved', 'data-amp-cur', 'data-amp-title',
                    'data-amp', 'data-amp-vgi', 'jsaction'];
  const patch = (node, attr, value) => {
    if (node.getAttribute(attr) === value) return;
    if (!modified.has(node)) {
      if (modifiedCount >= 4096) return;
      modified.add(node);
      modifiedCount++;
    }
    if (value === null) node.removeAttribute(attr); else node.setAttribute(attr, value);
  };
  // Accept only actual client AMP-cache encodings (no fuzzy host substrings).
  const decodeCache = url => {
    if (!url) return null;
    if (url.hostname.endsWith('.cdn.ampproject.org') ||
        url.hostname === 'cdn.ampproject.org') {
      const m = /^\/(?:c|v|wp)\/s\/(.+)$/.exec(url.pathname);
      return m ? parse('https://' + m[1] + url.search + url.hash) : null;
    }
    if (url.hostname.startsWith('amp.')) {
      url.hostname = url.hostname.slice(4);
      return url;
    }
    return parse(url.href.replace('?amp&', '?'));
  };
  const bindLink = (a, dst) => {
    if (!dst || dst.href === a.href || a.hasAttribute('download') ||
        ![null, '', '_self'].includes(a.getAttribute('target')) ||
        (!modified.has(a) && modifiedCount >= 4096)) return;
    patch(a, 'href', dst.href);
    mapped.set(a, dst.href);
    const logo = a.querySelector('[aria-label="AMP logo"], [aria-label="Logo AMP"]');
    if (logo) patch(logo, 'hidden', '');
  };
  const news = a => {
    const metadata = a.getAttribute('jslog') || '';
    if (metadata.length > 8192) return;
    const m = /^[^:]*:([^;]+); track:click,vis/.exec(metadata);
    if (!m) return;
    let list;
    try { list = JSON.parse(atob(m[1].trim())); } catch { return; }
    if (!Array.isArray(list) || list.length > 128) return;
    const urls = list.map(parse).filter(Boolean);
    const alt = urls.find(isAmpShape);
    const dst = urls.find(u => !isAmpShape(u));
    // The page supplies both links, but may not use this adapter to silently
    // map a publisher AMP article to a totally unrelated host.
    const unwrapped = decodeCache(alt);
    if (alt && dst && (samePublisher(alt, dst) ||
        (unwrapped && samePublisher(unwrapped, dst)))) bindLink(a, dst);
  };
  const searchShape = 'a[data-ved]:has(> div[class] > span + svg)';
  const selector = mode === 1 ?
      'a[data-amp],a[data-amp-vgi],a[data-amp-cdn],' + searchShape :
                   mode === 2 ? 'a[jslog]' : 'a[data-amp-cdn]';
  const boundAnchors = root => {
    if (root.nodeType === 1 && root.matches(selector)) processAnchor(root);
    // Query only bounded batch roots, not the full body on every mutation.
    const all = root.querySelectorAll?.(selector);
    if (all) for (let i = 0; i < Math.min(all.length, 4096); i++) processAnchor(all[i]);
  };
  function processAnchor(a) {
    if (mode === 2) { news(a); return; }
    if (a.hasAttribute('data-amp-cdn')) {
      const old = parse(a.href);
      const dst = decodeCache(old);
      if (dst && !isAmpShape(dst)) bindLink(a, dst);
    }
    if (mode === 1) {
      const isSearchShape = a.matches(searchShape);
      if (isSearchShape || a.hasAttribute('data-amp') || a.hasAttribute('data-amp-vgi')) {
        const previous = a.previousElementSibling;
        for (const attr of stripped) patch(a, attr, null);
        if (isSearchShape && previous?.matches('a[data-ved]')) {
          for (const attr of stripped) patch(previous, attr, null);
        }
      }
    }
  }
  const click = event => {
    if (!event.isTrusted || event.defaultPrevented || event.button ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const a = event.target?.closest?.('a');
    const dst = a && mapped.get(a);
    if (!dst || a.href !== dst || a.hasAttribute('download') ||
        ![null, '', '_self'].includes(a.getAttribute('target'))) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    location.assign(dst);
  };
  const observer = new MutationObserver(records => {
    if (observations.length >= 1024) return;
    for (const record of records) {
      if (observations.length >= 1024) break;
      if (record.type === 'attributes') observations.push(record.target);
      for (const node of record.addedNodes) {
        if (observations.length >= 1024) break;
        if (node.nodeType === 1) observations.push(node);
      }
    }
    if (!queued && observations.length) queued = setTimeout(flush, 0);
  });
  let queued = 0;
  function flush() {
    queued = 0;
    for (const node of observations.splice(0, 64)) if (node.isConnected) boundAnchors(node);
    if (observations.length) queued = setTimeout(flush, 0);
  }
  boundAnchors(document);
  document.addEventListener('click', click, true);
  observer.observe(document, {childList: true, subtree: true, attributes: true,
      attributeFilter: ['jslog', 'href', 'data-amp', 'data-amp-vgi', 'data-amp-cdn']});
})(MODE)
