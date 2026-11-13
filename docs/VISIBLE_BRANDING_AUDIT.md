# Sandium visible branding audit

Baseline: Sandium #1075 (`952b614ef375ec524954c27997d0e491936d21cb`), Brave v1.98.62 (`44a84b1f89d9a35287289d6a3d493e362f5a5123`). This update is independent of the paused Origin-removal branch.

## Scope implemented

A final pass after product overlay 29 changes browser-identity message bodies in eight pinned Android/shared GRD resources. The exact source fixture contained 1,018 changed message definitions, including shared non-Android variants; this is not a count of Android screens. IDs, descriptions, placeholders, URLs and code symbols are unchanged. Mandatory attribution, legal text and real Brave service identities remain. This is not a blind repository-wide string replacement.

Coverage includes browser name, open/default-browser prompts, settings/privacy/permissions copy, password-manager copy, Shields labels and generic notification copy. The explicit retention-notification title is changed separately.

Existing launcher, welcome artwork and balanced S tracer remain unchanged. Additional browser-owned logo replacements cover the incognito page, large rating/app-logo resource, circular browser-logo resource and tab-switcher NTP favicon. The latter has its own module-local registered drawable resources, avoiding a dependency on global chrome.R. Existing Sandium artwork is reused, with 64:77 aspect ratio and 12% top/bottom inset for square drawable hosts. Host layout sizes and tab-favicon tint/accessibility semantics remain.

## Intentionally preserved

- Brave Account settings-row name and logo, Brave Search and other actual third-party service identity, their endpoint URLs and payment/service notices.
- Copyright, licence, attribution and legal text.
- Preference keys, package name, signing identity, backend classes, telemetry keys and website content.
- Source identifiers named Brave; these are not UI labels.

## Verification and limits

Five local tests cover text-only replacement, idempotence, URL/placeholder/service/legal preservation, drawable dimensions/aspect and full application. Transformation was also exercised twice against exact pinned resource/Java inputs. No Android resource linking, compiled APK inventory or on-device screen traversal has yet run. English message edits can invalidate upstream translation lookup IDs, causing normal English fallback for affected translated text; full localization review remains pending. Do not claim every Brave occurrence in every reachable screen is gone without runtime auditing.

CI writes `sandium-visible-branding-report.json` and fails if an in-scope message remains transformable or the installed Sandium mark/GN resource registration is missing. A second application reports zero changed messages by design.
