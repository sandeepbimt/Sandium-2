// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// Cold-start source fallback only. Never writes caches or changes selection.
export function prependOfflineSource(contentURLs, assetKey, readyToFilter, sources) {
    if (readyToFilter === true) return contentURLs;
    const original = contentURLs.find(url => sources[url]) ||
        (sources[assetKey] ? assetKey : undefined);
    if (original === undefined) return contentURLs;
    return [sources[original].path, ...contentURLs];
}
