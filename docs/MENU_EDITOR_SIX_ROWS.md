# Editor:two quick rows plus four Available rows

Reviewed screenshot155994:the previous editor reserves only one Available row,
so additional hidden actions extend below the viewport. Regular menu dimensions
are not the problem and remain unchanged.

The editor now reserves one complete quick page (two rows at normal font scale),
its instruction/pager, and four full Available rows plus section heading. It has
one fixed envelope independent of the actual number of hidden actions, and the
Available grid reserves four row slots even when fewer actions exist. At nominal
64dp tiles the editor requests560dp; the regular menu still requests320dp.

Existing26dp icons,12sp text, minimum48dp targets, centered icon/name stacks,
fixed-last All menu, order/visibility persistence, Reset/Cancel/Done and native
handlers are unchanged. The regular menu is not enlarged.

Physical limits remain explicit:the popup is capped to the usable display.
Large accessibility fonts switch to two columns (thus four quick rows), short or
landscape windows, and more than four rows of hidden actions may still require
scrolling. We do not disable scrolling and make actions unreachable, shrink text,
or overlap touch targets to claim an impossible universal no-scroll guarantee.
The target phone at ordinary font/display settings should fit the six-row editor,
but this remains a sizing calculation until the next authorized APK device test.

Validation:focused32, active313, Full49 and legacy19 passed. Independent review
passed18 focused checks and confirmed the six-row arithmetic; no blocking
source/API issue found. No CI run or publication performed.
