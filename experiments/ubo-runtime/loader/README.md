# Isolated bundled uBO loader (not an engine replacement)

Run `apply.py --src <pinned-composed-src> --bundle <verified-normalized-zip>`
after the EXT0 source replay and product overlays, before GN. The normalized
ZIP is the output of bundle/prepare.py for pinned full uBO 1.76.4.

The fixed public key identifies this Sandium component. It is NOT an upstream
signature, and does not claim to be the Chrome Web Store uBO identity. No private
key was saved. All 668 release files remain packaged, including GPLv3 license.
The only release manifest edit is the fixed public key.

Activation defaults OFF. The explicit feature `SandiumUboRuntime` must be enabled
for a controlled runtime test. Field-trial setup enables all four Android runtime
prerequisites together. Arbitrary ordinary extension installation stays denied.
The loader registers only the fixed bundle/resource ID. All other built-in
component registration remains under Chromium's existing allowlist.

Brave ad filtering remains unchanged. Do NOT default-enable this overlay or hand
it off as a replacement: uBO initialization can itself start request filtering,
causing double filtering until an exclusive engine coordinator is integrated.
Registration is not a readiness acknowledgment. Background startup, request block
and exception, scriptlets, cosmetics, locale catalogs, private-profile isolation,
restart persistence and Shields parity require Android runtime verification.

Local test uses actual pinned Brave postimages, exact Chromium resource-manager
input and the verified complete release archive. It checks replay idempotence,
fixed identity, full resource inventory and default-off gates. Native GN/C++ and
Android execution have not run in this local fixture.

## Continuation and reset

Run overlays in order: source.py EXT0 replay, product overlays, loader, Shields.
Before any source.py mode-off/reset or continuation baseline audit, reset in
reverse order: Shields first, then `loader/apply.py --src SRC --reset`.

The loader plans all edits off-tree before writing. A durable ownership receipt
at `SRC/.sandium-ubo-loader-state/receipt.json` stores original/postimage SHA-256
hashes with content-addressed backups outside the Brave checkout. Reset restores
exact post-EXT0 input bytes and removes only files it created. Unknown edits,
unknown files in the component directory, symlinks and corrupt backups fail
closed before restoration. Do not delete the receipt to bypass an ownership
failure. Interrupted apply/reset can resume because each owned file must match
one of its two recorded states. After successful reset the receipt is removed;
backup blobs are deliberately retained. Calling reset again is safe. Do not run
concurrent overlays on the same source tree.

Tests exercise a modified-owned-file refusal, interrupted reset and apply replay,
repeat reset, complete restoration and repeat-apply idempotence on pinned inputs.

## Verified disk assets and localization

The component now snapshots bundled bytes on the browser sequence, then dispatches
all hashing, directory verification/writes and manifest localization onto Chromium's
sequenced extension file task runner. No Profile pointer crosses to that worker.
The UI reply is weak-pointer guarded; Shutdown invalidates replies. Repeated calls
while work is pending cannot register twice. Failure leaves Brave unchanged and
does not register an incomplete extension.

Assets use an app-private profile subdirectory with a content-addressed generation
name. Complete bytes are SHA256 checked before any write, staged into a private
temporary directory, checked on disk and then moved into place. Existing generations
are never overwritten; every expected file and absence of unexpected/symlink entries
are checked before reuse. Interrupted staging does not become a loadable generation.
Old generations and uBO storage are not removed by this implementation.

The worker calls the pinned `extension_l10n_util::LocalizeExtension` using the real
on-disk `_locales` catalogs, then the UI registers the localized dictionary and
absolute path. Runtime `chrome.i18n` can consequently use Chromium's normal disk
message-bundle loader rather than relying on URL-to-PAK mapping for filesystem APIs.
String-ID allowlisting is included because the dictionary Add overload checks it.

Bridge changes to bundled JS must regenerate `disk_resources.h` using the pure
`build_disk_inventory(core)` helper after editing the staged assets/resource map;
that header must be in the bridge's ownership receipt. Tests validate inventory
hashes, pure regeneration, source lifecycle and weak-reply structure. They do not
execute native extraction or Android i18n. Native compile/runtime remain required.
Resource capture itself is a bounded 27 MB memory snapshot on the browser sequence;
its startup cost is not measured and should not be called zero-overhead.
