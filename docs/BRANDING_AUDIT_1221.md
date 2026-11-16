# Sandium Android branding audit after #1221

## Observed defect and cause

Both supplied screenshots show `Brave Password Manager`: the Settings entry and
Password Manager page title. Both use `IDS_PASSWORD_MANAGER_SETTINGS_TITLE` in
`android_chrome_strings.grd`. The existing final branding pass modified Brave's
canonical source file, but npm had already copied it into Chromium's consumed
file. The previous About-specific correction only updated two IDs in that copy.

## Correction

- Apply safe browser-identity transformations to both canonical and consumed
  resources, without copying whole files or overwriting prior UI edits.
- Pin the recursive GRD/GRDP copy graph used by Brave's `branding.js` and
  `l10nUtil.js`: 107 source-to-destination bindings, 211 unique resource files.
- Traverse all mapped `<part>` files, not only top-level GRDs. This includes
  password/autofill, browsing data/history, permissions/site settings, tabs,
  page information, common browser dialogs, settings and accessibility labels.
- Require the inventory to match the source graph and fail on missing consumed
  files. The final verification reruns the transformation in read-only mode and
  rejects any missed safe browser-identity text.
- Rebrand the hardcoded Developer options hint in both resource sources.
- Existing About title, copyright relocation and Sandium artwork remain intact.

## Deliberate exclusions

No rename of package/class/resource identifiers, preference keys, API names,
URLs, telemetry identifiers, or external destinations. Placeholders and examples
remain unchanged. Preserve actual third-party services, support destinations,
provider/data-recipient disclosures, copyright, licenses and legal attribution.
Feedback/provider strings are not blindly rebranded to imply Sandium operates a
service or receives data it does not. No service/network behavior is changed.

## Verification and limits

- Actual pinned Brave source graph materialized into a disposable source/copy
  tree; transformed and verified successfully, including Password Manager title.
- 13 focused branding tests include copied source replay, nested parts, inventory
  drift, legal/service/URL preservation and developer-hint checks.
- Combined feedback branch: architecture 300, Full 49, legacy 19 tests pass.
- Pinned Developer resource is registered in both reset inventories; fixture
  composition includes the new input.
- No Android compilation or on-device screen sweep has run for this change.
  This is a broad source/resource audit, not proof that no raster logo, dynamic
  external content, or translated runtime screen can ever display Brave.

## Independent integration review

The initial broader graph exposed provider text previously outside the rename
pass. Added conservative whole-message exclusions for crash/metrics recipients,
page-content and cloud-processing disclosures, history personalization, managed
enterprise services, external account/Sync/DNS/Root Store/AI services, Gmail OTP,
merchant information, and payment encryption claims. Readable-text guards also
handle inline markup splitting a recipient name. Original provider statements
are preserved, not rewritten to suggest Sandium operates those services. Some
upstream Brave strings themselves name repackaged Chromium services unusually;
this patch deliberately does not reinterpret or redirect those integrations.

Independent replay against the pinned source examined 108 canonical resources:
1,533 changed message occurrences (1,407 unique IDs), 872 preserved occurrences.
All 107 copy bindings / 211 consumed-and-canonical paths passed transformation,
verification and idempotence; protected full message bodies remained identical.
This is conservative coverage, not a claim to have verified the behavior of each
external service or every translated runtime screen.
