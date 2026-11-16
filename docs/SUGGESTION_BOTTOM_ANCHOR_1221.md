# Bottom omnibox suggestion correction after #1221

The user's screenshots show a short, already-reversed suggestion group remaining at the top of the viewport while the focused address bar sits above the IME. The separate screenshot of the current-page Share/Copy/Edit row is also an omnibox suggestion, not the Android text-selection toolbar.

## Cause and correction

The existing overlay reversed LinearLayoutManager ranking correctly, but the pinned `suggestions_result_container.xml` makes the dropdown `wrap_content` inside a full-height FrameLayout. Reversal positions rank zero at the bottom of that short child, not the bottom of its parent.

The correction applies bottom vertical gravity to that child for a bottom, phone-style omnibox. It preserves original horizontal gravity and restores the exact original gravity for top/tablet/popover modes. Re-evaluation on measure covers window/IME/layout changes without absolute screen offsets or keyboard-height guessing. Native reversal, rank-zero scroll, keyboard direction and group decorations remain unchanged.

Share/Copy/Edit, clipboard privacy, navigation, suggestion actions and URL colors are unchanged. No Android ActionMode manipulation is included.

## Verification and limits

Pinned source transforms and repeat application tests cover the XML contract, both gravity paths and inherited ranking behavior. Canonical repository suites must pass before integration. These are not Android screenshot tests. Device validation is required for one/many suggestions, current-page actions, typed URL/search, IME show/hide, reopening focus, scrolling, landscape, RTL and large fonts.
