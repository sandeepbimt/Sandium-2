# Header-safe status gradient: isolated native candidate (not device-verified)

## Reproduced evidence

The #1175 screenshot shows Google's logo/sign-in row behind Android's status
icons at initial page top. The current implementation consumes root top padding
for all eligible pages, regardless of scroll. Its CSS safe-area metadata cannot
protect ordinary page headers that do not opt in to that CSS variable.

There is a second incorrect route: pinned ToolbarPositionController forwards
consumed top inset to ToolbarPhone.onToEdgeChange even with a bottom toolbar.
ToolbarPhone adds it to its padding/height. That does not reserve space above the
web page and may explain excess bottom space; screenshot alone cannot prove
all of that bottom gap's ownership.

## Prototype mechanism

- Reserve exactly the status inset as a native top browser-controls space when
  an eligible ordinary page uses the bottom toolbar.
- Let Chromium's compositor controls offsets scroll this space away together
  with page content. No website CSS/script, artificial page scroll, per-frame
  Android view translation, or threshold padding toggle.
- Paint the fade only inside the reserved status strip, not half a status-height
  farther into the page. Header begins outside the fade at initial origin.
- Do not send status padding to the bottom toolbar.
- Preserve existing page/keyboard/fullscreen/incognito/cutout eligibility.

The exact pinned Chromium browser-controls design explains that Android view
translations and web content are on different surfaces, and are not a substitute
for compositor-synchronized controls offsets. Relevant sources at
Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51:

- docs/ui/android/browser_controls.md
- chrome/android/java/src/org/chromium/chrome/browser/fullscreen/BrowserControlsManager.java
- chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorViewHolder.java
- chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java

## Ownership and lifecycle

The initial direct-height prototype was rejected: native TopControlsStacker can
replace aggregate height, so subtraction of an assumed owned delta is unsafe.
The current candidate registers a hidden-by-default SANDIUM_STATUS_SPACER layer
inside the pinned TopControlsStacker. Only that stacker computes aggregate
height/min-height; other native layers retain their ownership. The transitive inset-provider wrapper forwards the explicit web-underlap signal.
The layer uses
DEFAULT_SCROLLABLE and a zero minimum unless existing native constraints lock
controls. Ownership metadata is published before height observers run.

ToolbarPositionController updates this layer only for explicit Sandium web
underlap, bottom toolbar and browsing layout. Native NTP edge-to-edge does not
qualify. It separately prevents status padding being added to the bottom bar.
Edge eligibility accepts precisely the declared spacer height and rejects other
extra top layers and nonzero top minimum height. HUB/absent-tab, fallback and
teardown paths clear the layer; setters ignore changes after stacker destruction.

No scroll-threshold callback toggles window padding. Native compositor control
offsets handle motion and existing viewport synchronization. The fade is confined
to the reserved status strip, eliminating extra half-strip header shading.

## Remaining production gate

Independent review, Android compilation and device validation remain required.
Source tests cannot prove ordering of real Android inset/keyboard/control
callbacks or compositor rendering. Validate initial load, repeated scroll to/from
origin, focus/IME, rotation, tabs, fullscreen exit, back/forward history, short
pages and restored scroll positions. This candidate has not been built here.

## Test meaning

Source tests cover exact reversible transforms, unchanged downstream exclusions,
no DOM/scroll mutation, fade bounds, cleanup paths and positive-gesture creation.
Pinned reset/replay/interruption composition verifies source wiring, not native
rendering or native lifecycle correctness. No build was run.

Two native Robolectric regression cases are generated for layer preservation and destruction, but were not executed in this workspace.
