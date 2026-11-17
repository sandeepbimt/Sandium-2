import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('./sandium-user-filters.js', import.meta.url), 'utf8');
const { createUserFilterReconciler } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
function fake(content = '') {
    return { content, userFiltersPath: 'user-filters', selectedFilterLists: ['easylist'],
        reloads: 0, writes: 0,
        async loadUserFilters() { return { content: this.content }; },
        async saveUserFilters(s) { this.writes++; this.content = s; },
        async saveSelectedFilterLists(keys) { this.selectedFilterLists = keys; },
        async loadFilterLists() { this.reloads++; },
    };
}
const u = fake(), r = createUserFilterReconciler(u);
assert.deepEqual(await r.apply({ generation: 1, customFilters: ' ||ad.test^\n' }), { generation: 1, applied: true });
assert.equal(u.content, '||ad.test^'); assert.equal(u.writes, 1);
assert.deepEqual(u.selectedFilterLists, ['easylist', 'user-filters']);
await r.apply({ generation: 2, customFilters: '||ad.test^' });
assert.equal(u.reloads, 2); assert.equal(u.writes, 1);
await r.apply({ generation: 3, customFilters: '' });
assert.equal(u.content, ''); // Deletions are authoritative too.
let release;
u.loadFilterLists = () => new Promise(resolve => { release = resolve; });
const pending = r.apply({ generation: 4, customFilters: 'x##.ad' });
while ( !release ) { await new Promise(resolve => setImmediate(resolve)); }
r.invalidate(5); release();
assert.equal((await pending).applied, false); assert.equal(r.appliedGeneration, 0);
u.loadFilterLists = async () => { u.reloads++; };
assert.equal((await r.apply({ generation: 5, customFilters: 'y##.ad' })).applied, true);
assert.equal((await r.apply({ generation: 4, customFilters: 'old' })).applied, false);
u.saveUserFilters = async () => {}; // Simulate silent storage failure.
await assert.rejects(r.apply({ generation: 6, customFilters: 'lost' }), /readback/);
assert.equal(r.appliedGeneration, 0);
u.saveUserFilters = async s => { u.content = s; };
assert.equal((await r.apply({ generation: 7, customFilters: 'fixed' })).applied, true);
u.loadFilterLists = async () => { throw new Error('compile failed'); };
await assert.rejects(r.apply({ generation: 8, customFilters: 'fixed' }), /compile failed/);
assert.equal(r.appliedGeneration, 0);
r.dispose(); await assert.rejects(r.apply({ generation: 9, customFilters: '' }));
console.log('user-filter reconciliation: all assertions passed');
