'use strict';
(async () => {
  const q = new URLSearchParams(location.search);
  const scriptletRoute = /^\/fixture-scriptlet\/([a-f0-9]{24})$/.exec(location.pathname);
  const run = scriptletRoute ? scriptletRoute[1] : q.get('run');
  const lane = scriptletRoute ? 'scriptlet' : 'passive';
  if (!/^[a-f0-9]{24}$/.test(run ?? '') || !['passive','scriptlet'].includes(lane) ||
      location.hostname !== 'raws-news.test') throw new Error('Use the two-host lab fixture');
  if (lane === 'scriptlet' && (location.protocol !== 'https:' || location.port || location.search ||
      location.hash || !isSecureContext))
    throw new Error('Reviewed scriptlets need trusted HTTPS on port 443');
  const ads = new URL(location.origin);
  ads.hostname = 'raws-ads.test';
  const cases = {};
  const observe = async path => {
    const img = new Image();
    return await new Promise(resolve => {
      const end = state => { clearTimeout(timer); img.onload = img.onerror = null; resolve(state); };
      const timer = setTimeout(() => end('timeout'), 4500);
      img.onload = () => end(img.naturalWidth === 1 ? 'loaded' : 'wrong-image');
      img.onerror = () => end('error');
      img.src = new URL('/bank-image/' + path + '.png?run=' + run, ads).href;
    });
  };
  const node = id => document.getElementById(id);
  function visible(id) {
    const elt = node(id);
    return elt.checkVisibility({visibilityProperty:true, opacityProperty:true}) &&
        elt.getBoundingClientRect().height > 0 ? 'visible' : 'hidden';
  }
  function setupControls() {
    let clicks = 0, edits = 0;
    node('bank-button').addEventListener('click', () => clicks++);
    node('bank-input').addEventListener('input', () => edits++);
    node('bank-button').click();
    node('bank-input').value = 'ordinary local search';
    node('bank-input').dispatchEvent(new Event('input', {bubbles:true}));
    cases.interaction = clicks === 1 && edits === 1 && visible('bank-form') === 'visible' &&
        visible('bank-link') === 'visible' && visible('bank-input') === 'visible' &&
        visible('bank-button') === 'visible' && !node('bank-input').disabled &&
        !node('bank-button').disabled ? 'intact' : 'broken';
  }
  if (lane === 'passive') {
    const [a,b] = document.querySelectorAll('.bank-static,.bank-static-allowed');
    a.id = 'bank-static'; b.id = 'bank-static-allowed';
    document.querySelector('.bank-editorial').id = 'bank-editorial';
    const pending = Promise.all(['allowed-direct','blocked-hop','allowed-hop','excepted-hop']
        .map(path => observe(path).then(value => { cases[path] = value; })));
    await new Promise(resolve => setTimeout(resolve, 500));
    const late = document.createElement('section');
    late.innerHTML = '<p id="bank-late" class="bank-late">Synthetic late sponsor</p>' +
        '<p id="bank-late-allowed" class="bank-late-allowed">Synthetic late exception</p>';
    document.querySelector('main').append(late);
    await Promise.all([pending, new Promise(resolve => setTimeout(resolve, 2500))]);
    for (const id of ['bank-static','bank-static-allowed','bank-editorial','bank-late','bank-late-allowed'])
      cases[id] = visible(id);
  } else {
    await new Promise(resolve => setTimeout(resolve, 3000));
    cases.reviewed = node('bank-positive').hasAttribute('data-ppcnt_ads') ? 'retained' : 'removed';
    cases.excepted = node('bank-negative').hasAttribute('data-popunder-url') ? 'retained' : 'removed';
    cases.handler = ['bank-positive','bank-negative'].every(id => node(id).getAttribute('onclick') === '')
        ? 'intact' : 'changed';
  }
  setupControls();
  node('bank-report').textContent = JSON.stringify({
    suite:'raws-neutral-bank/1', lane, run, origin:location.origin, outcomes:cases
  }, null, 2);
})().catch(error => document.getElementById('bank-report').textContent = 'INVALID: '+error.message);
