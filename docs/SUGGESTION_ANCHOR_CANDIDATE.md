# Bottom-ranked omnibox suggestions candidate

User screenshots 155533.jpg and 155557.jpg show a correctly bottom-focused URL field above the keyboard, while native current-page Share/Copy/Edit/clipboard or typed website/search rows start at the top. These are autocomplete rows, not Android's floating selection toolbar.

Pinned native embedder sets top=0 and allocates the area above the bottom toolbar. Its normal LinearLayoutManager stacks items from the top. #1175 does not change that behavior.

## Latest user direction

The user explicitly wants the best/closest match nearest the URL bar, with subsequent matches running upward. This supersedes the earlier preserve-visual-top-to-bottom proposal. The candidate now uses native LinearLayoutManager reverseLayout, not manual child offsets or a reversed adapter. Native rank zero is physically nearest the bottom URL. Short and long result lists use the same placement; long lists retain native scrolling with no omitted suggestions. Native padding remains the spacing owner; the URL and keyboard geometry are unchanged.

A default-false embedder capability enables this only for phone-style windows with bottom controls. Initial observer attachment and alignment changes update it. Changes reset the native rank-zero scroll anchor. Scroll deltas are normalized before native keyboard hide/show logic and converted back afterward. Up/Down selection follows visual movement; Tab/Shift-Tab retain ranked traversal. Enter/action, selection content, clipboard reveal/privacy and adapter models are unchanged. Android's native reversed layout supplies accessible node geometry; TalkBack traversal remains a required runtime check, not a verified claim.

Current-page actions and typed suggestions are alternative native modes, but the same layout also supports combinations if the platform returns them together. No custom copy/paste toolbar or clipboard reads are introduced.

## Validation and integration

Eight source-contract tests pass. They do not execute Android RecyclerView. Independent review and native tests required: short/long and rank-zero placement, keyboard/IME resize, RTL, font scaling, rotation, selection with Up/Down/Tab, TalkBack, clipboard reveal, grouped row backgrounds and all scroll boundaries. Headers and group separators now reserve/draw on the logical leading edge (bottom when reversed), horizontal dividers mirror to the top, and BaseSuggestionView maps logical rounded edges to physical edges without changing the model. Attach/detach and direction changes reset this mapping; native bind updates continue to use logical edges. These changes still need rendered group/a11y validation.

No build/push, production registration or checkpoint edits. #1175 remains untouched. Integrator must add all eight pinned Java paths to reset/replay if approved. This candidate replaces the earlier manual short-group positioning code in this branch; do not combine the two approaches.
