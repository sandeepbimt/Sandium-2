# Pager whitespace after #1233

Inspected screenshots156057 and156059. Highlighted space is primarily the48dp
page-indicator band. Preserve coherent tile/header/group spacing and the editor's
six-row capacity rather than squeezing unrelated controls or shrinking fonts.

* Pager visual band is32dp instead of48dp, with existing centered20x3dp marks and
  consistent8dp horizontal gaps. Main and editor share this treatment.
* One-page menus do not create the indicator, keyboard/range control or its height
  reservation. Multi-page menus retain tap, swipe, drag-hover, keyboard and
  accessibility forward/back navigation. Dynamic model changes rebuild correctly.
* Direct tap is preserved with a16dp downward-only ancestor TouchDelegate into
  existing safe whitespace. Main has4dp group padding+4dp margin+8dp outer bottom
  padding. Editor has group padding/margin then the noninteractive Available
  heading, before any action tile. No target expands upward over the last row.
  Visible32dp tap cells plus the16dp extension retain48dp effective height when
  fully visible; clipping remains bounded by the actual panel.
* Coordinates are converted from target-local visible bounds into the menu root,
  not mixed with PopupWindow screen coordinates. Accessibility bounds extend in
  screen coordinates from the framework's supplied bounds.
* Extension bounds are recomputed for every DOWN, including after scrolling.
  Drags beyond slop or multiple pointers cancel the button and replay the proper
  DOWN into normal scroll dispatch. Model refresh cancels old targets but retains
  stream ownership until terminal event, preventing orphan MOVE/UP on new controls.
  Detach/native fallback clears references and events.

Normal-font nominal sizes:multi-page main304dp/editor544dp; single-page
main272dp/editor512dp. Editor still reserves two quick-action rows and four
Available rows. Existing large-font/small-window scrolling fallback stays.
No state migration, native action, colour, icon/font size or fixed-last All menu
change. No push or CI run in this task. Android tap/scroll/TalkBack visual behaviour
must still be verified in the next user-authorized APK.

Validation:active321, Full49, legacy19, menu-focused37, toolbar11, motion6 and
theme18 passed. Independent review passed29 checks after correcting PopupWindow
coordinate frames and held-touch ownership across model refresh. No Android
runtime rendering/input test was available in this workspace.
