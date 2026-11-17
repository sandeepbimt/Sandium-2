# Pinned rename source fixtures

Fetched unchanged from chromium/chromium commit
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`:

- `chrome/browser/android/ntp/most_visited_sites_bridge.cc`
  Git blob `90f9a6e1dc6eb21e018121d5caba10ff64465585`
- `components/ntp_tiles/custom_links_manager_impl.cc`
  Git blob `bce188c0c73e908369d99a95a8ae1dc0e3e50de6`

The test verifies these blob hashes and compiles the exact UpdateLink body with
minimal GURL/store substitutes. It models reconstruction from stored data, not
real Chromium preferences serialization, Android UI, synchronization or disk flush.
The pinned AssignCustomLink bridge converts same-URL updates into an empty new
URL, preserving the original URL and index. The Java dialog checks that the
link still exists immediately before Assign to avoid its add-if-missing path.
