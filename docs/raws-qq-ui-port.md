# Sealed RawS native presentation intake

The two user-supplied UI commits at `44c5f0b21d3bce163bc1a7e9f66443caa4ccbe05`
(parent `4264e3901ddccfcb0a1d694410a004b77506afce`) are based on #1462
`c86ff1a8575e49c0dff22610315004c0c1a48a95`. Their bundle ZIP has SHA-256
`7e6602be1c9af11bd362a191c53ab4256c798c13477209650bf1b3b392593812`.

This intake composes only the reviewed Android presentation transforms and
artwork onto #1471, without using the bundle's #1462-only runtime wrapper.
All newly tracked preimages were checked against Git blobs for the locked
Chromium revision, `52bdd21723d5db0c9ab11716d38feac74828cf84`. All overlaps with
the existing recipe are confirmed unchanged between #1462 and #1471 before
applying UI transforms to those postimages. Resource and Java owners extend
the existing default-toolchain GN linkage gate. The custom menu grid is
registered for the top-level menu only; native submenu flyouts must not
replace the current parent grid model or its action binding.

Included: Sandium display label and launcher artwork; default bottom toolbar
respecting explicit position choices; Chromium's existing no-Discover Home
and no injected AI row; paged native quick menu and remembered editor order;
limited native Welcome branding and palette.

Not included: app package or signer change, new ad controls, full Sandium
screen-for-screen parity, Android execution or physical-device validation.
Do not treat this source-only merge as a shippable APK. Do not use the
bundle's old-package/same-signer update check for a distinct RawS app.
