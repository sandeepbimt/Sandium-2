# Welcome restart button fill

The supplied screenshot shows a thin horizontal green strip above the blue
“Restarting in a moment…” capsule. The strip is a separate 4dp ProgressBar,
introduced in 675037c. Its immediate predecessor dispatches restart directly;
that history does not substantiate an earlier full-button fill.

The restart countdown now clips a saturated green rounded drawable over a dark-green
rounded button background. Drawable levels 0–10000 correspond to empty
through full. Text remains above the fill, and the capsule retains its 52dp
height. No extra row is revealed, avoiding countdown-induced layout movement.
The filter-download progress card remains unchanged.

This is explicitly a one-second pre-restart countdown, not measurement of
native restart completion. The existing Handler still dispatches restart
independently of animation, including when system animations are disabled.
Readiness, repeat-click and destroyed-view guards remain unchanged.

Verification: focused source/composition tests and a Java dispatch harness
exercise ready/not-ready, repeated clicks, no-restart, animated restart,
disabled animations, and destruction before dispatch. Android rendering and
device restart behavior require a later authorized APK build/device test.
No build or CI run was started for this candidate.


## Optimize color reference

The enabled Optimize button in the supplied Phone Manager screenshot has a
dominant interior RGB(36,169,50), #24A932. Start browsing uses that green only
when enabled; the disabled charcoal state and all unrelated blue controls are
unchanged. Dark text is retained for over 6:1 contrast on the green background,
rather than copying the reference's lower-contrast white label.

During restart only, the track darkens to RGB(9,38,16) and fills with saturated
green RGB(20,130,43). The label changes to near-white. The fill/track contrast
exceeds 3:1, and label contrast exceeds 4.5:1 over both halves. Neither label
nor button geometry changes, and no extra row is shown. This is a flat-color
match to the screenshot interior, not a reproduction of the subtle edge glow.
