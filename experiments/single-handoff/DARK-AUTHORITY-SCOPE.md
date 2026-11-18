# Dormant dark policy authority candidate

## Changed mechanism

DocumentToken is rejection metadata on the existing renderer preference endpoint, not a lookup/routing capability. A mismatched current document cannot consume the preferences, even for a same-URL reload. Global monotonic revisions order commit, activation and live policy updates; a WebContents-owned query epoch prevents an older reentrant sample from overwriting a newer sample without coupling unrelated tabs. No global document registry or document pointer escapes the content-owned helper.

Commit installs initial policy before Document/style creation through the existing commit hook. BFCache/prerender carry fresh policy authority through their existing transport. Invalid optional activation samples use -2/revision zero and omit the override, rather than deciding whether native activation completes. The native control flow continues; only a destroyed owner causes immediate return. NavigationRequest writes a locally owned cloned commit_params, not a member of a potentially destroyed owner.

## Validation and limits

Ten focused host/source tests pass, including exact 17-file baseline transform/replay, exact GN source anchors, actual injected renderer and BrowserClient methods, actual content helper implementation with explicit API doubles, and actual injected native producer prefixes. Negative mutations remove identity, revision and browser epoch guards and are rejected. The native-prefix harness is not the entire Chromium activation state machine; fake owner liveness is not an ASAN proof of real browser destruction.

Independent review approved the restricted dormant source/host authority candidate. It remains conditioned on the existing synchronous policy getter: SandiumDarkPages.flags reads profile policy/preferences and does not intentionally run arbitrary script/provider callbacks. There is no claim of correct first-frame policy under arbitrary same-owner reentrant providers. No generated Mojo/Settings, complete GN graph, Android compilation or device rendering verification has been performed. This does not establish that the characterized ordering issue caused the user's recorded flashes, nor promise no flashes.

## Integration

Apply dark_policy.plan(root) only after all existing .circleci/features/dark-pages/renderer/patches.json patches are applied. Its 17 keys are available from patches(). registration_plan(root) adds the public authority header/private content implementation and all-platform GN entries. It composes after the existing content_registration planner; unlike the Android presentation helper, authority transport has cross-platform callers. Do not independently activate these files or run a partial build.

Fixture seeding for tests: for each existing BASE patch in order, load fixtures/<path> only on first encounter, verify old-anchor count, then replace old→new. Seed only absent files in an existing composed tree; do not overwrite real composed inputs. GN fixtures are the verified text/hash records in fixtures/content-registration.json.gz. The source transformer fails closed on unknown/partial anchors.

Final UI integration regression additionally preserves page-text Settings methods and commit policy arguments, with dark revision inserted in the same order as its Mojo field. The full final UI unified navigation/dark/wallpaper staged replay and exact rollback passed; this is still source composition, not generated-code compilation.
