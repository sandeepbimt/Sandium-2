# Native homepage wallpaper surround

Paint consumer for the explicit native-page wallpaper backing contract. Requires the matching provider/NativePage owner patch before compiling or wiring this script.

The owner must report ready only when a real full-size native wallpaper backing is attached, correctly cropped and enabled, with foreground controls inset separately. It must notify registered Runnables when readiness changes, including load, resize, preferences and detach. Ordinary web and other native pages default false.

ToolbarPhone reuses upstream NTP visual-state color selection rather than changing viewport dimensions or inventing an animation. Only unfocused bottom NTP, outside layout/loading transitions, returns transparent surround color. Capsule color and controls geometry remain unchanged. The live toolbar publishes its actual surround color through the native-page owner, including focus and animation updates. The native toolbar layer consumes that same color only for a ready non-private bottom native page, while computing capsule color from the original theme. Readiness callbacks ignore paint-only notifications on the live side to avoid re-entering animations. Existing native Back scene suppression remains unchanged.

Observers follow the current NativePage and are removed on replacement/destroy. Readiness invalidates the Android toolbar and its bitmap resource; native color model also refreshes. Existing capture tokens include toolbar color, so the new color participates without introducing an unrelated cache key. Toolbar margin input stays unchanged: only wallpaper, not interactive page content, is behind those margins.

Tests exercise atomic/idempotent transforms, shipping bottom/unified/refinement composition and compiled exact live eligibility logic. This is not an Android screenshot or runtime pass. The entire feature must remain unwired until backing ownership and full source integration review pass. No emulator run is required or authorized by this patch.
