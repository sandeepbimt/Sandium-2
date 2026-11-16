# Ordinary Full restore: release consumed local archives

#1195 reported only 4.84 GB free for a delta requiring 9.40 GB staging after
successful base extraction. This is a job-local disk constraint; it is not a
claim about remote artifact quota. The conservative sparse staging guard stays
unchanged.

Ordinary Full restore now opts into releasing only exact downloaded local cache
payloads after successful consumption. All eight compressed base shards are
unlinked only after the legacy verifier/extractor returns successfully. Each
increment ZIP is unlinked only after its verified replay returns the expected
head. All candidate paths are checked before restore; symlink directories/files,
non-regular files, duplicate shard names and unexpected delta paths are refused.
No recursive deletion, remote cache deletion, checkpoint acceptance or expiry
change occurs. The manifest and plan metadata remain intact.

Ordinary Full capture uses the restored workspace and fresh begin inventory,
not previous ZIPs or base shards. Generic bridge restore defaults to retaining
inputs because its capture can compact them. Maintenance follows its existing
separate restore/rollup/republication path and must retain the compressed base.
The Full-only binding does not alter the generic CLI default.

A failed later delta invalidates this disposable job workspace. Earlier consumed
local inputs may already be released; retry must use a fresh job and restore
accepted remote caches, never continue the partially replayed tree. No restored
proof is written on failure. This does not guarantee sufficient space for every
future layer, nor weaken any hash/parent/topology/staging checks.

Validation: host tests exercise cleanup timing, default retention, failure,
symlink/path refusal and expected-head checks. Actual CircleCI disk savings and
successful end-to-end restore still need an authorized run. No run is authorized
by this document.
