# Brave 1.100.58 / Chromium 158 lint migration

This directory is a new target policy, **not** a relabelled #1394/#1401 inventory.
The historical 964 exact exceptions remain unchanged and are not installed for
this target. There is not yet a final158 composed resource/consumer graph or an
executed target lint report, so no target exception is approved.

Verified official target:
- Brave core bd6d26d1bced03c17a98baa86d2cd3425d543d1b
- Chromium 52bdd21723d5db0c9ab11716d38feac74828cf84

The target upstream suppression policy adds one upstream exact exception for
`R.dimen.toolbar_edge_padding_ntp`, documenting the replacement reference to
`R.dimen.brave_toolbar_edge_padding_ntp` in ToolbarPhone.java. The lint Python
hook has formatting changes, not a new suppression mechanism. Both exact files
are saved with Git-blob/SHA-256 identities in policy.json.

The target verifier checks both source revisions, pinned and live hook/policy
bytes, and zero additional exceptions. It neither writes a baseline nor disables
lint. It rejects a checkpoint containing old964 or other modified live policy;
the source preparation must restore exact target upstream before replay.
The legacy same-pin repair remains available through the existing dispatcher.

Passing this verifier means only **correct official lint policy admitted**. It
does not mean target lint is clean. Final composition evidence and actual158
lint results must be reviewed before any new exact exceptions are proposed.
Six host tests cover unchanged official policy, old964 rejection, foreign rule
rejection, pin validation, pinned-byte validation and no legacy-inventory load.

Definition audit completed against the exact target Git objects:
- 954 historical upstream resource declarations/generator entries still exist.
- 3 declarations are absent: `BraveLeoResetTextColor`,
  `TextAppearance_Brave_PreferenceTitle_WalletDestructiveAction`, and
  `leo_reset_text_color`. Do not generate exceptions for these absent entries.
- 7 Sandium-owned resources require final target composition evidence.
- Only185 candidate definition files are byte-identical;772 are changed files.
  A declaration remaining present is not proof its consumer/removal chain is
  unchanged, so these reports approve zero migrated exceptions.

`audit_definitions.py --core <exact-pinned-brave-core>` reproduces the
read-only Git-object comparison. It records each target Git blob and SHA-256.
