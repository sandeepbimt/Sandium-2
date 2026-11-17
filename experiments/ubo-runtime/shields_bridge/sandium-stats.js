// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// Local-only actual uBO network-block events. No synthetic counter resources.
export function createBlockReporter(api = globalThis.chrome?.sandiumUbo,
    schedule = fn => setTimeout(fn, 100)) {
    const pending = new Map();
    let scheduled = false;
    let pendingCount = 0;
    let pendingBytes = 0;
    const flush = () => {
        scheduled = false;
        const groups = Array.from(pending.values());
        pending.clear();
        pendingCount = 0;
        pendingBytes = 0;
        if ( !api?.reportBlocked ) return;
        for ( const group of groups ) {
            const urls = Array.from(group.urls);
            for ( let i = 0; i < urls.length; i += 32 ) {
                api.reportBlocked(group.tabId, group.pageDocumentId, urls.slice(i, i + 32), () => {
                    // Read lastError to suppress extension warnings. Native
                    // rejects stale page epochs; never replay onto a new page.
                    void globalThis.chrome?.runtime?.lastError;
                });
            }
        }
    };
    const report = details => {
        const p = details?.sandiumShields;
        if ( p?.protocol !== 1 || p.engineOwned !== true || p.runtimeAvailable !== true ||
             !Number.isInteger(details.tabId) || details.tabId < 0 ||
             typeof p.pageDocumentId !== 'string' || p.pageDocumentId.length < 1 || p.pageDocumentId.length > 128 ||
             typeof details.url !== 'string' || details.url.length > 8192 ||
             !/^https?:\/\//i.test(details.url) ) return;
        const key = `${details.tabId}:${p.pageDocumentId}`;
        if ( !pending.has(key) ) {
            // Bound renderer-side accumulation; missing telemetry is preferable
            // to invented counts or unbounded memory on a hostile site.
            if ( pending.size >= 64 ) return;
            pending.set(key, { tabId: details.tabId, pageDocumentId: p.pageDocumentId, urls: new Set() });
        }
        const group = pending.get(key);
        if ( !group.urls.has(details.url) && group.urls.size < 256 &&
             pendingCount < 512 && pendingBytes + details.url.length <= 128 * 1024 ) {
            group.urls.add(details.url);
            pendingCount++;
            pendingBytes += details.url.length;
        }
        if ( !scheduled ) { scheduled = true; schedule(flush); }
    };
    return { report, flush };
}
export const blockReporter = createBlockReporter();
