# Menu visual balance after #1225

Reviewed all three attached screenshots155985,155986,155992. The regular and
editor headers include an8dp top inset in addition to their48dp control row.
One-line tile labels also occupy a fixed two-line label box, leaving the visible
icon/name stack high within the tile despite symmetric outer tile padding.

* Remove only the header's8dp top inset; retain48dp interactive targets. Preferred
  sheet height decreases by the same8dp, in both regular and editing modes.
* Center header children vertically, disable horizontal baseline alignment, and
  exclude font padding for Menu/All menu/Edit and Cancel/Reset/Done. Equal left
  and right main-header slots and equal editor weights remain unchanged.
* Measure each tile's actual one/two-line label stack naturally, then center the
  complete icon+label stack vertically in the unchanged minimum-height tile.
  Two-line Desktop state stacks follow the same rule.26dp icons,12sp labels,
  two-line overflow protection, touch targets, pager, fixed-last All menu,
  persistence and action dispatch are unchanged.

The current user request deliberately supersedes earlier common icon/first-text
baseline alignment for differing label line counts:the complete visible group is
now centered, not a fixed two-line reservation. Row/sheet dimensions still do not
depend on which page or action labels are visible. Large fonts use the existing
font-derived row minimum and bounded-scroll fallback.

No build/push here. Device verification remains necessary; source and geometry
checks do not prove final Android pixels.

Validation:menu-focused29, active310, Full49, legacy19, motion6 and theme18
passed. Full suite initially had an unrelated timing-sensitive descendant-pidfile
failure; unchanged Full49 rerun passed. Independent review passed15 focused
checks and found no blocking source/API issue.
