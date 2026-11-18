# Native-home wallpaper request ownership (dormant)

The existing Brave `setBackgroundImage` creates a global-layout listener once,
capturing its first `ntpImage` argument. It subsequently starts work only when
width/height change. Thus same-size image replacement can keep the old selection,
and an already measured root unnecessarily waits for another layout notification.
The pinned worker already checks `isCancelled()` before callback dispatch; this
change does not pretend that check is absent.

For Sandium's existing coordinator-backed native homepage only, the candidate:
- owns the selected image, destination ImageView, measured dimensions and a unique
  request object;
- prepares immediately when real positive dimensions exist, otherwise waits for
  the ordinary layout observer (no guessed dimensions);
- rejects stale callbacks across selection, target, size, request generation,
  profile replacement, preference disable, detach, release and Activity destruction;
- rejects a stale logo callback if the preceding bitmap callback reentered and
  changed selection;
- clears a previous selection rather than presenting it as the new wallpaper;
- delegates accepted painting and readiness notification to the existing callback;
- preserves the non-backed/legacy sheet path.

There is no shared cache, pixel recycling, synchronous decode, attachment delay,
pre-draw veto, new compositor overlay or outgoing website retained under the home
URL. Existing FeedSurfaceCoordinator paints its opaque native fallback until its
actual wallpaper is prepared. A cold decode may therefore still produce the
ordinary native fallback first. The worker has no failure-result callback; a failed
decode does not gain an automatic same-size retry here. A later invalidation,
selection change, resize or lifecycle restart can issue another request. This is an actual selection/lifecycle correction
and reduced avoidable scheduling, not proof of a universal web-to-home atomic
presentation or elimination of cold-start wallpaper change.

The exact pinned worker crops to requested width/height and its gradient preserves
those dimensions; hashed full-source evidence is retained alongside the tests.

Tests compile the actual new Java methods with explicit collaborator doubles,
replay against the complete checked-in homepage pipeline fixture plus backing
patches, and include a generation-removal negative mutation. They do not replace
full Android compilation, real worker scheduling or phone testing.
