// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// Native effective selection is authoritative. No UUID/name guessing or proxies.
export function createListReconciler(ubo, storage) {
    let generation = 0;
    let disposed = false;
    const invalidate = value => { generation = Math.max(generation, value); };
    const apply = async snapshot => {
        const lists = snapshot?.lists;
        if (!lists?.ready || typeof lists.revision !== 'string' ||
            !lists.revision || !Array.isArray(lists.entries) ||
            lists.entries.length > 4096 || !Number.isSafeInteger(snapshot.generation)) {
            throw new Error('Native filter lists unavailable');
        }
        invalidate(snapshot.generation);
        const current = () => !disposed && generation === snapshot.generation;
        const urls = new Set();
        const ids = new Set();
        for (const entry of lists.entries) {
            if (typeof entry.id !== 'string' || ids.has(`${entry.kind}:${entry.id}`) ||
                !['regional','subscription'].includes(entry.kind) ||
                typeof entry.enabled !== 'boolean') throw new Error('Invalid native list entry');
            ids.add(`${entry.kind}:${entry.id}`);
            if (!entry.enabled) continue;
            const url = new URL(entry.url);
            if (!['https:','http:'].includes(url.protocol) || url.username ||
                url.password || url.hash || url.href.length > 8192) {
                throw new Error('Unsupported native list source');
            }
            urls.add(url.href);
        }
        const available = await ubo.getAvailableLists();
        if (!current()) return false;
        const selected = new Set([ubo.userFiltersPath]);
        const imported = [];
        for (const url of urls) {
            // Match only exact registered source URLs. Never infer from title/UUID.
            const stock = Object.entries(available).find(([key, asset]) =>
                !key.includes('://') && asset.content === 'filters' &&
                (Array.isArray(asset.contentURL) ? asset.contentURL : [asset.contentURL]).includes(url));
            const key = stock ? stock[0] : url;
            selected.add(key);
            if (!stock) imported.push(url);
        }
        imported.sort();
        // saveUserSettings() does not return its storage promise in pinned uBO.
        // Persist only these two documented settings, then verify readback.
        await storage.set({importedLists: imported, externalLists: imported.join('\n')});
        const saved = await storage.get(['importedLists','externalLists']);
        if (JSON.stringify(saved.importedLists) !== JSON.stringify(imported) ||
            saved.externalLists !== imported.join('\n')) throw new Error('List persistence failed');
        if (!current()) return false;
        ubo.userSettings.importedLists = imported;
        ubo.userSettings.externalLists = imported.join('\n');
        await ubo.saveSelectedFilterLists([...selected]);
        if (!current()) return false;
        ubo.availableFilterLists = await ubo.getAvailableLists();
        // Upstream loadFilterLists resolves even on a missing/error/empty list.
        // Inspect each real compiled source before acknowledging successful sync.
        const keys = [...selected].filter(key => key !== ubo.userFiltersPath);
        for (let i = 0; i < keys.length; i += 3) {
            await Promise.all(keys.slice(i, i + 3).map(async key => {
                const result = await ubo.getCompiledFilterList(key);
                if (result?.error || typeof result?.content !== 'string' || !result.content) {
                    throw new Error('Enabled native list unavailable or unsupported');
                }
            }));
            if (!current()) return false;
        }
        return current();
    };
    return {apply,invalidate,dispose(){disposed=true;}};
}
