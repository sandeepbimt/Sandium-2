# Local combined UI candidate (not published)

Base: navigation #1169 d6b31ba6165ab4afccdaef815236302c906c2805. Keep #1166 removal branch unchanged. Intended reviewed publication destination remains experiment/sandium-back-transition and its existing backpreview01 checkpoint only; allow_seed_import=false. Local experiment/sandium-ui-integration is deliberately not accepted by CI scope gate.

Integrated source provenance: homepage 4fc07f2,443d884,8e28410; blue/charcoal and menu 993a32b,0e5e113; status diagnostics 219ecea. Address and optional fullscreen gestures remain pending independent review.

Composition finding: homepage's top-sites listener changes overlap News removal's strict exact listener replacement. Apply homepage after removal, preserving strict News guards rather than relaxing them; accept only the two known listener indent variants. Extended reset/replay/interruption test must include homepage as well as existing overlays.

Status-bar addition only refreshes existing safe eligibility on controls callbacks and logs numeric state when tracing is enabled. It does not prove the reported solid status strip is fixed. No new alpha, geometry, or eligibility bypass.

Palette fallback is now blue #6E8EB5 and near-black #080808 for shortcuts; native shared attributes remain primary, including user's explicit dynamic-color choice.

Mandatory remaining acceptance: actual Android compile, APK inspection, device toolbar paint on both paths, IME focus/close, secure URL display, shortcuts longpress/drag/expand, menu normal/editor paging and TalkBack, reduced motion, status gradient under real inset conditions. Source and host checks are not substitutes.

Video omissions: no Quetta inline native toolbar, download, PiP, automatic fullscreen or double-tap-to-player is included at this point. Never enable unsafe page-owned controls.

Homepage/News collision resolved with exact-variant bb59ab6 (local cherry-pick ac433b7). Production reset recipe additionally restores brave_ids.xml, BraveMostVisitedSites.java and the two Chromium custom-link files; pinned Brave has no patches for these Chromium paths. This avoids a stronger test-only reset. Extended composition passed full replay, interruption and corrupt-patch preflight after post-removal homepage application.

Optional partial video stage is now included by coordinator decision: exact safe four-Java-file allowlist plus strings from 47adf26. Only opt-in fullscreen gestures after normal site entry; no inline/native/DOM toolbar, PiP, downloads, automatic fullscreen or double-tap player activation. Prototype C++/Mojo/Blink/DOM sources are not extracted. Installer still checks both pinned repositories and rejects stale experimental wiring. Output-map helper is shared with aggregate composition; 64 Java-double checks and pinned overlay checks pass. Combined UI/home/removal/video replay and interruption passed. Android compile and real playback remain untested.

Unified address exact reviewed source head2c6b08e integrated after all intermediate toolbar/menu/theme contracts in stage29, with pinned apply, actual-tree readback and seven source checks. Three added direct Chromium reset inputs (LocationBarModel, LocationBarPhone, ToolbarPositionController) have no pinned Brave patch mapping. Existing Brave toolbar-position adapter remains intact. Combined UI/address/home/fullscreen/removal replay and interruption passed. Source reviewer cleared both paint paths, destruction guard, focus visibility/touch and zero-width handling, not device visuals.
