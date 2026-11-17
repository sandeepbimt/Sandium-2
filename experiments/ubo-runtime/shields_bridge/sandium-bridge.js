// Copyright 2026 Sandium. SPDX-License-Identifier: GPL-3.0-or-later
// Prepared before readyToFilter; listener report occurs only after webRequest.start().
// This is observation wiring, not filter cutover or parity proof.
import { createListReconciler } from './sandium-lists.js';
import { createUserFilterReconciler } from './sandium-user-filters.js';
export async function startSandiumBridge(api = globalThis.chrome?.sandiumUbo, ubo, storage = globalThis.vAPI?.storage, { signal, readinessTimeoutMs = 10000 } = {}) {
    if ( !api ) { return { available: false, cutover: false }; }
    const call = (name, ...args) => new Promise((resolve, reject) => {
        api[name](...args, result => {
            const error = globalThis.chrome?.runtime?.lastError;
            if ( error ) { reject(new Error(error.message)); return; }
            resolve(result);
        });
    });
    const reconciler = ubo ? createUserFilterReconciler(ubo) : null;
    const listReconciler = ubo ? createListReconciler(ubo, storage) : null;
    let latestGeneration = 0;
    let snapshot = null;
    let disposed = false;
    let initialized = false;
    let listenersStarted = false;
    let resync = Promise.resolve();
    let wakePending = null;
    const deadline = Date.now() + Math.max(0, Math.min(readinessTimeoutMs, 10000));
    const waitForNativeLists = generation => new Promise((resolve, reject) => {
        if (disposed || signal?.aborted) { reject(new Error('Bridge disposed')); return; }
        if (Date.now() >= deadline) { reject(new Error('Native filter readiness timed out')); return; }
        if (latestGeneration > generation) { resolve(); return; }
        const finish = error => {
            clearTimeout(timer);
            signal?.removeEventListener('abort', abort);
            wakePending = null;
            error ? reject(error) : resolve();
        };
        const abort = () => finish(new Error('Bridge disposed'));
        const timer = setTimeout(() => finish(new Error('Native filter readiness timed out')),
            Math.max(0, deadline - Date.now()));
        wakePending = () => finish();
        signal?.addEventListener('abort', abort, {once:true});
    });
    const invalidated = generation => {
        if ( disposed ) return;
        latestGeneration = Math.max(latestGeneration, generation);
        snapshot = null;
        wakePending?.();
        reconciler?.invalidate(generation);
        listReconciler?.invalidate(generation);
        if ( initialized && reconciler ) {
            resync = resync.catch(() => {}).then(synchronize).catch(() => {
                // Keep native ACK invalid; coordinator decides bounded outcome.
                console.error('SANDIUM_UBO_SETTINGS synchronization failed');
            });
        }
    };
    if ( !api.onSettingsChanged || !api.getSettingsSnapshot ) {
        throw new Error('Settings mirror capability missing');
    }
    // Subscribe before the first snapshot. UI-thread native snapshots are atomic;
    // a change received while its reply is in flight invalidates that reply.
    api.onSettingsChanged.addListener(invalidated);
    const refreshSnapshot = async () => {
        for ( let attempt = 0; attempt < 3; attempt++ ) {
            const next = await call('getSettingsSnapshot');
            if ( disposed ) { throw new Error('Bridge disposed'); }
            if ( next?.protocol !== 1 || typeof next.engineCutover !== 'boolean' ||
                 !Number.isSafeInteger(next.generation) || next.generation < 1 ||
                 !['shields', 'ads', 'cosmetic'].every(k => Array.isArray(next[k])) ) {
                throw new Error('Invalid settings snapshot');
            }
            if ( next.generation < latestGeneration ) { continue; }
            latestGeneration = next.generation;
            snapshot = next;
            return next;
        }
        throw new Error('Settings changed during synchronization');
    };
    const reportListeners = async () => {
        const acknowledged = await call('reportReady', 1, 'listeners-ready');
        if ( acknowledged !== true ) { throw new Error('Runtime report rejected'); }
    };
    const synchronize = async () => {
        for ( let attempt = 0; attempt < 3; attempt++ ) {
            let current = await refreshSnapshot();
            if ( !reconciler ) return;
            // Native migration is asynchronous. Keep the listener alive until it
            // publishes readiness; do not mistake a pending seed for bad rules.
            while (current.lists?.ready === false && !initialized) {
                await waitForNativeLists(current.generation);
                current = await refreshSnapshot();
            }
            if (!await listReconciler.apply(current)) continue;
            const result = await reconciler.apply(current);
            if ( !result.applied || snapshot?.generation !== result.generation ) continue;
            const ack = await call('acknowledgeSettings', result.generation,
                current.customFiltersSha256, current.lists.revision);
            if ( ack !== true ) { throw new Error('Native filter ACK rejected'); }
            if ( listenersStarted ) await reportListeners();
            return;
        }
        throw new Error('Native filter generation changed');
    };
    try {
        await synchronize();
        initialized = true;
    } catch (error) {
        disposed = true;
        reconciler?.dispose();
        listReconciler?.dispose();
        api.onSettingsChanged.removeListener(invalidated);
        throw error;
    }
    return {
        available: true,
        reportListenersReady: async () => {
            listenersStarted = true;
            await reportListeners();
        },
        cutover: false,
        // Read-only observation. No conversion to uBO switches until Chromium
        // pattern semantics, native generations and custom-rule parity verified.
        get snapshot() { return snapshot; },
        refreshSnapshot,
        dispose() {
            disposed = true;
            reconciler?.dispose();
        listReconciler?.dispose();
            snapshot = null;
            api.onSettingsChanged.removeListener(invalidated);
        },
        getSettings: async url => {
            const snapshot = await call('getSettings', url);
            if ( snapshot?.protocol !== 1 || typeof snapshot.engineCutover !== 'boolean' ) {
                throw new Error('Unrecognized Shields bridge response');
            }
            return snapshot;
        },
    };
}
