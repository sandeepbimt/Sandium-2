// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// Native-authoritative policy. Missing/unknown capability never turns on uBO.
export function allowsNetwork(details) {
    const p = details?.sandiumShields;
    return p?.protocol === 1 && p.engineOwned === true &&
        p.shieldsEnabled === true && p.adControl !== 'allow' &&
        (p.adControl === 'block' || p.adControl === 'block_third_party');
}
export async function allowsTab(tabId, frameId, expectedUrl, cosmetic = false,
    api = globalThis.chrome?.sandiumUbo) {
    if ( !api?.getTabPolicy || !Number.isInteger(tabId) || tabId < 0 ||
         !Number.isInteger(frameId) || typeof expectedUrl !== 'string' ) return false;
    const policy = await new Promise(resolve => {
        api.getTabPolicy(tabId, frameId, expectedUrl, result => {
            if ( globalThis.chrome?.runtime?.lastError ) { resolve(null); return; }
            resolve(result);
        });
    });
    if ( !cosmetic ) return allowsNetwork({ sandiumShields: policy });
    // Native IsCosmeticFilteringEnabled is independent of BRAVE_ADS.
    // Do not let disabling network ads silently disable user cosmetic rules.
    return policy?.protocol === 1 && policy.engineOwned === true &&
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
        allowsTab(target.tabId, 0, target.url, false, api),
    ]);
    return allowed.every(Boolean);
}
