// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// uBO 1.76.4 storage.js API. Native customFilters is authoritative in this
// experiment. This helper never reads URLs, changes Shields, or enables cutover.
export function createUserFilterReconciler(ubo) {
    for ( const name of ['loadUserFilters', 'saveUserFilters',
        'saveSelectedFilterLists', 'loadFilterLists'] ) {
        if ( typeof ubo?.[name] !== 'function' ) {
            throw new Error(`Missing uBO filter API: ${name}`);
        }
    }
    let latest = 0;
    let applied = 0;
    let disposed = false;
    let chain = Promise.resolve();
    const validGeneration = n => Number.isSafeInteger(n) && n > 0;
    const current = generation => !disposed && generation === latest;
    const invalidate = generation => {
        if ( !validGeneration(generation) ) {
            throw new Error('Invalid filter generation');
        }
        latest = Math.max(latest, generation);
        // Even while a reload is pending, an earlier ACK is no longer valid.
        if ( applied < latest ) { applied = 0; }
    };
    const apply = snapshot => {
        if ( disposed || !validGeneration(snapshot?.generation) ||
             typeof snapshot.customFilters !== 'string' ) {
            return Promise.reject(new Error('Invalid filter snapshot'));
        }
        // Capture values, not the externally mutable snapshot object.
        const generation = snapshot.generation;
        const content = snapshot.customFilters.trim();
        invalidate(generation);
        const task = async () => {
            if ( !current(generation) ) { return { generation, applied: false }; }
            applied = 0;
            const existing = await ubo.loadUserFilters();
            if ( !existing || typeof existing.content !== 'string' || existing.error ) {
                throw new Error('Unable to read uBO user filters');
            }
            if ( !current(generation) ) { return { generation, applied: false }; }
            if ( existing.content.trim() !== content ) {
                await ubo.saveUserFilters(content);
                const saved = await ubo.loadUserFilters();
                if ( !saved || saved.error || saved.content?.trim() !== content ) {
                    throw new Error('uBO user filter readback failed');
                }
            }
            if ( !current(generation) ) { return { generation, applied: false }; }
            if ( typeof ubo.userFiltersPath !== 'string' ||
                 !Array.isArray(ubo.selectedFilterLists) ) {
                throw new Error('Missing uBO filter selection');
            }
            if ( !ubo.selectedFilterLists.includes(ubo.userFiltersPath) ) {
                // Unlike applyFilterListSelection, this API returns the storage
                // promise. Keep all existing lists, and await durable selection.
                await ubo.saveSelectedFilterLists([
                    ...ubo.selectedFilterLists, ubo.userFiltersPath,
                ]);
            }
            if ( !current(generation) ) { return { generation, applied: false }; }
            // Always reload, including first startup with unchanged disk text:
            // an existing selfie/compiled engine may predate the native rules.
            // Upstream invalidates selfies + broadcasts filteringBehaviorChanged.
            await ubo.loadFilterLists();
            if ( !current(generation) ) { return { generation, applied: false }; }
            applied = generation;
            return { generation, applied: true };
        };
        const result = chain.then(task);
        // A rejected write/reload must not poison all later generations.
        chain = result.catch(() => {});
        return result;
    };
    return {
        invalidate, apply,
        get appliedGeneration() { return applied; },
        dispose() { disposed = true; applied = 0; },
    };
}
