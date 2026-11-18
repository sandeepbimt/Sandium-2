// Sandium native-page handoff resource ownership. Not a presentation fence.
package org.chromium.chrome.browser.tab;

import java.util.IdentityHashMap;

/**
 * UI-thread-confined ownership of one temporarily retained browser-owned native page.
 *
 * <p>This class neither retains renderer content nor changes tab identity, input, views, or URLs.
 * The integration must disable input/accessibility on the leased native view before acquisition,
 * and must call release only after its separately validated presentation decision or revocation.
 * A release callback must clean up only the supplied resource, never a mutable "current page".
 */
public final class NativePageHandoffLeaseOwner<T> {
    public enum EndReason {
        PRESENTED, SUPERSEDED, CANCELLED, TAB_HIDDEN, DESTROYED, FRAME_SINK_LOST,
        SECURITY_DESTINATION, TARGET_CHANGED, VIEWPORT_CHANGED, DEADLINE
    }

    @FunctionalInterface
    public interface Releaser<T> {
        void release(T resource, EndReason reason);
    }

    /** Opaque per-acquisition authority. Equality is object identity, not an integer generation. */
    public static final class Lease<T> {
        private T mResource;
        private Releaser<T> mReleaser;

        private Lease(T resource, Releaser<T> releaser) {
            mResource = resource;
            mReleaser = releaser;
        }
    }

    private final Thread mOwnerThread = Thread.currentThread();
    private Lease<T> mCurrent;
    private Object mRevision = new Object();
    private boolean mDestroyed;
    private final IdentityHashMap<T, Boolean> mAcquiring = new IdentityHashMap<>();
    private final IdentityHashMap<T, Boolean> mReleasing = new IdentityHashMap<>();

    private void dispose(Lease<T> lease, EndReason reason) {
        T resource = lease.mResource;
        Releaser<T> releaser = lease.mReleaser;
        // Queued stale callbacks may retain tokens after shutdown. A spent token must not
        // retain an entire native page/view tree or its cleanup closure indefinitely.
        lease.mResource = null;
        lease.mReleaser = null;
        mReleasing.put(resource, Boolean.TRUE);
        try {
            releaser.release(resource, reason);
        } finally {
            mReleasing.remove(resource);
        }
    }

    private void checkThread() {
        if (Thread.currentThread() != mOwnerThread) {
            throw new IllegalStateException("Native page lease used outside its owner thread");
        }
    }

    /**
     * Transfers ownership only if a non-null lease is returned. If cleanup reenters and installs
     * another lease, this acquisition is rejected and the caller still owns its supplied resource.
     * Neither a rejected resource nor a newer reentrant lease is destroyed by this operation.
     */
    public Lease<T> acquire(T resource, Releaser<T> releaser) {
        checkThread();
        if (resource == null || releaser == null) throw new NullPointerException();
        // The same resource must never be destroyed and immediately re-leased by this call.
        if ((mCurrent != null && mCurrent.mResource == resource) || mReleasing.containsKey(resource)
                || mAcquiring.containsKey(resource)) {
            throw new IllegalArgumentException("Resource already owned or being transferred");
        }
        if (mDestroyed) return null;
        // Reserve the proposed resource while cleanup can call arbitrary/reentrant code.
        // Otherwise an inner acquire could own this same object while outer returns null.
        mAcquiring.put(resource, Boolean.TRUE);
        try {
            Lease<T> previous = mCurrent;
            mCurrent = null;
            Object revision = new Object();
            mRevision = revision;
            if (previous != null) dispose(previous, EndReason.SUPERSEDED);
            if (mDestroyed || mRevision != revision) return null;
            Lease<T> lease = new Lease<>(resource, releaser);
            mCurrent = lease;
            mRevision = new Object();
            return lease;
        } finally {
            mAcquiring.remove(resource);
        }
    }

    public boolean isCurrent(Lease<T> lease) {
        checkThread();
        return lease != null && !mDestroyed && mCurrent == lease;
    }

    /** Stale callbacks cannot release a replacement, even when it uses a reused native object. */
    public boolean release(Lease<T> lease, EndReason reason) {
        checkThread();
        if (reason == null) throw new NullPointerException();
        if (!isCurrent(lease)) return false;
        mCurrent = null;
        mRevision = new Object();
        dispose(lease, reason);
        return true;
    }

    /** Revokes pending ownership even when no resource is currently installed. */
    public void revoke(EndReason reason) {
        checkThread();
        if (reason == null) throw new NullPointerException();
        Lease<T> previous = mCurrent;
        mCurrent = null;
        mRevision = new Object();
        if (previous != null) dispose(previous, reason);
    }

    /** Irreversible shutdown. Reentrant acquisition during cleanup is rejected. */
    public void destroy() {
        checkThread();
        if (mDestroyed) return;
        mDestroyed = true;
        revoke(EndReason.DESTROYED);
    }
}
