// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// Native-authoritative policy. Missing/unknown capability never turns on uBO.
export function allowsNetwork(details) {
    const p = details?.sandiumShields;
    return p?.protocol === 1 && p.engineOwned === true && p.runtimeAvailable === true &&
        p.shieldsEnabled === true && p.adControl !== 'allow' &&
        (p.adControl === 'block' || p.adControl === 'block_third_party');
}
export async function allowsTab(tabId, frameId, expectedUrl, cosmetic = false,
    api = globalThis.chrome?.sandiumUbo, documentId = '') {
    if ( !api?.getTabPolicy || !Number.isInteger(tabId) || tabId < 0 ||
         !Number.isInteger(frameId) || typeof expectedUrl !== 'string' ) return false;
    const policy = await new Promise(resolve => {
        const args = [tabId, frameId, expectedUrl];
        if ( documentId ) args.push(documentId);
        api.getTabPolicy(...args, result => {
            if ( globalThis.chrome?.runtime?.lastError ) { resolve(null); return; }
            resolve(result);
        });
    });
    if ( !cosmetic ) return allowsNetwork({ sandiumShields: policy });
    // Native IsCosmeticFilteringEnabled is independent of BRAVE_ADS.
    // Do not let disabling network ads silently disable user cosmetic rules.
    return policy?.protocol === 1 && policy.engineOwned === true && policy.runtimeAvailable === true &&
        policy.shieldsEnabled === true &&
        (policy.cosmeticControl === 'block' ||
         policy.cosmeticControl === 'block_third_party' ||
         policy.cosmeticControl === 'default');
}

// Popup tab removal is a separate uBO path, not a webRequest response. Both
// opener and target must still be real, authorized documents. Caller rechecks
// its candidate identity and tab URLs after this asynchronous permission check.
export async function allowsPopup(opener, target, api = globalThis.chrome?.sandiumUbo) {
    if (!opener || !target) return false;
    const allowed = await Promise.all([
        allowsTab(opener.tabId, opener.frameId, opener.frameURL, false, api),
        allowsPopupTarget(target.tabId, target.url, api),
    ]);
    return allowed.every(Boolean);
}

async function allowsPopupTarget(tabId, expectedURL, api) {
    if (!api?.getPopupTargetPolicy || !Number.isInteger(tabId) || tabId < 0 ||
        typeof expectedURL !== 'string' || !/^https?:\/\//i.test(expectedURL)) return false;
    const policy = await new Promise(resolve => {
        api.getPopupTargetPolicy(tabId, expectedURL, result => {
            if (globalThis.chrome?.runtime?.lastError) { resolve(null); return; }
            resolve(result);
        });
    });
    return allowsNetwork({sandiumShields:policy});
}
