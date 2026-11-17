import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
const code=await readFile(new URL('./seed.js',import.meta.url),'utf8');
const {prependOfflineSource}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const source={'https://source/a':{path:'assets/sandium-offline/a.txt'}};
const urls=['https://source/a','https://cdn/a'];
assert.deepEqual(prependOfflineSource(urls,'stock-a',false,source),['assets/sandium-offline/a.txt',...urls]);
assert.deepEqual(urls,['https://source/a','https://cdn/a']); // source registry untouched
assert.equal(prependOfflineSource(urls,'stock-a',true,source),urls); // readd after ready uses originals
assert.deepEqual(prependOfflineSource([],'https://source/a',false,source),['assets/sandium-offline/a.txt']);
assert.deepEqual(prependOfflineSource(['https://missing'],'unknown',false,source),['https://missing']);
// No cache API is accepted or called, so concurrent normal-cache fills cannot
// be overwritten by this integration. The upstream normal cache read runs first.
assert.doesNotMatch(code,/assets\.put|assets\.metadata|assetCacheWrite/);
console.log('Cold-only, exact source, immutable registry, no cache-write race PASS');
const upstream=execFileSync('python3',['-c',`import hashlib,zipfile
p='/tmp/ubo-prepared-1764.zip'
assert hashlib.sha256(open(p,'rb').read()).hexdigest()=='580afa3547a46422b3752759b5a90018ba7bfa4320770ea863950c78b29932d5'
print(zipfile.ZipFile(p).read('js/assets.js').decode())`],{encoding:'utf8'});
const body=upstream.slice(upstream.indexOf('assets.fetchFilterList = async function('),upstream.indexOf('\n/*******************************************************************************',upstream.indexOf('assets.fetchFilterList = async function(')));
let fetched=[];const real={async fetchText(url){fetched.push(url);return {url,content:url.endsWith('/root.txt')?'!#include child.txt\n||root.example^':'||child.example^'};}};
new Function('assets','vAPI','reIsExternalPath','sfp','resourceTimeFromParts','isDiffUpdatableAsset',body)(real,{getURL:p=>'chrome-extension://fixed/'+p,webextFlavor:{env:new Set()}},/^https?:/,{utils:{preparser:{splitter:s=>[0,s.length]}}},()=>0,()=>false);
const included=await real.fetchFilterList('assets/sandium-offline/root.txt');
assert.deepEqual(fetched,['assets/sandium-offline/root.txt','assets/sandium-offline/child.txt']);
assert.match(included.content,/child.example/);assert.match(included.content,/root.example/);
console.log('Pinned upstream local relative include resolution PASS');
