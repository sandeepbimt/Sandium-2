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
    if ( !allowsNetwork({ sandiumShields: policy }) ) return false;
    return !cosmetic || policy.cosmeticControl === 'block' ||
        policy.cosmeticControl === 'block_third_party';
}
