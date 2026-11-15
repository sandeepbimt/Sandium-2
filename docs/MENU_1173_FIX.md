# #1173 blank menu editor and Edit alignment

## Evidence and cause

User screenshot `155512.jpg` shows Cancel and Done at the top of a tall dark
sheet, but no grid, instructions, or available actions. The main menu screenshot
`155513.jpg` still contains its normal grid and has Edit close to the right edge.

The #1171 correction removed the Edit Menu title by replacing its TextView with
a plain View through `weighted()`. That helper supplies width 0, height
WRAP_CONTENT, weight 1. A bare View has no text-derived intrinsic height: Android
View's default measurement selects the available AT_MOST size. Thus the empty
center header cell can consume the sheet height. The subsequent body ScrollView
has height 0 and weight 1, so no positive vertical space remains for its content.
This is a concrete source-level layout error consistent with the screenshot;
there is no indication that saved menu items were deleted.

## Correction

* Give only the empty center slot explicit 1px height, preserving its width weight.
* Leave Cancel and Done as intrinsic-height text controls with minimum 48dp height.
* Preserve draft/save/cancel semantics, catalog, paging, available actions and motion.
* Give the main Edit control minimum 64dp width and 8dp end margin, centering its
  label farther from the edge while preserving at least a 48dp high hit target.
  Relative end margin also respects RTL.

## Verification

Refinements 7 and motion 6 source/transform tests pass. The regression contract
rejects the unsafe `weighted(heading, new View(...))` pattern and requires the
bounded slot and Edit target/inset. No Android device or renderer test was run.
Before calling this device-fixed, open Edit, inspect both pages and available
items, drag/remove/re-add, then test Done and Cancel, large font and RTL.
No build/publication was initiated. Address and back-transition code untouched.

Full pinned composition passed, including reset/replay, interrupted-removal
recovery and bad-patch preflight.

## User-approved grouped surfaces

The subsequent reference 155514 requests dark background with grey rounded groups
in both main and edit menus. Retain Sandium's blue accents and existing grid/order
rather than copy the reference's pink palette or unrelated browser actions.
Group the four library actions, the paged customizable actions/indicators, and
(editor only) available actions/reset into separate 12dp-radius surfaces with 4dp
inner padding and 10dp vertical separation. Groups are decorative and do not
intercept clicks, TalkBack, reorder or paging. Dark groups are #242424 on existing
#101010 shell; light mode uses white groups on its existing light shell.
Contrast on dark groups: primary text 14.87:1, secondary 8.26:1, blue accent 4.58:1.
Refinements now 8 tests; motion 6 and native theme 13 pass. Device rendering,
large font, scroll extent and drag across groups remain untested.
