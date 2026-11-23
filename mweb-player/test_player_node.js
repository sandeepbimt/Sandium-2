// Offline tests of the fixed page-world JavaScript. Does not test Android timing.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const script = fs.readFileSync(require('node:path').join(__dirname, 'player.js'), 'utf8');
const ad = {
  playabilityStatus: {status: 'OK'}, videoDetails: {videoId: 'fixture'},
  streamingData: {formats: [{url: 'https://media.invalid/content'}]},
  adPlacements: [{fixture: true}], adSlots: [{fixture: true}], playerAds: [{fixture: true}],
  captions: {fixture: true}
};
const clean = structuredClone(ad);
for (const key of ['adPlacements','adSlots','playerAds']) delete clean[key];
function context(origin = 'https://m.youtube.com', isTop = true) {
  const c = vm.createContext({location: {origin}, document: {contentType: 'text/html'}, Response,
    payload: JSON.stringify(ad), clean: JSON.stringify(clean)});
  vm.runInContext('globalThis.self = globalThis; globalThis.top = ' + (isTop ? 'self' : '{}'), c);
  const run = code => vm.runInContext(code, c);
  const hook = enabled => run(script + '(' + enabled + ', "https://m.youtube.com")');
  return {run, hook};
}
const view = (c, expr) => JSON.parse(c.run('JSON.stringify(' + expr + ')'));
(async () => {
  {
    const c = context();
    c.hook(true);
    c.run('ytInitialPlayerResponse = JSON.parse(payload, (k, v) => v)');
    assert.deepEqual(view(c,'ytInitialPlayerResponse'), clean);
    c.run('ytInitialPlayerResponse = Object.freeze(JSON.parse(payload, (k,v)=>v))');
    assert.deepEqual(view(c,'ytInitialPlayerResponse'), ad);
    assert.deepEqual(view(c,'JSON.parse(payload)'), clean);
    assert.deepEqual(view(c,'JSON.parse(clean)'), clean);
    c.hook(false);
    assert.equal(c.run('Object.getOwnPropertyDescriptor(self, "ytInitialPlayerResponse").writable'),true);
    c.run('ytInitialPlayerResponse = JSON.parse(payload)');
    assert.deepEqual(view(c,'ytInitialPlayerResponse'), ad);
  }
  {
    const c = context();
    c.run('ytInitialPlayerResponse = {"owned":true}');
    c.hook(true);
    assert.equal(c.run('Object.getOwnPropertyDescriptor(self,"ytInitialPlayerResponse").get'),undefined);
    assert.deepEqual(view(c,'ytInitialPlayerResponse'),{owned:true});
    c.hook(false);
    assert.deepEqual(view(c,'ytInitialPlayerResponse'),{owned:true});
  }
  for (const c of [context('https://m.youtube.com.example.test'), context(undefined, false)]) {
    c.hook(true);
    assert.deepEqual(view(c,'JSON.parse(payload)'),ad);
    assert.equal(c.run('Object.hasOwn(self,"ytInitialPlayerResponse")'),false);
  }
  {
    const c = context();
    c.hook(true);
    const out = await c.run(`(async () => {
      const r = new Response(payload, {headers: {'content-type':'application/json'}});
      Object.defineProperty(r,'url',{value:location.origin + '/youtubei/v1/player'});
      return JSON.stringify(await r.json());
    })()`);
    assert.deepEqual(JSON.parse(out),clean);
    c.hook(false);
    assert.equal(c.run('Object.hasOwn(self,"ytInitialPlayerResponse")'),false);
  }
  console.log('PASS early direct assignment, parsed and response data, clean content, existing descriptor, wrong scope, and disable');
})().catch(e => { console.error(e); process.exitCode=1; });
